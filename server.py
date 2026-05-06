#!/usr/bin/env python3
"""
Realtime Polymarket dashboard server.

Architecture:
  - Background poller thread refreshes a shared in-memory cache every few seconds.
  - HTTP handlers serve cached state instantly, no upstream wait.
  - SSE endpoint /api/stream pushes the full cache to every connected browser
    on each cache update, so the UI moves in near-real-time.

Polling cadence (cycle = 3s):
  - markets screen + rocha:    every 3s
  - recent trades tape:        every 3s (different upstream)
  - trending events:           every 9s
  - news (Rocha):              every 90s

Endpoints:
  GET  /              -> dashboard.html
  GET  /api/state     -> cached snapshot (JSON)
  GET  /api/stream    -> Server-Sent Events stream
  GET  /api/history   -> daily snapshots from snapshots/
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

import tracker

ROOT = Path(__file__).resolve().parent
SNAP_DIR = ROOT / "snapshots"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

POLL_INTERVAL_S = 3
TRENDING_LIMIT = 20
TRADES_LIMIT = 30
EVENTS_LIMIT = 12
GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
DATA_TRADES = "https://data-api.polymarket.com/trades"


def slog(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}\n"
    with open(LOG_DIR / "server.log", "a") as f:
        f.write(line)


def _http_get_json(url: str, timeout: int = 15):
    req = urllib.request.Request(url, headers={"User-Agent": "rocha-dash/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        slog(f"GET fail {url}: {e}")
        return None


def fetch_trending_events(limit: int = EVENTS_LIMIT) -> list[dict]:
    url = (
        f"{GAMMA_EVENTS}?active=true&closed=false&archived=false"
        f"&limit={limit}&order=volume24hr&ascending=false"
    )
    data = _http_get_json(url) or []
    out = []
    now = datetime.now(timezone.utc)
    for e in data:
        end_raw = e.get("endDate")
        try:
            end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00")) if end_raw else None
            days = (end_dt - now).days if end_dt else None
        except Exception:
            days = None
        # Pull top YES from first market
        top_yes = None
        top_q = None
        markets = e.get("markets") or []
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
            "volume": float(e.get("volume") or 0),
            "liquidity": float(e.get("liquidity") or 0),
            "n_markets": len(markets),
            "days": days,
            "top_yes": top_yes,
            "top_q": top_q,
            "image": e.get("icon") or e.get("image"),
        })
    return out


def fetch_recent_trades(limit: int = TRADES_LIMIT) -> list[dict]:
    url = f"{DATA_TRADES}?limit={limit}"
    data = _http_get_json(url) or []
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


# ---------- shared cache ----------

class Cache:
    def __init__(self):
        self.lock = threading.Lock()
        self.state: dict = {}
        self.subscribers: set[queue.Queue] = set()
        self.running = True

    def snapshot(self) -> dict:
        with self.lock:
            return dict(self.state)

    def update(self, partial: dict) -> None:
        with self.lock:
            self.state.update(partial)
            self.state["ts"] = datetime.now().astimezone().isoformat()
            snap = dict(self.state)
            subs = list(self.subscribers)
        for q in subs:
            try:
                q.put_nowait(snap)
            except queue.Full:
                pass

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=8)
        with self.lock:
            self.subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            self.subscribers.discard(q)


CACHE = Cache()


def poller():
    """Background loop refreshing cache. Different cadences per data source."""
    cycle = 0
    while CACHE.running:
        try:
            # Every cycle: markets screen + rocha + trades
            rows = tracker.fetch_screen()
            rocha = {}
            for cfg in tracker.MARKETS:
                m = tracker.fetch_market(cfg["slug"])
                if m:
                    rocha[cfg["key"]] = {
                        **m,
                        "label": cfg["label"],
                        "fair_yes": cfg["fair_yes"],
                        "key": cfg["key"],
                    }
            trades = fetch_recent_trades()

            CACHE.update({
                "rocha": rocha,
                "trending_markets": rows[:TRENDING_LIMIT],
                "high_conv": tracker.screen_high_conviction(rows),
                "top_movers": tracker.screen_top_movers(rows),
                "top_flow": tracker.screen_top_flow(rows),
                "trades": trades,
            })

            # Every 3 cycles (~9s): events
            if cycle % 3 == 0:
                events = fetch_trending_events()
                CACHE.update({"events": events})

            # Every 30 cycles (~90s): news
            if cycle % 30 == 0:
                news_raw = tracker.fetch_news()
                news = [
                    {"title": n["title"], "source": n["source"], "pub": n["pub"].isoformat()}
                    for n in news_raw
                ]
                CACHE.update({"news": news})

        except Exception as e:
            slog(f"poller cycle {cycle} error: {e}")

        cycle += 1
        time.sleep(POLL_INTERVAL_S)


# ---------- HTTP handlers ----------

class Handler(BaseHTTPRequestHandler):
    def _send_bytes(self, body: bytes, content_type: str, status: int = 200, extra_headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, status: int = 200):
        body = json.dumps(obj, default=str).encode()
        self._send_bytes(body, "application/json; charset=utf-8", status)

    def _send_file(self, path: Path, content_type: str):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return self.send_error(404)
        self._send_bytes(data, content_type)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                return self._send_file(ROOT / "dashboard.html", "text/html; charset=utf-8")
            if path == "/api/state":
                return self._send_json(CACHE.snapshot())
            if path == "/api/history":
                return self._send_json(_collect_history())
            if path == "/api/stream":
                return self._stream_sse()
            self.send_error(404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            slog(f"handler error {path}: {e}")
            try:
                self.send_error(500)
            except Exception:
                pass

    def _stream_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        q = CACHE.subscribe()
        # Push initial snapshot immediately
        try:
            initial = CACHE.snapshot()
            if initial:
                self._sse_send(initial)
            while True:
                try:
                    state = q.get(timeout=15)
                    self._sse_send(state)
                except queue.Empty:
                    # heartbeat to keep proxies/Safari happy
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            CACHE.unsubscribe(q)

    def _sse_send(self, payload: dict):
        msg = f"data: {json.dumps(payload, default=str)}\n\n"
        self.wfile.write(msg.encode())
        self.wfile.flush()

    def log_message(self, *a, **kw):
        return  # silence access log


def _collect_history() -> list[dict]:
    out = []
    for p in sorted(SNAP_DIR.glob("snapshot_*.json")):
        try:
            with open(p) as f:
                data = json.load(f)
            out.append({"date": p.stem.replace("snapshot_", ""), "data": data})
        except Exception:
            pass
    return out


def main():
    port = int(os.environ.get("DASH_PORT", "7878"))
    threading.Thread(target=poller, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    msg = f"[dash] http://127.0.0.1:{port}  (poll {POLL_INTERVAL_S}s, SSE on)"
    print(msg, flush=True)
    slog(msg)
    server.serve_forever()


if __name__ == "__main__":
    main()
