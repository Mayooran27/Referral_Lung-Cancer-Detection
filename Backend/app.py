"""Flask REST API for lung CT scan classification (Normal / Benign / Malignant).

Run:  python app.py            (http://127.0.0.1:5000)
"""
import io
import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from PIL import Image, UnidentifiedImageError

import config
from services import ct_validator, model_service, storage
from services.ct_validator import NotCTScanError

FRONTEND_DIST = os.path.join(config.BASE_DIR, "..", "Frontend", "dist")

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS}})
storage.init()


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def _extension(filename):
    return filename.rsplit(".", 1)[1].lower() if "." in filename else ""


def _read_upload():
    """Validate the upload and return (PIL image, filename).

    Raises ValueError when no file was sent, and ct_validator.NotCTScanError when the file
    is not a lung CT scan image (wrong file type, PDF/video/audio, colour photo, ...).
    """
    if "file" not in request.files:
        raise ValueError("No file uploaded. Send the image in a form field named 'file'.")
    file = request.files["file"]
    if not file.filename:
        raise ValueError("No file selected.")
    data = file.read()
    if not data:
        raise NotCTScanError("The uploaded file is empty.")
    kind = ct_validator.detect_non_image(data)
    if kind:
        raise NotCTScanError(f"You uploaded {kind}. Only JPG or PNG CT scan images are accepted.")
    if _extension(file.filename) not in config.ALLOWED_EXTENSIONS:
        raise NotCTScanError(
            "Unsupported file type. Allowed: " + ", ".join(sorted(config.ALLOWED_EXTENSIONS))
        )
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise NotCTScanError("The file could not be read as an image.")
    ct_validator.validate(img)
    return img, os.path.basename(file.filename)


def _upload_or_error():
    """Return ((img, filename), None) on success or (None, error response)."""
    try:
        return _read_upload(), None
    except NotCTScanError as exc:
        body = {"success": False, "error": str(exc), "reason": exc.reason, "code": "not_ct_scan"}
        return None, (jsonify(body), 400)
    except ValueError as exc:
        return None, error(str(exc))


def _flag(value):
    return str(value).lower() not in ("0", "false", "no", "off")


def _model_info(model_id):
    cfg = config.MODELS[model_id]
    metrics = model_service.load_test_metrics(model_id)
    accuracy = metrics.get("accuracy") if metrics else None
    return {
        "id": model_id,
        "name": cfg["name"],
        "description": cfg["description"],
        "input_size": cfg["input_size"],
        "classes": model_service.load_class_names(model_id),
        "loaded": model_service.is_loaded(model_id),
        "metrics": metrics,
        "reliable": accuracy is None or accuracy >= config.RELIABILITY_THRESHOLD,
        "plots": {k: f"/api/models/{model_id}/plots/{k}" for k in cfg["plots"]},
    }


def _run_model(img, model_id, with_gradcam):
    """Predict with one model; errors are returned in the result instead of raised."""
    try:
        result = model_service.predict(img, model_id, with_gradcam)
    except Exception as exc:
        app.logger.exception("Prediction failed for %s", model_id)
        return {"model_id": model_id, "model_name": config.MODELS[model_id]["name"], "error": str(exc)}
    info = _model_info(model_id)
    result["model_reliable"] = info["reliable"]
    result["model_test_accuracy"] = info["metrics"]["accuracy"] if info["metrics"] else None
    return result


def _save_and_respond(img, filename, mode, model_id, results):
    summary = model_service.summarise(results)
    if summary is None:
        return error("Prediction failed: " + "; ".join(r["error"] for r in results), 500)
    scan = storage.save_scan(img, filename, mode, model_id, results, summary)
    return jsonify({"success": True, "scan": scan})


# ---------------------------------------------------------------- API routes
@app.get("/api/health")
def health():
    return jsonify(
        {"status": "ok", "models_loaded": [m for m in config.MODELS if model_service.is_loaded(m)]}
    )


@app.get("/api/models")
def list_models():
    return jsonify({"models": [_model_info(m) for m in config.MODELS]})


@app.get("/api/models/<model_id>/plots/<plot>")
def model_plot(model_id, plot):
    cfg = config.MODELS.get(model_id)
    if not cfg or plot not in cfg["plots"]:
        return error("Plot not found", 404)
    return send_from_directory(os.path.join(config.MODEL_DIR, cfg["folder"]), cfg["plots"][plot])


@app.post("/api/predict/all")
def predict_all():
    """Classify with all three models and combine them into one verdict."""
    upload, err = _upload_or_error()
    if err:
        return err
    img, filename = upload
    with_gradcam = _flag(request.form.get("gradcam", "1"))
    results = [_run_model(img, m, with_gradcam) for m in config.MODELS]
    return _save_and_respond(img, filename, "all", None, results)


@app.get("/api/scans")
def scans():
    label = request.args.get("label") or None
    if label and label not in ("Malignant", "Benign", "Normal"):
        return error("label must be Malignant, Benign or Normal")
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return error("limit and offset must be integers")
    return jsonify(
        {"scans": storage.list_scans(limit, offset, label, request.args.get("search") or None)}
    )


@app.get("/api/scans/stats")
def scan_stats():
    return jsonify(storage.stats())


@app.get("/api/scans/<scan_id>")
def scan_detail(scan_id):
    scan = storage.get_scan(scan_id)
    return jsonify({"success": True, "scan": scan}) if scan else error("Scan not found", 404)


@app.get("/api/scans/<scan_id>/image")
def scan_image(scan_id):
    path = storage.image_path(scan_id)
    if not scan_id.isalnum() or not os.path.isfile(path):
        return error("Image not found", 404)
    return send_file(path, mimetype="image/png")


@app.delete("/api/scans/<scan_id>")
def scan_delete(scan_id):
    return jsonify({"success": True}) if storage.delete_scan(scan_id) else error("Scan not found", 404)


@app.errorhandler(413)
def too_large(_):
    return error(f"File too large. Maximum size is {config.MAX_UPLOAD_MB} MB.", 413)


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return error("Endpoint not found", 404)
    return _serve_frontend("index.html")


# ------------------------------------------------- serve built React frontend
@app.get("/")
@app.get("/<path:path>")
def _serve_frontend(path="index.html"):
    dist = os.path.abspath(FRONTEND_DIST)
    if not os.path.isdir(dist):
        return (
            "<h3>Backend is running.</h3><p>Run <code>npm run dev</code> in the Frontend folder "
            "and open http://localhost:3000, or <code>npm run build</code> to serve it from here.</p>",
            200,
        )
    if os.path.isfile(os.path.join(dist, path)):
        return send_from_directory(dist, path)
    return send_from_directory(dist, "index.html")


if __name__ == "__main__":
    if config.PRELOAD_MODELS:
        for m in config.MODELS:
            model_service.get_model(m)
        ct_validator.similarity_score(Image.new("L", (224, 224)))  # load CT reference features
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
