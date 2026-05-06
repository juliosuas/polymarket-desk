"""Vercel serverless function: combined Polymarket state.

GET /api/state -> { rocha, trending_markets, high_conv, top_movers, top_flow,
                    events, trades, news, ts }

Stateless. Each invocation fetches upstream in parallel. Cached at the edge
via Cache-Control header.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler

# ---------- Config ----------
GAMMA_MARKETS = "https://gamma-api.polymarket.com/markets"
GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
DATA_TRADES = "https://data-api.polymarket.com/trades"
GNEWS = "https://news.google.com/rss/search"

NEWS_QUERY = '"Rocha Moya"'
NEWS_LOOKBACK_HOURS = 28
NEWS_MAX_ITEMS = 5
NEWS_TITLE_MAX = 95

SCREEN_LIMIT = 250
TRENDING_LIMIT = 20
EVENTS_LIMIT = 12
TRADES_LIMIT = 30

HC_MIN_YES = 0.70
HC_MAX_YES = 0.97
HC_MIN_DAYS = 3
HC_MAX_DAYS = 60
MIN_VOL24 = 20_000
MOVER_MIN_CHG = 0.05
MOVER_MIN_VOL24 = 10_000
TOP_N = 5

EXCLUDE_PATTERNS = [
    re.compile(r"\bvs\.?\s+\w+"),
    re.compile(r"^[A-Z][a-zA-Z]+:\s"),
]

ROCHA_MARKETS = [
    {"key": "extr_jun30", "label": "Extradited by Jun 30",
     "slug": "sinaloa-gov-ruben-rocha-extradited-to-us-by-june-30",
     "fair_yes": 0.05},
    {"key": "arr_may31", "label": "Arrested by May 31",
     "slug": "sinaloa-gov-ruben-rocha-arrested-by-may-31",
     "fair_yes": 0.07},
    {"key": "out_may31", "label": "Out as Gov by May 31",
     "slug": "ruben-rocha-out-as-governor-of-sinaloa-by-may-31",
     "fair_yes": None},
]


# ---------- HTTP helper ----------
def _get_json(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers={"User-Agent": "polydash-vercel/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def _get_bytes(url: str, timeout: int = 12) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "polydash-vercel/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


# ---------- Fetchers ----------
def fetch_market(slug: str) -> dict | None:
    data = _get_json(f"{GAMMA_MARKETS}?slug={slug}")
    if not data:
        return None
    m = data[0]
    try:
        prices = json.loads(m.get("outcomePrices") or '["0","0"]')
    except Exception:
        return None
    return {
        "slug": slug,
        "question": m.get("question"),
        "yes": float(prices[0]),
        "no": float(prices[1]),
        "last_trade": float(m.get("lastTradePrice") or 0),
        "best_bid": float(m.get("bestBid") or 0),
        "best_ask": float(m.get("bestAsk") or 0),
        "one_day_change": float(m.get("oneDayPriceChange") or 0),
        "volume": float(m.get("volume") or 0),
        "liquidity": float(m.get("liquidity") or 0),
        "end_date": m.get("endDate"),
    }


def fetch_screen():
    url = (f"{GAMMA_MARKETS}?active=true&closed=false&limit={SCREEN_LIMIT}"
           f"&order=volume24hr&ascending=false")
    data = _get_json(url) or []
    now = datetime.now(timezone.utc)
    out = []
    for m in data:
        try:
            prices = json.loads(m.get("outcomePrices") or '["0","0"]')
            yes = float(prices[0])
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
            "vol24h": float(m.get("volume24hr") or 0),
            "vol_total": float(m.get("volume") or 0),
            "one_day_change": float(m.get("oneDayPriceChange") or 0),
            "slug": m.get("slug"),
        })
    return out


def fetch_events():
    url = (f"{GAMMA_EVENTS}?active=true&closed=false&archived=false"
           f"&limit={EVENTS_LIMIT}&order=volume24hr&ascending=false")
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
        top_yes, top_q = None, None
        if markets:
            try:
                prices = json.loads(markets[0].get("outcomePrices") or '["0","0"]')
                top_yes = float(prices[0])
                top_q = markets[0].get("question")
            except Exception:
                pass
        out.append({
            "title": (e.get("title") or "").strip(),
            "slug": e.get("slug"),
            "volume24hr": float(e.get("volume24hr") or 0),
            "n_markets": len(markets),
            "days": days,
            "top_yes": top_yes,
            "top_q": top_q,
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
            "size": float(t.get("size") or 0),
            "price": float(t.get("price") or 0),
            "ts": int(t.get("timestamp") or 0),
            "pseudonym": t.get("pseudonym") or t.get("name"),
        })
    return out


def fetch_news():
    url = f"{GNEWS}?q={urllib.parse.quote(NEWS_QUERY)}&hl=es-419&gl=MX&ceid=MX:es-419"
    raw = _get_bytes(url)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_LOOKBACK_HOURS)
    items = []
    for it in root.iterfind(".//item"):
        title = (it.findtext("title") or "").strip()
        pub_raw = (it.findtext("pubDate") or "").strip()
        src_el = it.find("source")
        src = (src_el.text or "").strip() if src_el is not None else ""
        try:
            pub = parsedate_to_datetime(pub_raw)
        except Exception:
            continue
        if pub < cutoff:
            continue
        clean = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
        if len(clean) > NEWS_TITLE_MAX:
            clean = clean[:NEWS_TITLE_MAX - 1].rstrip() + "…"
        items.append({"title": clean, "source": src, "pub": pub.isoformat()})
    items.sort(key=lambda x: x["pub"], reverse=True)
    return items[:NEWS_MAX_ITEMS]


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
    keep = [r for r in rows if abs(r["one_day_change"]) >= MOVER_MIN_CHG
            and r["vol24h"] >= MOVER_MIN_VOL24 and r["days"] > 0]
    keep.sort(key=lambda r: -abs(r["one_day_change"]))
    return keep[:TOP_N]


# ---------- Aggregator ----------
def collect():
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        f_screen = ex.submit(fetch_screen)
        f_events = ex.submit(fetch_events)
        f_trades = ex.submit(fetch_trades)
        f_news = ex.submit(fetch_news)
        f_rocha = {cfg["key"]: ex.submit(fetch_market, cfg["slug"])
                   for cfg in ROCHA_MARKETS}

        rows = f_screen.result() or []
        events = f_events.result() or []
        trades = f_trades.result() or []
        news = f_news.result() or []
        rocha = {}
        for cfg in ROCHA_MARKETS:
            m = f_rocha[cfg["key"]].result()
            if m:
                rocha[cfg["key"]] = {**m, "label": cfg["label"],
                                      "fair_yes": cfg["fair_yes"], "key": cfg["key"]}

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "rocha": rocha,
        "trending_markets": rows[:TRENDING_LIMIT],
        "high_conv": screen_high_conv(rows),
        "top_movers": screen_top_movers(rows),
        "top_flow": screen_top_flow(rows),
        "events": events,
        "trades": trades,
        "news": news,
    }


# ---------- Vercel handler ----------
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = collect()
            body = json.dumps(data, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=5, stale-while-revalidate=20")
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
