# Contributing

Thanks for helping make Polymarket Desk sharper.

This project aims to stay small, fast, readable, and useful for prediction-market research. The best contributions improve signal, reliability, deployment, or developer experience without adding unnecessary framework weight.

## Good First Contributions

- Improve market screens, filters, labels, and empty/error states.
- Add alert integrations for Discord, Telegram, email, or webhooks.
- Add tests or lightweight checks for API normalization.
- Improve docs for deployment, Vercel KV, or data-source behavior.
- Tighten privacy, security, accessibility, and mobile behavior.

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
- Preserve the read-only product boundary: no wallet connection, custody, or order execution without a separate design and risk discussion.
- Add or update documentation when behavior, setup, or API output changes.
- Include screenshots or short clips for meaningful UI changes.

## Data And Product Notes

Polymarket Desk consumes public Polymarket endpoints and applies heuristic screens. It is a research interface, not financial advice or a trading system. Please avoid copy or features that imply guaranteed returns, investment recommendations, or jurisdiction-specific compliance advice.
