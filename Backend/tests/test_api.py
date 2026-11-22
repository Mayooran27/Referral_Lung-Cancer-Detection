"""End-to-end API tests using real models and real test-split images.

Run from the Backend folder:  python -m pytest tests -v
"""
import glob
import io
import os
import sys
import tempfile

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ["LUNG_DATA_DIR"] = tempfile.mkdtemp(prefix="lung_test_")  # isolated scan history

from app import app  # noqa: E402

SPLITS = {"cnn": "Split_data_CNN", "vgg16": "Split_data_VGG_16", "inceptionv3": "Split_data_inception_V3"}
CLASSES = {"Benign": "Benign cases", "Malignant": "Malignant cases", "Normal": "Normal cases"}


@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def sample(model_id, label, n=1):
    files = sorted(glob.glob(os.path.join(BACKEND, SPLITS[model_id], "testing", CLASSES[label], "*")))
    return files[:n]


def post(client, path, filename, model=None, gradcam="1"):
    with open(filename, "rb") as f:
        data = {"file": (io.BytesIO(f.read()), os.path.basename(filename)), "gradcam": gradcam}
    if model:
        data["model"] = model
    return client.post(path, data=data, content_type="multipart/form-data")


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json["status"] == "ok"


def test_models_listing(client):
    models = {m["id"]: m for m in client.get("/api/models").json["models"]}
    assert set(models) == {"cnn", "vgg16", "inceptionv3"}
    for m in models.values():
        assert m["classes"] == ["Benign", "Malignant", "Normal"]
        assert 0 <= m["metrics"]["accuracy"] <= 1
    assert models["vgg16"]["reliable"] and models["inceptionv3"]["reliable"]
    assert not models["cnn"]["reliable"]


@pytest.mark.parametrize("model_id", ["cnn", "vgg16", "inceptionv3"])
def test_each_model_predicts_with_gradcam(client, model_id):
    r = post(client, "/api/predict/all", sample(model_id, "Malignant")[0])
    assert r.status_code == 200, r.json
    scan = r.json["scan"]
    assert scan["mode"] == "all"
    res = next(x for x in scan["results"] if x["model_id"] == model_id)
    assert res["prediction"] in CLASSES
    assert abs(sum(res["probabilities"].values()) - 1) < 1e-3
    assert res["gradcam"]["overlay"].startswith("data:image/png;base64,")


@pytest.mark.parametrize("model_id", ["vgg16", "inceptionv3"])
def test_reliable_models_are_accurate(client, model_id):
    correct = total = 0
    for label in CLASSES:
        for f in sample(model_id, label, n=5):
            r = post(client, "/api/predict/all", f, gradcam="0")
            res = next(x for x in r.json["scan"]["results"] if x["model_id"] == model_id)
            correct += res["prediction"] == label
            total += 1
    assert correct / total >= 0.8, f"{model_id}: {correct}/{total}"


def test_single_model_endpoint_removed(client):
    assert client.post("/api/predict", data={"model": "vgg16"}).status_code in (404, 405)


def test_predict_all_summary_ignores_unreliable_model(client):
    r = post(client, "/api/predict/all", sample("vgg16", "Malignant")[0], gradcam="0")
    assert r.status_code == 200
    scan = r.json["scan"]
    assert [x["model_id"] for x in scan["results"]] == ["cnn", "vgg16", "inceptionv3"]
    assert scan["summary"]["models_used"] == ["vgg16", "inceptionv3"]
    assert scan["prediction"] == "Malignant"


def test_history_stats_detail_image_delete(client):
    stats = client.get("/api/scans/stats").json
    assert stats["total"] == stats["Malignant"] + stats["Benign"] + stats["Normal"] > 0

    scans = client.get("/api/scans?limit=5").json["scans"]
    assert 0 < len(scans) <= 5
    assert "gradcam" not in scans[0]["results"][0]  # list view is lightweight

    assert all(s["prediction"] == "Normal" for s in client.get("/api/scans?label=Normal").json["scans"])

    sid = scans[0]["id"]
    assert client.get(f"/api/scans/{sid}").json["scan"]["id"] == sid
    img = client.get(f"/api/scans/{sid}/image")
    assert img.status_code == 200 and img.mimetype == "image/png"
    img.close()

    assert client.delete(f"/api/scans/{sid}").status_code == 200
    assert client.get(f"/api/scans/{sid}").status_code == 404
    assert client.get("/api/scans/stats").json["total"] == stats["total"] - 1


def test_rejects_bad_input(client):
    assert client.post("/api/predict/all", data={}).status_code == 400
    r = client.post(
        "/api/predict/all",
        data={"file": (io.BytesIO(b"not an image"), "x.png")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400 and "image" in r.json["error"]
    r = client.post(
        "/api/predict/all",
        data={"file": (io.BytesIO(b"abc"), "x.txt")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert client.get("/api/scans?label=Cancer").status_code == 400
    assert client.get("/api/scans/doesnotexist").status_code == 404


# ------------------------------------------------- only CT scan images accepted
def _png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _rejected(client, data, filename, path="/api/predict/all"):
    before = client.get("/api/scans/stats").json["total"]
    r = client.post(
        path,
        data={"file": (io.BytesIO(data), filename), "model": "vgg16", "gradcam": "0"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400, r.json
    assert r.json["code"] == "not_ct_scan"
    assert r.json["error"].startswith("Please predict correct images")
    assert client.get("/api/scans/stats").json["total"] == before  # nothing saved
    return r.json["reason"]


@pytest.mark.parametrize(
    "data, filename, kind",
    [
        (b"%PDF-1.7\n%...", "report.pdf", "PDF"),
        (b"%PDF-1.7\n%...", "renamed.jpg", "PDF"),  # renamed PDF is still caught
        (b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32, "clip.mp4", "video"),
        (b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 32, "voice.wav", "audio"),
        (b"ID3\x03\x00" + b"\x00" * 32, "song.png", "audio"),
    ],
)
def test_rejects_pdf_video_audio(client, data, filename, kind):
    assert kind in _rejected(client, data, filename)


def test_rejects_colour_photo(client):
    from PIL import Image

    img = Image.new("RGB", (300, 300), (220, 60, 90))
    assert "colour" in _rejected(client, _png(img), "photo.png")


def test_rejects_greyscale_non_ct_images(client):
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(0)
    noise = Image.fromarray(rng.integers(0, 255, (256, 256), dtype=np.uint8))
    gradient = Image.fromarray(np.tile(np.linspace(0, 255, 256, dtype=np.uint8), (256, 1)))
    blank = Image.new("L", (256, 256), 255)
    for img in (noise, gradient, blank):
        assert "does not look like" in _rejected(client, _png(img), "grey.png")


def test_accepts_all_ct_test_images_sample(client):
    from PIL import Image

    from services import ct_validator

    for label in CLASSES:
        for f in sample("vgg16", label, n=20):
            ct_validator.validate(Image.open(f))  # must not raise


def test_scan_codes_are_sequential_and_never_reused(client):
    first = post(client, "/api/predict/all", sample("vgg16", "Normal")[0], gradcam="0").json["scan"]
    assert first["scan_code"] == f"CT-{10000 + first['scan_no']}"
    client.delete(f"/api/scans/{first['id']}")  # delete the newest scan
    second = post(client, "/api/predict/all", sample("vgg16", "Benign")[0], gradcam="0").json["scan"]
    assert second["scan_no"] == first["scan_no"] + 1  # deleted number is not reused
    listed = client.get("/api/scans?limit=1").json["scans"][0]
    assert listed["scan_code"] == second["scan_code"]
