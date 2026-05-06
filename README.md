# polymarket-desk

A Bloomberg-terminal-styled dashboard for Polymarket. Live trending markets, top movers, value plays auto-screen, and a synced personal watchlist. Read-only by design — no trading, no keys.

## Features

- **Watchlist** — star any market, syncs across devices via a per-user token
- **Trending** — top events by 24h volume, top movers, top markets
- **Value Plays** — heuristic auto-screen that surfaces extreme prices with active flow
- **Screens** — high-conviction (YES 70-97%, ending soon) + top flow
- **Live Tape** — last 30 trades platform-wide, flashing on each new fill
- **Real-time-ish** — 5s polling with edge-cached responses

## Stack

- Python serverless functions on Vercel (`api/state.py`, `api/watchlist.py`)
- Vercel KV (Redis) for watchlist persistence
- Vanilla JS / HTML / CSS dashboard (`public/index.html`) — no build step
- Polymarket Gamma + data-api endpoints (public, unauthenticated)

## Layout

```
.
├── api/
│   ├── state.py        # combined Polymarket fetcher (parallel)
│   └── watchlist.py    # KV CRUD: GET/POST/DELETE /api/watchlist?u=<token>
├── public/
│   └── index.html      # SPA dashboard
├── vercel.json         # functions + headers config
└── README.md
```

## How identity works

No login. Each browser generates a UUID v4 and stores it in `localStorage['polydash_user']`. Every API call appends `?u=<uuid>`. To use the same watchlist on another device, click **share watchlist** in the header — it copies a URL with your token. Open that URL on the other device once and the token is adopted.

## Data sources

- `https://gamma-api.polymarket.com/markets` — market list, prices, volumes
- `https://gamma-api.polymarket.com/events` — events with grouped sub-markets
- `https://data-api.polymarket.com/trades` — recent trade tape

## Local development

```bash
# clone
git clone git@github.com:juliosuas/polymarket-desk.git
cd polymarket-desk

# spin up Vercel-like dev environment
vercel dev      # auto-installs Python runtime, runs at http://localhost:3000
```

Without Vercel KV configured locally, the `/api/watchlist` endpoints will error and the watchlist tab will be empty — the rest works (trending, value plays, screens, live tape).

You can also exercise the data layer in plain Python:

```bash
python3 -c "import sys; sys.path.insert(0,'api'); import state; print(state.collect()['value_plays'])"
```

## Production deploy

Connected to GitHub via Vercel git integration — every push to `main` triggers a build. To deploy manually:

```bash
vercel deploy --prod
```

### One-time KV provisioning

1. In the Vercel dashboard → Project → Storage → Create → KV (Upstash Redis)
2. Connect it to this project; Vercel injects `KV_REST_API_URL` + `KV_REST_API_TOKEN` env vars automatically.
3. Redeploy.

If env vars are missing, watchlist endpoints return 500 and the dashboard's watchlist tab will be empty (everything else still works).

## Value Plays scoring

```
score = extremity × log10(vol24h/10k) × (1 + |Δ24h|*5)
```

Filter: YES in [5%, 20%] ∪ [80%, 95%], `vol24h ≥ $30k`, end in 3-90d, sports heads-up excluded.

The premise: extreme prices with active flow are where conviction trades typically live. The market is making a strong call — your edge is having a contrarian view backed by analysis. The screen surfaces candidates; the homework is yours.

## Out of scope

- Trading integration (CLOB orders, wallet connect) — explicitly deferred
- Daily snapshots / historical sparklines — not implemented in cloud
- News scraping — removed (was Rocha-specific)
- iMessage alert tracker — removed (was Rocha-specific)

## License

Personal use. Polymarket data is public; don't redistribute commercially. Trading on Polymarket: at your own risk and only where legal in your jurisdiction.
