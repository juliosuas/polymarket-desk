"""Vercel serverless function: curated and shared public desks.

GET  /api/desk?desk=<id>         -> public desk payload
POST /api/desk?u=<token>         -> create read-only share snapshot from slugs
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any

try:
    from api.common import (
        GAMMA_MARKETS,
        build_url,
        clean_name,
        fetch_market_by_slug,
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
        validate_slug,
        validate_token,
    )
except ModuleNotFoundError:  # pragma: no cover - Vercel may import from api/ directly.
    from common import (  # type: ignore
        GAMMA_MARKETS,
        build_url,
        clean_name,
        fetch_market_by_slug,
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
        validate_slug,
        validate_token,
    )

DESK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
MAX_PUBLIC_MARKETS = 250
MAX_DESK_MARKETS = 30

DESKS = {
    "top-movers": {
        "name": "Top Movers",
        "description": "Largest active 24h probability moves with real flow.",
        "kind": "movers",
    },
    "crypto": {
        "name": "Crypto",
        "description": "Bitcoin, ETH, Solana, ETFs, and crypto policy markets.",
        "keywords": ("bitcoin", "btc", "ethereum", "eth", "solana", "crypto", "xrp", "doge", "coinbase", "binance", "etf"),
    },
    "macro": {
        "name": "Macro",
        "description": "Rates, inflation, recession, oil, jobs, GDP, and central banks.",
        "keywords": ("fed", "rate", "rates", "cpi", "inflation", "unemployment", "jobs", "gdp", "recession", "oil", "treasury"),
    },
    "sports": {
        "name": "Sports",
        "description": "High-liquidity sports outcomes and futures.",
        "keywords": ("nba", "nfl", "mlb", "nhl", "ufc", "champions", "world cup", "super bowl", "playoffs", "premier league"),
    },
    "ai": {
        "name": "AI",
        "description": "AI labs, chips, regulation, and product-launch markets.",
        "keywords": (" ai ", "artificial intelligence", "openai", "anthropic", "nvidia", "chatgpt", "llm", "gpu"),
    },
    "geopolitics": {
        "name": "Geopolitics",
        "description": "Elections, conflicts, diplomacy, and policy-risk markets.",
        "keywords": ("china", "russia", "ukraine", "iran", "israel", "gaza", "nato", "election", "tariff", "sanction", "ceasefire"),
    },
    "extreme-consensus": {
        "name": "Extreme Consensus",
        "description": "Open markets priced near YES/NO consensus extremes.",
        "kind": "consensus",
    },
}


def _desk_key(desk_id: str) -> str:
    return f"desk:{desk_id}"


def _validate_desk_id(value: str | None) -> str:
    if not value or not DESK_ID_RE.match(value):
        raise ValueError("invalid desk id")
    return value


def _public_markets() -> list[dict[str, Any]]:
    data = get_json(
        build_url(
            GAMMA_MARKETS,
            {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "limit": MAX_PUBLIC_MARKETS,
                "order": "volume24hr",
                "ascending": "false",
            },
        ),
        timeout=8,
    )
    now = datetime.now(timezone.utc)
    markets = [normalize_market(raw, now=now) for raw in data] if isinstance(data, list) else []
    return [
        market
        for market in markets
        if market
        and market.get("open")
        and market.get("slug")
        and (market.get("days") is None or safe_float(market.get("days")) >= 0)
    ]


def _matches_keywords(market: dict[str, Any], keywords: tuple[str, ...]) -> bool:
    text = f" {market.get('question') or ''} {market.get('slug') or ''} ".lower()
    return any(keyword in text for keyword in keywords)


def _curated_desk(desk_id: str) -> dict[str, Any]:
    spec = DESKS.get(desk_id)
    if not spec:
        raise ValueError("unknown public desk")
    markets = _public_markets()
    kind = spec.get("kind")
    if kind == "movers":
        rows = [m for m in markets if abs(safe_float(m.get("one_day_change"))) >= 0.03 and safe_float(m.get("vol24h")) >= 5_000]
        rows.sort(key=lambda m: (-abs(safe_float(m.get("one_day_change"))), -safe_float(m.get("vol24h"))))
    elif kind == "consensus":
        rows = [m for m in markets if safe_float(m.get("yes")) >= 0.92 or safe_float(m.get("yes")) <= 0.08]
        rows.sort(key=lambda m: (-abs(safe_float(m.get("yes")) - 0.5), -safe_float(m.get("vol24h"))))
    else:
        keywords = tuple(spec.get("keywords") or ())
        rows = [m for m in markets if _matches_keywords(m, keywords)]
        rows.sort(key=lambda m: -safe_float(m.get("vol24h")))
    rows = rows[:MAX_DESK_MARKETS]
    return {
        "id": desk_id,
        "desk": desk_id,
        "name": spec["name"],
        "description": spec["description"],
        "curated": True,
        "slugs": [m["slug"] for m in rows if m.get("slug")],
        "watchlist": rows,
        "updated_at": iso_now(),
    }


def _clean_slugs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in value:
        try:
            slug = validate_slug(raw if isinstance(raw, str) else None)
        except ValueError:
            continue
        if slug in seen:
            continue
        seen.add(slug)
        out.append(slug)
        if len(out) >= MAX_DESK_MARKETS:
            break
    return out


def _shared_desk(desk_id: str) -> dict[str, Any] | None:
    data = kv_try_get_json(_desk_key(desk_id), default=None, read_only=True)
    if not isinstance(data, dict):
        return None
    slugs = _clean_slugs(data.get("slugs"))
    markets: list[dict[str, Any]] = []
    for slug in slugs:
        market, _raw = fetch_market_by_slug(slug)
        if market:
            markets.append(market)
    return {
        "id": desk_id,
        "desk": desk_id,
        "name": clean_name(data.get("name"), "Shared Desk"),
        "description": "Read-only shared desk snapshot.",
        "curated": False,
        "slugs": slugs,
        "watchlist": markets,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at") or data.get("created_at"),
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self, methods="GET, POST, OPTIONS")

    def do_GET(self):
        try:
            params = parse_params(self.path)
            desk_id = _validate_desk_id(first_param(params, "desk") or first_param(params, "id"))
            if desk_id in DESKS:
                send_json(self, _curated_desk(desk_id), cache="public, max-age=10, stale-while-revalidate=30", methods="GET, POST, OPTIONS")
                return
            shared = _shared_desk(desk_id)
            if shared:
                send_json(self, shared, cache="public, max-age=10, stale-while-revalidate=30", methods="GET, POST, OPTIONS")
                return
            send_json(self, {"error": "desk not found"}, 404, methods="GET, POST, OPTIONS")
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400, methods="GET, POST, OPTIONS")
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500, methods="GET, POST, OPTIONS")

    def do_POST(self):
        try:
            params = parse_params(self.path)
            validate_token(first_param(params, "u"))
            data = read_json_body(self)
            slugs = _clean_slugs(data.get("slugs"))
            if not slugs:
                send_json(self, {"error": "at least one slug is required"}, 400, methods="GET, POST, OPTIONS")
                return
            desk_id = "share_" + uuid.uuid4().hex[:16]
            now = iso_now()
            payload = {
                "id": desk_id,
                "name": clean_name(data.get("name"), "Shared Desk"),
                "slugs": slugs,
                "created_at": now,
                "updated_at": now,
            }
            kv_set_json(_desk_key(desk_id), payload)
            send_json(self, {"desk": desk_id, **payload}, status=201, methods="GET, POST, OPTIONS")
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400, methods="GET, POST, OPTIONS")
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500, methods="GET, POST, OPTIONS")
