<div align="center">

# Polymarket Desk

**An open-source Polymarket terminal and market intelligence desk.**

Track Polymarket flow, spot sharp 24h moves, surface extreme consensus bets, follow the live tape, and build toward daily briefs, alerts, public desks, and richer market context from one read-only interface.

[![Live Demo](https://img.shields.io/badge/live-vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://polymarket-desk-seven.vercel.app)
[![GitHub](https://img.shields.io/badge/github-polymarket--desk-181717?style=for-the-badge&logo=github)](https://github.com/juliosuas/polymarket-desk)
[![Quality](https://img.shields.io/github/actions/workflow/status/juliosuas/polymarket-desk/quality.yml?branch=main&label=quality&style=for-the-badge&logo=github)](https://github.com/juliosuas/polymarket-desk/actions/workflows/quality.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/python-serverless-3776AB?style=for-the-badge&logo=python&logoColor=white)](#stack)
[![Vercel KV](https://img.shields.io/badge/storage-vercel%20kv-000000?style=for-the-badge&logo=vercel)](#stack)

[Open the app](https://polymarket-desk-seven.vercel.app) · [Features](#features) · [V2 Direction](#v2-direction) · [Quick start](#quick-start) · [API](#api) · [Contribute](CONTRIBUTING.md)

</div>

![Polymarket Desk product tour](docs/screenshots/product-tour.gif)

## What You Get

| Signal | Why it is useful |
| --- | --- |
| 24h market movers | See where pricing changed before the story gets old |
| Top flow | Follow where attention and liquidity are concentrating |
| Consensus screens | Find markets priced near certainty but still unresolved |
| Value plays | Surface extreme-price candidates worth deeper research |
| Live tape | Watch public trades print in real time |
| Shareable watchlists | Track and share a market set without accounts or wallets |
| V2 market desk | Daily brief, market detail, named watchlists, in-app alerts, public desks, and privacy-light analytics |

Polymarket Desk is intentionally **read-only**. It does not place orders, connect wallets, custody funds, or require private Polymarket credentials.

## Why It Exists

Prediction markets are becoming a real-time layer for news, politics, sports, macro, crypto, AI, and internet culture. Polymarket has the liquidity and the narratives, but the default experience is optimized for browsing markets, not for operating like a trader.

Polymarket Desk turns public market data into an **open-source operator console**:

- See what the market is paying attention to.
- Catch 24h price dislocations before they disappear.
- Watch trade flow print live.
- Save and share a watchlist without creating an account.
- Use the dashboard as a base layer for daily briefs, alerts, analytics, newsletters, bots, public desks, or paid tooling.

## Why It Matters

Every active prediction-market user asks the same questions:

- **What is moving right now?**
- **Where is volume concentrating?**
- **What has the crowd priced as nearly certain?**
- **Which markets are mispriced if my view is different?**
- **What are other traders actually doing?**

Polymarket Desk compresses those answers into one screen.

## Who It Is For

| Audience | Why they care |
| --- | --- |
| Prediction-market traders | Faster market scanning, watchlists, live tape, and catalyst detection |
| Reddit / Discord bettors | A clean way to find spicy markets and big moves without scrolling forever |
| Developers | A small, hackable Polymarket data app with serverless APIs and no framework overhead |
| Newsletter writers | A source for daily "top movers", "market heat", and "consensus watch" sections |
| Investors / YC-style reviewers | A wedge into the prediction-market tooling layer: dashboards, alerts, analytics, and trade infrastructure |

## Product Thesis

Prediction markets are still early, but the tooling gap is obvious. Crypto got block explorers, DEX screeners, wallet trackers, alert bots, and trading terminals. Prediction markets will need the same stack.

Polymarket Desk is a small wedge into that stack:

- **Start with read-only intelligence**, because it is safer and broadly useful.
- **Build habits around watchlists and alerts**, because traders come back when the market moves.
- **Layer in data history and collaboration**, because market context compounds.
- **Optionally expand toward execution later**, once risk, compliance, and UX are mature.

## Live Demo

Production is deployed on Vercel:

```text
https://polymarket-desk-seven.vercel.app
```

## Product Surface

| Area | Purpose |
| --- | --- |
| Market Dashboard | Consensus markets, 24h catalysts, watchlist, and summary stats |
| Trending | Top events, top movers, and highest-flow markets |
| Value Plays | Heuristic screen for extreme prices with meaningful recent volume |
| Screens | High-conviction and top-flow filters for fast scanning |
| Live Tape | Recent public trades across Polymarket |
| Watchlist | Shareable per-user market list backed by Vercel KV |

## V2 Direction

V2 grows Polymarket Desk from a fast market scanner into a lightweight market intelligence desk:

| Feature | Product intent |
| --- | --- |
| Daily Brief | A shareable summary of top movers, flow, consensus shifts, and markets worth checking each day |
| Market Detail | One focused view per market with price movement, liquidity, event context, live trades, and watchlist actions |
| Named Watchlists | Human-readable lists for themes like elections, crypto, AI, sports, macro, or a community's favorite markets |
| In-App Alerts | Browser-visible alerts for watchlist moves, volume spikes, consensus changes, and notable tape activity |
| Public Desks | Curated public watchlists that can be linked from posts, newsletters, Discords, and research pages |
| Privacy-Light Analytics | Aggregate usage signals for product decisions without wallets, trading keys, personal profiles, or invasive tracking |

These features should preserve the current boundary: Polymarket Desk is a read-only research terminal, not an execution system.

## Features

- **Built for scanning, not browsing**: dense layout, tabbed screens, fast polling, and tape-first market context.
- **No wallet required**: useful to lurkers, researchers, traders, and builders before any transaction.
- **Shareable watchlists**: a simple URL can carry a market list across devices or groups.
- **Hackable architecture**: no heavy frontend framework, simple Python APIs, easy to fork.
- **Clear expansion path**: daily briefs, market detail, named watchlists, alerts, analytics, public desks, and historical data.

## Screenshots

### Desktop

![Polymarket Desk desktop dashboard](docs/screenshots/dashboard-markets.png)

### Mobile

![Polymarket Desk mobile dashboard](docs/screenshots/dashboard-mobile.png)

## Highlights

- **Fast market triage**: scan top markets, events, movers, and trade flow from one page.
- **Value discovery**: rank markets with extreme implied probabilities and real liquidity.
- **Zero-login watchlists**: browser-generated token, backed by KV, shareable by URL.
- **Serverless data layer**: Python functions aggregate public Polymarket APIs.
- **No build pipeline**: vanilla HTML/CSS/JS frontend, deployable directly on Vercel.
- **Read-only by design**: no trading keys, no wallet connection, no order execution.

## Use Cases

### For prediction-market traders

- Open it before trading to see where attention and liquidity are moving.
- Use `Value Plays` to find extreme consensus markets worth researching.
- Track a personalized watchlist across devices with a share link.
- Watch the live tape to understand what is actively printing.

### For Reddit and Discord communities

- Share a watchlist link around a theme: elections, sports, crypto, AI, geopolitics.
- Use the dashboard as a "what is hot today?" reference.
- Publish public desks for recurring community threads, contest watchlists, or event-specific research.
- Pull screenshots for posts, threads, and daily discussion.

### For developers

- Fork it as a starter for Polymarket data apps.
- Add Telegram, Discord, email, or webhook alerts.
- Store snapshots for historical charts.
- Build public desk directories around specific topics or communities.
- Build a richer API around market discovery and event tracking.

### For builders and investors

This is not just a dashboard. It is a wedge into prediction-market infrastructure:

- **Market**: prediction markets are becoming a real-time information and trading layer.
- **User pain**: active users need discovery, monitoring, alerts, and context.
- **Initial wedge**: free read-only dashboard with live utility.
- **Expansion**: daily briefs, market detail, named watchlists, alerts, public desks, historical analytics, premium screens, execution workflows.
- **Distribution**: Reddit, Discord, crypto Twitter, prediction-market communities, newsletters, and open-source developers.

## Stack

| Layer | Tech |
| --- | --- |
| Frontend | Vanilla HTML, CSS, JavaScript |
| API | Python serverless functions on Vercel |
| Storage | Vercel KV / Upstash Redis |
| Hosting | Vercel |
| Data | Polymarket Gamma API and Data API |

## Architecture

```text
Browser
  |
  | polls /api/state?u=<token>
  v
Vercel Python Functions
  |-- gamma-api.polymarket.com/markets
  |-- gamma-api.polymarket.com/events
  |-- data-api.polymarket.com/trades
  `-- Vercel KV watchlist lookup
  |
  v
Single normalized dashboard payload
```

Repository layout:

```text
.
|-- api/
|   |-- state.py        # Aggregates Polymarket markets, events, trades, and watchlist
|   `-- watchlist.py    # Watchlist CRUD using Vercel KV / Upstash Redis
|-- .github/            # CI, issue templates, and PR template
|-- docs/
|   |-- LAUNCH.md       # Public launch checklist and copy
|   `-- screenshots/    # README screenshots and product tour
|-- public/
|   `-- index.html      # Single-page dashboard
|-- scripts/
|   `-- check_repo.py   # Zero-dependency repository quality checks
|-- .env.example        # Vercel KV environment variable template
|-- vercel.json         # Rewrites, CORS headers, and function limits
`-- README.md
```

## Data Sources

Polymarket Desk uses public unauthenticated endpoints:

- `https://gamma-api.polymarket.com/markets`
- `https://gamma-api.polymarket.com/events`
- `https://data-api.polymarket.com/trades`

The API layer normalizes those upstream responses into a single `/api/state` payload used by the dashboard.

## API

### `GET /api/state`

Returns the combined dashboard state.

Optional query parameter:

- `u`: user token used to resolve the watchlist.

Representative fields:

| Field | Description |
| --- | --- |
| `ts` | API response timestamp |
| `safest` | High-consensus near-term markets |
| `today_movers` | Large 24h price movers with volume |
| `trending_markets` | Top individual markets by 24h volume |
| `events` | Top grouped events by 24h volume |
| `value_plays` | Heuristic extreme-price screen |
| `high_conv` | High-conviction screen |
| `top_flow` | Top liquid markets |
| `trades` | Latest public trade tape |
| `watchlist` | Resolved watchlist markets when `u` is provided |

### `GET /api/watchlist?u=<token>`

Returns saved watchlist slugs for a user token.

### `POST /api/watchlist?u=<token>`

Adds a slug to the watchlist.

```json
{ "slug": "example-market-slug" }
```

### `DELETE /api/watchlist?u=<token>&slug=<slug>`

Removes a slug from the watchlist.

## User Identity Model

There is no login system. On first load, the browser generates a UUID and stores it in:

```text
localStorage["polydash_user"]
```

That token is sent as `?u=<token>` to the API. The share action copies a URL containing the token, which lets another browser or device adopt the same watchlist.

Treat watchlist links as bearer-style edit links. Anyone with the token can view and modify that watchlist.

## Value Plays Scoring

The value screen ranks markets with extreme implied prices, meaningful volume, and a medium-term horizon.

```text
score = extremity * log(liquidity) * (1 + movement)
```

This is a discovery screen, not a trading recommendation. It highlights candidates for deeper independent research.

## Monetization Paths

This repo is currently an open-source personal project, but the product direction is commercially plausible:

- Premium alerts for price moves, volume spikes, and watchlist changes.
- Saved dashboards and private watchlists for serious traders.
- Historical analytics and market backtesting.
- Newsletter or community intelligence product.
- API access for market discovery and event monitoring.
- Pro terminal for prediction-market power users.

## Growth Loops

- Watchlists are shareable by URL.
- Screenshots are naturally postable to Reddit, Discord, and X.
- Public desks turn community themes into reusable links.
- Daily briefs create a repeatable habit and a natural newsletter/social format.
- In-app alerts bring users back when watched markets actually move.
- The live demo gives immediate utility without signup.
- The open-source repo gives developers a reason to fork, star, and extend it.
- Each new alert/channel integration creates another distribution surface.

## Quick Start

Prerequisites:

- Python 3.11+
- Current Vercel CLI for local serverless routing
- `uv` on your PATH for the Vercel Python builder
- Vercel KV / Upstash Redis if you want watchlist persistence

Clone and run:

```bash
git clone https://github.com/juliosuas/polymarket-desk.git
cd polymarket-desk
cp .env.example .env.local
vercel dev
```

If `vercel dev` fails while trying to install `uv` into an externally managed Python, install `uv` directly first, for example with Homebrew:

```bash
brew install uv
```

If your local Vercel CLI asks `uv` for `--python 3.0`, upgrade the CLI and retry:

```bash
npm i -g vercel@latest
```

The app runs at:

```text
http://localhost:3000
```

Without KV environment variables, market data can still render, but watchlist reads/writes will fail.

Run the lightweight repository check:

```bash
python3 scripts/check_repo.py
```

## Local Development Notes

The frontend is a single HTML file with embedded CSS and JavaScript. The API layer is two Vercel Python functions:

- `api/state.py` aggregates market, event, trade, screen, and optional watchlist data.
- `api/watchlist.py` stores and mutates per-token watchlist slugs in Vercel KV / Upstash Redis.

This keeps the project easy to fork: no framework lock-in, no client build step, and no private Polymarket credentials.

## Environment Variables

Production expects Vercel KV variables:

| Variable | Required | Purpose |
| --- | --- | --- |
| `KV_REST_API_URL` | Yes for watchlists | Upstash/Vercel KV REST endpoint |
| `KV_REST_API_TOKEN` | Yes for watchlists | Read/write token for `/api/watchlist` |
| `KV_REST_API_READ_ONLY_TOKEN` | Optional | Read-only token used by `/api/state` when resolving watchlists |

When Vercel KV is connected through the Vercel dashboard, these are injected automatically.
Market data itself uses public Polymarket endpoints and does not require private credentials.

## Deployment

The project is configured for Vercel. Deploy through Vercel Git integration or the CLI:

```bash
vercel deploy --prod
```

The included GitHub Actions deploy-hook workflow is manual (`workflow_dispatch`) so the public repo does not fail CI when a fork has no Vercel secret. If you want to use it, create a Vercel Deploy Hook and save it as `VERCEL_DEPLOY_HOOK_URL`.

Current production URL:

```text
https://polymarket-desk-seven.vercel.app
```

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and keep the product boundary read-only unless a separate risk and compliance design exists.

Good first areas:

- Better market filters and ranking heuristics.
- Alert integrations for Discord, Telegram, email, or webhooks.
- Market detail, named watchlists, public desks, historical snapshots, charts, and daily briefs.
- More tests around API normalization and watchlist behavior.
- Accessibility, mobile polish, and copy improvements.

## Public Launch

Use [docs/LAUNCH.md](docs/LAUNCH.md) before public posts, demo days, or community launches. It includes repository checks, product checks, suggested GitHub topics, and reusable launch copy.

## Roadmap

### Near term

- Add privacy-light analytics for visitors, sessions, most-used screens, and public desk referrals.
- Add named watchlists and public desks.
- Add in-app alerts for price moves, volume spikes, and watchlist changes.
- Add richer market detail pages with event context and recent tape.
- Add daily brief generation for top movers, flow, consensus shifts, and watchlist changes.

### Medium term

- Store historical snapshots for charts and momentum curves.
- Add user accounts while keeping the public dashboard read-only.
- Add custom alert rules and webhook delivery.

### Long term

- Backtesting for market-screen strategies.
- Team/shared desks for research groups.
- Premium data and pro filters.
- Optional execution layer, only after careful wallet, risk, and compliance work.

## Security And Privacy

- No trading execution or wallet connection is implemented.
- No Polymarket API keys are required.
- Watchlist state is keyed by opaque browser tokens.
- Watchlist share links are bearer-style edit links.
- Analytics should stay privacy-light: aggregate page/screen usage, avoid wallet or trading identity, avoid selling behavioral profiles, and disclose tracking clearly.
- Real `.env` files and `.vercel/` are ignored and should not be committed.
- Sensitive vulnerability reports should follow [SECURITY.md](SECURITY.md).

## Limitations

- No historical database or backfilled chart storage yet.
- No authenticated user accounts yet.
- No analytics tracking is currently installed; V2 analytics should be aggregate and transparent.
- Watchlists are simple slug arrays capped server-side.
- Market screens are heuristics and should be independently validated.

## Disclaimer

This project is for market monitoring and research. It is not financial advice, not a trading system, and not an endorsement of any market position. Trading prediction markets involves risk and may be restricted by jurisdiction.

## License

MIT. See [LICENSE](LICENSE).

Polymarket data belongs to its respective providers. This project is independent and is not affiliated with or endorsed by Polymarket.
