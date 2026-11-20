"""Checks that an upload really is a lung CT scan image before any model sees it.

Three checks, cheapest first:

1. File type: read from the file's own bytes, not its name. PDFs, videos, audio and
   other non-image files are rejected even if they are renamed to .jpg.
2. Greyscale: CT slices have no colour (every image in the dataset has exactly 0
   colour difference between R, G and B), while ordinary photos score about 3-40.
3. Similarity to the training CT scans: the image's VGG16 features (global average pooling
   layer) are compared with features of the CT training images. A grey photo,
   document or drawing is far from every CT scan and is rejected.

The reference features are built once from Split_data_VGG_16/train and cached in
Models/ct_reference.npz. Rebuild them with:  python -m services.ct_validator
"""
import glob
import os
import threading

import numpy as np
from PIL import Image

import config

REJECT_MESSAGE = "Please predict correct images. Only lung CT scan images are accepted."

# Magic bytes of common non-image files, so we can tell the user what they uploaded.
_SIGNATURES = [
    (b"%PDF", "a PDF document"),
    (b"ID3", "an audio file"),
    (b"fLaC", "an audio file"),
    (b"OggS", "an audio or video file"),
    (b"\x1aE\xdf\xa3", "a video file"),  # webm / mkv
    (b"PK\x03\x04", "a ZIP / Office document"),
    (b"GIF8", "a GIF animation"),
]
_IMAGE_FORMATS = {"JPEG", "PNG"}

_ref = None
_extractor = None
_lock = threading.Lock()



class NotCTScanError(ValueError):
    """Raised when an upload is not an acceptable CT scan image."""

    def __init__(self, reason):
        super().__init__(REJECT_MESSAGE)
        self.reason = reason




# --------------------------------------------------------------- 1. file type
def detect_non_image(data):
    """Return a description like 'a PDF document' if the bytes are a known non-image type."""
    head = data[:16]
    for sig, kind in _SIGNATURES:
        if head.startswith(sig):
            return kind
    if head[4:8] == b"ftyp":  # mp4, mov, m4a, heic
        return "a video or audio file"
    if head[:4] == b"RIFF":  # wav, avi, webp
        return {b"WAVE": "an audio file", b"AVI ": "a video file"}.get(head[8:12], "an unsupported file")
    if head[:3] == b"\xff\xfb" or head[:2] in (b"\xff\xf3", b"\xff\xf2"):  # mp3 without ID3
        return "an audio file"
    return None


def check_format(img):
    if img.format not in _IMAGE_FORMATS:
        raise NotCTScanError(f"Unsupported image format ({img.format}). Use a JPG or PNG CT image.")
    if getattr(img, "n_frames", 1) > 1:
        raise NotCTScanError("Animated or multi-frame images are not accepted.")
    w, h = img.size
    if min(w, h) < config.CT_MIN_SIZE:
        raise NotCTScanError(f"Image is too small ({w}x{h}). CT images must be at least {config.CT_MIN_SIZE} px.")
    if max(w, h) / min(w, h) > config.CT_MAX_ASPECT:
        raise NotCTScanError("Image shape does not match a CT slice (it is far from square).")


# --------------------------------------------------------------- 2. greyscale
def colour_score(img):
    """Mean absolute difference between each channel and the pixel's grey value (0 = greyscale)."""
    a = np.asarray(img.convert("RGB").resize((128, 128)), dtype=np.float32)
    return float(np.abs(a - a.mean(axis=2, keepdims=True)).mean())


# ------------------------------------------------- 3. similarity to CT scans
def _get_extractor():
    global _extractor
    if _extractor is None:
        import keras

        from services import model_service

        model = model_service.get_model("vgg16")
        _extractor = keras.Model(model.inputs, model.get_layer(config.CT_FEATURE_LAYER).output)
    return _extractor


def _features(images, batch_size=32):
    from services import model_service

    batch = np.concatenate([model_service.preprocess(im, "vgg16")[0] for im in images])
    f = _get_extractor().predict(batch, batch_size=batch_size, verbose=0)
    return f / np.linalg.norm(f, axis=1, keepdims=True)


def build_reference():
    """Compute features of every CT training image and save them."""
    files = sorted(glob.glob(os.path.join(config.CT_REFERENCE_DIR, "*", "*")))
    if not files:
        raise RuntimeError(f"No CT training images found in {config.CT_REFERENCE_DIR}")
    feats = []
    for i in range(0, len(files), 64):
        feats.append(_features([Image.open(f) for f in files[i : i + 64]]))
        print(f"[ct_validator] reference {min(i + 64, len(files))}/{len(files)}")
    feats = np.concatenate(feats).astype(np.float16)
    np.savez_compressed(config.CT_REFERENCE_FILE, features=feats)
    return feats


def _reference():
    global _ref
    if _ref is None:
        with _lock:
            if _ref is None:
                if os.path.exists(config.CT_REFERENCE_FILE):
                    _ref = np.load(config.CT_REFERENCE_FILE)["features"].astype(np.float32)
                else:
                    print("[ct_validator] building CT reference features (first run only)...")
                    _ref = build_reference().astype(np.float32)
    return _ref


def similarity_score(img):
    """Mean cosine similarity to the 5 most similar CT training images (1 = identical)."""
    sims = _features([img])[0] @ _reference().T
    return float(np.sort(sims)[-5:].mean())


# ------------------------------------------------------------------- public
def validate(img):
    """Raise NotCTScanError if the image is not a lung CT scan."""
    check_format(img)
    if colour_score(img) > config.CT_MAX_COLOUR:
        raise NotCTScanError("This is a colour image. CT scans are greyscale.")
    if similarity_score(img) < config.CT_MIN_SIMILARITY:
        raise NotCTScanError("This image does not look like a lung CT scan.")


if __name__ == "__main__":
    build_reference()
    print("Saved", config.CT_REFERENCE_FILE)
