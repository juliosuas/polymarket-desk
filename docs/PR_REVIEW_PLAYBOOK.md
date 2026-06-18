# Pull Request Review Playbook

This repo should accept pull requests only when they improve the product without weakening the non-custodial boundary, privacy posture, or deployment reliability.

## Review Philosophy

Polymarket Desk is an open-source market cockpit, not an exchange, broker, wallet, custodian, or financial adviser. PRs should make the app clearer, safer, faster, easier to fork, or easier to operate.

Good PRs are small, testable, and user-facing. Prefer narrow improvements over broad rewrites.

## Required Gates

Every PR needs:

- A clear summary of the user impact.
- A clean CodeRabbit review, or a documented CodeRabbit/auth blocker.
- Passing repository checks.
- A reviewer-owned acceptance decision.
- No unresolved critical or major issues.
- No secrets, generated caches, local Vercel state, or private environment files.

Do not merge PRs that add wallet custody, private-key handling, server-side order execution, guaranteed-return language, raw user-token analytics, or hidden referral/builder fees without a separate design and risk review.

## Standard Review Flow

1. Confirm the diff is focused.
2. Read the PR description and check the risk level.
3. Run CodeRabbit on the PR or latest diff.
4. Resolve all critical and major issues.
5. Run local checks.
6. For UI changes, test the relevant user workflow in a browser.
7. For API/data changes, inspect endpoint output shape and add or update tests.
8. For docs/process changes, confirm links, commands, and filenames are accurate.
9. Merge only after CI is green and the acceptance checklist is complete.

## Commands

Baseline local acceptance:

```bash
python3 scripts/pr_acceptance.py
```

Repository checks only:

```bash
python3 scripts/check_repo.py
```

Contract tests only:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Production smoke after a deploy:

```bash
python3 scripts/pr_acceptance.py --production-url https://polymarket-desk-seven.vercel.app
```

CodeRabbit review for recent committed changes:

```bash
coderabbit review --agent -t committed
```

CodeRabbit review against a base commit:

```bash
coderabbit review --agent --base-commit <sha>
```

## Acceptance Criteria By Change Type

### UI / UX

- The app loads without console errors.
- Mobile and desktop layout remain usable.
- Text does not overlap buttons, cards, tables, or drawer content.
- Market cards, tables, drawer, watchlists, alerts, and public desks keep obvious navigation paths.
- Screenshots or smoke-test notes are attached when the visual behavior changes.

### API / Data

- Endpoint output is backward-compatible unless the PR calls out a breaking change.
- Slugs, tokens, and user input are validated.
- Expired or stale markets do not leak into primary screens.
- KV failures degrade gracefully instead of breaking the dashboard.
- Tests cover normalization, contracts, and edge cases.

### Privacy / Analytics

- Do not store raw watchlist tokens, wallet addresses, IPs, private notes, or user-agent timelines.
- Analytics must remain aggregate and privacy-light.
- Public desk links must be read-only unless explicitly marked as edit links.

### Trading / Polymarket Routing

- The app may prepare an order intent or route the user to Polymarket.
- The user must sign on Polymarket or another explicitly trusted venue.
- The app must not store private keys, CLOB API secrets, or submit server-side orders.
- Any builder/referral fee must be transparent in copy and docs.

## Merge Decision

Merge when:

- CI is green.
- CodeRabbit raised 0 unresolved critical/major issues.
- The reviewer can explain the user-visible value.
- Acceptance checks match the PR risk.
- The PR can be reverted cleanly if production behaves unexpectedly.

Do not merge because the diff is small, because it looks visually fine, or because a bot approved it. The human reviewer owns the final decision.
