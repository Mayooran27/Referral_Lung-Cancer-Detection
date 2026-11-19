"""Model loading, preprocessing and inference."""
import csv
import json
import os
import threading
import time

import numpy as np
from PIL import Image

import config

_models = {}
_lock = threading.Lock()


def _model_dir(model_id):
    return os.path.join(config.MODEL_DIR, config.MODELS[model_id]["folder"])


def load_class_names(model_id):
    path = os.path.join(_model_dir(model_id), config.CLASS_INDEX_FILE)
    with open(path, encoding="utf-8") as f:
        indices = json.load(f)
    ordered = sorted(indices.items(), key=lambda kv: kv[1])
    return [config.CLASS_DISPLAY.get(name, name) for name, _ in ordered]


def load_test_metrics(model_id):
    """Parse the classification report CSV saved during training."""
    path = os.path.join(_model_dir(model_id), config.MODELS[model_id]["report"])
    if not os.path.exists(path):
        return None
    metrics = {"per_class": {}}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            label = (row.get("") or row.get("Unnamed: 0") or "").strip()
            if label == "accuracy":
                metrics["accuracy"] = float(row["precision"])
            elif label in ("macro avg", "weighted avg"):
                metrics[label.replace(" ", "_")] = {
                    k: float(row[k]) for k in ("precision", "recall", "f1-score")
                }
            elif label:
                metrics["per_class"][config.CLASS_DISPLAY.get(label, label)] = {
                    "precision": float(row["precision"]),
                    "recall": float(row["recall"]),
                    "f1": float(row["f1-score"]),
                    "support": int(float(row["support"])),
                }
    return metrics


def get_model(model_id):
    """Load a model lazily and cache it. Thread-safe."""
    if model_id in _models:
        return _models[model_id]
    with _lock:
        if model_id not in _models:
            import keras  # imported here so the API starts quickly

            path = os.path.join(_model_dir(model_id), config.MODELS[model_id]["file"])
            t0 = time.time()
            model = keras.models.load_model(path, compile=False)
            print(f"[model] loaded {model_id} in {time.time() - t0:.1f}s")
            _models[model_id] = model
    return _models[model_id]


def is_loaded(model_id):
    return model_id in _models


def preprocess(pil_image, model_id):
    """Return (batch array for the model, resized RGB uint8 image for display)."""
    cfg = config.MODELS[model_id]
    size = cfg["input_size"]
    rgb = pil_image.convert("RGB").resize((size, size), Image.BILINEAR)
    arr = np.asarray(rgb, dtype=np.float32)
    if cfg["preprocessing"] == "vgg16":
        from keras.applications.vgg16 import preprocess_input

        arr = preprocess_input(arr.copy())
    elif cfg["preprocessing"] == "rescale":
        arr = arr / 255.0
    else:
        raise ValueError(f"Unknown preprocessing: {cfg['preprocessing']}")
    return np.expand_dims(arr, 0), np.asarray(rgb, dtype=np.uint8)


def summarise(results):
    """Combine per-model results into one verdict.

    Averages the probabilities of the reliable models (falls back to all successful
    models if none are flagged reliable). Returns None if every model failed.
    """
    ok = [r for r in results if "error" not in r]
    if not ok:
        return None
    pool = [r for r in ok if r.get("model_reliable", True)] or ok
    classes = list(pool[0]["probabilities"])
    avg = {c: sum(r["probabilities"][c] for r in pool) / len(pool) for c in classes}
    top = max(avg, key=avg.get)
    return {
        "prediction": top,
        "confidence": avg[top],
        "probabilities": avg,
        "models_used": [r["model_id"] for r in pool],
        "agreement": all(r["prediction"] == top for r in pool),
        "method": "single model" if len(pool) == 1 else "average of reliable models",
    }


def predict(pil_image, model_id, with_gradcam=True):
    model = get_model(model_id)
    batch, display_img = preprocess(pil_image, model_id)
    class_names = load_class_names(model_id)

    t0 = time.time()
    probs = model.predict(batch, verbose=0)[0].astype(float)
    elapsed_ms = (time.time() - t0) * 1000

    top = int(np.argmax(probs))
    result = {
        "model_id": model_id,
        "model_name": config.MODELS[model_id]["name"],
        "prediction": class_names[top],
        "confidence": float(probs[top]),
        "probabilities": {name: float(p) for name, p in zip(class_names, probs)},
        "inference_ms": round(elapsed_ms, 1),
        "gradcam": None,
    }

    if with_gradcam:
        from services.gradcam import make_gradcam

        try:
            result["gradcam"] = make_gradcam(
                model, batch, display_img, top, config.MODELS[model_id]["gradcam_layer"]
            )
        except Exception as exc:  # Grad-CAM is a bonus; never fail the prediction for it
            print(f"[gradcam] failed for {model_id}: {exc}")
            result["gradcam_error"] = str(exc)

    return result
