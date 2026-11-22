import { useEffect, useState } from "react";
import ErrorMessage from "./ErrorMessage.jsx";

const ALLOWED_EXT = ["jpg", "jpeg", "png"];
const ALLOWED_TYPES = ["image/jpeg", "image/png"];
const MAX_MB = 10;

// CT slices are greyscale, so the R, G and B values of each pixel should be (almost) equal.
// Returns the average colour difference per pixel (0 = pure greyscale), or null if the image can't be read.
function colourScore(file) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const size = 128;
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, size, size);
      const d = ctx.getImageData(0, 0, size, size).data;
      let total = 0;
      for (let i = 0; i < d.length; i += 4) {
        const mean = (d[i] + d[i + 1] + d[i + 2]) / 3;
        total += (Math.abs(d[i] - mean) + Math.abs(d[i + 1] - mean) + Math.abs(d[i + 2] - mean)) / 3;
      }
      URL.revokeObjectURL(url);
      resolve(total / (size * size));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    img.src = url;
  });
}

// Quick checks in the browser before sending to the server (the server checks again).
async function checkFile(file) {
  const ext = file.name.split(".").pop().toLowerCase();
  if (!ALLOWED_EXT.includes(ext) || (file.type && !ALLOWED_TYPES.includes(file.type))) {
    return "Wrong file type. Please choose a .jpg, .jpeg or .png CT image.";
  }
  if (file.size > MAX_MB * 1024 * 1024) return `File is too big (max ${MAX_MB} MB).`;
  const score = await colourScore(file);
  if (score === null) return "The file could not be opened as an image.";
  if (score > 2) return "This looks like a colour image. CT scans are greyscale.";
  return "";
}

export default function ImageInput({ file, onFile, disabled }) {
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  async function handleChange(e) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    const problem = await checkFile(f);
    if (problem) {
      onFile(null);
      setError({ message: "Only lung CT scan images can be used.", reason: problem });
      return;
    }
    setError("");
    onFile(f);
  }

  return (
    <div className="image-input">
      <div className="form-label">CT image</div>
      <label className={`preview-box ${disabled ? "disabled" : ""}`} htmlFor="ct-file">
        {preview ? (
          <>
            <img src={preview} alt="Selected CT scan" />
            <div className="preview-name">{file.name} &middot; <span className="link-like">change</span></div>
          </>
        ) : (
          <>
            <span className="btn">Choose image...</span>
            <span className="muted small">JPG or PNG, max {MAX_MB} MB</span>
          </>
        )}
      </label>
      <input id="ct-file" type="file" accept=".jpg,.jpeg,.png" onChange={handleChange} disabled={disabled} hidden />

      <ErrorMessage error={error} />
    </div>
  );
}
