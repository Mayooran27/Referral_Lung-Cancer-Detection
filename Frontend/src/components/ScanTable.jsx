import { Link } from "react-router-dom";
import { formatDay, formatTime, pct } from "../constants.js";
import Badge from "./Badge.jsx";

function modelsUsed(scan) {
  if (scan.mode === "all") return "All 3";
  return scan.results[0]?.model_name || scan.model_id;
}

export default function ScanTable({ scans, onDelete, emptyText = "No scans yet." }) {
  if (scans.length === 0) return <p className="muted">{emptyText}</p>;

  return (
    <div className="table-wrap">
      <table className="table table-striped">
        <thead>
          <tr>
            <th>Scan ID</th>
            <th>Date</th>
            <th>Time</th>
            <th>File name</th>
            <th>Model(s)</th>
            <th>Result</th>
            <th className="right">Confidence</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {scans.map((s) => (
            <tr key={s.id}>
              <td className="nowrap">{s.scan_code || s.id}</td>
              <td className="nowrap">{formatDay(s.created_at)}</td>
              <td>{formatTime(s.created_at)}</td>
              <td className="filename" title={s.filename}>{s.filename}</td>
              <td className="nowrap">{modelsUsed(s)}</td>
              <td><Badge label={s.prediction} /></td>
              <td className="right">{pct(s.confidence)}</td>
              <td className="nowrap right">
                <Link to={`/history/${s.id}`}>View</Link>
                {onDelete && (
                  <>
                    {" | "}
                    <button className="link-button danger" onClick={() => onDelete(s)}>Delete</button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
