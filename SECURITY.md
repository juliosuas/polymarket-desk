# Security Policy

Polymarket Desk is a read-only market-monitoring app. It does not connect wallets, place trades, custody funds, or require private Polymarket credentials.

## Supported Version

Security fixes are handled on the default branch of this repository.

## Reporting A Vulnerability

Please report sensitive issues through GitHub's private vulnerability reporting or Security Advisories flow for this repository. If that is unavailable, open a public issue with a high-level description only and avoid posting secrets, exploit payloads, private tokens, or data that could affect users.

Useful details include:

- affected endpoint, page, or workflow
- steps to reproduce
- expected and actual behavior
- impact and suggested severity
- whether the issue requires Vercel KV credentials, a watchlist share link, or only public market data

## Watchlist Privacy Model

Watchlist URLs contain bearer-style edit tokens. Anyone with a shared watchlist URL can view and modify that list. Do not put private or sensitive information in market slugs, issue reports, screenshots, or demo links.

## Scope

In scope:

- XSS or injection through market, event, trade, or watchlist data
- token leakage through logs, URLs, repository files, or deployment output
- CORS, cache, or API behavior that exposes watchlist data unexpectedly
- denial-of-service issues in serverless API parsing or upstream fetch handling

Out of scope:

- upstream Polymarket data correctness
- trading losses or market outcomes
- issues caused by leaked Vercel or Upstash credentials outside this repository
