export const CLASS_ORDER = ["Malignant", "Benign", "Normal"];

export const CLASS_NOTE = {
  Malignant: "Pattern consistent with a malignant nodule. Should be reviewed by a specialist.",
  Benign: "Pattern consistent with a benign (non-cancerous) nodule.",
  Normal: "No abnormal nodule pattern detected.",
};

export const MODEL_ORDER = ["vgg16", "inceptionv3", "cnn"];

export const pct = (v, digits = 1) => (v == null ? "-" : `${(v * 100).toFixed(digits)}%`);

export function sortResults(results) {
  return [...results].sort((a, b) => MODEL_ORDER.indexOf(a.model_id) - MODEL_ORDER.indexOf(b.model_id));
}

// e.g. 2026-11-16
export function formatDay(iso) {
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// e.g. 22:11
export function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}
