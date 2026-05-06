#!/usr/bin/env python3
"""
MEX-POL-ROCHA-EXTR daily tracker.

- Fetches Polymarket Gamma API for 3 contracts on Rocha Moya.
- Diffs against previous snapshot to compute 24h change.
- Builds a structured iMessage and sends it via osascript.
- Logs everything to logs/.

Designed to be run via cron once a day. See README.md.

Phone number is taken from env var ROCHA_PHONE (international format,
e.g. +52155...). If unset, the script logs and exits 0 — no message sent.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
SNAPSHOT_DIR = ROOT / "snapshots"
LOG_DIR.mkdir(exist_ok=True)
SNAPSHOT_DIR.mkdir(exist_ok=True)

GAMMA = "https://gamma-api.polymarket.com/markets"

NEWS_QUERY = '"Rocha Moya"'  # Google News query
NEWS_LOOKBACK_HOURS = 28  # generous to cover overnight news + tz drift
NEWS_MAX_ITEMS = 5
NEWS_MAX_TITLE_LEN = 95

# Polymarket daily screen — broader than the Rocha contracts.
SCREEN_FETCH_LIMIT = 300       # markets to pull per scan
SCREEN_HIGH_CONV_MIN_YES = 0.70
SCREEN_HIGH_CONV_MAX_YES = 0.97  # exclude effectively-resolved
SCREEN_HIGH_CONV_MIN_DAYS = 3
SCREEN_HIGH_CONV_MAX_DAYS = 60
SCREEN_MIN_VOL24 = 20_000      # liquidity floor
SCREEN_MOVER_MIN_ABS_CHG = 0.05  # 5pp+ move qualifies
SCREEN_MOVER_MIN_VOL24 = 10_000
SCREEN_TOP_N = 4               # items per section
# Skip noisy single-event tennis/sports markets in high-conviction list.
SCREEN_HIGH_CONV_EXCLUDE_PATTERNS = [
    r"\bvs\.?\s+\w+",            # "X vs Y" style heads-up matchups
    r"^[A-Z][a-zA-Z]+:\s",        # tournament prefix like "Jiujiang: ..."
]

MARKETS = [
    {
        "key": "extr_jun30",
        "label": "Extradited by Jun 30",
        "slug": "sinaloa-gov-ruben-rocha-extradited-to-us-by-june-30",
        "fair_yes": 0.05,  # our analyst desk fair value
    },
    {
        "key": "arr_may31",
        "label": "Arrested by May 31",
        "slug": "sinaloa-gov-ruben-rocha-arrested-by-may-31",
        "fair_yes": 0.07,
    },
    {
        "key": "out_may31",
        "label": "Out as Gov by May 31",
        "slug": "ruben-rocha-out-as-governor-of-sinaloa-by-may-31",
        "fair_yes": None,  # ambiguous resolution; track but no fair value
    },
]


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_DIR / "tracker.log", "a") as f:
        f.write(line + "\n")


def fetch_market(slug: str) -> dict | None:
    url = f"{GAMMA}?slug={slug}"
    req = urllib.request.Request(url, headers={"User-Agent": "rocha-tracker/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        log(f"FETCH FAIL {slug}: {e}")
        return None
    if not data:
        log(f"FETCH EMPTY {slug}")
        return None
    m = data[0]
    prices = json.loads(m.get("outcomePrices", "[\"0\",\"0\"]"))
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


def fetch_screen() -> list[dict]:
    """Pull a broad slice of active Polymarket markets sorted by 24h volume."""
    url = (
        f"{GAMMA}?active=true&closed=false"
        f"&limit={SCREEN_FETCH_LIMIT}&order=volume24hr&ascending=false"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "rocha-tracker/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        log(f"SCREEN fetch fail: {e}")
        return []
    out: list[dict] = []
    now = datetime.now(timezone.utc)
    for m in data:
        try:
            prices = json.loads(m.get("outcomePrices") or '["0","0"]')
            yes = float(prices[0])
        except (TypeError, ValueError, json.JSONDecodeError):
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


def screen_high_conviction(rows: list[dict]) -> list[dict]:
    excl = [re.compile(p) for p in SCREEN_HIGH_CONV_EXCLUDE_PATTERNS]
    keep = []
    for r in rows:
        if not (SCREEN_HIGH_CONV_MIN_YES <= r["yes"] <= SCREEN_HIGH_CONV_MAX_YES):
            continue
        if not (SCREEN_HIGH_CONV_MIN_DAYS <= r["days"] <= SCREEN_HIGH_CONV_MAX_DAYS):
            continue
        if r["vol24h"] < SCREEN_MIN_VOL24:
            continue
        if any(p.search(r["question"]) for p in excl):
            continue
        keep.append(r)
    keep.sort(key=lambda r: (-r["yes"], -r["vol24h"]))
    return keep[:SCREEN_TOP_N]


def screen_top_flow(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: -r["vol24h"])[:SCREEN_TOP_N]


def screen_top_movers(rows: list[dict]) -> list[dict]:
    keep = [
        r for r in rows
        if abs(r["one_day_change"]) >= SCREEN_MOVER_MIN_ABS_CHG
        and r["vol24h"] >= SCREEN_MOVER_MIN_VOL24
        and r["days"] > 0
    ]
    keep.sort(key=lambda r: -abs(r["one_day_change"]))
    return keep[:SCREEN_TOP_N]


def fmt_short_q(q: str, n: int = 70) -> str:
    if len(q) <= n:
        return q
    return q[: n - 1].rstrip() + "…"


def fmt_vol(v: float) -> str:
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}k"
    return f"${v:.0f}"


def fetch_news(query: str = NEWS_QUERY) -> list[dict]:
    """Fetch Google News RSS items, filtered to last NEWS_LOOKBACK_HOURS."""
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=MX&ceid=MX:es-419"
    req = urllib.request.Request(url, headers={"User-Agent": "rocha-tracker/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_data = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        log(f"NEWS fetch fail: {e}")
        return []

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        log(f"NEWS parse fail: {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_LOOKBACK_HOURS)
    items: list[dict] = []
    for item in root.iterfind(".//item"):
        title = (item.findtext("title") or "").strip()
        pub_raw = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        try:
            pub_dt = parsedate_to_datetime(pub_raw)
        except (TypeError, ValueError):
            continue
        if pub_dt < cutoff:
            continue
        # Trim trailing source: "Title - El Universal" → "Title"
        title_clean = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
        if len(title_clean) > NEWS_MAX_TITLE_LEN:
            title_clean = title_clean[: NEWS_MAX_TITLE_LEN - 1].rstrip() + "…"
        items.append({
            "title": title_clean,
            "source": source,
            "pub": pub_dt,
        })

    items.sort(key=lambda x: x["pub"], reverse=True)
    return items[:NEWS_MAX_ITEMS]


def load_prev() -> dict:
    snaps = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
    if not snaps:
        return {}
    try:
        with open(snaps[-1]) as f:
            return json.load(f)
    except Exception:
        return {}


def save_snapshot(snap: dict) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p = SNAPSHOT_DIR / f"snapshot_{today}.json"
    with open(p, "w") as f:
        json.dump(snap, f, indent=2)
    return p


def fmt_pct(x: float) -> str:
    return f"{x*100:.1f}%"


def fmt_delta(today: float, prev: float | None) -> str:
    if prev is None:
        return "  · new"
    d = (today - prev) * 100
    arrow = "▲" if d > 0 else ("▼" if d < 0 else "·")
    return f"{arrow}{abs(d):.1f}pp"


def build_message(
    snap: dict,
    prev: dict,
    news: list[dict] | None = None,
    high_conv: list[dict] | None = None,
    top_flow: list[dict] | None = None,
    top_movers: list[dict] | None = None,
) -> str:
    today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines = [
        "ROCHA-EXTR Daily",
        f"{today}",
        "",
    ]
    for cfg in MARKETS:
        key = cfg["key"]
        m = snap.get(key)
        if not m:
            lines.append(f"{cfg['label']}: FETCH FAIL")
            continue
        prev_yes = (prev.get(key) or {}).get("yes")
        delta = fmt_delta(m["yes"], prev_yes)
        fair = ""
        if cfg["fair_yes"] is not None:
            edge_pp = (m["yes"] - cfg["fair_yes"]) * 100
            sign = "+" if edge_pp > 0 else ""
            fair = f" | fair {fmt_pct(cfg['fair_yes'])} (edge {sign}{edge_pp:.1f}pp)"
        lines.append(
            f"{cfg['label']}: YES {fmt_pct(m['yes'])} ({delta}){fair}"
        )
        lines.append(
            f"  bid {fmt_pct(m['best_bid'])} / ask {fmt_pct(m['best_ask'])} | vol ${m['volume']:.0f}"
        )

    extr = snap.get("extr_jun30")
    if extr:
        lines.append("")
        if extr["yes"] > 0.45:
            lines.append("SIGNAL: YES > 45% — re-evaluate thesis (catalyst likely)")
        elif extr["yes"] < 0.10:
            lines.append("SIGNAL: YES < 10% — short edge eroded, consider close")
        else:
            lines.append(f"SIGNAL: SHORT YES intact (mkt {fmt_pct(extr['yes'])} vs fair 5%)")

    if news:
        lines.append("")
        lines.append(f"NEWS (last {NEWS_LOOKBACK_HOURS}h):")
        for n in news:
            local_pub = n["pub"].astimezone()
            stamp = local_pub.strftime("%m-%d %H:%M")
            src = f" [{n['source']}]" if n["source"] else ""
            lines.append(f"• {stamp}{src} {n['title']}")
    elif news is not None:
        lines.append("")
        lines.append(f"NEWS (last {NEWS_LOOKBACK_HOURS}h): (no fresh items)")

    if high_conv:
        lines.append("")
        lines.append(f"HIGH-CONVICTION (YES {int(SCREEN_HIGH_CONV_MIN_YES*100)}-{int(SCREEN_HIGH_CONV_MAX_YES*100)}%, end <{SCREEN_HIGH_CONV_MAX_DAYS}d):")
        for r in high_conv:
            lines.append(
                f"• YES {fmt_pct(r['yes'])} | {r['days']:>2}d | "
                f"vol24h {fmt_vol(r['vol24h'])} | {fmt_short_q(r['question'])}"
            )

    if top_movers:
        lines.append("")
        lines.append("TOP MOVERS (24h Δ ≥5pp):")
        for r in top_movers:
            chg = r["one_day_change"] * 100
            sign = "+" if chg > 0 else ""
            lines.append(
                f"• {sign}{chg:>5.1f}pp | YES {fmt_pct(r['yes'])} | {r['days']:>2}d | "
                f"vol24h {fmt_vol(r['vol24h'])} | {fmt_short_q(r['question'])}"
            )

    if top_flow:
        lines.append("")
        lines.append("TOP FLOW (24h volume):")
        for r in top_flow:
            lines.append(
                f"• {fmt_vol(r['vol24h'])} | YES {fmt_pct(r['yes'])} | {r['days']:>2}d | "
                f"{fmt_short_q(r['question'])}"
            )

    return "\n".join(lines)


# ---------- Alert gating ----------
# User preference (2026-05-06): NO routine daily messages. Only send iMessage
# when something actionable happens — a near-cert bet, a regime change, a
# catalyst-grade news headline, or a major price dislocation.

ALERT_ROCHA_MOVE_PP = 0.07          # Δ ≥ 7pp on Rocha extr contract
ALERT_ROCHA_REGIME_HIGH = 0.50      # YES > 50% = catalyst priced in
ALERT_ROCHA_REGIME_LOW = 0.05       # YES < 5% = short edge done
ALERT_NEAR_CERT_MIN_YES = 0.95      # ≥95% YES = "casi seguro"
ALERT_NEAR_CERT_MAX_DAYS = 10
ALERT_NEAR_CERT_MIN_VOL24 = 30_000
ALERT_BIG_MOVE_MIN_PP = 0.25        # any market |Δ24h| ≥ 25pp
ALERT_BIG_MOVE_MIN_VOL24 = 200_000  # with size behind it

ALERT_NEWS_KEYWORDS = [
    "detenido", "detenida", "detiene",
    "extradit",                      # extraditado / extradición
    "captura", "capturado",
    "orden de aprehensión", "orden de detención",
    "fuga", "huye", "huyó", "huida",
    "FGR ordena", "FGR detiene",
    "consigna", "consignado",
    "vincula a proceso",
    "prisión preventiva",
]


def check_alerts(
    snap: dict,
    prev: dict,
    news: list[dict],
    high_conv: list[dict],
    top_movers: list[dict],
) -> list[str]:
    """Return list of alert lines. Empty list = no message should be sent."""
    alerts: list[str] = []

    extr = snap.get("extr_jun30")
    prev_extr = (prev or {}).get("extr_jun30") or {}
    if extr:
        # 1. Big intraday move on the Rocha contract
        if prev_extr.get("yes") is not None:
            d = extr["yes"] - prev_extr["yes"]
            if abs(d) >= ALERT_ROCHA_MOVE_PP:
                arrow = "▲" if d > 0 else "▼"
                alerts.append(
                    f"ROCHA Δ{arrow} {abs(d)*100:.1f}pp · YES now {extr['yes']*100:.1f}% "
                    f"(was {prev_extr['yes']*100:.1f}%) — catalyst likely, re-evaluate."
                )
        # 2. Regime change
        if extr["yes"] >= ALERT_ROCHA_REGIME_HIGH:
            alerts.append(
                f"ROCHA REGIME HIGH · YES {extr['yes']*100:.1f}% ≥ 50% — "
                "thesis at risk, the market thinks it'll happen."
            )
        elif extr["yes"] <= ALERT_ROCHA_REGIME_LOW:
            alerts.append(
                f"ROCHA REGIME LOW · YES {extr['yes']*100:.1f}% ≤ 5% — "
                "short edge eroded, close the carry trade."
            )

    # 3. Near-cert + soon + liquid (in HC list, only if it just appeared / moved)
    prev_hc_questions = set()  # (we don't carry HC between snaps; treat as fresh)
    for r in high_conv:
        if (r["yes"] >= ALERT_NEAR_CERT_MIN_YES
            and r["days"] <= ALERT_NEAR_CERT_MAX_DAYS
            and r["vol24h"] >= ALERT_NEAR_CERT_MIN_VOL24):
            chg = r.get("one_day_change", 0) * 100
            sign = "+" if chg > 0 else ""
            alerts.append(
                f"NEAR-CERT · YES {r['yes']*100:.1f}% · {r['days']}d · vol ${r['vol24h']:.0f} · "
                f"({sign}{chg:.1f}pp 24h) — {r['question'][:70]}"
            )

    # 4. Major dislocation in any market (skip sports heads-up which resolve daily)
    excl = [re.compile(p) for p in SCREEN_HIGH_CONV_EXCLUDE_PATTERNS]
    for r in top_movers:
        if any(p.search(r["question"]) for p in excl):
            continue  # filter out tennis-match style noise
        if (abs(r["one_day_change"]) >= ALERT_BIG_MOVE_MIN_PP
            and r["vol24h"] >= ALERT_BIG_MOVE_MIN_VOL24):
            chg = r["one_day_change"] * 100
            sign = "+" if chg > 0 else ""
            alerts.append(
                f"BIG MOVE · {sign}{chg:.1f}pp · YES {r['yes']*100:.1f}% · "
                f"vol ${r['vol24h']:.0f} — {r['question'][:65]}"
            )

    # 5. Rocha news with red-flag keywords
    for n in news[:8]:
        title_l = (n.get("title") or "").lower()
        for kw in ALERT_NEWS_KEYWORDS:
            if kw.lower() in title_l:
                alerts.append(f"NEWS FLAG · [{kw}] {n.get('source','')} · {n['title'][:80]}")
                break

    return alerts


def build_alert_message(alerts: list[str]) -> str:
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    head = f"⚡ POLYMARKET ALERT · {ts}"
    body = "\n\n".join(alerts)
    foot = "\n\nDashboard: http://127.0.0.1:7878"
    return f"{head}\n\n{body}{foot}"


def send_imessage(phone: str, body: str) -> bool:
    body_escaped = body.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        f'tell application "Messages"\n'
        f'    set targetService to 1st service whose service type = iMessage\n'
        f'    set targetBuddy to buddy "{phone}" of targetService\n'
        f'    send "{body_escaped}" to targetBuddy\n'
        f'end tell'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log(f"iMessage FAIL rc={result.returncode} stderr={result.stderr.strip()}")
            return False
        log("iMessage sent OK")
        return True
    except Exception as e:
        log(f"iMessage EXCEPTION: {e}")
        return False


def main() -> int:
    log("=== run start ===")
    snap: dict = {}
    for cfg in MARKETS:
        m = fetch_market(cfg["slug"])
        if m:
            snap[cfg["key"]] = m

    if not snap:
        log("All fetches failed; aborting.")
        return 1

    prev = load_prev()
    news = fetch_news()
    log(f"NEWS items fetched: {len(news)}")

    screen_rows = fetch_screen()
    log(f"SCREEN rows fetched: {len(screen_rows)}")
    high_conv = screen_high_conviction(screen_rows)
    top_flow = screen_top_flow(screen_rows)
    top_movers = screen_top_movers(screen_rows)
    log(f"SCREEN: high_conv={len(high_conv)} flow={len(top_flow)} movers={len(top_movers)}")

    full_msg = build_message(snap, prev, news, high_conv, top_flow, top_movers)
    log("DAILY DIGEST (not sent unless alerts):\n" + full_msg)

    save_snapshot(snap)

    # Alert gate — user only wants iMessage when something is actionable.
    alerts = check_alerts(snap, prev, news, high_conv, top_movers)
    if not alerts:
        log("ALERT GATE: no actionable signals — skipping iMessage send.")
        log("=== run end (silent) ===")
        return 0

    log(f"ALERT GATE: {len(alerts)} signal(s) — sending iMessage.")
    alert_msg = build_alert_message(alerts)
    log("ALERT MESSAGE:\n" + alert_msg)

    phone = os.environ.get("ROCHA_PHONE", "").strip()
    if not phone:
        log("ROCHA_PHONE not set; would have sent but no destination.")
        return 0

    ok = send_imessage(phone, alert_msg)
    log("=== run end ===")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
