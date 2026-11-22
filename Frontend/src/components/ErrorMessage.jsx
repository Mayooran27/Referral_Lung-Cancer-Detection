// error can be a plain string or { message, reason } (used when an upload is rejected)
export default function ErrorMessage({ error }) {
  if (!error) return null;
  if (typeof error === "string") return <div className="alert alert-error">{error}</div>;
  return (
    <div className="alert alert-error" role="alert">
      <strong>{error.message}</strong>
      {error.reason && <div>{error.reason}</div>}
    </div>
  );
}
