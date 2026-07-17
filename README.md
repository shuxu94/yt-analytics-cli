# YouTube Analytics CLI

`yt` is a scriptable YouTube Analytics command-line tool with a reusable Python service layer.
The first release supports OAuth profiles, channel summaries, and title-enriched top-video reports.

## Install for development

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Google Cloud setup

1. Create or select a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable **YouTube Analytics API** and **YouTube Data API v3**.
3. Configure the OAuth consent screen.
4. Create an OAuth client with application type **Desktop app**.

Keep the OAuth client secret private. The CLI opens the system browser, receives the callback on
localhost, and stores refreshable credentials in the operating-system keychain. Only non-secret
channel metadata is written to `~/.config/ytanalytics/profiles.json`.

Copy `.env.example` to `.env` and set `YT_CLIENT_ID` and `YT_CLIENT_SECRET` from the Desktop OAuth
client. The `.env` file is ignored by Git.

## Usage

```bash
yt auth login
yt auth status

yt channel summary --period 28d
yt channel summary --period 90d --format json

yt videos top --period 28d --limit 20
yt videos top --period 90d --format csv

# Download the 100-point audience-retention curve for one video.
yt videos retention VIDEO_ID --output retention.csv
yt videos retention VIDEO_ID --period 90d --format json --output retention.json
```

Named profiles allow multiple creators or channels:

```bash
yt auth login --profile second-channel
yt videos top --profile second-channel --format jsonl
```

Revenue access is opt-in because it requires another OAuth scope:

```bash
yt auth login --monetary
```

Every report supports `table`, `json`, `csv`, `jsonl`, and `markdown`. Structured data is
written only to stdout; errors are written to stderr, so piping remains reliable.

The retention report uses YouTube's `audienceWatchRatio` metric at each
`elapsedVideoTimeRatio` point. A watch ratio can exceed `1.0` when viewers rewind and watch a
segment more than once. YouTube only permits retention queries for one owned video at a time.

## Design

```text
CLI / future agent tools
        │
AnalyticsService          stable, normalized report methods
        │
GoogleAPIClient           YouTube Analytics + Data API requests
        │
CredentialStore           OS keychain secrets + named profile metadata
```

The next useful increments are a SQLite response cache, daily/traffic/geography report presets,
period comparisons, and a small agent-safe tool surface built on `AnalyticsService`.

## Test

```bash
pytest
ruff check .
```
