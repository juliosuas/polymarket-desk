"""Shared helpers for Polymarket Desk serverless API functions."""
from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any

GAMMA_MARKETS = "https://gamma-api.polymarket.com/markets"
GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
DATA_TRADES = "https://data-api.polymarket.com/trades"

TOKEN_RE = re.compile(r"^[a-zA-Z0-9_-]{6,64}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,200}$")
WATCHLIST_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
SAFE_ID_RE = re.compile(r"[^a-z0-9_-]+")


class KVError(RuntimeError):
    """Raised when Vercel KV/Upstash REST access fails."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_params(path: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(path).query)


def first_param(params: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    return (params.get(key) or [default])[0]


def read_json_body(handler: BaseHTTPRequestHandler, max_bytes: int = 64_000) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length > max_bytes:
        raise ValueError("request body too large")
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON body") from exc
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def send_json(
    handler: BaseHTTPRequestHandler,
    obj: Any,
    status: int = 200,
    cache: str = "no-store",
    methods: str = "GET, POST, PUT, PATCH, DELETE, OPTIONS",
) -> None:
    body = json.dumps(obj, default=str, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", cache)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", methods)
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_options(handler: BaseHTTPRequestHandler, methods: str = "GET, POST, PUT, PATCH, DELETE, OPTIONS") -> None:
    handler.send_response(204)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", methods)
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()


def build_url(base: str, params: dict[str, Any]) -> str:
    clean: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        clean[key] = value
    return f"{base}?{urllib.parse.urlencode(clean, doseq=True)}"


def get_json(url: str, timeout: int = 6, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "polydash/2.0", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ):
        return None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(default if value is None else value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_json_field(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def days_until(value: Any, now: datetime | None = None) -> int | None:
    end_dt = parse_datetime(value)
    if not end_dt:
        return None
    return (end_dt - (now or utc_now())).days


def validate_token(token: str | None) -> str:
    if not token or not TOKEN_RE.match(token):
        raise ValueError("invalid token")
    return token


def validate_slug(slug: str | None) -> str:
    if not slug or not SLUG_RE.match(slug):
        raise ValueError("invalid slug")
    return slug


def validate_watchlist_id(wl_id: str | None, allow_default: bool = True) -> str | None:
    if wl_id in (None, "", "default", "legacy"):
        return None if allow_default else "default"
    if not WATCHLIST_ID_RE.match(wl_id):
        raise ValueError("invalid watchlist id")
    return wl_id


def watchlist_key(token: str, wl_id: str | None = None) -> str:
    return f"wl:{token}" if not wl_id else f"wl:{token}:{wl_id}"


def watchlists_key(token: str) -> str:
    return f"wls:{token}"


def alerts_key(token: str) -> str:
    return f"alerts:{token}"


def market_history_key(slug: str) -> str:
    return f"hist:{slug}"


def slugify_id(value: str, fallback: str = "watchlist") -> str:
    compact = SAFE_ID_RE.sub("-", (value or "").strip().lower()).strip("-_")
    return compact[:48] or fallback


def clean_name(value: Any, default: str = "Watchlist") -> str:
    if not isinstance(value, str):
        return default
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned[:80] or default


def _kv_token(read_only: bool = False) -> tuple[str, str]:
    base = os.environ.get("KV_REST_API_URL")
    token = None
    if read_only:
        token = os.environ.get("KV_REST_API_READ_ONLY_TOKEN")
    token = token or os.environ.get("KV_REST_API_TOKEN")
    if not base or not token:
        raise KVError("KV_REST_API_URL/TOKEN not configured on this deployment")
    return base.rstrip("/"), token


def kv_call(method: str, path: str, body: bytes | None = None, read_only: bool = False) -> Any:
    base, token = _kv_token(read_only=read_only)
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
        with urllib.request.urlopen(req, timeout=6) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", "replace")
        except Exception:
            err_body = ""
        raise KVError(f"KV {method} {path} failed: {exc.code} {err_body[:200]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise KVError(f"KV {method} {path} failed: {exc}") from exc


def kv_get_json(key: str, default: Any = None, read_only: bool = False) -> Any:
    res = kv_call("GET", f"/get/{urllib.parse.quote(key, safe='')}", read_only=read_only)
    val = res.get("result") if isinstance(res, dict) else None
    if val in (None, ""):
        return default
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return default
    return default


def kv_set_json(key: str, value: Any) -> None:
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
    kv_call("POST", f"/set/{urllib.parse.quote(key, safe='')}", body=payload)


def kv_try_get_json(key: str, default: Any = None, read_only: bool = False) -> Any:
    try:
        return kv_get_json(key, default=default, read_only=read_only)
    except KVError:
        return default


def kv_try_set_json(key: str, value: Any) -> bool:
    try:
        kv_set_json(key, value)
        return True
    except KVError:
        return False


def normalize_market(raw: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    prices = parse_json_field(raw.get("outcomePrices"), [])
    yes = safe_float(prices[0], default=float("nan")) if len(prices) > 0 else float("nan")
    no = safe_float(prices[1], default=float("nan")) if len(prices) > 1 else 1 - yes
    if not math.isfinite(yes):
        last_trade = safe_float(raw.get("lastTradePrice"), default=float("nan"))
        yes = last_trade if math.isfinite(last_trade) else float("nan")
    if not math.isfinite(yes):
        return None
    if not math.isfinite(no):
        no = max(0.0, min(1.0, 1 - yes))
    now_dt = now or utc_now()
    end_raw = raw.get("endDate")
    end_dt = parse_datetime(end_raw)
    days = (end_dt - now_dt).days if end_dt else None
    closed = bool(raw.get("closed"))
    active = raw.get("active")
    archived = bool(raw.get("archived"))
    is_expired = bool(end_dt and end_dt < now_dt)
    is_open = active is not False and not closed and not archived and not is_expired
    return {
        "id": raw.get("id"),
        "condition_id": raw.get("conditionId") or raw.get("condition_id"),
        "question": (raw.get("question") or raw.get("title") or "").strip(),
        "slug": raw.get("slug"),
        "yes": yes,
        "no": no,
        "last_trade": safe_float(raw.get("lastTradePrice")),
        "best_bid": safe_float(raw.get("bestBid")),
        "best_ask": safe_float(raw.get("bestAsk")),
        "one_day_change": safe_float(raw.get("oneDayPriceChange")),
        "volume": safe_float(raw.get("volume")),
        "vol24h": safe_float(raw.get("volume24hr")),
        "liquidity": safe_float(raw.get("liquidity")),
        "end_date": end_raw,
        "days": days,
        "image": raw.get("icon") or raw.get("image"),
        "event_slug": raw.get("eventSlug") or raw.get("event_slug"),
        "outcomes": parse_json_field(raw.get("outcomes"), []),
        "active": active,
        "closed": closed,
        "archived": archived,
        "open": is_open,
    }


def normalize_event(raw: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    markets = raw.get("markets") or []
    now_dt = now or utc_now()
    end_raw = raw.get("endDate")
    days = days_until(end_raw, now=now_dt)
    top_yes = None
    top_q = None
    top_slug = None
    if markets:
        top_market = normalize_market(markets[0], now=now_dt)
        if top_market:
            top_yes = top_market.get("yes")
            top_q = top_market.get("question")
            top_slug = top_market.get("slug")
    return {
        "id": raw.get("id"),
        "title": (raw.get("title") or raw.get("ticker") or "").strip(),
        "slug": raw.get("slug"),
        "volume24hr": safe_float(raw.get("volume24hr")),
        "volume": safe_float(raw.get("volume")),
        "liquidity": safe_float(raw.get("liquidity")),
        "n_markets": len(markets),
        "days": days,
        "top_yes": top_yes,
        "top_q": top_q,
        "top_slug": top_slug,
        "image": raw.get("icon") or raw.get("image"),
    }


def normalize_trade(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        "title": (raw.get("title") or "").strip(),
        "slug": raw.get("slug") or raw.get("eventSlug"),
        "side": raw.get("side"),
        "outcome": raw.get("outcome"),
        "size": safe_float(raw.get("size")),
        "price": safe_float(raw.get("price")),
        "ts": safe_int(raw.get("timestamp")),
        "pseudonym": raw.get("pseudonym") or raw.get("name"),
        "transaction_hash": raw.get("transactionHash"),
    }


def fetch_market_by_slug(slug: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    data = get_json(build_url(GAMMA_MARKETS, {"slug": slug}), timeout=7)
    if not data or not isinstance(data, list):
        return None, None
    raw = data[0] if data else None
    return normalize_market(raw), raw


def fetch_recent_trades(slug: str | None = None, condition_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
    limit = max(1, min(100, int(limit or 30)))
    attempts: list[str] = []
    if condition_id:
        attempts.append(build_url(DATA_TRADES, {"limit": limit, "market": condition_id}))
    if slug:
        attempts.append(build_url(DATA_TRADES, {"limit": limit, "slug": slug}))
    attempts.append(build_url(DATA_TRADES, {"limit": min(250, max(limit * 4, 60))}))

    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for url in attempts:
        data = get_json(url, timeout=7) or []
        if not isinstance(data, list):
            continue
        for raw in data:
            trade = normalize_trade(raw)
            if not trade:
                continue
            if slug and trade.get("slug") and trade.get("slug") != slug:
                continue
            key = (
                trade.get("transaction_hash"),
                trade.get("slug"),
                trade.get("ts"),
                trade.get("price"),
                trade.get("size"),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(trade)
            if len(out) >= limit:
                return out
    return out[:limit]
