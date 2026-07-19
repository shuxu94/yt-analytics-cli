# YouTube Analytics CLI

`yt` is a scriptable YouTube Analytics command-line tool with a reusable Python service and
agent-tool layer. It supports growth audits, normalized video rankings, discovery and audience
reports, retention diagnostics, local history, experiments, forecasts, and interactive dashboards.

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
yt channel trend --period 90d
yt channel compare --current 28d
yt channel forecast --history 90d --days 28
yt channel anomalies --period 90d

yt videos top --period 28d --limit 20
yt videos top --period 90d --format csv
yt videos rank --period 90d --metric views_per_day
yt videos rank --period 90d --metric subscribers_per_1000_views
yt videos compare VIDEO_ID VIDEO_ID --period 90d

yt shorts performance --period 28d --metric engaged_view_ratio

yt traffic sources --period 28d
yt traffic search --period 90d
yt audience devices --period 28d
yt audience geography --period 90d
yt audience subscribers --period 28d

# Download the 100-point audience-retention curve for one video.
yt videos retention VIDEO_ID --output retention.csv
yt videos retention VIDEO_ID --period 90d --format json --output retention.json
yt retention diagnose VIDEO_ID --period lifetime

# Open the real YouTube player synchronized with its retention graph.
yt video retention VIDEO_ID --open
yt video retention VIDEO_ID --period 28d --port 8765

# Compare the Top 5 and Bottom 5 by views in one synchronized dashboard.
yt dashboard videos --period 28d

# Run the evidence-backed audit in the terminal or interactive dashboard.
yt audit grow --period 90d --compare previous
yt audit grow --period 90d --format json
yt dashboard grow --period 90d
```

The growth audit compares the selected period with the immediately preceding equal-length period.
Recommendations include their evidence, actions, expected impact, confidence, and effort. They are
deterministic rules over the retrieved data; an LLM is not required to run an audit.

## Normalized metrics

`yt videos rank` enriches Analytics API rows with owned-video metadata and calculates:

- Views per active day in the selected report window.
- Subscribers gained per 1,000 views.
- Likes, comments, and shares per 1,000 views.
- Engaged views divided by views.
- Average view percentage and watch time.

Shorts classification is deliberately strict. A video is labeled `shorts` only when owned-file
metadata confirms a vertical aspect ratio and the duration is no more than 180 seconds. If Google
does not return aspect-ratio metadata, the video remains `unknown` instead of being guessed from
duration alone. `engaged_view_ratio` is an API-computable proxy for continuing past the initial
seconds, not YouTube Studio's exact stayed-to-watch versus swiped-away percentage.

## History and experiments

```bash
# Pull a complete audit and save it locally.
yt sync snapshot --period 90d
yt history list

# Record a content hypothesis before publishing and close it after evaluation.
yt experiment add "Result-first hook" \
  --hypothesis "Showing the result first improves 3-second retention" \
  --video VIDEO_ID
yt experiment list --status active
yt experiment close 1 --result "3-second retention improved by 8 percentage points"
```

Snapshots and experiments are stored in `~/.local/share/ytanalytics/history.db`. The database does
not contain OAuth credentials; refreshable credentials remain in the operating-system keychain.

## Bulk reach and click-through reports

Thumbnail impressions and click-through rates are supplied through scheduled YouTube Reporting API
reach reports rather than the targeted query used by most CLI commands. Enable the **YouTube
Reporting API** in the Google Cloud project, then use:

```bash
yt reporting types --contains reach
yt reporting create --report-type REPORT_TYPE_ID --name "Channel reach"
yt reporting jobs
yt reporting reports JOB_ID
yt reporting download DOWNLOAD_URL --output channel-reach.csv.gz
```

Reporting jobs are asynchronous. A newly created job will not have historical files immediately;
Google generates reports on its own schedule.

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

The local retention dashboard runs only on `127.0.0.1`. It embeds YouTube's player, follows the
player's current time, and seeks the video when you click or drag the graph controls. The command
keeps running while the dashboard is open; press Ctrl+C in the terminal to stop it. Public and
unlisted videos can play directly. Private videos require the browser to be signed into an account
that can view them.

The growth dashboard also binds only to `127.0.0.1`. It displays period-over-period KPIs, a daily
views trend, content-type filtering, leading traffic sources, subscriber conversion, and the audit's
evidence-backed next actions.

## Design

```text
CLI / ChannelGrowthTools
        │
AnalyticsService          normalized reports, audits, forecasts, diagnostics
        │
GoogleAPIClient           Analytics + Data + bulk Reporting APIs
        │
CredentialStore           OS keychain secrets + named profile metadata
HistoryStore              local SQLite snapshots and experiments
```

`ytanalytics.agent_tools.ChannelGrowthTools` is the stable deterministic surface for a future AI
agent. It exposes growth diagnosis, content opportunities, video retention explanations, and search
opportunities without allowing an agent to construct unrestricted Google API requests.

## Test

```bash
pytest
ruff check src tests
```
