"""Central configuration for the Lung Cancer Detection backend.

Preprocessing for each model was verified against the held-out test split:
  * CNN         -> pixels / 255
  * VGG16       -> keras.applications.vgg16.preprocess_input (caffe-style BGR mean subtraction)
  * InceptionV3 -> pixels / 255
Using the wrong preprocessing drops VGG16 from ~98% to ~33% accuracy, so do not change
these without re-checking.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "Models")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_UPLOAD_MB = 10

# ---- CT scan validation (services/ct_validator.py): reject anything that is not a CT scan.
CT_MIN_SIZE = 64            # px, shortest side
CT_MAX_ASPECT = 2.0         # longest side / shortest side
# Greyscale check. Every dataset CT image scores 0.0; ordinary colour photos score 3.5-40.
CT_MAX_COLOUR = 2.0
# Similarity to the CT training images (VGG16 features, mean of the 5 nearest).
CT_FEATURE_LAYER = "global_average_pooling2d_1"
CT_MIN_SIMILARITY = 0.70    # CT val/test scans score >= 0.79; grey photos <= 0.61, noise/blank <= 0.41
CT_REFERENCE_DIR = os.path.join(BASE_DIR, "Split_data_VGG_16", "train")
CT_REFERENCE_FILE = os.path.join(MODEL_DIR, "ct_reference.npz")

# Order of the softmax outputs (from class_indices.json produced during training).
CLASS_INDEX_FILE = "class_indices.json"
CLASS_DISPLAY = {
    "Benign cases": "Benign",
    "Malignant cases": "Malignant",
    "Normal cases": "Normal",
}

MODELS = {
    "cnn": {
        "name": "Custom CNN",
        "folder": "CNN",
        "file": "CNN_best_model.keras",
        "report": "CNN_classification_report.csv",
        "input_size": 224,
        "preprocessing": "rescale",
        "gradcam_layer": None,  # auto-detect last 4D layer
        "description": "Convolutional network trained from scratch on the lung CT dataset.",
        "plots": {
            "accuracy": "CNN_accuracy.png",
            "loss": "CNN_loss.png",
            "confusion_matrix": "CNN_confusion_matrix.png",
        },
    },
    "vgg16": {
        "name": "VGG16",
        "folder": "VGG16",
        "file": "VGG16_best_model.keras",
        "report": "VGG16_classification_report.csv",
        "input_size": 224,
        "preprocessing": "vgg16",
        "gradcam_layer": "block5_conv3",
        "description": "Transfer learning from ImageNet VGG16 with a fine-tuned classification head.",
        "plots": {
            "accuracy": "VGG16_accuracy.png",
            "loss": "VGG16_loss.png",
            "confusion_matrix": "VGG16_confusion_matrix.png",
        },
    },
    "inceptionv3": {
        "name": "InceptionV3",
        "folder": "Inception V3",
        "file": "best_model.keras",
        "report": "inceptionv3_classification_report.csv",
        "input_size": 299,
        "preprocessing": "rescale",
        "gradcam_layer": "mixed10",
        "description": "Transfer learning from ImageNet InceptionV3 with multi-scale inception blocks.",
        "plots": {
            "accuracy": "inceptionv3_accuracy.png",
            "loss": "inceptionv3_loss.png",
            "confusion_matrix": "inceptionv3_confusion_matrix.png",
        },
    },
}

# A model whose test accuracy is below this is flagged as unreliable in the UI.
RELIABILITY_THRESHOLD = 0.60

CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

# Scan history (SQLite database + saved upload images)
DATA_DIR = os.environ.get("LUNG_DATA_DIR", os.path.join(BASE_DIR, "data"))
PRELOAD_MODELS = os.environ.get("PRELOAD_MODELS", "0") == "1"
