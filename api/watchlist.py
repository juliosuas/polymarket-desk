"""Vercel serverless function: per-user Polymarket watchlist (Vercel KV).

  GET    /api/watchlist?u=<uuid>[&wl=<id>]            -> {slugs: [...]}
  POST   /api/watchlist?u=<uuid>[&wl=<id>]            body {slug:"..."}     -> add
  DELETE /api/watchlist?u=<uuid>[&wl=<id>]&slug=<s>                         -> remove

Identity: opaque token sent by browser (UUID v4 stored in localStorage).
KV key layout:
    `wl:<token>`      -> default legacy JSON-encoded list of slugs
    `wl:<token>:<id>` -> named watchlist JSON-encoded list of slugs

Required env (auto-injected when KV is connected to the project):
    KV_REST_API_URL
    KV_REST_API_TOKEN
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

MAX_WATCHLIST = 50
TOKEN_RE = re.compile(r"^[a-zA-Z0-9_-]{6,64}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,200}$")
WATCHLIST_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _kv_call(method: str, path: str, body: bytes | None = None):
    base = os.environ.get("KV_REST_API_URL")
    token = os.environ.get("KV_REST_API_TOKEN")
    if not base or not token:
        raise RuntimeError("KV_REST_API_URL/TOKEN not configured on this deployment")
    req = urllib.request.Request(
        f"{base}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "polydash/2.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", "replace")
        except Exception:
            err_body = ""
        raise RuntimeError(f"KV {method} {path} failed: {e.code} {err_body[:200]}")


def kv_get_list(key: str) -> list[str]:
    res = _kv_call("GET", f"/get/{urllib.parse.quote(key)}")
    if not res:
        return []
    val = res.get("result") if isinstance(res, dict) else None
    if not val:
        return []
    try:
        parsed = json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []
    return [s for s in parsed if isinstance(s, str)] if isinstance(parsed, list) else []


def kv_set_list(key: str, value: list[str]) -> None:
    payload = json.dumps(value).encode("utf-8")
    _kv_call("POST", f"/set/{urllib.parse.quote(key)}", body=payload)


def _validate_token(token: str | None) -> str:
    if not token or not TOKEN_RE.match(token):
        raise ValueError("invalid token")
    return token


def _validate_slug(slug: str | None) -> str:
    if not slug or not SLUG_RE.match(slug):
        raise ValueError("invalid slug")
    return slug


def _validate_watchlist_id(wl_id: str | None) -> str | None:
    if wl_id in (None, "", "default", "legacy"):
        return None
    if not WATCHLIST_ID_RE.match(wl_id):
        raise ValueError("invalid watchlist id")
    return wl_id


def _watchlist_key(token: str, wl_id: str | None = None) -> str:
    return f"wl:{token}" if not wl_id else f"wl:{token}:{wl_id}"


# ---------- Vercel handler ----------
class handler(BaseHTTPRequestHandler):
    def _send(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _params(self):
        qs = urllib.parse.urlparse(self.path).query
        return urllib.parse.parse_qs(qs)

    def do_OPTIONS(self):
        self._send({"ok": True})

    def do_GET(self):
        try:
            params = self._params()
            token = _validate_token((params.get("u") or [None])[0])
            wl_id = _validate_watchlist_id((params.get("wl") or [None])[0])
            slugs = kv_get_list(_watchlist_key(token, wl_id))
            self._send({"slugs": slugs, "wl": wl_id or "default"})
        except ValueError as e:
            self._send({"error": str(e)}, 400)
        except Exception as e:
            self._send({"error": str(e)}, 500)

    def do_POST(self):
        try:
            params = self._params()
            token = _validate_token((params.get("u") or [None])[0])
            wl_id = _validate_watchlist_id((params.get("wl") or [None])[0])
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._send({"error": "invalid JSON body"}, 400)
                return
            slug = _validate_slug((data or {}).get("slug"))
            existing = kv_get_list(_watchlist_key(token, wl_id))
            if slug not in existing:
                if len(existing) >= MAX_WATCHLIST:
                    self._send({"error": f"watchlist full ({MAX_WATCHLIST} max)"}, 400)
                    return
                existing.append(slug)
                kv_set_list(_watchlist_key(token, wl_id), existing)
            self._send({"slugs": existing, "wl": wl_id or "default"})
        except ValueError as e:
            self._send({"error": str(e)}, 400)
        except Exception as e:
            self._send({"error": str(e)}, 500)

    def do_DELETE(self):
        try:
            params = self._params()
            token = _validate_token((params.get("u") or [None])[0])
            wl_id = _validate_watchlist_id((params.get("wl") or [None])[0])
            slug = _validate_slug((params.get("slug") or [None])[0])
            existing = kv_get_list(_watchlist_key(token, wl_id))
            new = [s for s in existing if s != slug]
            if new != existing:
                kv_set_list(_watchlist_key(token, wl_id), new)
            self._send({"slugs": new, "wl": wl_id or "default"})
        except ValueError as e:
            self._send({"error": str(e)}, 400)
        except Exception as e:
            self._send({"error": str(e)}, 500)
