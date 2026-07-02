#!/usr/bin/env python3
"""
Fetches the deliverables Google Sheet, renders chunked screenshots
(~10 rows each), and uploads them to Slack as multiple images.
"""

import csv
import io
import os
import re
import sys
import tempfile
from datetime import date

import requests
import weasyprint
from pdf2image import convert_from_path
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────

SHEET_ID      = "1M_ZTPSUVLskxa_cuEXgUE2B6YR8LV_hm54GXjRDCg94"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
SLACK_TOKEN   = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL = "C0B1J30FN8L"
ROWS_PER_SHOT = 10              # rows per screenshot

# ── Fetch & parse sheet ───────────────────────────────────────────────────────

def clean_status(s):
    """Strip leading emoji and whitespace to get plain status text."""
    s = s.strip()
    # Remove any leading Unicode emoji / symbol characters
    s = re.sub(r'^[\U0001F000-\U0001FFFF☀-➿⬀-⯿︀-️]+\s*', '', s)
    return s.strip()

def fetch_rows():
    resp = requests.get(SHEET_CSV_URL, timeout=30)
    resp.raise_for_status()
    # Force UTF-8 so emoji in Status aren't mangled
    text = resp.content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    completed, blocked, in_progress = [], [], []
    for row in reader:
        meet     = row.get("Meet", "").strip()
        customer = row.get("Customer", "").strip()
        task     = row.get("Module / Task", "").strip()
        owners   = row.get("Owner(s)", "").strip()
        status   = clean_status(row.get("Status", ""))
        stage    = row.get("Stage", "").strip()
        int_dl   = row.get("Internal - Deadline", "").strip() or "—"
        cli_dl   = row.get("Client- Deadline", "").strip() or "—"
        del_date = row.get("Delivered Date", "").strip()
        notes    = row.get("Notes", "").strip()
        if not meet:
            continue
        entry = (meet, customer, task, owners, status, stage, int_dl, cli_dl, del_date, notes)
        if stage.strip().lower() == "complete":
            completed.append(entry)
        elif stage.strip().lower() == "blocked":
            blocked.append(entry)
        else:
            in_progress.append(entry)
    print(f"Fetched: {len(completed)} completed, {len(blocked)} blocked, {len(in_progress)} in-progress")
    return completed, blocked, in_progress

# ── Style maps ────────────────────────────────────────────────────────────────

MEET_COLORS = {
    "Klay / Kreedo": ("#ede7f6", "#6a3ea1"),
    "ERP":           ("#e8f5e9", "#2e7d32"),
    "Fee":           ("#fff3e0", "#e65100"),
    "AI":            ("#e3f2fd", "#1565c0"),
    "Admission":     ("#f3e5f5", "#7b1fa2"),
    "US Readiness":  ("#fce4ec", "#c62828"),
}

STATUS_STYLES = {
    "Miss Timeline": ("background:#fce4e4;color:#c62828;border:1px solid #f5c6c6;", "●"),
    "On Track":      ("background:#e6f4ea;color:#2e7d32;border:1px solid #b7dfb9;", "●"),
    "At Risk":       ("background:#fff8e1;color:#e65100;border:1px solid #ffe0b2;", "●"),
    "Blocked":       ("background:#212121;color:#fff;border:1px solid #212121;",    ""),
}

STAGE_STYLES = {
    "Complete":              "background:#e6f4ea;color:#2e7d32;border:1px solid #b7dfb9;",
    "In Progress - Testing": "background:#fff3e0;color:#e65100;border:1px solid #ffe0b2;",
    "In Progress - DEV":     "background:#e8eaf6;color:#3949ab;border:1px solid #c5cae9;",
    "Not Started":           "background:#f5f5f5;color:#616161;border:1px solid #e0e0e0;",
    "Blocked":               "background:#212121;color:#fff;border:1px solid #212121;",
}

def meet_chip(meet):
    bg, fg = MEET_COLORS.get(meet, ("#f5f5f5", "#333"))
    return (f'<span style="background:{bg};color:{fg};border-radius:4px;'
            f'padding:2px 7px;font-size:11px;font-weight:600;white-space:nowrap;">{meet}</span>')

def status_badge(status):
    style, dot = STATUS_STYLES.get(status, ("background:#eee;color:#333;border:1px solid #ccc;", ""))
    dot_html = f'<span style="margin-right:4px;font-size:9px;">{dot}</span>' if dot else ""
    return (f'<span style="display:inline-block;{style}border-radius:20px;'
            f'padding:2px 10px;font-size:11px;font-weight:600;white-space:nowrap;">'
            f'{dot_html}{status}</span>')

def stage_badge(stage):
    style = STAGE_STYLES.get(stage, "background:#eee;color:#333;border:1px solid #ccc;")
    return (f'<span style="display:inline-block;{style}border-radius:20px;'
            f'padding:2px 10px;font-size:11px;font-weight:600;white-space:nowrap;">{stage}</span>')

# ── HTML builder ──────────────────────────────────────────────────────────────

HEADERS = ["#", "Meet", "Customer", "Module / Task", "Owner(s)", "Status", "Stage",
           "Internal Deadline", "Client Deadline", "Delivered Date", "Notes"]

