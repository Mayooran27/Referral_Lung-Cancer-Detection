import io
import json
import os
import threading
from datetime import datetime, timezone

import numpy as np
from PIL import Image, UnidentifiedImageError

from flask import Flask, request, jsonify, render_template
from keras.models import load_model
from keras.preprocessing import image



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "Models")
TEMPLATE_FOLDER = os.path.join(BASE_DIR, "templates")
STATIC_FOLDER = os.path.join(BASE_DIR, "static")