# Polymarket Desk

Polymarket Desk is a real-time market intelligence dashboard for Polymarket. It surfaces high-flow markets, top movers, heuristic value screens, a live trade tape, and a shareable watchlist in a fast terminal-style interface.

The project is intentionally read-only: it does not place orders, connect wallets, or require private Polymarket credentials.

## Live Demo

Production: [https://polymarket-desk-seven.vercel.app](https://polymarket-desk-seven.vercel.app)

## Screenshots

### Desktop

![Polymarket Desk desktop dashboard](docs/screenshots/dashboard-markets.png)

### Mobile

![Polymarket Desk mobile dashboard](docs/screenshots/dashboard-mobile.png)

## Features

- Market dashboard with consensus markets, 24h catalysts, trending events, top movers, and top-flow screens.
- Value Plays screen that ranks extreme-price markets with meaningful recent volume.
- Live trade tape polling the latest public Polymarket trades.
- Shareable watchlist backed by Vercel KV.
- No build step: vanilla HTML, CSS, and JavaScript served by Vercel.
- Python serverless API functions for data aggregation and watchlist persistence.
- Public-data only: no wallet, no trading keys, no private Polymarket authentication.

## Architecture

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

The API layer normalizes these responses into a single `/api/state` payload used by the browser.

## API

### `GET /api/state`

Returns combined dashboard state.

Optional query parameter:

- `u`: user token used to resolve the watchlist.

Representative response fields:

- `ts`: API response timestamp.
- `safest`: high-consensus near-term markets.
- `today_movers`: large 24h price movers with volume.
- `trending_markets`: top individual markets by 24h volume.
- `events`: top grouped events by 24h volume.
- `value_plays`: heuristic extreme-price screen.
- `high_conv`: high-conviction screen.
- `top_flow`: top liquid markets.
- `trades`: latest public trade tape.
- `watchlist`: resolved watchlist markets when `u` is provided.

### `GET /api/watchlist?u=<token>`

Returns the saved watchlist slugs for a user token.

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

That token is sent as `?u=<token>` to the API. The "share watchlist" action copies a URL containing the token, which allows another browser/device to adopt the same watchlist.

Treat watchlist links as editable private links. Anyone with the token can view and modify that watchlist.

## Value Plays Scoring

The value screen ranks markets with extreme implied prices, meaningful volume, and a medium-term horizon.

```text
score = extremity * log(liquidity) * (1 + movement)
```

The screen is a discovery tool, not a trading recommendation. It highlights candidates for further research.

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

The app will run at:

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

Current production URL:

```text
https://polymarket-desk-seven.vercel.app
```

Manual production deploy:

```bash
vercel deploy --prod
```

If the GitHub integration is connected, pushes to `main` trigger production deployments automatically.

## Security And Privacy

- No trading execution or wallet connection is implemented.
- No Polymarket API keys are required.
- Watchlist state is keyed by opaque browser tokens.
- Watchlist share links are bearer-style edit links.
- `.env*.local` and `.vercel/` are ignored and should not be committed.

## Limitations

- No historical database or backfilled chart storage.
- No authenticated user accounts.
- No analytics tracking is currently installed.
- Watchlists are simple slug arrays capped server-side.
- Market screens are heuristics and should be independently validated.

## License

Personal project. Polymarket data belongs to its respective providers. Trading involves risk and may be restricted by jurisdiction.
