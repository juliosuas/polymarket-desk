# polymarket-desk

A Bloomberg-terminal-styled Polymarket dashboard with a daily research tracker. Originally built around the Sinaloa Gov. Rubén Rocha Moya extradition contract; generalized to surface trending markets, top movers, and high-conviction events across the platform.

## What's in here

```
.
├── tracker.py                   # daily research script (cron-driven)
├── server.py                    # local realtime dashboard (SSE + polling)
├── dashboard.html               # SPA UI for the local dashboard
├── run.sh                       # launchd wrapper
├── com.ghostcat.rocha-tracker.plist.example   # daily 09:00 cron template
├── com.ghostcat.rocha-dashboard.plist         # always-on dashboard service
├── REPORT_2026-05-06.md         # initial analyst desk note (Rocha case)
├── SUMMARY.md                   # quick-read summary
└── vercel/                      # serverless deploy of the dashboard
    ├── api/state.py             # combined Polymarket fetcher
    ├── public/index.html        # polling-based version of the dashboard
    └── vercel.json
```

## What it does

### Local services (macOS launchd)

- **`com.ghostcat.rocha-tracker`** — runs `tracker.py` daily at 09:00.
  - Pulls Polymarket Gamma API for tracked contracts and trending markets.
  - Pulls Google News RSS for headline scanning.
  - Saves a JSON snapshot for historical sparklines.
  - **Sends iMessage only when alert gates fire** (catalyst-grade move, near-cert bet, news red-flag). Silent otherwise.
- **`com.ghostcat.rocha-dashboard`** — keeps `server.py` running on `127.0.0.1:7878`.
  - Background thread polls Polymarket every 3s and pushes via Server-Sent Events to all connected browsers.
  - Endpoints: `/`, `/api/state`, `/api/stream` (SSE), `/api/history`.

### Cloud deploy (Vercel)

- Same dashboard, polling-based (no SSE — Vercel is serverless).
- `api/state.py` is a Vercel Python function that fetches Polymarket in parallel per request.
- `public/index.html` polls `/api/state` every 5 s, pauses when tab is hidden.

## Data sources

- **Polymarket Gamma API** — `https://gamma-api.polymarket.com/markets`, `/events`
- **Polymarket Data API** — `https://data-api.polymarket.com/trades` (live tape)
- **Google News RSS** — `https://news.google.com/rss/search` (Spanish-language, MX region)

All endpoints are public and unauthenticated.

## Alert gating philosophy

The tracker is **silent by default**. iMessage fires only when:

| # | Trigger | Threshold |
|---|---------|-----------|
| 1 | Tracked contract Δ24h | ≥ 7 pp |
| 2 | Tracked contract regime change | YES > 50 % or < 5 % |
| 3 | Near-certainty bet | YES ≥ 95 %, end ≤ 10 d, vol24h ≥ $30 k |
| 4 | Major dislocation | \|Δ24h\| ≥ 25 pp AND vol24h ≥ $200 k |
| 5 | News red-flag keyword | "extraditado", "detenido", "orden de aprehensión", "fuga", etc. |

Sports heads-up matches (e.g., tennis singles) are filtered out of trigger 4 — they resolve daily with huge swings but are not catalyst events.

## Setup (local)

```bash
# 1. Clone and enter
git clone git@github.com:juliosuas/polymarket-desk.git
cd polymarket-desk

# 2. Sanity-check that Python 3 + osascript work
python3 -c "import urllib.request,xml.etree.ElementTree"
which osascript

# 3. Make a real plist from the example, set your iMessage phone (E.164)
cp com.ghostcat.rocha-tracker.plist.example com.ghostcat.rocha-tracker.plist
# edit the file: replace +1XXXXXXXXXX and YOUR_USER

# 4. Install launchd jobs
mkdir -p ~/Library/LaunchAgents
cp com.ghostcat.rocha-tracker.plist ~/Library/LaunchAgents/
cp com.ghostcat.rocha-dashboard.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.ghostcat.rocha-tracker.plist
launchctl load -w ~/Library/LaunchAgents/com.ghostcat.rocha-dashboard.plist

# 5. Open dashboard
open http://127.0.0.1:7878
```

On first iMessage send, macOS will prompt for **Automation → Messages** permission. Allow it.

## Setup (Vercel)

```bash
cd vercel
vercel link
vercel deploy --prod
```

Disable deployment protection if needed:

```bash
vercel project protection disable <project-name> --sso --non-interactive
vercel project protection disable <project-name> --password --non-interactive
```

`*.vercel.app` URLs may still show "Pending Approval" to logged-in Vercel users on a different team. Workarounds: incognito window, or attach a custom domain.

## Adding new tracked contracts

Edit `tracker.MARKETS` (and `vercel/api/state.py`'s `ROCHA_MARKETS`) with new Polymarket slugs and your analyst desk fair-value estimates:

```python
{"key": "my_event",
 "label": "Will X happen by Y?",
 "slug": "polymarket-slug-here",
 "fair_yes": 0.10}
```

Snapshots, screen filters, and dashboard cards pick up the change automatically.

## Files NOT in this repo (gitignored)

- `logs/` — runtime logs.
- `snapshots/` — daily JSON snapshots (host filesystem).
- `com.ghostcat.rocha-tracker.plist` — the live plist with your phone number.
- `.vercel/` — Vercel project linkage.

## License

Personal use. Polymarket data is public; news content belongs to its publishers. Don't redistribute headlines as your own. Trading at your own risk.
