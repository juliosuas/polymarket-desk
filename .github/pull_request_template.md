## Summary

What changed and why?

- 

## User impact

Who benefits, and what workflow gets better?

- 

## Risk

- [ ] Low-risk docs/tests/process-only change
- [ ] UI change with screenshots or smoke-test notes
- [ ] API/data change with contract-test coverage
- [ ] Production behavior change with rollback notes

## Review gates

- [ ] CodeRabbit reviewed the PR, or a CodeRabbit/auth blocker is documented in the PR.
- [ ] No critical or major review issues remain unresolved.
- [ ] The change stays non-custodial: no wallet custody, private-key handling, server-side order execution, or guaranteed-return language.
- [ ] No secrets, `.env` files, Vercel linkage, tokens, or generated caches are committed.

## Verification

- [ ] `python3 scripts/check_repo.py`
- [ ] `python3 scripts/pr_acceptance.py`
- [ ] UI checked locally or in preview when frontend behavior changed
- [ ] Production smoke checked after deploy when this changes user-facing behavior: `/` and `/api/state`
- [ ] Docs updated when setup, API output, product behavior, or review process changed

## Screenshots / notes

Add screenshots, a short clip, or exact reproduction notes for UI changes.
