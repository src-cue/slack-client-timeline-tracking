#!/usr/bin/env python3
"""
Fetches the deliverables Google Sheet, renders two screenshots
(Completed and In Progress), and uploads them to Slack.
"""

import csv
import io
import os
import re
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
SLACK_CHANNEL = "D0ASJB5DW7N"

# ── Fetch & parse sheet ───────────────────────────────────────────────────────

def clean_status(s):
    """Strip leading emoji characters and whitespace."""
    s = s.strip()
    s = re.sub(r'^[\U00010000-\U0010FFFF☀-➿⬀-⯿\U0001F300-\U0001F9FF]+\s*', '', s)
    return s.strip()

def fetch_rows():
    print(f"Fetching: {SHEET_CSV_URL}")
    resp = requests.get(SHEET_CSV_URL, timeout=30)
    print(f"HTTP {resp.status_code}  content-type: {resp.headers.get('content-type','?')}")
    print(f"First 300 chars: {resp.text[:300]!r}")
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    completed, in_progress = [], []
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
        else:
            in_progress.append(entry)
    return completed, in_progress

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

def build_html(rows, title):
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
          <td style="color:#aaa;font-size:11px;padding:6px 8px;text-align:center;white-space:nowrap;">{i+1}</td>
          <td style="padding:5px 8px;">{meet_chip(meet)}</td>
          <td style="padding:5px 8px;font-size:12px;color:#333;white-space:nowrap;">{customer}</td>
          <td style="padding:5px 10px;font-size:12px;color:#222;max-width:280px;line-height:1.4;">{task}</td>
          <td style="padding:5px 8px;font-size:12px;color:#555;max-width:140px;">{owners}</td>
          <td style="padding:5px 8px;">{status_badge(status)}</td>
          <td style="padding:5px 8px;">{stage_badge(stage)}</td>
          <td style="padding:5px 8px;font-size:12px;color:#555;white-space:nowrap;">{int_dl}</td>
          <td style="padding:5px 8px;font-size:12px;color:#555;white-space:nowrap;">{cli_dl}</td>
          <td style="padding:5px 8px;font-size:12px;color:#555;white-space:nowrap;">{del_date or "—"}</td>
          <td style="padding:5px 8px;font-size:11px;color:#666;max-width:180px;line-height:1.4;">{notes}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ margin:0; padding:16px 20px; background:#fff; font-family:Arial,sans-serif; width:290mm; }}
  h2   {{ font-size:14px; color:#333; margin:0 0 10px; font-weight:600; }}
  table {{ border-collapse:collapse; width:100%; }}
  th, td {{ vertical-align:middle; }}
  @page {{ size:310mm 297mm; margin:8mm; }}
</style></head>
<body>
<h2>{title} <span style="color:#888;font-weight:400;font-size:12px;">({len(rows)} items · {today})</span></h2>
<table><thead><tr>{header_cells}</tr></thead><tbody>{rows_html}</tbody></table>
</body></html>"""

# ── Render ────────────────────────────────────────────────────────────────────

def render_png(rows, title, out_path):
    html = build_html(rows, title)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name
    try:
        weasyprint.HTML(string=html).write_pdf(pdf_path, presentational_hints=True)
        pages = convert_from_path(pdf_path, dpi=150)
        total_h = sum(p.height for p in pages)
        canvas  = Image.new("RGB", (pages[0].width, total_h), "white")
        y = 0
        for p in pages:
            canvas.paste(p, (0, y))
            y += p.height
        canvas.save(out_path, "PNG")
        print(f"Rendered {out_path}  ({canvas.width}×{canvas.height}px)")
    finally:
        os.unlink(pdf_path)

# ── Slack upload ──────────────────────────────────────────────────────────────

def slack_upload(file_path, filename, title, comment):
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}"}
    file_size = os.path.getsize(file_path)

    # 1. Get upload URL
    r = requests.post("https://slack.com/api/files.getUploadURLExternal",
                      headers=headers,
                      data={"filename": filename, "length": file_size})
    r.raise_for_status()
    data = r.json()
    assert data.get("ok"), f"getUploadURLExternal: {data}"

    # 2. Upload bytes
    with open(file_path, "rb") as fh:
        up = requests.post(data["upload_url"], files={"file": (filename, fh, "image/png")})
    up.raise_for_status()

    # 3. Complete & post to channel
    done = requests.post("https://slack.com/api/files.completeUploadExternal",
                         headers={**headers, "Content-Type": "application/json"},
                         json={
                             "files": [{"id": data["file_id"], "title": title}],
                             "channel_id": SLACK_CHANNEL,
                             "initial_comment": comment,
                         })
    done.raise_for_status()
    result = done.json()
    assert result.get("ok"), f"completeUploadExternal: {result}"
    print(f"Uploaded to Slack: {filename}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Fetching Google Sheet...")
    completed, in_progress = fetch_rows()
    print(f"  {len(completed)} completed, {len(in_progress)} in-progress rows")

    today_str = date.today().strftime("%-d %B %Y")

    with tempfile.TemporaryDirectory() as tmp:
        comp_path = os.path.join(tmp, "completed.png")
        inp_path  = os.path.join(tmp, "in_progress.png")

        render_png(completed,   "✅ Completed  (Stage = Complete)",                 comp_path)
        render_png(in_progress, "🔄 In Progress / Not Started  (Stage ≠ Complete)", inp_path)

        slack_upload(comp_path,
                     f"completed_{date.today():%Y%m%d}.png",
                     f"✅ Completed — {today_str}",
                     f"*✅ Completed Tasks* — {today_str}  ({len(completed)} items)")

        slack_upload(inp_path,
                     f"in_progress_{date.today():%Y%m%d}.png",
                     f"🔄 In Progress / Not Started — {today_str}",
                     f"*🔄 In Progress / Not Started* — {today_str}  ({len(in_progress)} items)")

    print("Done.")

if __name__ == "__main__":
    main()
