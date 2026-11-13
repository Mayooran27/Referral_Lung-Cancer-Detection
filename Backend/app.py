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