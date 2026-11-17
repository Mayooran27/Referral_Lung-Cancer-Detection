const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    throw new Error("Cannot reach the backend. Is the Flask server running on port 5000?");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.success === false) {
    const err = new Error(body.error || `Request failed (${res.status})`);
    err.reason = body.reason;
    err.code = body.code;
    throw err;
  }
  return body;
}

function upload(path, file, fields = {}) {
  const form = new FormData();
  form.append("file", file);
  Object.entries(fields).forEach(([k, v]) => form.append(k, v));
  return request(path, { method: "POST", body: form }).then((b) => b.scan);
}

export const apiUrl = (path) => BASE + path;

export const getHealth = () => request("/api/health");
export const getModels = () => request("/api/models").then((b) => b.models);

/** Run all three models; returns the saved scan. */
export const checkScan = (file, gradcam = true) =>
  upload("/api/predict/all", file, { gradcam: gradcam ? "1" : "0" });

export function getScans({ limit = 100, label, search } = {}) {
  const q = new URLSearchParams({ limit });
  if (label) q.set("label", label);
  if (search) q.set("search", search);
  return request(`/api/scans?${q}`).then((b) => b.scans);
}

export const getStats = () => request("/api/scans/stats");
export const getScan = (id) => request(`/api/scans/${id}`).then((b) => b.scan);
export const deleteScan = (id) => request(`/api/scans/${id}`, { method: "DELETE" });