def build_html(rows, title, row_offset=0):
    today = date.today().strftime("%-d %B %Y")
    header_cells = "".join(
        f'<th style="background:#1a3a2a;color:#fff;padding:8px 10px;font-size:12px;'
        f'font-weight:600;text-align:left;white-space:nowrap;letter-spacing:0.3px;">{h}</th>'
        for h in HEADERS
    )
    rows_html = ""
    for i, (meet, customer, task, owners, status, stage, int_dl, cli_dl, del_date, notes) in enumerate(rows):
        bg = "#ffffff" if i % 2 == 0 else "#f9f9f9"
        rows_html += f"""
        <tr style="background:{bg};border-bottom:1px solid #e8e8e8;">
          <td style="color:#aaa;font-size:11px;padding:6px 8px;text-align:center;white-space:nowrap;">{row_offset+i+1}</td>
          <td style="padding:5px 8px;">{meet_chip(meet)}</td>
          <td style="padding:5px 8px;font-size:12px;color:#333;white-space:nowrap;">{customer}</td>
          <td style="padding:5px 10px;font-size:12px;color:#222;max-width:380px;line-height:1.4;">{task}</td>
          <td style="padding:5px 8px;font-size:12px;color:#555;max-width:140px;">{owners}</td>
          <td style="padding:5px 8px;">{status_badge(status)}</td>
          <td style="padding:5px 8px;">{stage_badge(stage)}</td>
          <td style="padding:5px 8px;font-size:12px;color:#555;white-space:nowrap;">{int_dl}</td>
          <td style="padding:5px 8px;font-size:12px;color:#555;white-space:nowrap;">{cli_dl}</td>
          <td style="padding:5px 8px;font-size:12px;color:#555;white-space:nowrap;">{del_date or "—"}</td>
          <td style="padding:5px 8px;font-size:11px;color:#666;max-width:250px;line-height:1.4;">{notes}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ margin:0; padding:14px 18px; background:#fff; font-family:Arial,sans-serif; width:340mm; }}
  h2   {{ font-size:13px; color:#333; margin:0 0 8px; font-weight:600; }}
  table {{ border-collapse:collapse; width:100%; }}
  th, td {{ vertical-align:middle; }}
  @page {{ size:360mm 5000mm; margin:0; }}
</style></head>
<body>
<h2>{title} <span style="color:#888;font-weight:400;font-size:11px;">{today}</span></h2>
<table><thead><tr>{header_cells}</tr></thead><tbody>{rows_html}</tbody></table>
</body></html>"""

# ── Render a chunk → single tight PNG ────────────────────────────────────────

def render_chunk(rows, title, out_path, row_offset=0):
    html = build_html(rows, title, row_offset)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name
    try:
        weasyprint.HTML(string=html).write_pdf(pdf_path, presentational_hints=True)
        pages = convert_from_path(pdf_path, dpi=150)
        # Use only the first page (chunk fits on one tall page)
        img = pages[0]
        # Crop white space at the bottom
        gray = img.convert("L")
        bbox = gray.point(lambda x: 0 if x > 248 else 255).getbbox()
        if bbox:
            img = img.crop((0, 0, img.width, min(bbox[3] + 20, img.height)))
        img.save(out_path, "PNG")
        print(f"  Rendered {out_path}  ({img.width}×{img.height}px)")
    finally:
        os.unlink(pdf_path)

# ── Slack helpers ─────────────────────────────────────────────────────────────


def upload_file(file_path, filename):
    """Upload file bytes, return file_id (does not post to channel yet)."""
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}"}
    file_size = os.path.getsize(file_path)

    r = requests.post("https://slack.com/api/files.getUploadURLExternal",
                      headers=headers,
                      data={"filename": filename, "length": file_size})
    r.raise_for_status()
    data = r.json()
    assert data.get("ok"), f"getUploadURLExternal: {data}"

    with open(file_path, "rb") as fh:
        up = requests.post(data["upload_url"], files={"file": (filename, fh, "image/png")})
    up.raise_for_status()
    print(f"  Staged: {filename}")
    return data["file_id"]

def complete_upload(file_ids, label, comment, channel_id):
    """Post all staged files as a single Slack message."""
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"}
    done = requests.post("https://slack.com/api/files.completeUploadExternal",
                         headers=headers,
                         json={
                             "files": [{"id": fid, "title": label} for fid in file_ids],
                             "channel_id": channel_id,
                             "initial_comment": comment,
                         })
    done.raise_for_status()
    result = done.json()
    assert result.get("ok"), f"completeUploadExternal: {result}"
    print(f"  Posted {len(file_ids)} screenshot(s) as one message")

# ── Main ──────────────────────────────────────────────────────────────────────

def upload_chunks(rows, label, emoji, slug, today_str, channel_id, tmp):
    total = len(rows)
    if total == 0:
        print(f"  Skipping {label}: no items")
        return
    chunks = [rows[i:i+ROWS_PER_SHOT] for i in range(0, total, ROWS_PER_SHOT)]
    # Stage all files first
    file_ids = []
    for idx, chunk in enumerate(chunks, 1):
        out = os.path.join(tmp, f"{slug}_{idx:02d}.png")
        render_chunk(chunk, f"{emoji} {label}", out, row_offset=(idx-1)*ROWS_PER_SHOT)
        file_ids.append(upload_file(out, f"{slug}_{date.today():%Y%m%d}_{idx:02d}.png"))
    # Post all as one message
    complete_upload(file_ids, f"{emoji} {label}",
                    f"*{emoji} {label}* — {today_str}  ({total} items)",
                    channel_id)

def main():
    completed, blocked, in_progress = fetch_rows()
    today_str = date.today().strftime("%-d %B %Y")

    with tempfile.TemporaryDirectory() as tmp:
        upload_chunks(completed,   "Completed",              "✅", "completed",   today_str, SLACK_CHANNEL, tmp)
        upload_chunks(blocked,     "Blocked",                "⛔", "blocked",     today_str, SLACK_CHANNEL, tmp)
        upload_chunks(in_progress, "In Progress/Not Started","🔄", "in_progress", today_str, SLACK_CHANNEL, tmp)

    print("Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
