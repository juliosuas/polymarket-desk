# Launch Checklist

Use this when preparing Polymarket Desk for a public push, demo day, community post, or open-source launch.

Position it as an open-source Polymarket terminal and probability intelligence desk: useful today as a non-custodial cockpit with optional accounts, market scanning, detail views, Market Pit community votes/chat, named watchlists, in-app alerts, public desks, privacy-light analytics, and order-intent plans that users sign on Polymarket.

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
- Public copy stays non-custodial and research-oriented.
- V2 copy is clearly framed as shipped status versus open roadmap.
- Analytics language is privacy-light: aggregate usage, no wallets, no trading keys, no raw account tokens, and no behavioral resale story.

## Distribution

- Post the live demo with a short clip or screenshot.
- Share in prediction-market, Polymarket, crypto, data, and builder communities.
- Ask for specific feedback: best screen, missing filter, alert ideas, and data bugs.
- Turn useful feedback into labeled GitHub issues quickly.
- Keep a small changelog thread for visible momentum.
- Seed one or two public desks around timely themes so people have something specific to share.

## Short Pitch

Polymarket Desk is an open-source Polymarket terminal: top markets, 24h movers, consensus screens, live money flow, Market Pit chat, optional accounts, watchlists, alerts, public desks, and order-intent plans in one fast non-custodial probability desk.

## Longer Pitch

Prediction markets are becoming a real-time layer for news, politics, sports, crypto, AI, and internet culture. Polymarket has the liquidity, but active users still need better discovery, watchlists, alerts, public context, and daily market intelligence. Polymarket Desk is a small open-source wedge into that tooling layer.

## Launch Copy Snippets

### X

```text
I built Polymarket Desk: an open-source, non-custodial Polymarket terminal for scanning top markets, 24h movers, consensus probabilities, live money flow, Market Pit community takes, optional accounts, watchlists, alerts, public desks, and order-intent plans.

Now live: market detail, per-market votes/chat, optional accounts, named watchlists, in-app alerts, public desks, privacy-light analytics, and a probability ticket that opens Polymarket for user-side signing.

Demo: https://polymarket-desk-seven.vercel.app
Repo: https://github.com/juliosuas/polymarket-desk
```

### Reddit

```text
I built an open-source Polymarket desk for market scanning: top flow, 24h movers, consensus screens, live money flow, per-market votes/chat, optional accounts, shareable watchlists, alerts, public desks, and order-intent plans. It is non-custodial: no wallet connection, no server-side order execution, no private Polymarket credentials.

I am especially looking for feedback on which screens are useful, which alerts would matter, and what a daily prediction-market brief should include.

Demo: https://polymarket-desk-seven.vercel.app
Repo: https://github.com/juliosuas/polymarket-desk
```

### Hacker News

```text
Show HN: Polymarket Desk - an open-source terminal for prediction-market intelligence

Polymarket Desk is a non-custodial Vercel app that aggregates public Polymarket data into a fast probability cockpit: top markets, 24h movers, consensus screens, live money flow, per-market Market Pit chat, optional accounts, shareable watchlists, alerts, public desks, and order-intent plans.

The repo is intentionally small: vanilla HTML/CSS/JS, Python serverless functions, Vercel KV for accounts, watchlists, and alerts, no wallet connection, and no private Polymarket credentials. The open roadmap focuses on daily brief export, historical snapshots, richer alerts, community public desks, and contributor-friendly tests.
```

### Discord

```text
I shipped Polymarket Desk, a non-custodial market intelligence desk for Polymarket.

Useful bits:
- top markets and 24h movers
- consensus and high-flow screens
- live public trade tape
- Market Pit votes and anonymous market chat
- shareable watchlists for themes or groups
- alerts, public desks, and order-intent plans

Open-source contributors wanted: public desk curation, alert delivery, mobile polish, tests, historical charts, and daily brief export.

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
