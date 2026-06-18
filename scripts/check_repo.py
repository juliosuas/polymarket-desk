#!/usr/bin/env python3
"""Zero-dependency repository checks for Polymarket Desk."""

from __future__ import annotations

import ast
from html.parser import HTMLParser
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

V2_OPTIONAL_ENDPOINTS = {
    "api/market.py": {
        "endpoint": "/api/market?slug=<market-slug>",
        "methods": ["do_GET"],
        "purpose": "single-market detail and slug validation",
    },
    "api/watchlists.py": {
        "endpoint": "/api/watchlists",
        "methods": ["do_GET", "do_POST"],
        "purpose": "named watchlist schema and CRUD",
    },
    "api/alerts.py": {
        "endpoint": "/api/alerts",
        "methods": ["do_GET", "do_POST"],
        "purpose": "alert rule evaluation, cooldowns, and dedupe",
    },
    "api/analytics.py": {
        "endpoint": "/api/analytics",
        "methods": ["do_POST"],
        "purpose": "analytics event sanitization",
    },
    "api/desk.py": {
        "endpoint": "/api/desk?desk=<id>",
        "methods": ["do_GET", "do_POST"],
        "purpose": "curated public desks and read-only desk snapshots",
    },
}

COMMAND_DOCS = [
    ("All checks", "python3 scripts/check_repo.py"),
    ("Contract tests only", "python3 -m unittest discover -s tests -p 'test_*.py' -v"),
    ("Python syntax only", "python3 -m py_compile api/*.py scripts/*.py tests/*.py"),
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


class InlineScriptExtractor(HTMLParser):
    """Collect executable inline JavaScript blocks from an HTML document."""

    JS_TYPES = {
        "",
        "module",
        "text/javascript",
        "application/javascript",
        "application/ecmascript",
        "text/ecmascript",
    }

    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[tuple[str, str]] = []
        self._capture_type: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "script":
            return
        attr_map = {name.lower(): (value or "") for name, value in attrs}
        if attr_map.get("src"):
            return
        script_type = attr_map.get("type", "").strip().lower()
        if script_type in self.JS_TYPES or script_type.endswith("/javascript"):
            self._capture_type = script_type or "text/javascript"
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_type is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capture_type is not None:
            code = "".join(self._parts).strip()
            if code:
                self.scripts.append((code, self._capture_type))
            self._capture_type = None
            self._parts = []


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
    for directory in ("api", "scripts", "tests"):
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.py")):
            ast.parse(read_text(path), filename=str(path))


def _handler_methods(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "handler":
            return {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return set()


def check_v2_endpoint_files() -> None:
    print("V2 endpoint readiness:")
    vercel = json.loads(read_text(ROOT / "vercel.json"))
    configured_functions = set((vercel.get("functions") or {}).keys())
    for rel_path, spec in V2_OPTIONAL_ENDPOINTS.items():
        path = ROOT / rel_path
        if not path.exists():
            print(f"  SKIP {rel_path}: optional V2 file not present yet ({spec['purpose']})")
            continue
        if not path.is_file():
            fail(f"{rel_path} exists but is not a file")
        ast.parse(read_text(path), filename=str(path))
        methods = _handler_methods(ast.parse(read_text(path), filename=str(path)))
        missing_methods = [method for method in spec["methods"] if method not in methods]
        if missing_methods:
            fail(f"{rel_path} handler is missing methods: {', '.join(missing_methods)}")
        if rel_path not in configured_functions:
            print(f"  WARN {rel_path}: endpoint exists but has no explicit maxDuration in vercel.json")
        print(f"  OK   {rel_path}: {spec['endpoint']}")


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
    extractor = InlineScriptExtractor()
    extractor.feed(html)
    if not extractor.scripts:
        fail("public/index.html does not contain an inline script")
    for index, (script, script_type) in enumerate(extractor.scripts, start=1):
        suffix = ".mjs" if script_type == "module" else ".js"
        with tempfile.NamedTemporaryFile("w", suffix=suffix, encoding="utf-8", delete=False) as tmp:
            tmp.write(script)
            tmp_path = tmp.name
        try:
            result = subprocess.run([node, "--check", tmp_path], text=True, capture_output=True)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        if result.returncode != 0:
            fail(f"inline JavaScript syntax check failed in script #{index}:\n{result.stderr.strip()}")


def check_contract_tests() -> None:
    tests_dir = ROOT / "tests"
    if not tests_dir.is_dir():
        print("SKIP: tests/ not present; no V2 contract tests to run")
        return
    cmd = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(tests_dir),
        "-p",
        "test_*.py",
        "-v",
    ]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if output:
        print(output)
    if result.returncode != 0:
        fail("V2 contract tests failed")


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


def print_command_docs() -> None:
    print("Commands:")
    for label, command in COMMAND_DOCS:
        print(f"  {label}: {command}")


def main() -> None:
    check_required_files()
    check_json()
    check_python_syntax()
    check_html_shape()
    check_v2_endpoint_files()
    check_inline_js_syntax()
    check_contract_tests()
    check_no_obvious_secrets()
    print_command_docs()
    print("OK: repository checks passed")


if __name__ == "__main__":
    main()
