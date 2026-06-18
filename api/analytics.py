"""Vercel serverless function: privacy-light aggregate analytics.

GET  /api/analytics?u=<token>
POST /api/analytics  body {"event":"state_refresh","surface":"dashboard"}

The POST path records aggregate daily counters only. It does not store user
tokens, IP addresses, user agents, slugs, or per-user timelines.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any

try:
    from api.common import (
        GAMMA_MARKETS,
        alerts_key,
        build_url,
        first_param,
        get_json,
        iso_now,
        kv_get_json,
        kv_set_json,
        kv_try_get_json,
        normalize_market,
        parse_params,
        read_json_body,
        safe_float,
        send_json,
        send_options,
        validate_token,
        watchlist_key,
        watchlists_key,
    )
except ModuleNotFoundError:  # pragma: no cover - Vercel may import from api/ directly.
    from common import (  # type: ignore
        GAMMA_MARKETS,
        alerts_key,
        build_url,
        first_param,
        get_json,
        iso_now,
        kv_get_json,
        kv_set_json,
        kv_try_get_json,
        normalize_market,
        parse_params,
        read_json_body,
        safe_float,
        send_json,
        send_options,
        validate_token,
        watchlist_key,
        watchlists_key,
    )

EVENT_RE = re.compile(r"[^a-z0-9_-]+")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MARKET_SAMPLE = 250


def _analytics_key(day: str) -> str:
    return f"analytics:{day}"


def _clean_label(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    label = EVENT_RE.sub("_", value.strip().lower()).strip("_-")
    return (label or default)[:64]


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _market_aggregate() -> dict[str, Any]:
    data = get_json(
        build_url(
            GAMMA_MARKETS,
            {
                "active": "true",
                "closed": "false",
                "limit": MARKET_SAMPLE,
                "order": "volume24hr",
                "ascending": "false",
            },
        ),
        timeout=7,
    )
    if not isinstance(data, list):
        data = []
    markets = [m for m in (normalize_market(raw) for raw in data) if m]
    open_markets = [
        m
        for m in markets
        if m.get("open") and (m.get("days") is None or safe_float(m.get("days")) >= 0)
    ]
    count = len(open_markets)
    total_vol24h = sum(safe_float(m.get("vol24h")) for m in open_markets)
    total_liquidity = sum(safe_float(m.get("liquidity")) for m in open_markets)
    avg_yes = sum(safe_float(m.get("yes")) for m in open_markets) / count if count else 0
    expiring_soon = sum(
        1
        for m in open_markets
        if isinstance(m.get("days"), int) and 0 <= int(m.get("days")) <= 2
    )
    active_movers = sum(1 for m in open_markets if abs(safe_float(m.get("one_day_change"))) >= 0.05)
    return {
        "sample_size": len(markets),
        "open_markets": count,
        "total_vol24h": round(total_vol24h, 2),
        "total_liquidity": round(total_liquidity, 2),
        "avg_yes": round(avg_yes, 4),
        "expiring_soon": expiring_soon,
        "active_movers": active_movers,
    }


def _personal_aggregate(token: str) -> dict[str, Any]:
    default_slugs = kv_try_get_json(watchlist_key(token), default=[], read_only=True)
    default_count = len(default_slugs) if isinstance(default_slugs, list) else 0
    meta = kv_try_get_json(watchlists_key(token), default=[], read_only=True)
    named_count = len(meta) if isinstance(meta, list) else 0
    named_slugs = 0
    if isinstance(meta, list):
        for item in meta[:25]:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            slugs = kv_try_get_json(watchlist_key(token, str(item.get("id"))), default=[], read_only=True)
            if isinstance(slugs, list):
                named_slugs += len(slugs)
    alerts = kv_try_get_json(alerts_key(token), default=[], read_only=True)
    alert_count = len(alerts) if isinstance(alerts, list) else 0
    return {
        "watchlists": 1 + named_count,
        "watchlist_slugs": default_count + named_slugs,
        "alerts": alert_count,
    }


def _load_day(day: str) -> dict[str, Any]:
    data = kv_get_json(_analytics_key(day), default={})
    return data if isinstance(data, dict) else {}


def _record_event(event: str, surface: str, day: str) -> bool:
    try:
        aggregate = _load_day(day)
        aggregate.setdefault("day", day)
        aggregate.setdefault("events", {})
        aggregate.setdefault("surfaces", {})
        aggregate["events"][event] = int(aggregate["events"].get(event, 0)) + 1
        aggregate["surfaces"][surface] = int(aggregate["surfaces"].get(surface, 0)) + 1
        aggregate["updated_at"] = iso_now()
        kv_set_json(_analytics_key(day), aggregate)
        return True
    except Exception:
        return False


def _day_param(value: str | None) -> str:
    day = value or _today()
    if not DAY_RE.match(day):
        raise ValueError("invalid day")
    return day


def sanitize_event(data: dict[str, Any]) -> dict[str, str]:
    """Return only aggregate labels; drop tokens, IPs, user agents, slugs, and notes."""
    if not isinstance(data, dict):
        data = {}
    props = data.get("props") if isinstance(data.get("props"), dict) else {}
    properties = data.get("properties") if isinstance(data.get("properties"), dict) else {}
    surface_hint = (
        data.get("surface")
        or props.get("surface")
        or properties.get("surface")
        or data.get("path")
        or "dashboard"
    )
    surface = _clean_label(str(surface_hint).split("?")[0].split("#")[0].strip("/") or "dashboard", "dashboard")
    return {
        "event": _clean_label(data.get("event"), "event"),
        "surface": surface,
    }


_sanitize_event = sanitize_event


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self, methods="GET, POST, OPTIONS")

    def do_GET(self):
        try:
            params = parse_params(self.path)
            day = _day_param(first_param(params, "day"))
            payload: dict[str, Any] = {
                "ts": iso_now(),
                "day": day,
                "markets": _market_aggregate(),
                "daily": kv_try_get_json(_analytics_key(day), default={}, read_only=True),
                "privacy": {
                    "stores_user_ids": False,
                    "stores_ips": False,
                    "stores_user_agents": False,
                    "personal_data": "counts only when u is supplied",
                },
            }
            user_token = first_param(params, "u")
            if user_token:
                token = validate_token(user_token)
                payload["personal"] = _personal_aggregate(token)
            send_json(self, payload, cache="public, max-age=10, stale-while-revalidate=30", methods="GET, POST, OPTIONS")
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400, methods="GET, POST, OPTIONS")
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500, methods="GET, POST, OPTIONS")

    def do_POST(self):
        try:
            data = read_json_body(self)
            sanitized = sanitize_event(data)
            event = sanitized["event"]
            surface = sanitized["surface"]
            day = _today()
            recorded = _record_event(event, surface, day)
            send_json(
                self,
                {
                    "ok": True,
                    "recorded": recorded,
                    "day": day,
                    "privacy": {
                        "stored": ["event_count", "surface_count", "day"],
                        "not_stored": ["user_id", "ip", "user_agent", "slug"],
                    },
                },
                status=202,
                methods="GET, POST, OPTIONS",
            )
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400, methods="GET, POST, OPTIONS")
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500, methods="GET, POST, OPTIONS")
