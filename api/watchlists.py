"""Vercel serverless function: named watchlists.

The legacy default list remains `wl:<token>`. Named lists use
`wl:<token>:<id>`, with metadata at `wls:<token>`.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from typing import Any

try:
    from api.common import (
        clean_name,
        first_param,
        iso_now,
        kv_get_json,
        kv_set_json,
        parse_params,
        read_json_body,
        send_json,
        send_options,
        slugify_id,
        validate_slug,
        validate_token,
        validate_watchlist_id,
        watchlist_key,
        watchlists_key,
    )
except ModuleNotFoundError:  # pragma: no cover - Vercel may import from api/ directly.
    from common import (  # type: ignore
        clean_name,
        first_param,
        iso_now,
        kv_get_json,
        kv_set_json,
        parse_params,
        read_json_body,
        send_json,
        send_options,
        slugify_id,
        validate_slug,
        validate_token,
        validate_watchlist_id,
        watchlist_key,
        watchlists_key,
    )

MAX_WATCHLIST = 50
MAX_NAMED_WATCHLISTS = 25


def _clean_slugs(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("slugs must be a list")
    out: list[str] = []
    seen: set[str] = set()
    for raw in value:
        slug = validate_slug(raw if isinstance(raw, str) else None)
        if slug in seen:
            continue
        seen.add(slug)
        out.append(slug)
        if len(out) >= MAX_WATCHLIST:
            break
    return out


def normalize_watchlist_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the public named-watchlist payload shape used by API and tests."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if "name" in payload and clean_name(payload.get("name"), "") == "":
        raise ValueError("watchlist name is required")
    return {
        "name": clean_name(payload.get("name"), "Watchlist"),
        "slugs": _clean_slugs(payload.get("slugs", [])),
    }


_validate_watchlist_payload = normalize_watchlist_payload


def _load_slugs(token: str, wl_id: str | None) -> list[str]:
    data = kv_get_json(watchlist_key(token, wl_id), default=[])
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for slug in data:
        if isinstance(slug, str):
            out.append(slug)
    return out[:MAX_WATCHLIST]


def _save_slugs(token: str, wl_id: str | None, slugs: list[str]) -> None:
    kv_set_json(watchlist_key(token, wl_id), slugs[:MAX_WATCHLIST])


def _load_meta(token: str) -> list[dict[str, Any]]:
    data = kv_get_json(watchlists_key(token), default=[])
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            wl_id = validate_watchlist_id(item.get("id"), allow_default=False)
        except ValueError:
            continue
        if not wl_id or wl_id == "default" or wl_id in seen:
            continue
        seen.add(wl_id)
        out.append(
            {
                "id": wl_id,
                "name": clean_name(item.get("name"), wl_id),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
        )
        if len(out) >= MAX_NAMED_WATCHLISTS:
            break
    return out


def _save_meta(token: str, meta: list[dict[str, Any]]) -> None:
    kv_set_json(watchlists_key(token), meta[:MAX_NAMED_WATCHLISTS])


def _default_entry(token: str) -> dict[str, Any]:
    slugs = _load_slugs(token, None)
    return {
        "id": "default",
        "name": "Default",
        "default": True,
        "count": len(slugs),
        "slugs": slugs,
    }


def _entry(token: str, item: dict[str, Any]) -> dict[str, Any]:
    wl_id = item["id"]
    slugs = _load_slugs(token, wl_id)
    return {
        "id": wl_id,
        "name": item.get("name") or wl_id,
        "default": False,
        "count": len(slugs),
        "slugs": slugs,
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def _find_meta(meta: list[dict[str, Any]], wl_id: str) -> tuple[int, dict[str, Any] | None]:
    for idx, item in enumerate(meta):
        if item.get("id") == wl_id:
            return idx, item
    return -1, None


def _unique_id(meta: list[dict[str, Any]], desired: str, explicit: bool) -> str:
    existing = {"default", *(item.get("id") for item in meta)}
    if desired not in existing:
        return desired
    if explicit:
        raise ValueError("watchlist id already exists")
    base = desired[:56] or "watchlist"
    for idx in range(2, 100):
        candidate = f"{base}-{idx}"
        if candidate not in existing:
            return candidate
    raise ValueError("could not allocate watchlist id")


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self)

    def _token(self) -> str:
        return validate_token(first_param(parse_params(self.path), "u"))

    def do_GET(self):
        try:
            params = parse_params(self.path)
            token = validate_token(first_param(params, "u"))
            wl_id = validate_watchlist_id(first_param(params, "wl"))
            meta = _load_meta(token)
            if wl_id:
                idx, item = _find_meta(meta, wl_id)
                if item:
                    send_json(self, {"watchlist": _entry(token, item)})
                    return
                slugs = _load_slugs(token, wl_id)
                if slugs:
                    send_json(
                        self,
                        {
                            "watchlist": {
                                "id": wl_id,
                                "name": wl_id.replace("-", " ").replace("_", " ").title(),
                                "default": False,
                                "count": len(slugs),
                                "slugs": slugs,
                            }
                        },
                    )
                    return
                send_json(self, {"error": "watchlist not found"}, 404)
                return
            watchlists = [_default_entry(token)] + [_entry(token, item) for item in meta]
            send_json(self, {"watchlists": watchlists, "count": len(watchlists)})
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_POST(self):
        try:
            token = self._token()
            data = read_json_body(self)
            meta = _load_meta(token)
            if len(meta) >= MAX_NAMED_WATCHLISTS:
                send_json(self, {"error": f"watchlist limit reached ({MAX_NAMED_WATCHLISTS})"}, 400)
                return
            normalized = normalize_watchlist_payload(data)
            name = normalized["name"]
            explicit = bool(data.get("id"))
            desired = validate_watchlist_id(str(data.get("id") or slugify_id(name)), allow_default=False)
            if not desired or desired == "default":
                raise ValueError("invalid watchlist id")
            wl_id = _unique_id(meta, desired, explicit)
            slugs = normalized["slugs"]
            now = iso_now()
            item = {"id": wl_id, "name": name, "created_at": now, "updated_at": now}
            meta.append(item)
            _save_slugs(token, wl_id, slugs)
            _save_meta(token, meta)
            send_json(self, {"watchlist": _entry(token, item)}, status=201)
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_PATCH(self):
        try:
            params = parse_params(self.path)
            token = validate_token(first_param(params, "u"))
            data = read_json_body(self)
            wl_id = validate_watchlist_id(first_param(params, "wl") or data.get("id"))
            meta = _load_meta(token)
            if not wl_id:
                if "slugs" in data:
                    _save_slugs(token, None, _clean_slugs(data.get("slugs")))
                send_json(self, {"watchlist": _default_entry(token)})
                return
            idx, item = _find_meta(meta, wl_id)
            if item is None:
                send_json(self, {"error": "watchlist not found"}, 404)
                return
            if "name" in data:
                item["name"] = clean_name(data.get("name"), item.get("name") or wl_id)
            if "slugs" in data:
                _save_slugs(token, wl_id, _clean_slugs(data.get("slugs")))
            item["updated_at"] = iso_now()
            meta[idx] = item
            _save_meta(token, meta)
            send_json(self, {"watchlist": _entry(token, item)})
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_PUT(self):
        self.do_PATCH()

    def do_DELETE(self):
        try:
            params = parse_params(self.path)
            token = validate_token(first_param(params, "u"))
            wl_id = validate_watchlist_id(first_param(params, "wl"))
            if not wl_id:
                send_json(self, {"error": "cannot delete default watchlist"}, 400)
                return
            meta = _load_meta(token)
            new_meta = [item for item in meta if item.get("id") != wl_id]
            if len(new_meta) == len(meta):
                send_json(self, {"error": "watchlist not found"}, 404)
                return
            _save_slugs(token, wl_id, [])
            _save_meta(token, new_meta)
            send_json(self, {"deleted": wl_id, "watchlists": [_default_entry(token)] + [_entry(token, item) for item in new_meta]})
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)
