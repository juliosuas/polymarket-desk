#!/usr/bin/env python3
"""Zero-dependency repository checks for Polymarket Desk."""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".env.example",
    "vercel.json",
    "public/index.html",
    "api/state.py",
    "api/watchlist.py",
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yml",
    ".yaml",
}

IGNORED_PARTS = {".git", ".venv", ".vercel", "node_modules", "__pycache__"}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_required_files() -> None:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))


def check_json() -> None:
    for path in ROOT.glob("*.json"):
        json.loads(read_text(path))


def check_python_syntax() -> None:
    for path in sorted((ROOT / "api").glob("*.py")):
        ast.parse(read_text(path), filename=str(path))


def check_html_shape() -> None:
    html = read_text(ROOT / "public/index.html")
    required = [
        "<title>POLYMARKET DESK</title>",
        'id="status-alert"',
        "function render(",
        "startPolling();",
        "</html>",
    ]
    missing = [token for token in required if token not in html]
    if missing:
        fail("public/index.html is missing expected markers: " + ", ".join(missing))


def check_inline_js_syntax() -> None:
    node = shutil.which("node")
    if not node:
        print("WARN: node not found; skipping inline JavaScript syntax check")
        return
    html = read_text(ROOT / "public/index.html")
    scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)
    if not scripts:
        fail("public/index.html does not contain an inline script")
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tmp:
        tmp.write("\n\n".join(scripts))
        tmp_path = tmp.name
    result = subprocess.run([node, "--check", tmp_path], text=True, capture_output=True)
    Path(tmp_path).unlink(missing_ok=True)
    if result.returncode != 0:
        fail("inline JavaScript syntax check failed:\n" + result.stderr.strip())


def check_no_obvious_secrets() -> None:
    for path in ROOT.rglob("*"):
        if IGNORED_PARTS.intersection(path.parts) or not path.is_file():
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in {".env.example", ".gitignore"}:
            continue
        text = read_text(path)
        for pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                fail(f"possible secret in {path.relative_to(ROOT)}: {match.group(0)[:8]}...")


def main() -> None:
    check_required_files()
    check_json()
    check_python_syntax()
    check_html_shape()
    check_inline_js_syntax()
    check_no_obvious_secrets()
    print("OK: repository checks passed")


if __name__ == "__main__":
    main()
