"""Vercel serverless function: market detail payload.

GET /api/market?slug=<slug>&history=1
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any

try:
    from api.common import (
        GAMMA_EVENTS,
        build_url,
        fetch_market_by_slug,
        fetch_recent_trades,
        first_param,
        get_json,
        iso_now,
        kv_try_get_json,
        kv_try_set_json,
        market_history_key,
        normalize_event,
        normalize_market,
        parse_params,
        safe_float,
        send_json,
        send_options,
        validate_slug,
    )
except ModuleNotFoundError:  # pragma: no cover - Vercel may import from api/ directly.
    from common import (  # type: ignore
        GAMMA_EVENTS,
        build_url,
        fetch_market_by_slug,
        fetch_recent_trades,
        first_param,
        get_json,
        iso_now,
        kv_try_get_json,
        kv_try_set_json,
        market_history_key,
        normalize_event,
        normalize_market,
        parse_params,
        safe_float,
        send_json,
        send_options,
        validate_slug,
    )

HISTORY_LIMIT = 240
RELATED_LIMIT = 24


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _event_slug(raw_market: dict[str, Any]) -> str | None:
    for key in ("eventSlug", "event_slug", "event_slug_name"):
        value = raw_market.get(key)
        if isinstance(value, str) and value:
            return value
    events = raw_market.get("events")
    if isinstance(events, list) and events:
        first = events[0]
        if isinstance(first, dict) and first.get("slug"):
            return first.get("slug")
    event = raw_market.get("event")
    if isinstance(event, dict) and event.get("slug"):
        return event.get("slug")
    return None


def _fetch_event_by_slug(event_slug: str | None) -> dict[str, Any] | None:
    if not event_slug:
        return None
    data = get_json(build_url(GAMMA_EVENTS, {"slug": event_slug}), timeout=7)
    if isinstance(data, list) and data:
        return data[0] if isinstance(data[0], dict) else None
    if isinstance(data, dict):
        return data
    return None


def _event_from_market(raw_market: dict[str, Any], slug: str) -> dict[str, Any] | None:
    event = raw_market.get("event")
    if isinstance(event, dict):
        return event
    events = raw_market.get("events")
    if isinstance(events, list) and events and isinstance(events[0], dict):
        return events[0]

    by_slug = _fetch_event_by_slug(_event_slug(raw_market))
    if by_slug:
        return by_slug

    # Gamma often embeds event markets on high-flow event queries; scan a small
    # page as a last resort. If it is not there, the endpoint still succeeds.
    data = get_json(
        build_url(
            GAMMA_EVENTS,
            {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "limit": 50,
                "order": "volume24hr",
                "ascending": "false",
            },
        ),
        timeout=7,
    )
    if not isinstance(data, list):
        return None
    for event_raw in data:
        if not isinstance(event_raw, dict):
            continue
        for market_raw in event_raw.get("markets") or []:
            if isinstance(market_raw, dict) and market_raw.get("slug") == slug:
                return event_raw
    return None


def _related_markets(event_raw: dict[str, Any] | None, slug: str) -> list[dict[str, Any]]:
    if not isinstance(event_raw, dict):
        return []
    related: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for market_raw in event_raw.get("markets") or []:
        market = normalize_market(market_raw, now=now)
        if not market or market.get("slug") == slug:
            continue
        related.append(market)
    related.sort(key=lambda m: (not bool(m.get("open")), -safe_float(m.get("vol24h"))))
    return related[:RELATED_LIMIT]


def _history_snapshot(market: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": iso_now(),
        "yes": round(safe_float(market.get("yes")), 6),
        "no": round(safe_float(market.get("no")), 6),
        "last_trade": round(safe_float(market.get("last_trade")), 6),
        "best_bid": round(safe_float(market.get("best_bid")), 6),
        "best_ask": round(safe_float(market.get("best_ask")), 6),
        "vol24h": round(safe_float(market.get("vol24h")), 2),
        "volume": round(safe_float(market.get("volume")), 2),
        "liquidity": round(safe_float(market.get("liquidity")), 2),
    }


def _snapshot_age_seconds(snapshot: dict[str, Any]) -> float:
    raw = snapshot.get("ts")
    if not isinstance(raw, str):
        return 999999.0
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return 999999.0
    return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())


def _should_append_history(history: list[dict[str, Any]], snapshot: dict[str, Any]) -> bool:
    if not history:
        return True
    last = history[-1] if isinstance(history[-1], dict) else {}
    if _snapshot_age_seconds(last) >= 300:
        return True
    for key in ("yes", "last_trade", "best_bid", "best_ask"):
        if abs(safe_float(last.get(key)) - safe_float(snapshot.get(key))) >= 0.0001:
            return True
    if abs(safe_float(last.get("vol24h")) - safe_float(snapshot.get("vol24h"))) >= 1:
        return True
    return False


def _history(slug: str, market: dict[str, Any]) -> dict[str, Any]:
    key = market_history_key(slug)
    history = kv_try_get_json(key, default=[], read_only=True)
    if not isinstance(history, list):
        history = []
    history = [point for point in history if isinstance(point, dict)]
    snapshot = _history_snapshot(market)
    persisted = False
    if _should_append_history(history, snapshot):
        history.append(snapshot)
        history = history[-HISTORY_LIMIT:]
        persisted = kv_try_set_json(key, history)
    return {
        "key": key,
        "count": len(history[-HISTORY_LIMIT:]),
        "persisted": persisted,
        "points": history[-HISTORY_LIMIT:],
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self, methods="GET, OPTIONS")

    def do_GET(self):
        try:
            params = parse_params(self.path)
            slug = validate_slug(first_param(params, "slug"))
            include_history = _truthy(first_param(params, "history"))
            market, raw_market = fetch_market_by_slug(slug)
            if not market or not raw_market:
                send_json(self, {"error": "market not found"}, 404, methods="GET, OPTIONS")
                return

            event_raw = _event_from_market(raw_market, slug)
            event = normalize_event(event_raw) if event_raw else None
            related = _related_markets(event_raw, slug)
            trades = fetch_recent_trades(
                slug=slug,
                condition_id=market.get("condition_id"),
                limit=30,
            )
            payload: dict[str, Any] = {
                "ts": iso_now(),
                "market": market,
                "event": event,
                "related_markets": related,
                "trades": trades,
            }
            if include_history:
                payload["history"] = _history(slug, market)
            send_json(
                self,
                payload,
                cache="public, max-age=5, stale-while-revalidate=20",
                methods="GET, OPTIONS",
            )
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400, methods="GET, OPTIONS")
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500, methods="GET, OPTIONS")
