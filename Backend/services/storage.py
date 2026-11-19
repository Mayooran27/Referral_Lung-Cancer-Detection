"""Persistent scan history stored in SQLite, with uploaded images saved to disk."""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

import config

UPLOAD_DIR = os.path.join(config.DATA_DIR, "uploads")
DB_PATH = os.path.join(config.DATA_DIR, "scans.db")
MAX_SAVED_SIDE = 1024
SCAN_CODE_PREFIX = "CT-"
SCAN_CODE_BASE = 10000  # scan number 1 is shown as CT-10001

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    filename      TEXT NOT NULL,
    mode          TEXT NOT NULL,          -- 'all' (three models) or 'single'
    model_id      TEXT,                   -- set when mode = 'single'
    prediction    TEXT NOT NULL,          -- final verdict
    confidence    REAL NOT NULL,
    summary_json  TEXT NOT NULL,
    results_json  TEXT NOT NULL,          -- per-model results without Grad-CAM images
    gradcam_json  TEXT NOT NULL           -- {model_id: gradcam dict}
);
CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);
CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
"""


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with _connect() as conn:
        conn.executescript(SCHEMA)
        _migrate_scan_numbers(conn)


def _migrate_scan_numbers(conn):
    """Give every scan a permanent sequential number (shown as CT-10001, CT-10002, ...).

    Older databases have no scan_no column; existing scans are numbered oldest first.
    The counter only goes up, so a deleted scan's number is never reused.
    """
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(scans)")}
    if "scan_no" not in columns:
        conn.execute("ALTER TABLE scans ADD COLUMN scan_no INTEGER")
    last = conn.execute("SELECT COALESCE(MAX(scan_no), 0) FROM scans").fetchone()[0]
    for row in conn.execute("SELECT id FROM scans WHERE scan_no IS NULL ORDER BY created_at").fetchall():
        last += 1
        conn.execute("UPDATE scans SET scan_no = ? WHERE id = ?", (last, row["id"]))
    conn.execute(
        "INSERT INTO counters (name, value) VALUES ('scan_no', ?) "
        "ON CONFLICT(name) DO UPDATE SET value = MAX(value, excluded.value)",
        (last,),
    )


def _next_scan_no(conn):
    conn.execute("UPDATE counters SET value = value + 1 WHERE name = 'scan_no'")
    return conn.execute("SELECT value FROM counters WHERE name = 'scan_no'").fetchone()[0]


def scan_code(scan_no):
    return f"{SCAN_CODE_PREFIX}{SCAN_CODE_BASE + scan_no}" if scan_no else None


def image_path(scan_id):
    return os.path.join(UPLOAD_DIR, f"{scan_id}.png")


def _slim(result):
    keep = ("model_id", "model_name", "prediction", "confidence", "error", "model_reliable")
    return {k: result[k] for k in keep if k in result}


def _to_dict(row, full):
    scan = {
        "id": row["id"],
        "scan_no": row["scan_no"],
        "scan_code": scan_code(row["scan_no"]),
        "created_at": row["created_at"],
        "filename": row["filename"],
        "mode": row["mode"],
        "model_id": row["model_id"],
        "prediction": row["prediction"],
        "confidence": row["confidence"],
        "summary": json.loads(row["summary_json"]),
        "image_url": f"/api/scans/{row['id']}/image",
    }
    results = json.loads(row["results_json"])
    if full:
        gradcams = json.loads(row["gradcam_json"])
        for r in results:
            r["gradcam"] = gradcams.get(r.get("model_id"))
        scan["results"] = results
    else:
        scan["results"] = [_slim(r) for r in results]
    return scan


def save_scan(pil_image, filename, mode, model_id, results, summary):
    scan_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat()

    img = pil_image.convert("RGB")
    img.thumbnail((MAX_SAVED_SIDE, MAX_SAVED_SIDE))
    img.save(image_path(scan_id), format="PNG")

    gradcams = {r["model_id"]: r["gradcam"] for r in results if r.get("gradcam")}
    stored = [{k: v for k, v in r.items() if k != "gradcam"} for r in results]

    with _connect() as conn:
        conn.execute(
            "INSERT INTO scans (id, created_at, filename, mode, model_id, prediction, confidence,"
            " summary_json, results_json, gradcam_json, scan_no) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                scan_id, created, filename, mode, model_id,
                summary["prediction"], summary["confidence"],
                json.dumps(summary), json.dumps(stored), json.dumps(gradcams),
                _next_scan_no(conn),
            ),
        )
    return get_scan(scan_id)


def list_scans(limit=100, offset=0, label=None, search=None):
    sql, args = "SELECT * FROM scans WHERE 1=1", []
    if label:
        sql += " AND prediction = ?"
        args.append(label)
    if search:
        sql += " AND filename LIKE ?"
        args.append(f"%{search}%")
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    with _connect() as conn:
        return [_to_dict(r, full=False) for r in conn.execute(sql, args)]


def get_scan(scan_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    return _to_dict(row, full=True) if row else None


def delete_scan(scan_id):
    with _connect() as conn:
        deleted = conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,)).rowcount
    if deleted and os.path.exists(image_path(scan_id)):
        try:
            os.remove(image_path(scan_id))
        except OSError as exc:  # e.g. file still open on Windows; the record is already gone
            print(f"[storage] could not delete image for {scan_id}: {exc}")
    return bool(deleted)


def stats():
    counts = {"Malignant": 0, "Benign": 0, "Normal": 0}
    with _connect() as conn:
        for row in conn.execute("SELECT prediction, COUNT(*) AS n FROM scans GROUP BY prediction"):
            counts[row["prediction"]] = row["n"]
    return {"total": sum(counts.values()), **counts}
