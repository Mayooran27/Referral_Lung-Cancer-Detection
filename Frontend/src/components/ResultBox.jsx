import { CLASS_NOTE, pct } from "../constants.js";

// Simple box showing the predicted class and confidence
export default function ResultBox({ title, prediction, confidence, note }) {
  return (
    <div className={`result-box result-${(prediction || "").toLowerCase()}`}>
      <div className="result-title">{title}</div>
      <div className="result-main">
        <span className="result-class">{prediction}</span>
        <span className="result-conf">Confidence: {pct(confidence)}</span>
      </div>
      <div className="result-note">{note ?? CLASS_NOTE[prediction]}</div>
    </div>
  );
}
