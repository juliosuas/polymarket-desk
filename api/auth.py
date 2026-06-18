"""Vercel serverless function: lightweight Polymarket Desk accounts.

POST /api/auth                  -> signup/login with handle + password
GET  /api/auth?u=<account-token> -> resolve current account profile

Accounts intentionally stay small: a handle, a password hash, and the same
opaque user token the rest of the desk already uses for watchlists and alerts.
No wallet data, IP addresses, user agents, or Polymarket credentials are stored.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
from http.server import BaseHTTPRequestHandler
from typing import Any

try:
    from api.common import (
        KVError,
        alerts_key,
        clean_name,
        first_param,
        iso_now,
        kv_get_json,
        kv_set_json,
        kv_try_get_json,
        kv_try_set_json,
        parse_params,
        read_json_body,
        send_json,
        send_options,
        validate_slug,
        validate_token,
        validate_watchlist_id,
        watchlist_key,
        watchlists_key,
    )
except ModuleNotFoundError:  # pragma: no cover - Vercel may import from api/ directly.
    from common import (  # type: ignore
        KVError,
        alerts_key,
        clean_name,
        first_param,
        iso_now,
        kv_get_json,
        kv_set_json,
        kv_try_get_json,
        kv_try_set_json,
        parse_params,
        read_json_body,
        send_json,
        send_options,
        validate_slug,
        validate_token,
        validate_watchlist_id,
        watchlist_key,
        watchlists_key,
    )
HANDLE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,31}$")
PASSWORD_MIN = 8
PASSWORD_MAX = 128
PASSWORD_ITERATIONS = 220_000
MAX_WATCHLIST = 50
MAX_NAMED_WATCHLISTS = 25
MAX_ALERTS = 100
MAX_FAILED_ATTEMPTS = 5
RATE_LIMIT_SECONDS = 10 * 60


def auth_user_key(handle: str) -> str:
    return f"auth:user:{handle}"


def auth_token_key(token: str) -> str:
    return f"auth:token:{token}"


def auth_rate_key(handle: str) -> str:
    return f"auth:rate:{handle}"


def normalize_handle(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("handle is required")
    handle = value.strip()
    if not HANDLE_RE.match(handle):
        raise ValueError("handle must be 3-32 chars and start with a letter")
    return handle.lower()


def display_handle(value: Any) -> str:
    handle = str(value or "").strip()
    return handle if HANDLE_RE.match(handle) else normalize_handle(handle)


def validate_password(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("password is required")
    if len(value) < PASSWORD_MIN:
        raise ValueError(f"password must be at least {PASSWORD_MIN} characters")
    if len(value) > PASSWORD_MAX:
        raise ValueError(f"password must be at most {PASSWORD_MAX} characters")
    return value


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password(password: str, salt: bytes | None = None, iterations: int = PASSWORD_ITERATIONS) -> str:
    password = validate_password(password)
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations_raw, salt_raw, digest_raw = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _unb64(salt_raw)
        expected = _unb64(digest_raw)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def normalize_auth_payload(payload: dict[str, Any], default_action: str = "login") -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    action = str(payload.get("action") or payload.get("type") or default_action).strip().lower()
    if action not in {"signup", "login"}:
        raise ValueError("invalid auth action")
    raw_handle = payload.get("handle") or payload.get("username")
    handle = normalize_handle(raw_handle)
    password = validate_password(payload.get("password"))
    adopt_token = payload.get("adopt_token") or payload.get("adoptToken") or ""
    if adopt_token:
        adopt_token = validate_token(str(adopt_token))
    return {
        "action": action,
        "handle": handle,
        "handle_display": display_handle(raw_handle),
        "password": password,
        "adopt_token": adopt_token or "",
    }


def public_user(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    token = record.get("token")
    handle = record.get("handle")
    if not token or not handle:
        return None
    return {
        "handle": record.get("handle_display") or handle,
        "token": token,
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }


def _load_user(handle: str) -> dict[str, Any] | None:
    data = kv_get_json(auth_user_key(handle), default=None)
    return data if isinstance(data, dict) else None


def _load_user_by_token(token: str) -> dict[str, Any] | None:
    index = kv_get_json(auth_token_key(token), default=None)
    if not isinstance(index, dict):
        return None
    handle = index.get("handle")
    if not isinstance(handle, str):
        return None
    return _load_user(handle)


def _save_user(record: dict[str, Any]) -> None:
    handle = normalize_handle(record.get("handle"))
    token = validate_token(record.get("token"))
    kv_set_json(auth_user_key(handle), record)
    kv_set_json(auth_token_key(token), {"handle": handle, "created_at": record.get("created_at")})


def _new_account_token() -> str:
    for _ in range(12):
        token = "acct_" + secrets.token_urlsafe(24)
        validate_token(token)
        if _load_user_by_token(token) is None:
            return token
    raise KVError("could not allocate account token")


def _merge_slugs(target: list[Any], source: list[Any], limit: int = MAX_WATCHLIST) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in list(target or []) + list(source or []):
        try:
            slug = validate_slug(raw if isinstance(raw, str) else None)
        except ValueError:
            continue
        if slug in seen:
            continue
        seen.add(slug)
        out.append(slug)
        if len(out) >= limit:
            break
    return out


def _load_meta(token: str) -> list[dict[str, Any]]:
    data = kv_try_get_json(watchlists_key(token), default=[])
    return data if isinstance(data, list) else []


def _clean_meta_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    try:
        wl_id = validate_watchlist_id(item.get("id"), allow_default=False)
    except ValueError:
        return None
    if not wl_id or wl_id == "default":
        return None
    return {
        "id": wl_id,
        "name": clean_name(item.get("name"), wl_id),
        "created_at": item.get("created_at") or iso_now(),
        "updated_at": iso_now(),
    }


def _merge_watchlists(source_token: str, target_token: str) -> dict[str, int]:
    migrated = {"default_slugs": 0, "named_lists": 0, "named_slugs": 0}

    source_default = kv_try_get_json(watchlist_key(source_token), default=[])
    target_default = kv_try_get_json(watchlist_key(target_token), default=[])
    merged_default = _merge_slugs(target_default, source_default)
    if merged_default != target_default:
        kv_try_set_json(watchlist_key(target_token), merged_default)
        migrated["default_slugs"] = max(0, len(merged_default) - len(target_default or []))

    source_meta = [_clean_meta_item(item) for item in _load_meta(source_token)]
    source_meta = [item for item in source_meta if item]
    target_meta = [_clean_meta_item(item) for item in _load_meta(target_token)]
    target_meta = [item for item in target_meta if item]
    by_id = {item["id"]: item for item in target_meta}

    for item in source_meta:
        wl_id = item["id"]
        source_slugs = kv_try_get_json(watchlist_key(source_token, wl_id), default=[])
        if wl_id in by_id:
            target_slugs = kv_try_get_json(watchlist_key(target_token, wl_id), default=[])
            merged_slugs = _merge_slugs(target_slugs, source_slugs)
            if merged_slugs != target_slugs:
                kv_try_set_json(watchlist_key(target_token, wl_id), merged_slugs)
                migrated["named_slugs"] += max(0, len(merged_slugs) - len(target_slugs or []))
            continue
        if len(target_meta) >= MAX_NAMED_WATCHLISTS:
            continue
        target_meta.append(item)
        by_id[wl_id] = item
        kv_try_set_json(watchlist_key(target_token, wl_id), _merge_slugs([], source_slugs))
        migrated["named_lists"] += 1
        migrated["named_slugs"] += min(len(source_slugs or []), MAX_WATCHLIST)

    if target_meta:
        kv_try_set_json(watchlists_key(target_token), target_meta[:MAX_NAMED_WATCHLISTS])
    return migrated


def _merge_alerts(source_token: str, target_token: str) -> int:
    source = kv_try_get_json(alerts_key(source_token), default=[])
    target = kv_try_get_json(alerts_key(target_token), default=[])
    if not isinstance(source, list) or not isinstance(target, list):
        return 0
    out = [item for item in target if isinstance(item, dict)]
    seen = {str(item.get("id")) for item in out if item.get("id")}
    added = 0
    for item in source:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        if item_id and item_id in seen:
            continue
        out.append(item)
        if item_id:
            seen.add(item_id)
        added += 1
        if len(out) >= MAX_ALERTS:
            break
    if added:
        kv_try_set_json(alerts_key(target_token), out[:MAX_ALERTS])
    return added


def merge_user_data(source_token: str | None, target_token: str) -> dict[str, Any]:
    if not source_token:
        return {"migrated": False}
    try:
        source = validate_token(source_token)
        target = validate_token(target_token)
    except ValueError:
        return {"migrated": False}
    if source == target or source.startswith("acct_"):
        return {"migrated": False}
    watchlists = _merge_watchlists(source, target)
    alerts = _merge_alerts(source, target)
    return {"migrated": True, "watchlists": watchlists, "alerts": alerts}


def _load_rate(handle: str) -> dict[str, Any]:
    data = kv_try_get_json(auth_rate_key(handle), default={})
    return data if isinstance(data, dict) else {}


def login_is_limited(rate: dict[str, Any], now: float | None = None) -> bool:
    now = now or time.time()
    first_failed = float(rate.get("first_failed_at") or 0)
    failed = int(rate.get("failed") or 0)
    return failed >= MAX_FAILED_ATTEMPTS and now - first_failed < RATE_LIMIT_SECONDS


def record_login_failure(handle: str, now: float | None = None) -> None:
    now = now or time.time()
    rate = _load_rate(handle)
    first_failed = float(rate.get("first_failed_at") or 0)
    if now - first_failed >= RATE_LIMIT_SECONDS:
        rate = {"first_failed_at": now, "failed": 1}
    else:
        rate = {"first_failed_at": first_failed or now, "failed": int(rate.get("failed") or 0) + 1}
    kv_try_set_json(auth_rate_key(handle), rate)


def clear_login_failures(handle: str) -> None:
    kv_try_set_json(auth_rate_key(handle), {"first_failed_at": 0, "failed": 0})


def create_account(credentials: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    handle = credentials["handle"]
    if _load_user(handle):
        raise ValueError("handle already exists")
    now = iso_now()
    record = {
        "handle": handle,
        "handle_display": credentials["handle_display"],
        "token": _new_account_token(),
        "password_hash": hash_password(credentials["password"]),
        "created_at": now,
        "updated_at": now,
    }
    _save_user(record)
    migration = merge_user_data(credentials.get("adopt_token"), record["token"])
    return record, migration


def authenticate(credentials: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    handle = credentials["handle"]
    rate = _load_rate(handle)
    if login_is_limited(rate):
        raise PermissionError("too many failed attempts; try again later")
    record = _load_user(handle)
    if not record or not verify_password(credentials["password"], str(record.get("password_hash") or "")):
        record_login_failure(handle)
        raise PermissionError("invalid handle or password")
    clear_login_failures(handle)
    migration = merge_user_data(credentials.get("adopt_token"), record["token"])
    return record, migration


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options(self, methods="GET, POST, OPTIONS")

    def do_GET(self):
        try:
            params = parse_params(self.path)
            token = validate_token(first_param(params, "u"))
            record = _load_user_by_token(token)
            send_json(self, {"authenticated": bool(record), "user": public_user(record)})
        except ValueError as exc:
            send_json(self, {"error": str(exc)}, 400)
        except KVError as exc:
            send_json(self, {"error": str(exc)}, 500)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_POST(self):
        try:
            credentials = normalize_auth_payload(read_json_body(self))
            if credentials["action"] == "signup":
                record, migration = create_account(credentials)
                status = 201
                event = "signup"
            else:
                record, migration = authenticate(credentials)
                status = 200
                event = "login"
            send_json(
                self,
                {
                    "authenticated": True,
                    "event": event,
                    "user": public_user(record),
                    "migration": migration,
                },
                status=status,
            )
        except PermissionError as exc:
            status = 429 if "too many" in str(exc) else 401
            send_json(self, {"error": str(exc)}, status)
        except ValueError as exc:
            status = 409 if "already exists" in str(exc) else 400
            send_json(self, {"error": str(exc)}, status)
        except KVError as exc:
            send_json(self, {"error": str(exc)}, 500)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)
