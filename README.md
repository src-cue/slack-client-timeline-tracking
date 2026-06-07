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
