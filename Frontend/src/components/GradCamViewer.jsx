import { useState } from "react";

export default function GradCamViewer({ gradcam }) {
  const [opacity, setOpacity] = useState(0.5);
  const [sideBySide, setSideBySide] = useState(false);

  if (!gradcam) return <p className="muted">Grad-CAM was not generated for this model.</p>;

  return (
    <div className="gradcam">
      <div className="gradcam-options">
        <label>
          <input type="checkbox" checked={sideBySide} onChange={(e) => setSideBySide(e.target.checked)} /> Show
          original, heatmap and overlay side by side
        </label>
      </div>

      {gradcam.empty && (
        <div className="alert alert-warn">
          The model gave no positive activation for this class, so the heatmap is empty.
        </div>
      )}

      {sideBySide ? (
        <div className="figure-row">
          <figure><img src={gradcam.original} alt="Original" /><figcaption>(a) Input image</figcaption></figure>
          <figure><img src={gradcam.heatmap} alt="Heatmap" /><figcaption>(b) Grad-CAM heatmap</figcaption></figure>
          <figure><img src={gradcam.overlay} alt="Overlay" /><figcaption>(c) Overlay</figcaption></figure>
        </div>
      ) : (
        <>
          <div className="overlay-img">
            <img src={gradcam.original} alt="CT scan" />
            <img src={gradcam.heatmap} alt="Grad-CAM heatmap" className="overlay-top" style={{ opacity }} />
          </div>
          <div className="slider-row">
            <label htmlFor="opacity">Heatmap opacity:</label>
            <input
              id="opacity"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
            />
            <span>{Math.round(opacity * 100)}%</span>
          </div>
        </>
      )}

      <p className="muted small">
        Red/yellow areas had the most influence on the prediction, blue areas the least. Target layer:{" "}
        <code>{gradcam.layer}</code>
      </p>
    </div>
  );
}
