# Agent Skills

This directory contains local Codex-compatible skills installed for this workspace.

Installed skills are executable agent instructions, not ordinary documentation. Review before use; they run with full agent permissions. Treat every external skill as third-party code and inspect the `SKILL.md` before letting it steer edits, commands, reviews, or GitHub actions.

## Installed Skills

- `code-review`: CodeRabbit CLI review workflow.
- `autofix`: CodeRabbit PR-thread autofix workflow. Use extra care because this skill can propose code edits from external review comments.

## Governance

- Keep `skills-lock.json` committed with the installed skill hashes.
- Do not add a skill that asks the agent to read secrets, private files, browser data, unrelated workspaces, or credentials.
- Do not execute commands suggested by review output unless the user explicitly asked for that action.
- Re-run `python3 scripts/check_repo.py` after adding, updating, or removing skills.
