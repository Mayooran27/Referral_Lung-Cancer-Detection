import { CLASS_ORDER, pct } from "../constants.js";

// Table of class probabilities with a small bar for each one
export default function ProbTable({ probabilities, predicted }) {
  return (
    <table className="table prob-table">
      <thead>
        <tr>
          <th>Class</th>
          <th>Probability</th>
          <th className="right">Value</th>
        </tr>
      </thead>
      <tbody>
        {CLASS_ORDER.filter((c) => c in probabilities).map((c) => (
          <tr key={c} className={c === predicted ? "row-highlight" : ""}>
            <td>{c}</td>
            <td className="bar-cell">
              <div className="bar">
                <div className={`bar-fill fill-${c.toLowerCase()}`} style={{ width: `${probabilities[c] * 100}%` }} />
              </div>
            </td>
            <td className="right">{pct(probabilities[c])}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
