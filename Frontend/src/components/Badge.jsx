export default function Badge({ label }) {
  if (!label) return <span>-</span>;
  return <span className={`label label-${label.toLowerCase()}`}>{label}</span>;
}
