#!/usr/bin/env python3
"""PR acceptance checks for Polymarket Desk.

This script intentionally stays zero-dependency so contributors can run it
before opening or approving a pull request.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(cmd: list[str], label: str) -> None:
    print(f"==> {label}")
    result = subprocess.run(cmd, cwd=ROOT, text=True)
    if result.returncode != 0:
        fail(f"{label} failed with exit code {result.returncode}")


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "polymarket-desk-pr-acceptance"})
    try:
        with urlopen(request, timeout=20) as response:
            status = getattr(response, "status", response.getcode())
            if status != 200:
                fail(f"{url} returned HTTP {status}")
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        fail(f"{url} returned HTTP {exc.code}")
    except URLError as exc:
        fail(f"{url} is unreachable: {exc.reason}")
    except json.JSONDecodeError as exc:
        fail(f"{url} did not return valid JSON: {exc}")


def fetch_head(url: str) -> None:
    request = Request(url, method="HEAD", headers={"User-Agent": "polymarket-desk-pr-acceptance"})
    try:
        with urlopen(request, timeout=20) as response:
            status = getattr(response, "status", response.getcode())
            if status != 200:
                fail(f"{url} returned HTTP {status}")
    except HTTPError as exc:
        fail(f"{url} returned HTTP {exc.code}")
    except URLError as exc:
        fail(f"{url} is unreachable: {exc.reason}")


def check_production(base_url: str) -> None:
    base = base_url.rstrip("/")
    print(f"==> Production smoke: {base}")
    fetch_head(base + "/")
    state = fetch_json(base + "/api/state")
    if not isinstance(state.get("trending_markets"), list):
        fail("/api/state is missing trending_markets[]")
    if not isinstance(state.get("events"), list):
        fail("/api/state is missing events[]")
    print(
        "OK: production state contains "
        f"{len(state.get('trending_markets') or [])} markets and "
        f"{len(state.get('events') or [])} events"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PR acceptance checks.")
    parser.add_argument(
        "--production-url",
        help="Optional deployed URL to smoke-test after preview or production deploy.",
    )
    args = parser.parse_args()

    run([sys.executable, "scripts/check_repo.py"], "Repository checks")
    if args.production_url:
        check_production(args.production_url)
    print("OK: PR acceptance checks passed")


if __name__ == "__main__":
    main()
