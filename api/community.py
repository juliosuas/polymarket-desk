"""Vercel serverless function: per-market votes and chat.

GET  /api/community?slug=<market-slug>&u=<token>
POST /api/community?slug=<market-slug>&u=<token>

The endpoint stores only hashed anonymous user ids. It never stores raw user
tokens, wallet data, IP addresses, or user agents.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any

try:
    from api.common import (
        first_param,
        iso_now,
        kv_get_json,
        kv_set_json,
        parse_datetime,
        parse_params,
        read_json_body,
        send_json,
        send_options,
        validate_slug,
        validate_token,
    )
except ModuleNotFoundError:  # pragma: no cover - Vercel may import from api/ directly.
    from common import (  # type: ignore
        first_param,
        iso_now,
        kv_get_json,
        kv_set_json,
        parse_datetime,
        parse_params,
        read_json_body,
        send_json,
        send_options,
        validate_slug,
        validate_token,
    )

MAX_MESSAGES = 100
MAX_MESSAGE_CHARS = 240
MAX_ALIAS_CHARS = 24
RATE_LIMIT_MESSAGES = 3
RATE_LIMIT_SECONDS = 60
REPORT_HIDE_THRESHOLD = 3
CONVICTION_WEIGHTS = {"low": 1, "medium": 2, "high": 3}
SIDE_VALUES = {"YES", "NO"}

URL_RE = re.compile(
    r"(https?://|www\.|\b[a-z0-9][a-z0-9.-]{1,}\.(?:com|net|org|io|xyz|app|dev|co|gg|ai|money|finance)\b)",
    re.IGNORECASE,
)
HTML_RE = re.compile(r"(<|>|</|script|javascript:|onerror\s*=|onclick\s*=)", re.IGNORECASE)
SPAM_RE = re.compile(
    r"(airdrop|claim\s+now|seed\s+phrase|private\s+key|wallet\s+drain|guaranteed\s+profit|"
    r"double\s+your|free\s+money|pump\s+group|telegram\s+group|whatsapp|discord\.gg)",
    re.IGNORECASE,
)
THREAT_RE = re.compile(
    r"(kill\s+yourself|kys\b|death\s+threat|i\s+will\s+kill|rape\s+you|doxx|swat\s+you)",
    re.IGNORECASE,
)
ALIAS_RE = re.compile(r"[^a-zA-Z0-9 _.-]+")


def messages_key(slug: str) -> str:
    return f"cm:messages:{slug}"


def votes_key(slug: str) -> str:
    return f"cm:votes:{slug}"


def anonymous_user_hash(token: str, slug: str) -> str:
    return hashlib.sha256(f"community:v1:{slug}:{token}".encode("utf-8")).hexdigest()[:24]


def _collapse(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_alias(value: Any, user_hash: str = "") -> str:
    alias = ALIAS_RE.sub("", _collapse(value))[:MAX_ALIAS_CHARS].strip(" ._-")
    if alias:
        return alias
    suffix = int(user_hash[:6] or "0", 16) % 10_000 if user_hash else 0
    return f"ProbDegen{suffix:04d}"


def clean_message(value: Any) -> str:
    text = _collapse(value)
    if not text:
        raise ValueError("message is required")
    if len(text) > MAX_MESSAGE_CHARS:
        text = text[:MAX_MESSAGE_CHARS].rstrip()
    if URL_RE.search(text):
        raise ValueError("links are not allowed in Market Pit")
    if HTML_RE.search(text):
        raise ValueError("HTML or executable-looking text is not allowed")
    if SPAM_RE.search(text):
        raise ValueError("spam or scam text is not allowed")
    if THREAT_RE.search(text):
        raise ValueError("threatening text is not allowed")
    return text


def normalize_vote_payload(payload: dict[str, Any]) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    side = str(payload.get("side") or "").strip().upper()
    conviction = str(payload.get("conviction") or "medium").strip().lower()
    if side not in SIDE_VALUES:
        raise ValueError("side must be YES or NO")
    if conviction not in CONVICTION_WEIGHTS:
        raise ValueError("conviction must be low, medium, or high")
    return {"side": side, "conviction": conviction}


def _now(value: datetime | None = None) -> datetime:
    return value or datetime.now(timezone.utc)


def _message_id(slug: str, user_hash: str, text: str, created_at: str) -> str:
    raw = f"{slug}:{user_hash}:{created_at}:{text[:48]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _coerce_messages(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    out: list[dict[str, Any]] = []
    for item in records:
        if isinstance(item, dict) and item.get("id") and item.get("text"):
            out.append(item)
    return out[-MAX_MESSAGES:]


def _coerce_votes(records: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(records, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for user_hash, vote in records.items():
        if not isinstance(user_hash, str) or not isinstance(vote, dict):
            continue
        try:
            normalized = normalize_vote_payload(vote)
        except ValueError:
            continue
        out[user_hash] = {
            **normalized,
            "updated_at": vote.get("updated_at") or iso_now(),
        }
    return out


def _recent_count(records: list[dict[str, Any]], user_hash: str, now: datetime) -> int:
    cutoff = now - timedelta(seconds=RATE_LIMIT_SECONDS)
    count = 0
    for item in records:
        if item.get("user_hash") != user_hash:
            continue
        created = parse_datetime(item.get("created_at"))
        if created and created >= cutoff:
            count += 1
    return count


def public_messages(records: Any, hidden_ids: set[str] | None = None) -> list[dict[str, Any]]:
    hidden_ids = hidden_ids or set()
    out: list[dict[str, Any]] = []
    for item in _coerce_messages(records):
        message_id = str(item.get("id") or "")
        if message_id in hidden_ids:
            continue
        if int(item.get("report_count") or 0) >= REPORT_HIDE_THRESHOLD:
            continue
        out.append(
            {
                "id": message_id,
                "alias": clean_alias(item.get("alias"), str(item.get("user_hash") or "")),
                "text": str(item.get("text") or "")[:MAX_MESSAGE_CHARS],
                "created_at": item.get("created_at"),
                "side": item.get("side") if item.get("side") in SIDE_VALUES else None,
                "conviction": item.get("conviction") if item.get("conviction") in CONVICTION_WEIGHTS else None,
            }
        )
    return out[-MAX_MESSAGES:]


def append_message(
    records: Any,
    slug: str,
    token: str,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    clean_slug = validate_slug(slug)
    user_hash = anonymous_user_hash(validate_token(token), clean_slug)
    items = _coerce_messages(records)
    current = _now(now)
    if _recent_count(items, user_hash, current) >= RATE_LIMIT_MESSAGES:
        raise ValueError("rate limit exceeded")
    text = clean_message(payload.get("text"))
    alias = clean_alias(payload.get("alias"), user_hash)
    created_at = current.isoformat()
    item = {
        "id": _message_id(clean_slug, user_hash, text, created_at),
        "user_hash": user_hash,
        "alias": alias,
        "text": text,
        "created_at": created_at,
        "report_count": 0,
        "reported_by": [],
    }
    items.append(item)
    return items[-MAX_MESSAGES:], item


def upsert_vote(records: Any, slug: str, token: str, payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    clean_slug = validate_slug(slug)
    user_hash = anonymous_user_hash(validate_token(token), clean_slug)
    votes = _coerce_votes(records)
    vote = {
        **normalize_vote_payload(payload),
        "updated_at": iso_now(),
    }
    votes[user_hash] = vote
    return votes, vote


def report_message(records: Any, slug: str, token: str, message_id: str | None) -> list[dict[str, Any]]:
    validate_slug(slug)
    reporter = anonymous_user_hash(validate_token(token), slug)
    if not message_id:
        raise ValueError("message_id is required")
    items = _coerce_messages(records)
    found = False
    for item in items:
        if item.get("id") != message_id:
            continue
        found = True
        reporters = item.get("reported_by") if isinstance(item.get("reported_by"), list) else []
        if reporter not in reporters:
            reporters.append(reporter)
        item["reported_by"] = reporters[-25:]
        item["report_count"] = len(set(reporters))
        break
    if not found:
        raise ValueError("message not found")
    return items[-MAX_MESSAGES:]


def vote_summary(records: Any) -> dict[str, Any]:
    votes = _coerce_votes(records)
    yes = no = yes_weight = no_weight = 0
    for vote in votes.values():
        weight = CONVICTION_WEIGHTS.get(vote.get("conviction"), 2)
        if vote.get("side") == "YES":
            yes += 1
            yes_weight += weight
        elif vote.get("side") == "NO":
            no += 1
            no_weight += weight
    total = yes + no
    total_weight = yes_weight + no_weight
    return {
        "total": total,
        "yes": yes,
        "no": no,
        "yes_weight": yes_weight,
        "no_weight": no_weight,
        "yes_weighted_share": round(yes_weight / total_weight, 4) if total_weight else 0,
        "no_weighted_share": round(no_weight / total_weight, 4) if total_weight else 0,
    }


def my_vote(records: Any, slug: str, token: str) -> dict[str, Any] | None:
    user_hash = anonymous_user_hash(validate_token(token), validate_slug(slug))
    vote = _coerce_votes(records).get(user_hash)
    if not vote:
        return None
    return {
        "side": vote.get("side"),
        "conviction": vote.get("conviction"),
        "updated_at": vote.get("updated_at"),
    }


def response_payload(slug: str, token: str, messages: Any, votes: Any) -> dict[str, Any]:
    clean_slug = validate_slug(slug)
    validate_token(token)
    return {
        "slug": clean_slug,
        "vote_summary": vote_summary(votes),
        "my_vote": my_vote(votes, clean_slug, token),
        "messages": public_messages(messages),
        "limits": {
            "max_messages": MAX_MESSAGES,
            "max_message_chars": MAX_MESSAGE_CHARS,
            "rate_limit_messages": RATE_LIMIT_MESSAGES,
            "rate_limit_seconds": RATE_LIMIT_SECONDS,
            "report_hide_threshold": REPORT_HIDE_THRESHOLD,
        },
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self, methods="GET, POST, OPTIONS")

    def _params(self) -> tuple[str, str]:
        params = parse_params(self.path)
        slug = validate_slug(first_param(params, "slug"))
        token = validate_token(first_param(params, "u"))
        return slug, token

    def do_GET(self):
        try:
            slug, token = self._params()
            messages = kv_get_json(messages_key(slug), default=[], read_only=True)
            votes = kv_get_json(votes_key(slug), default={}, read_only=True)
            send_json(self, response_payload(slug, token, messages, votes), methods="GET, POST, OPTIONS")
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400, methods="GET, POST, OPTIONS")
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500, methods="GET, POST, OPTIONS")

    def do_POST(self):
        try:
            slug, token = self._params()
            data = read_json_body(self)
            action = str(data.get("type") or "").strip().lower()
            messages = kv_get_json(messages_key(slug), default=[])
            votes = kv_get_json(votes_key(slug), default={})
            status = 200
            if action == "vote":
                votes, vote = upsert_vote(votes, slug, token, data)
                kv_set_json(votes_key(slug), votes)
                payload = response_payload(slug, token, messages, votes)
                payload["vote"] = vote
            elif action == "message":
                messages, message = append_message(messages, slug, token, data)
                kv_set_json(messages_key(slug), messages)
                payload = response_payload(slug, token, messages, votes)
                payload["message"] = public_messages([message])[0]
                status = 201
            elif action == "report":
                messages = report_message(messages, slug, token, data.get("message_id"))
                kv_set_json(messages_key(slug), messages)
                payload = response_payload(slug, token, messages, votes)
                payload["reported"] = data.get("message_id")
            else:
                raise ValueError("type must be vote, message, or report")
            send_json(self, payload, status=status, methods="GET, POST, OPTIONS")
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400, methods="GET, POST, OPTIONS")
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500, methods="GET, POST, OPTIONS")
