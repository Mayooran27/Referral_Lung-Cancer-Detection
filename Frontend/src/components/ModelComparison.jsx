import { CLASS_ORDER, pct, sortResults } from "../constants.js";
import Badge from "./Badge.jsx";

// One row per model. If showProbs is true the probability of every class is shown as well.
export default function ModelComparison({ results, showProbs = false }) {
  const rows = sortResults(results);
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Prediction</th>
            <th className="right">Confidence</th>
            {showProbs && CLASS_ORDER.map((c) => <th key={c} className="right">P({c})</th>)}
            {showProbs && <th className="right">Time (ms)</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.model_id}>
              <td>
                {r.model_name}
                {r.model_reliable === false && <span className="warn-text"> (unreliable)</span>}
              </td>
              {r.error ? (
                <td colSpan={showProbs ? 6 : 2} className="error-text">Failed: {r.error}</td>
              ) : (
                <>
                  <td><Badge label={r.prediction} /></td>
                  <td className="right">{pct(r.confidence)}</td>
                  {showProbs &&
                    CLASS_ORDER.map((c) => (
                      <td key={c} className="right">{r.probabilities ? pct(r.probabilities[c]) : "-"}</td>
                    ))}
                  {showProbs && <td className="right">{r.inference_ms ?? "-"}</td>}
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
