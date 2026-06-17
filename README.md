<div align="center">

# Polymarket Desk

**The Bloomberg Terminal for prediction-market traders.**

Track Polymarket flow, spot sharp 24h moves, surface extreme consensus bets, and watch the live tape from one fast desk-style interface.

[![Live Demo](https://img.shields.io/badge/live-vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://polymarket-desk-seven.vercel.app)
[![GitHub](https://img.shields.io/badge/github-polymarket--desk-181717?style=for-the-badge&logo=github)](https://github.com/juliosuas/polymarket-desk)
[![Python](https://img.shields.io/badge/python-serverless-3776AB?style=for-the-badge&logo=python&logoColor=white)](#stack)
[![Vercel KV](https://img.shields.io/badge/storage-vercel%20kv-000000?style=for-the-badge&logo=vercel)](#stack)

[Open the app](https://polymarket-desk-seven.vercel.app) · [Why it matters](#why-it-matters) · [Use cases](#use-cases) · [Roadmap](#roadmap)

</div>

![Polymarket Desk product tour](docs/screenshots/product-tour.gif)

## The Pitch

Prediction markets are becoming a real-time layer for news, politics, sports, macro, crypto, AI, and internet culture. Polymarket has the liquidity and the narratives, but the default experience is optimized for browsing markets, not for operating like a trader.

Polymarket Desk turns public market data into an **operator console**:

- See what the market is paying attention to.
- Catch 24h price dislocations before they disappear.
- Watch trade flow print live.
- Save and share a watchlist without creating an account.
- Use the dashboard as a base layer for alerts, analytics, newsletters, bots, or paid tooling.

It is intentionally **read-only**. It does not place orders, connect wallets, custody funds, or require private Polymarket credentials.

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

## What Makes It Different

- **Built for scanning, not browsing**: dense layout, tabbed screens, fast polling, and tape-first market context.
- **No wallet required**: useful to lurkers, researchers, traders, and builders before any transaction.
- **Shareable watchlists**: a simple URL can carry a market list across devices or groups.
- **Hackable architecture**: no heavy frontend framework, simple Python APIs, easy to fork.
- **Clear expansion path**: alerts, analytics, historical data, user accounts, premium filters, and eventually execution tools.

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
- Pull screenshots for posts, threads, and daily discussion.

### For developers

- Fork it as a starter for Polymarket data apps.
- Add Telegram, Discord, email, or webhook alerts.
- Store snapshots for historical charts.
- Build a richer API around market discovery and event tracking.

### For VC / YC-style evaluation

This is not just a dashboard. It is a wedge into prediction-market infrastructure:

- **Market**: prediction markets are becoming a real-time information and trading layer.
- **User pain**: active users need discovery, monitoring, alerts, and context.
- **Initial wedge**: free read-only dashboard with live utility.
- **Expansion**: alerts, accounts, collaboration, historical analytics, premium screens, execution workflows.
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
|-- docs/
|   `-- screenshots/    # README screenshots
|-- public/
|   `-- index.html      # Single-page dashboard
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
- The live demo gives immediate utility without signup.
- The open-source repo gives developers a reason to fork, star, and extend it.
- Each new alert/channel integration creates another distribution surface.

## Local Development

Prerequisites:

- Vercel CLI
- Python 3.11+
- Vercel KV / Upstash Redis for watchlist persistence

Clone and run:

```bash
git clone https://github.com/juliosuas/polymarket-desk.git
cd polymarket-desk
vercel dev
```

The app runs at:

```text
http://localhost:3000
```

Without KV environment variables, market data can still render, but watchlist reads/writes will fail.

## Environment Variables

Production expects Vercel KV variables:

```text
KV_REST_API_URL
KV_REST_API_TOKEN
KV_REST_API_READ_ONLY_TOKEN
```

When Vercel KV is connected through the Vercel dashboard, these are injected automatically.

## Deployment

The project is configured for Vercel.

```bash
vercel deploy --prod
```

Current production URL:

```text
https://polymarket-desk-seven.vercel.app
```

## Roadmap

### Near term

- Add analytics for visitors, sessions, and most-used screens.
- Add saved filters and named watchlists.
- Add Telegram/Discord alerts for price moves and volume spikes.
- Add richer market detail pages with event context.

### Medium term

- Store historical snapshots for charts and momentum curves.
- Add user accounts while keeping the public dashboard read-only.
- Add daily market digest generation.
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
- `.env*.local` and `.vercel/` are ignored and should not be committed.

## Limitations

- No historical database or backfilled chart storage yet.
- No authenticated user accounts yet.
- No analytics tracking is currently installed.
- Watchlists are simple slug arrays capped server-side.
- Market screens are heuristics and should be independently validated.

## Disclaimer

This project is for market monitoring and research. It is not financial advice, not a trading system, and not an endorsement of any market position. Trading prediction markets involves risk and may be restricted by jurisdiction.

## License

Personal project. Polymarket data belongs to its respective providers.
