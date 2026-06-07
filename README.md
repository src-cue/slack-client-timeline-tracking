# Slack Client Timeline Tracker

Automated workflow that renders a color-coded snapshot of client project timelines from Google Sheets and posts it to Slack every weekday morning.

## What it does

1. Pulls deliverable data from a public Google Sheet (CSV export)
2. Categorises rows into **Completed** and **In Progress** tasks
3. Renders styled HTML tables (color-coded by meet type, status, and stage) into PNG images
4. Chunks the data (~10 rows per image) and posts all images as a single Slack message

## Schedule

Runs automatically Monday–Friday at **10:30 AM IST** (05:00 UTC) via GitHub Actions.
Can also be triggered manually from the Actions tab.

## Setup

### 1. Fork / clone this repo

### 2. Set repository secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|---|---|
| `SLACK_BOT_TOKEN` | Bot token with `files:write` and `chat:write` scopes |
| `SLACK_CHANNEL_ID` | Target channel ID (e.g. `C012AB3CD`) |

### 3. Update the Google Sheet URL

In `scripts/render_and_upload.py`, replace the `SHEET_URL` value with your own Google Sheet's CSV export URL:
File → Share → Publish to web → CSV format → Copy link

### 4. (Optional) Adjust chunk size

Change the `CHUNK_SIZE` variable in the script to control how many rows appear per image (default: 10).

## Local development

```bash
pip install -r requirements.txt

# System deps (Ubuntu/Debian)
sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
     libgdk-pixbuf2.0-0 libffi-dev shared-mime-info poppler-utils

python scripts/render_and_upload.py


---

**Repo description** (the one-liner shown on GitHub):

> Automated GitHub Action that snapshots client project timelines from Google Sheets and posts color-coded images to Slack every weekday.

---

To push this: share a `GITHUB_TOKEN` with `repo` scope and I'll create the file and update the description via the API. Or I can give you the exact `curl` commands to run yourself.
