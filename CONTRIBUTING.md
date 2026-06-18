# Contributing

Thanks for helping make Polymarket Desk sharper.

This project aims to stay small, fast, readable, and useful for prediction-market research. The best contributions improve signal, reliability, deployment, or developer experience without adding unnecessary framework weight.

## Good First Contributions

- Improve market screens, filters, labels, and empty/error states.
- Add alert integrations for Discord, Telegram, email, or webhooks.
- Add tests or lightweight checks for API normalization.
- Improve docs for deployment, Vercel KV, or data-source behavior.
- Tighten privacy, security, accessibility, and mobile behavior.

## Contributor Issue Roadmap

When opening roadmap issues, keep each one narrow, user-facing, and labeled with `area:product`, `area:data`, `area:frontend`, `area:docs`, or `good first issue`.

Good V2 starter issues:

- `Daily brief MVP`: summarize top movers, top flow, consensus shifts, and watchlist changes in a shareable section.
- `Market detail page`: add a focused market view with price, liquidity, event context, recent trades, and watchlist actions.
- `Named watchlists`: let users name lists for themes such as elections, crypto, AI, sports, and macro.
- `In-app alerts`: surface browser-visible alerts for watchlist moves, volume spikes, and consensus changes.
- `Public desks`: document and support curated watchlist links for communities, newsletters, and research pages.
- `Privacy-light analytics`: measure aggregate usage for screens, sessions, and referrals with clear disclosure and no wallet identity.

Each issue should include the user problem, proposed behavior, non-goals, and a lightweight acceptance checklist.

## Local Setup

```bash
git clone https://github.com/juliosuas/polymarket-desk.git
cd polymarket-desk
cp .env.example .env.local
vercel dev
```

For local Vercel Python functions, make sure `uv` is available on your PATH. If the Vercel CLI tries to install it into an externally managed Python and fails, install it directly first, for example with `brew install uv`. If the CLI asks `uv` for `--python 3.0`, upgrade to the latest Vercel CLI.

Market data works without private Polymarket credentials. Watchlist persistence requires `KV_REST_API_URL`, `KV_REST_API_TOKEN`, and optionally `KV_REST_API_READ_ONLY_TOKEN`.

Run the repository check before opening a pull request:

```bash
python3 scripts/check_repo.py
```

## Pull Request Guidelines

- Keep changes focused and explain the user-visible impact.
- Do not commit real `.env` files, Vercel project linkage, tokens, or generated caches.
- Preserve the non-custodial product boundary: no wallet connection, custody, private-key handling, or server-side order execution without a separate design and risk discussion.
- Add or update documentation when behavior, setup, or API output changes.
- Include screenshots or short clips for meaningful UI changes.

## Data And Product Notes

Polymarket Desk consumes public Polymarket endpoints and applies heuristic screens. It is a research interface, not financial advice or a trading system. Please avoid copy or features that imply guaranteed returns, investment recommendations, or jurisdiction-specific compliance advice.
