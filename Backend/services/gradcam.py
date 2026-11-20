"""Grad-CAM visual explanations (Selvaraju et al., 2017)."""
import base64
import io

import cv2
import numpy as np
from PIL import Image

_grad_models = {}


def _find_last_conv_layer(model):
    import keras

    # Prefer a real conv layer: Dropout/Pooling outputs can be identities with no gradient path.
    for layer in reversed(model.layers):
        if isinstance(layer, (keras.layers.Conv2D, keras.layers.SeparableConv2D)):
            return layer.name
    for layer in reversed(model.layers):
        shape = getattr(layer, "output", None)
        shape = getattr(shape, "shape", None)
        if shape is not None and len(shape) == 4:
            return layer.name
    raise ValueError("No 4D convolutional layer found for Grad-CAM")


def _get_grad_model(model, layer_name):
    import keras

    key = (id(model), layer_name)
    if key not in _grad_models:
        _grad_models[key] = keras.Model(
            inputs=model.inputs,
            outputs=[model.get_layer(layer_name).output, model.outputs[0]],
        )
    return _grad_models[key]


def _to_base64_png(rgb_uint8):
    buf = io.BytesIO()
    Image.fromarray(rgb_uint8).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def make_gradcam(model, batch, display_img, class_index, layer_name=None, alpha=0.45):
    """Return base64 PNGs of the heatmap and overlay, plus the layer used."""
    import tensorflow as tf

    import keras

    layer_name = layer_name or _find_last_conv_layer(model)
    inputs = tf.convert_to_tensor(batch)
    if isinstance(model, keras.Sequential):
        # A reloaded Sequential model's symbolic graph can be disconnected in Keras 3,
        # so run its layers eagerly and capture the target activation directly.
        with tf.GradientTape() as tape:
            h, conv_out = inputs, None
            for layer in model.layers:
                h = layer(h, training=False)
                if layer.name == layer_name:
                    conv_out = h
                    tape.watch(conv_out)
            score = h[:, class_index]
    else:
        grad_model = _get_grad_model(model, layer_name)
        with tf.GradientTape() as tape:
            conv_out, preds = grad_model(inputs, training=False)
            score = preds[:, class_index]
    grads = tape.gradient(score, conv_out)
    if grads is None:
        raise ValueError(f"No gradient path from layer '{layer_name}' to the output")

    weights = tf.reduce_mean(grads, axis=(0, 1, 2))
    cam = tf.reduce_sum(conv_out[0] * weights, axis=-1)
    cam = tf.nn.relu(cam).numpy()

    peak = float(cam.max())
    cam = cam / peak if peak > 1e-10 else np.zeros_like(cam)

    h, w = display_img.shape[:2]
    cam = cv2.resize(cam.astype(np.float32), (w, h))
    heat_bgr = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
    heat_rgb = cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)
    overlay = np.uint8(np.clip(display_img * (1 - alpha) + heat_rgb * alpha, 0, 255))

    return {
        "layer": layer_name,
        "heatmap": _to_base64_png(heat_rgb),
        "overlay": _to_base64_png(overlay),
        "original": _to_base64_png(display_img),
        "empty": peak <= 1e-10,
    }
