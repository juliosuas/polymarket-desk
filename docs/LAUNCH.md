# Launch Checklist

Use this when preparing Polymarket Desk for a public push, demo day, community post, or open-source launch.

Position it as an open-source Polymarket terminal and market intelligence desk: useful today as a read-only scanner, with V2 building toward daily briefs, market detail, named watchlists, in-app alerts, public desks, and privacy-light analytics.

## Repository

- README opens with a clear product promise and live demo link.
- Screenshots and product tour are current.
- License, contributing guide, security policy, and code of conduct are present.
- `.env.example` documents every required variable without secrets.
- `python3 scripts/check_repo.py` passes locally.
- GitHub Actions quality workflow is green on `main`.
- Repo topics are set in GitHub: `polymarket`, `prediction-markets`, `trading`, `dashboard`, `vercel`, `python`, `serverless`.

## Product

- Live demo loads market data from `/api/state`.
- Watchlist add/remove works when Vercel KV is configured.
- Empty states are understandable when filters return no markets.
- Mobile layout is readable and screenshots match the current UI.
- Public copy stays read-only and research-oriented.
- V2 copy is clearly framed as product direction unless the feature is already shipped.
- Analytics language is privacy-light: aggregate usage, no wallets, no trading keys, no personal profiles.

## Distribution

- Post the live demo with a short clip or screenshot.
- Share in prediction-market, Polymarket, crypto, data, and builder communities.
- Ask for specific feedback: best screen, missing filter, alert ideas, and data bugs.
- Turn useful feedback into labeled GitHub issues quickly.
- Keep a small changelog thread for visible momentum.
- Seed one or two public desks around timely themes so people have something specific to share.

## Short Pitch

Polymarket Desk is an open-source Polymarket terminal: top markets, 24h movers, consensus screens, live tape, and shareable watchlists in one fast read-only desk.

## Longer Pitch

Prediction markets are becoming a real-time layer for news, politics, sports, crypto, AI, and internet culture. Polymarket has the liquidity, but active users still need better discovery, watchlists, alerts, public context, and daily market intelligence. Polymarket Desk is a small open-source wedge into that tooling layer.

## Launch Copy Snippets

### X

```text
I built Polymarket Desk: an open-source, read-only Polymarket terminal for scanning top markets, 24h movers, consensus bets, live tape, and shareable watchlists.

V2 direction: daily brief, market detail, named watchlists, in-app alerts, public desks, and privacy-light analytics.

Demo: https://polymarket-desk-seven.vercel.app
Repo: https://github.com/juliosuas/polymarket-desk
```

### Reddit

```text
I built an open-source Polymarket desk for market scanning: top flow, 24h movers, consensus screens, live tape, and shareable watchlists. It is read-only: no wallet connection, no order execution, no private Polymarket credentials.

I am especially looking for feedback on which screens are useful, which alerts would matter, and what a daily prediction-market brief should include.

Demo: https://polymarket-desk-seven.vercel.app
Repo: https://github.com/juliosuas/polymarket-desk
```

### Hacker News

```text
Show HN: Polymarket Desk - an open-source terminal for prediction-market intelligence

Polymarket Desk is a read-only Vercel app that aggregates public Polymarket data into a fast market scanner: top markets, 24h movers, consensus screens, live tape, and shareable watchlists.

The repo is intentionally small: vanilla HTML/CSS/JS, Python serverless functions, Vercel KV for watchlists, no wallet connection, and no private Polymarket credentials. The V2 roadmap focuses on daily briefs, market detail pages, named watchlists, in-app alerts, public desks, and privacy-light analytics.
```

### Discord

```text
I shipped Polymarket Desk, a read-only market intelligence desk for Polymarket.

Useful bits:
- top markets and 24h movers
- consensus and high-flow screens
- live public trade tape
- shareable watchlists for themes or groups

V2 is aimed at daily briefs, market detail, named watchlists, in-app alerts, public desks, and privacy-light analytics.

Demo: https://polymarket-desk-seven.vercel.app
Repo: https://github.com/juliosuas/polymarket-desk
```

## Public Desks

Public desks are curated watchlists meant to travel as links. Use them for timely themes such as elections, sports slates, crypto catalysts, AI regulation, macro events, or a community's recurring watchlist.

Good public desk copy should include:

- A clear theme name.
- A short reason the desk exists.
- A watchlist link or screenshot.
- A request for missing markets or better alert ideas.

Examples:

- `Election Desk`: high-volume election markets, key swing-state narratives, and consensus shifts.
- `Crypto Macro Desk`: BTC, ETH, rates, ETF, regulation, and exchange-related markets.
- `AI Policy Desk`: AI regulation, company, model-release, and geopolitics markets.

## Privacy Note For Analytics

If analytics are added, keep the launch copy plain: Polymarket Desk measures aggregate product usage so the project can improve the screens, alerts, and public desks people actually use.

Avoid claims or implementation that depend on wallet identity, trade history, behavioral profiling, ad retargeting, or selling user data. Disclose analytics in the README and app copy before enabling it.
