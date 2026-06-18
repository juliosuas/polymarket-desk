# Launch Checklist

Use this when preparing Polymarket Desk for a public push, demo day, community post, or open-source launch.

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

## Distribution

- Post the live demo with a short clip or screenshot.
- Share in prediction-market, Polymarket, crypto, data, and builder communities.
- Ask for specific feedback: best screen, missing filter, alert ideas, and data bugs.
- Turn useful feedback into labeled GitHub issues quickly.
- Keep a small changelog thread for visible momentum.

## Short Pitch

Polymarket Desk is a read-only terminal for prediction-market traders: top markets, 24h movers, consensus screens, live tape, and shareable watchlists in one fast Vercel app.

## Longer Pitch

Prediction markets are becoming a real-time layer for news, politics, sports, crypto, AI, and internet culture. Polymarket has the liquidity, but active users still need better discovery, watchlists, alerts, and market context. Polymarket Desk is a small open-source wedge into that tooling layer.
