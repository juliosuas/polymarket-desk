"""Vercel serverless function: per-user in-app alert rules.

GET    /api/alerts?u=<token>           -> {alerts:[...]}
POST   /api/alerts?u=<token>           -> create rule from JSON body
PATCH  /api/alerts?u=<token>&id=<id>   -> update rule
PUT    /api/alerts?u=<token>&id=<id>   -> update rule
DELETE /api/alerts?u=<token>&id=<id>   -> delete rule

Supported rule types:
  - price_cross:    {slug?, threshold, direction:"above"|"below", field?}
  - move_threshold: {slug?, threshold, direction:"either"|"up"|"down"}
  - volume_spike:   {slug?, multiplier?, min_vol24h?, threshold?}
  - closing_soon:   {slug?, days}
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any

try:
    from api.common import (
        KVError,
        alerts_key,
        first_param,
        iso_now,
        kv_get_json,
        kv_set_json,
        kv_try_get_json,
        kv_try_set_json,
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
        KVError,
        alerts_key,
        first_param,
        iso_now,
        kv_get_json,
        kv_set_json,
        kv_try_get_json,
        kv_try_set_json,
        parse_params,
        read_json_body,
        safe_float,
        send_json,
        send_options,
        validate_slug,
        validate_token,
    )

ALERT_TYPES = {"price_cross", "move_threshold", "volume_spike", "closing_soon"}
PRICE_FIELDS = {"yes", "no", "last_trade", "best_bid", "best_ask"}
MAX_ALERTS = 100
MAX_EVENTS = 50
MAX_STATE_ITEMS = 200


def _load_rules(token: str, read_only: bool = False) -> list[dict[str, Any]]:
    data = kv_get_json(alerts_key(token), default=[], read_only=read_only)
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict)]


def _save_rules(token: str, rules: list[dict[str, Any]]) -> None:
    kv_set_json(alerts_key(token), rules[:MAX_ALERTS])


def _bool_value(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _number(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    number = safe_float(value, default=float("nan"))
    return None if number != number else number


def _alert_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean_rule(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    now = iso_now()
    base = dict(existing or {})
    alert_type = payload.get("type", base.get("type"))
    if alert_type not in ALERT_TYPES:
        raise ValueError("invalid alert type")

    slug = payload.get("slug", base.get("slug"))
    slug = validate_slug(slug) if slug else None
    name = payload.get("name", base.get("name") or alert_type.replace("_", " ").title())
    if not isinstance(name, str):
        name = alert_type.replace("_", " ").title()
    name = " ".join(name.split())[:80]

    rule: dict[str, Any] = {
        "id": base.get("id") or str(payload.get("id") or _alert_id())[:64],
        "type": alert_type,
        "name": name,
        "slug": slug,
        "enabled": _bool_value(payload.get("enabled", base.get("enabled", True))),
        "created_at": base.get("created_at") or now,
        "updated_at": now,
    }

    if alert_type == "price_cross":
        field = payload.get("field", base.get("field") or "yes")
        if field not in PRICE_FIELDS:
            raise ValueError("invalid price field")
        threshold = _number(payload.get("threshold", base.get("threshold")))
        if threshold is None or not (0 <= threshold <= 1):
            raise ValueError("price_cross threshold must be between 0 and 1")
        direction = payload.get("direction", base.get("direction") or "above")
        if direction == "up":
            direction = "above"
        if direction == "down":
            direction = "below"
        if direction not in {"above", "below"}:
            raise ValueError("price_cross direction must be above or below")
        rule.update({"field": field, "threshold": threshold, "direction": direction})

    elif alert_type == "move_threshold":
        threshold = _number(payload.get("threshold", base.get("threshold")), 0.05)
        if threshold is None or threshold <= 0:
            raise ValueError("move_threshold threshold must be positive")
        direction = payload.get("direction", base.get("direction") or "either")
        if direction not in {"either", "up", "down"}:
            raise ValueError("move_threshold direction must be either, up, or down")
        rule.update({"threshold": threshold, "direction": direction})

    elif alert_type == "volume_spike":
        multiplier = _number(payload.get("multiplier", base.get("multiplier")), 2.0)
        min_vol24h = _number(payload.get("min_vol24h", base.get("min_vol24h")), 10_000.0)
        threshold = _number(payload.get("threshold", base.get("threshold")), None)
        if multiplier is None or multiplier < 1:
            raise ValueError("volume_spike multiplier must be at least 1")
        if min_vol24h is None or min_vol24h < 0:
            raise ValueError("volume_spike min_vol24h must be non-negative")
        if threshold is not None and threshold < 0:
            raise ValueError("volume_spike threshold must be non-negative")
        rule.update({"multiplier": multiplier, "min_vol24h": min_vol24h})
        if threshold is not None:
            rule["threshold"] = threshold

    elif alert_type == "closing_soon":
        days = int(_number(payload.get("days", base.get("days")), 1) or 1)
        if days < 0 or days > 365:
            raise ValueError("closing_soon days must be between 0 and 365")
        rule.update({"days": days})

    state = base.get("state") if isinstance(base.get("state"), dict) else {}
    if state:
        rule["state"] = state
    for key in ("last_checked_at", "last_triggered_at"):
        if base.get(key):
            rule[key] = base[key]
    return rule


def _dedupe_markets(markets: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    by_slug: dict[str, dict[str, Any]] = {}
    for market in markets or []:
        if not isinstance(market, dict):
            continue
        slug = market.get("slug")
        if not slug:
            continue
        days = market.get("days")
        if isinstance(days, (int, float)) and days < 0:
            continue
        prev = by_slug.get(slug)
        if not prev or (market.get("question") and not prev.get("question")):
            by_slug[slug] = market
    return list(by_slug.values())


def _field_value(market: dict[str, Any], field: str) -> float | None:
    aliases = {"price": "yes", "vol24h": "vol24h", "volume24hr": "vol24h"}
    key = aliases.get(field, field)
    value = _number(market.get(key))
    return value


def _state_dict(rule: dict[str, Any], key: str) -> dict[str, Any]:
    state = rule.setdefault("state", {})
    bucket = state.setdefault(key, {})
    return bucket if isinstance(bucket, dict) else {}


def _remember_event(rule: dict[str, Any], key: str) -> bool:
    state = rule.setdefault("state", {})
    keys = state.setdefault("event_keys", [])
    if not isinstance(keys, list):
        keys = []
        state["event_keys"] = keys
    if key in keys:
        return False
    keys.append(key)
    if len(keys) > MAX_STATE_ITEMS:
        del keys[: len(keys) - MAX_STATE_ITEMS]
    return True


def _trim_state(rule: dict[str, Any]) -> None:
    state = rule.get("state")
    if not isinstance(state, dict):
        return
    for key in ("values", "volumes"):
        bucket = state.get(key)
        if isinstance(bucket, dict) and len(bucket) > MAX_STATE_ITEMS:
            for old_key in list(bucket.keys())[: len(bucket) - MAX_STATE_ITEMS]:
                bucket.pop(old_key, None)


def _event(rule: dict[str, Any], market: dict[str, Any], message: str, value: Any) -> dict[str, Any]:
    return {
        "id": rule.get("id"),
        "type": rule.get("type"),
        "name": rule.get("name"),
        "slug": market.get("slug"),
        "question": market.get("question"),
        "value": value,
        "threshold": rule.get("threshold"),
        "message": message,
        "ts": iso_now(),
    }


def _now_seconds(now: Any = None) -> float:
    if now is None:
        return datetime.now(timezone.utc).timestamp()
    if isinstance(now, datetime):
        return now.timestamp()
    try:
        return float(now)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).timestamp()


def evaluate_alert_rule(
    rule: dict[str, Any],
    market: dict[str, Any],
    history: dict[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any] | bool:
    """Small contract helper for one-off rule evaluation with cooldown dedupe."""
    if not isinstance(rule, dict) or not isinstance(market, dict):
        return False
    slug = rule.get("market_slug") or rule.get("slug")
    if slug and slug != market.get("slug"):
        return False
    metric = rule.get("metric") or rule.get("field") or "yes"
    value = _field_value(market, str(metric))
    threshold = _number(rule.get("threshold"))
    if value is None or threshold is None:
        return False
    operator = rule.get("operator") or (">=" if rule.get("direction") in (None, "above", "up") else "<=")
    matched = {
        ">": value > threshold,
        ">=": value >= threshold,
        "<": value < threshold,
        "<=": value <= threshold,
    }.get(str(operator), False)
    if not matched:
        return False
    store = history if isinstance(history, dict) else {}
    fired = store.setdefault("fired", {})
    key = f"{rule.get('id') or 'rule'}:{market.get('slug')}:{metric}:{operator}:{threshold}"
    now_ts = _now_seconds(now)
    cooldown = int(_number(rule.get("cooldown_seconds"), 300) or 0)
    last_ts = _number(fired.get(key))
    if last_ts is not None and now_ts - last_ts < cooldown:
        return False
    fired[key] = now_ts
    return {
        "triggered": True,
        "id": rule.get("id"),
        "slug": market.get("slug"),
        "value": round(value, 6),
        "threshold": threshold,
    }


def _eval_price_cross(rule: dict[str, Any], market: dict[str, Any]) -> dict[str, Any] | None:
    slug = market.get("slug")
    field = rule.get("field") or "yes"
    threshold = float(rule.get("threshold"))
    current = _field_value(market, field)
    if current is None:
        return None
    values = _state_dict(rule, "values")
    previous = _number(values.get(slug))
    values[slug] = round(current, 6)
    if previous is None:
        return None
    direction = rule.get("direction") or "above"
    crossed = previous < threshold <= current if direction == "above" else previous > threshold >= current
    if not crossed:
        return None
    side = "above" if direction == "above" else "below"
    return _event(
        rule,
        market,
        f"{market.get('question') or slug} crossed {side} {threshold:.3f}",
        round(current, 6),
    )


def _eval_move_threshold(rule: dict[str, Any], market: dict[str, Any]) -> dict[str, Any] | None:
    slug = market.get("slug")
    change = _number(market.get("one_day_change"))
    if change is None:
        return None
    threshold = float(rule.get("threshold") or 0.05)
    direction = rule.get("direction") or "either"
    matches = abs(change) >= threshold
    if direction == "up":
        matches = change >= threshold
    elif direction == "down":
        matches = change <= -threshold
    if not matches:
        return None
    event_key = f"move:{slug}:{direction}:{round(change, 4)}"
    if not _remember_event(rule, event_key):
        return None
    return _event(
        rule,
        market,
        f"{market.get('question') or slug} moved {change:+.1%} in 24h",
        round(change, 6),
    )


def _eval_volume_spike(rule: dict[str, Any], market: dict[str, Any]) -> dict[str, Any] | None:
    slug = market.get("slug")
    current = _number(market.get("vol24h"))
    if current is None:
        return None
    volumes = _state_dict(rule, "volumes")
    previous = _number(volumes.get(slug))
    volumes[slug] = round(current, 2)
    multiplier = float(rule.get("multiplier") or 2.0)
    min_vol24h = float(rule.get("min_vol24h") or 0)
    absolute = _number(rule.get("threshold"))
    matches = bool(absolute is not None and current >= absolute)
    if previous and previous > 0:
        matches = matches or (current >= min_vol24h and current >= previous * multiplier)
    if not matches:
        return None
    bucket = round(current / max(min_vol24h, 1), 2) if min_vol24h else round(current, -3)
    event_key = f"volume:{slug}:{bucket}"
    if not _remember_event(rule, event_key):
        return None
    return _event(
        rule,
        market,
        f"{market.get('question') or slug} printed elevated 24h volume",
        round(current, 2),
    )


def _eval_closing_soon(rule: dict[str, Any], market: dict[str, Any]) -> dict[str, Any] | None:
    slug = market.get("slug")
    days = market.get("days")
    if not isinstance(days, (int, float)) or days < 0:
        return None
    threshold = int(rule.get("days") or 1)
    if days > threshold:
        return None
    event_key = f"closing:{slug}:{int(days)}"
    if not _remember_event(rule, event_key):
        return None
    return _event(
        rule,
        market,
        f"{market.get('question') or slug} closes in {int(days)}d",
        int(days),
    )


def _matches(rule: dict[str, Any], market: dict[str, Any]) -> bool:
    return not rule.get("slug") or rule.get("slug") == market.get("slug")


def evaluate_alerts(user_token: str, markets: list[dict[str, Any]], persist: bool = True) -> list[dict[str, Any]]:
    """Evaluate stored alert rules against normalized markets.

    KV failures return no events rather than breaking the dashboard state call.
    """
    try:
        token = validate_token(user_token)
    except ValueError:
        return []
    try:
        rules = _load_rules(token)
        can_write = True
    except KVError:
        rules = kv_try_get_json(alerts_key(token), default=[], read_only=True)
        rules = rules if isinstance(rules, list) else []
        can_write = False

    market_rows = _dedupe_markets(markets)
    events: list[dict[str, Any]] = []
    now = iso_now()
    evaluators = {
        "price_cross": _eval_price_cross,
        "move_threshold": _eval_move_threshold,
        "volume_spike": _eval_volume_spike,
        "closing_soon": _eval_closing_soon,
    }

    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("enabled", True):
            continue
        evaluator = evaluators.get(rule.get("type"))
        if not evaluator:
            continue
        rule["last_checked_at"] = now
        for market in market_rows:
            if not _matches(rule, market):
                continue
            event = evaluator(rule, market)
            if not event:
                continue
            rule["last_triggered_at"] = event["ts"]
            events.append(event)
            if len(events) >= MAX_EVENTS:
                break
        _trim_state(rule)
        if len(events) >= MAX_EVENTS:
            break

    if persist and can_write:
        kv_try_set_json(alerts_key(token), rules[:MAX_ALERTS])
    return events


def evaluate_alerts_for_snapshot(user_token: str, markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return evaluate_alerts(user_token, markets, persist=True)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self)

    def _token_and_rules(self) -> tuple[str, list[dict[str, Any]]]:
        params = parse_params(self.path)
        token = validate_token(first_param(params, "u"))
        return token, _load_rules(token)

    def do_GET(self):
        try:
            params = parse_params(self.path)
            token, rules = self._token_and_rules()
            alert_id = first_param(params, "id")
            if alert_id:
                for rule in rules:
                    if rule.get("id") == alert_id:
                        send_json(self, {"alert": rule})
                        return
                send_json(self, {"error": "alert not found"}, 404)
                return
            send_json(self, {"alerts": rules, "count": len(rules)})
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_POST(self):
        try:
            token, rules = self._token_and_rules()
            if len(rules) >= MAX_ALERTS:
                send_json(self, {"error": f"alert limit reached ({MAX_ALERTS})"}, 400)
                return
            data = read_json_body(self)
            rule = _clean_rule(data)
            existing_ids = {r.get("id") for r in rules}
            while rule["id"] in existing_ids:
                rule["id"] = _alert_id()
            rules.append(rule)
            _save_rules(token, rules)
            send_json(self, {"alert": rule, "alerts": rules}, status=201)
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_PATCH(self):
        try:
            params = parse_params(self.path)
            token, rules = self._token_and_rules()
            alert_id = first_param(params, "id")
            if not alert_id:
                send_json(self, {"error": "missing alert id"}, 400)
                return
            data = read_json_body(self)
            for idx, rule in enumerate(rules):
                if rule.get("id") != alert_id:
                    continue
                updated = _clean_rule(data, existing=rule)
                rules[idx] = updated
                _save_rules(token, rules)
                send_json(self, {"alert": updated, "alerts": rules})
                return
            send_json(self, {"error": "alert not found"}, 404)
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_PUT(self):
        self.do_PATCH()

    def do_DELETE(self):
        try:
            params = parse_params(self.path)
            token, rules = self._token_and_rules()
            alert_id = first_param(params, "id")
            if not alert_id:
                send_json(self, {"error": "missing alert id"}, 400)
                return
            new_rules = [r for r in rules if r.get("id") != alert_id]
            if len(new_rules) == len(rules):
                send_json(self, {"error": "alert not found"}, 404)
                return
            _save_rules(token, new_rules)
            send_json(self, {"alerts": new_rules, "deleted": alert_id})
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)
