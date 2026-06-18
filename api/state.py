"""Vercel serverless function: combined Polymarket state.

GET /api/state?u=<uuid> -> {
    ts, trending_markets, events, trades,
    high_conv, top_movers, top_flow, value_plays,
    watchlist  # only when ?u=<uuid> is provided
}

Stateless. Each invocation fetches upstream in parallel. Cached at the edge
via Cache-Control header.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

# ---------- Config ----------
GAMMA_MARKETS = "https://gamma-api.polymarket.com/markets"
GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
DATA_TRADES = "https://data-api.polymarket.com/trades"

SCREEN_LIMIT = 250
TRENDING_LIMIT = 25
EVENTS_LIMIT = 12
TRADES_LIMIT = 30

HC_MIN_YES = 0.70
HC_MAX_YES = 0.97
HC_MIN_DAYS = 3
HC_MAX_DAYS = 60
MIN_VOL24 = 20_000

MOVER_MIN_CHG = 0.05
MOVER_MIN_VOL24 = 10_000

VP_LO_MIN = 0.05
VP_LO_MAX = 0.20
VP_HI_MIN = 0.80
VP_HI_MAX = 0.95
VP_MIN_VOL24 = 30_000
VP_MIN_DAYS = 3
VP_MAX_DAYS = 90

# Safest picks (near-cert, ending soon, liquid). Used by APUESTAS landing.
# Bands chosen so there's still meaningful payout per share (1.5pp to 8pp).
# Below 0.015 / above 0.985 the payout is dust and the market is effectively resolved.
SAFEST_YES_LO = 0.92
SAFEST_YES_HI = 0.985
SAFEST_NO_LO = 0.015
SAFEST_NO_HI = 0.08
SAFEST_MIN_VOL24 = 30_000
SAFEST_MIN_DAYS = 1
SAFEST_MAX_DAYS = 30
SAFEST_TOP_N = 6

# Today's movers (catalyst-driven, but stricter than the general top_movers screen).
TODAY_MIN_CHG = 0.08
TODAY_MIN_VOL24 = 50_000
TODAY_RESOLVED_BAND = 0.005   # exclude markets at <=0.5% or >=99.5% (essentially closed)
TODAY_TOP_N = 6

TOP_N = 8

EXCLUDE_PATTERNS = [
    re.compile(r"\bvs\.?\s+\w+", re.IGNORECASE),
    re.compile(r"^[A-Z][a-zA-Z]+:\s"),
]


# ---------- HTTP helpers ----------
def _get_json(url: str, timeout: int = 6, headers: dict | None = None):
    req = urllib.request.Request(
        url, headers={"User-Agent": "polydash/2.0", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _safe_float(value, default: float = 0.0) -> float:
    try:
        number = float(default if value is None else value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


# ---------- Polymarket fetchers ----------
def fetch_market(slug: str) -> dict | None:
    data = _get_json(f"{GAMMA_MARKETS}?slug={slug}")
    if not data or not isinstance(data, list):
        return None
    try:
        m = data[0]
        prices = json.loads(m.get("outcomePrices") or '["0","0"]')
        yes = float(prices[0])
        no = float(prices[1])
        if not (math.isfinite(yes) and math.isfinite(no)):
            return None
    except (IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None
    end_raw = m.get("endDate")
    days = None
    if end_raw:
        try:
            end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            days = (end_dt - datetime.now(timezone.utc)).days
        except ValueError:
            pass
    return {
        "slug": slug,
        "question": m.get("question"),
        "yes": yes,
        "no": no,
        "last_trade": _safe_float(m.get("lastTradePrice")),
        "best_bid": _safe_float(m.get("bestBid")),
        "best_ask": _safe_float(m.get("bestAsk")),
        "one_day_change": _safe_float(m.get("oneDayPriceChange")),
        "volume": _safe_float(m.get("volume")),
        "vol24h": _safe_float(m.get("volume24hr")),
        "liquidity": _safe_float(m.get("liquidity")),
        "end_date": end_raw,
        "days": days,
        "image": m.get("icon") or m.get("image"),
    }


def fetch_screen():
    url = (
        f"{GAMMA_MARKETS}?active=true&closed=false&limit={SCREEN_LIMIT}"
        f"&order=volume24hr&ascending=false"
    )
    data = _get_json(url) or []
    now = datetime.now(timezone.utc)
    out = []
    for m in data:
        try:
            prices = json.loads(m.get("outcomePrices") or '["0","0"]')
            yes = float(prices[0])
            if not math.isfinite(yes):
                continue
        except Exception:
            continue
        end_raw = m.get("endDate")
        if not end_raw:
            continue
        try:
            end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        days = (end_dt - now).days
        out.append({
            "question": (m.get("question") or "").strip(),
            "yes": yes,
            "days": days,
            "vol24h": _safe_float(m.get("volume24hr")),
            "vol_total": _safe_float(m.get("volume")),
            "one_day_change": _safe_float(m.get("oneDayPriceChange")),
            "slug": m.get("slug"),
        })
    return out


def fetch_events():
    url = (
        f"{GAMMA_EVENTS}?active=true&closed=false&archived=false"
        f"&limit={EVENTS_LIMIT}&order=volume24hr&ascending=false"
    )
    data = _get_json(url) or []
    out = []
    now = datetime.now(timezone.utc)
    for e in data:
        end_raw = e.get("endDate")
        try:
            end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00")) if end_raw else None
            days = (end_dt - now).days if end_dt else None
        except Exception:
            days = None
        markets = e.get("markets") or []
        top_yes, top_q, top_slug = None, None, None
        if markets:
            try:
                prices = json.loads(markets[0].get("outcomePrices") or '["0","0"]')
                top_yes = float(prices[0])
                if not math.isfinite(top_yes):
                    top_yes = None
                top_q = markets[0].get("question")
                top_slug = markets[0].get("slug")
            except Exception:
                pass
        out.append({
            "title": (e.get("title") or "").strip(),
            "slug": e.get("slug"),
            "volume24hr": _safe_float(e.get("volume24hr")),
            "n_markets": len(markets),
            "days": days,
            "top_yes": top_yes,
            "top_q": top_q,
            "top_slug": top_slug,
            "image": e.get("icon") or e.get("image"),
        })
    return out


def fetch_trades():
    data = _get_json(f"{DATA_TRADES}?limit={TRADES_LIMIT}") or []
    out = []
    for t in data:
        out.append({
            "title": (t.get("title") or "").strip(),
            "slug": t.get("slug") or t.get("eventSlug"),
            "side": t.get("side"),
            "outcome": t.get("outcome"),
            "size": _safe_float(t.get("size")),
            "price": _safe_float(t.get("price")),
            "ts": int(_safe_float(t.get("timestamp"))),
            "pseudonym": t.get("pseudonym") or t.get("name"),
        })
    return out


# ---------- Watchlist KV (read-only here; CRUD lives in api/watchlist.py) ----------
def _kv_get(key: str):
    base = os.environ.get("KV_REST_API_URL")
    token = os.environ.get("KV_REST_API_READ_ONLY_TOKEN") or os.environ.get("KV_REST_API_TOKEN")
    if not base or not token:
        return None
    raw = _get_json(
        f"{base}/get/{urllib.parse.quote(key)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not raw:
        return None
    val = raw.get("result") if isinstance(raw, dict) else None
    if not val:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


def fetch_watchlist(user_token: str) -> list[dict]:
    if not user_token or not re.match(r"^[a-zA-Z0-9_-]{6,64}$", user_token):
        return []
    slugs = _kv_get(f"wl:{user_token}") or []
    if not isinstance(slugs, list):
        return []
    with cf.ThreadPoolExecutor(max_workers=min(8, max(1, len(slugs)))) as ex:
        results = list(ex.map(fetch_market, slugs))
    return [r for r in results if r is not None]


# ---------- Screens ----------
def screen_high_conv(rows):
    keep = []
    for r in rows:
        if not (HC_MIN_YES <= r["yes"] <= HC_MAX_YES):
            continue
        if not (HC_MIN_DAYS <= r["days"] <= HC_MAX_DAYS):
            continue
        if r["vol24h"] < MIN_VOL24:
            continue
        if any(p.search(r["question"]) for p in EXCLUDE_PATTERNS):
            continue
        keep.append(r)
    keep.sort(key=lambda r: (-r["yes"], -r["vol24h"]))
    return keep[:TOP_N]


def screen_top_flow(rows):
    return sorted(rows, key=lambda r: -r["vol24h"])[:TOP_N]


def screen_top_movers(rows):
    keep = [
        r for r in rows
        if abs(r["one_day_change"]) >= MOVER_MIN_CHG
        and r["vol24h"] >= MOVER_MIN_VOL24
        and r["days"] > 0
        and not any(p.search(r["question"]) for p in EXCLUDE_PATTERNS)
    ]
    keep.sort(key=lambda r: -abs(r["one_day_change"]))
    return keep[:TOP_N]


def _annotate_side(r: dict) -> dict:
    """Annotate a market row with the recommended bet side (YES/NO) and economics.

    A market at YES=97% maps to: side=YES, price=0.97, payout=0.03, risk=0.97
    A market at YES= 3% maps to: side=NO,  price=0.97, payout=0.03, risk=0.97

    'price' is what you pay per share, 'payout' is profit if you win, 'risk' is
    what you lose if you lose. Per-share economics; multiply by share count.
    """
    y = r["yes"]
    if y >= 0.5:
        side, price, payout, risk = "YES", y, 1 - y, y
    else:
        side, price, payout, risk = "NO", 1 - y, y, 1 - y
    return {
        **r,
        "rec_side": side,
        "rec_price": round(price, 4),
        "rec_payout": round(payout, 4),
        "rec_risk": round(risk, 4),
    }


def screen_safest(rows):
    """Markets the consensus is overwhelmingly committed to but not yet resolved.

    Filter:
      - YES in [0.92, 0.985] (BET YES, payout 1.5-8pp) OR
        YES in [0.015, 0.08] (BET NO,  payout 1.5-8pp)
      - liquid (vol24h >= $30k) and ending within 1-30 days
      - excludes sports heads-up
    Sort: most-confident first (highest rec_price), then sooner-resolution.
    """
    keep = []
    for r in rows:
        y = r["yes"]
        side_ok = (SAFEST_YES_LO <= y <= SAFEST_YES_HI) or (SAFEST_NO_LO <= y <= SAFEST_NO_HI)
        if not side_ok:
            continue
        if r["vol24h"] < SAFEST_MIN_VOL24:
            continue
        if not (SAFEST_MIN_DAYS <= r["days"] <= SAFEST_MAX_DAYS):
            continue
        if any(p.search(r["question"]) for p in EXCLUDE_PATTERNS):
            continue
        keep.append(_annotate_side(r))
    keep.sort(key=lambda r: (-r["rec_price"], r["days"]))
    return keep[:SAFEST_TOP_N]


def screen_today(rows):
    """Catalyst-grade movers in the last 24h. Stricter than top_movers; skip resolved."""
    keep = [
        r for r in rows
        if abs(r["one_day_change"]) >= TODAY_MIN_CHG
        and r["vol24h"] >= TODAY_MIN_VOL24
        and r["days"] > 0
        and TODAY_RESOLVED_BAND < r["yes"] < (1 - TODAY_RESOLVED_BAND)
        and not any(p.search(r["question"]) for p in EXCLUDE_PATTERNS)
    ]
    keep.sort(key=lambda r: -abs(r["one_day_change"]))
    return keep[:TODAY_TOP_N]


def screen_value_plays(rows):
    """Surface markets at extreme implied probabilities with active flow.

    Score = extremity * liquidity_weight * (1 + movement_signal)
        extremity = |yes - 0.5| * 2                   in [0, 1]
        liquidity_weight = clip(log10(vol24h / 10k), 0, 2)
        movement_signal = clip(|Δ24h| * 5, 0, 1)

    Reasoning: the market is making a strong call (extreme price). Your edge is
    a contrarian view backed by analysis. This screen surfaces candidates;
    the trader still has to do the homework.
    """
    out = []
    for r in rows:
        y = r["yes"]
        if not (
            (VP_LO_MIN <= y <= VP_LO_MAX)
            or (VP_HI_MIN <= y <= VP_HI_MAX)
        ):
            continue
        if r["vol24h"] < VP_MIN_VOL24:
            continue
        if not (VP_MIN_DAYS <= r["days"] <= VP_MAX_DAYS):
            continue
        if any(p.search(r["question"]) for p in EXCLUDE_PATTERNS):
            continue
        extremity = abs(y - 0.5) * 2
        liq_w = max(0.0, min(2.0, math.log10(r["vol24h"] / 10_000) if r["vol24h"] > 0 else 0))
        mv = max(0.0, min(1.0, abs(r["one_day_change"]) * 5))
        score = extremity * liq_w * (1 + mv)
        out.append({**r, "value_score": round(score, 4)})
    out.sort(key=lambda r: -r["value_score"])
    return out[:TOP_N]


# ---------- Aggregator ----------
def collect(user_token: str | None = None):
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        f_screen = ex.submit(fetch_screen)
        f_events = ex.submit(fetch_events)
        f_trades = ex.submit(fetch_trades)
        f_wl = ex.submit(fetch_watchlist, user_token) if user_token else None

        rows = f_screen.result() or []
        events = f_events.result() or []
        trades = f_trades.result() or []
        watchlist = None
        if f_wl:
            try:
                watchlist = f_wl.result() or []
            except Exception:
                watchlist = []

    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "safest": screen_safest(rows),
        "today_movers": screen_today(rows),
        "trending_markets": rows[:TRENDING_LIMIT],
        "high_conv": screen_high_conv(rows),
        "top_movers": screen_top_movers(rows),
        "top_flow": screen_top_flow(rows),
        "value_plays": screen_value_plays(rows),
        "events": events,
        "trades": trades,
    }
    if watchlist is not None:
        payload["watchlist"] = watchlist
    return payload


# ---------- Vercel handler ----------
class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self):
        try:
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            user_token = (params.get("u") or [None])[0]
            data = collect(user_token=user_token)
            body = json.dumps(data, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            cache = "private, max-age=3" if user_token else "public, max-age=5, stale-while-revalidate=20"
            self.send_header("Cache-Control", cache)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            err = json.dumps({"error": str(e)}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)
