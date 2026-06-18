"""Stdlib contract tests for Polymarket Desk V2 helper surfaces.

These tests intentionally skip optional V2 modules that are not present yet.
When a module exists and exposes the expected helper, the contract becomes
active without requiring network access or third-party packages.
"""

from __future__ import annotations

import datetime as dt
import importlib
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def import_optional(*module_names: str):
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name or module_name.startswith(f"{exc.name}."):
                continue
            raise
    raise unittest.SkipTest("optional module not present: " + ", ".join(module_names))


def helper(module, *names: str):
    for name in names:
        value = getattr(module, name, None)
        if callable(value):
            return value
    raise unittest.SkipTest(
        f"{module.__name__} is importable but no helper found: {', '.join(names)}"
    )


def market_row(slug: str, *, days: int, yes: float, change: float = 0.12) -> dict:
    return {
        "question": f"Will {slug} resolve before the deadline?",
        "slug": slug,
        "yes": yes,
        "days": days,
        "vol24h": 100_000,
        "vol_total": 1_000_000,
        "one_day_change": change,
    }


def is_triggered(result) -> bool:
    if isinstance(result, bool):
        return result
    if isinstance(result, dict):
        return any(
            bool(result.get(key))
            for key in ("triggered", "fired", "should_fire", "emit", "ok")
        )
    if isinstance(result, (list, tuple, set)):
        return bool(result)
    return bool(result)


def call_with_known_names(fn, **values):
    signature = inspect.signature(fn)
    kwargs = {}
    aliases = {
        "rule": {"rule", "alert", "alert_rule"},
        "market": {"market", "row", "market_row"},
        "history": {"history", "state", "dedupe", "dedupe_state", "alert_state"},
        "now": {"now", "current_time", "ts", "timestamp"},
    }
    for name, parameter in signature.parameters.items():
        matched_key = next((key for key, names in aliases.items() if name in names), None)
        if matched_key is not None:
            kwargs[name] = values[matched_key]
        elif parameter.default is inspect.Parameter.empty:
            raise TypeError(f"unrecognized required parameter: {name}")
    return fn(**kwargs)


class StateScreenContractTests(unittest.TestCase):
    def test_candidate_screens_exclude_expired_markets(self):
        state = import_optional("api.state")
        cases = {
            "screen_high_conv": {"yes": 0.74, "live_days": 10},
            "screen_top_movers": {"yes": 0.55, "live_days": 10},
            "screen_safest": {"yes": 0.95, "live_days": 7},
            "screen_today": {"yes": 0.55, "live_days": 4},
            "screen_value_plays": {"yes": 0.85, "live_days": 14},
        }

        for name, values in cases.items():
            screen = helper(state, name)
            rows = [
                market_row(f"{name}-expired", days=-1, yes=values["yes"]),
                market_row(f"{name}-same-day", days=0, yes=values["yes"]),
                market_row(f"{name}-live", days=values["live_days"], yes=values["yes"]),
            ]
            with self.subTest(screen=name):
                slugs = {row["slug"] for row in screen(rows)}
                self.assertIn(f"{name}-live", slugs)
                self.assertNotIn(f"{name}-expired", slugs)
                self.assertNotIn(f"{name}-same-day", slugs)


class MarketEndpointContractTests(unittest.TestCase):
    def test_market_slug_validation_shape(self):
        market = import_optional("api.market")
        validate_slug = helper(
            market,
            "_validate_slug",
            "validate_slug",
            "validate_market_slug",
            "parse_slug",
        )

        self.assertEqual(validate_slug("will-fed-cut-rates-in-july"), "will-fed-cut-rates-in-july")
        bad_slugs = [None, "", "../secret", "UPPER", "space slug", "-starts-with-dash", "x" * 202]
        for bad_slug in bad_slugs:
            with self.subTest(slug=bad_slug):
                with self.assertRaises((TypeError, ValueError)):
                    validate_slug(bad_slug)


class MarketNormalizationContractTests(unittest.TestCase):
    def test_normalized_market_preserves_clob_trade_fields(self):
        common = import_optional("api.common")
        normalize_market = helper(common, "normalize_market")
        now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        raw = {
            "question": "Will BTC close above 100k?",
            "slug": "will-btc-close-above-100k",
            "outcomePrices": "[\"0.42\", \"0.58\"]",
            "outcomes": "[\"Yes\", \"No\"]",
            "clobTokenIds": "[\"yes-token\", \"no-token\"]",
            "marketUrl": "https://polymarket.com/market/will-btc-close-above-100k",
            "endDate": "2026-02-01T00:00:00Z",
            "active": True,
        }

        normalized = normalize_market(raw, now=now)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["outcomes"], ["Yes", "No"])
        self.assertEqual(normalized["clob_token_ids"], ["yes-token", "no-token"])
        self.assertEqual(normalized["market_url"], raw["marketUrl"])


class NamedWatchlistContractTests(unittest.TestCase):
    def test_named_watchlist_schema_helper(self):
        watchlists = import_optional("api.watchlists", "api.named_watchlists")
        validate_payload = helper(
            watchlists,
            "_validate_watchlist_payload",
            "validate_watchlist_payload",
            "normalize_watchlist_payload",
            "sanitize_watchlist_payload",
        )

        payload = {"name": "Election desk", "slugs": ["will-fed-cut-rates", "will-btc-hit-100k"]}
        normalized = validate_payload(payload)
        self.assertIsInstance(normalized, dict)
        self.assertEqual(normalized.get("name"), "Election desk")
        self.assertEqual(normalized.get("slugs"), payload["slugs"])

        for bad_payload in (
            {"name": "", "slugs": ["will-fed-cut-rates"]},
            {"name": "Bad slug", "slugs": ["../secret"]},
            {"name": "Not a list", "slugs": "will-fed-cut-rates"},
        ):
            with self.subTest(payload=bad_payload):
                with self.assertRaises((TypeError, ValueError)):
                    validate_payload(bad_payload)


class AlertContractTests(unittest.TestCase):
    def test_alert_rule_evaluation_respects_cooldown_or_dedupe(self):
        alerts = import_optional("api.alerts", "api.alert_rules")
        evaluate = helper(
            alerts,
            "evaluate_alert_rule",
            "evaluate_rule",
            "should_fire_alert",
            "should_emit_alert",
        )
        rule = {
            "id": "rule-1",
            "market_slug": "will-fed-cut-rates",
            "metric": "yes",
            "operator": ">=",
            "threshold": 0.7,
            "cooldown_seconds": 300,
        }
        market = {"slug": "will-fed-cut-rates", "yes": 0.72, "vol24h": 100_000}
        history = {"fired": {}, "dedupe": set()}
        now = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc)

        try:
            first = call_with_known_names(
                evaluate, rule=rule, market=market, history=history, now=now
            )
            second = call_with_known_names(
                evaluate,
                rule=rule,
                market=market,
                history=history,
                now=now + dt.timedelta(seconds=60),
            )
        except TypeError as exc:
            raise unittest.SkipTest(f"unrecognized alert evaluator signature: {exc}") from exc

        self.assertTrue(is_triggered(first), "matching rule should trigger the first alert")
        self.assertFalse(
            is_triggered(second),
            "same matching rule should be deduped or cooled down on immediate repeat",
        )


class AnalyticsContractTests(unittest.TestCase):
    def test_analytics_event_sanitization_helper(self):
        analytics = import_optional("api.analytics")
        sanitize = helper(
            analytics,
            "_sanitize_event",
            "sanitize_event",
            "normalize_event",
            "clean_event",
        )

        raw = {
            "event": "market_view<script>",
            "path": "/market/will-fed-cut-rates",
            "ip": "203.0.113.1",
            "token": "private-token",
            "properties": {"slug": "will-fed-cut-rates", "html": "<b>unsafe</b>"},
        }
        cleaned = sanitize(raw)
        self.assertIsInstance(cleaned, dict)
        self.assertNotIn("ip", cleaned)
        self.assertNotIn("token", cleaned)
        self.assertNotIn("<", str(cleaned.get("event", "")))
        self.assertNotIn(">", str(cleaned.get("event", "")))


class AuthContractTests(unittest.TestCase):
    def test_auth_payload_validates_handle_password_and_adopt_token(self):
        auth = import_optional("api.auth")
        normalize = helper(auth, "normalize_auth_payload")

        payload = normalize(
            {
                "action": "signup",
                "handle": "ProbTrader_7",
                "password": "correct horse",
                "adopt_token": "anon12345",
            }
        )
        self.assertEqual(payload["action"], "signup")
        self.assertEqual(payload["handle"], "probtrader_7")
        self.assertEqual(payload["handle_display"], "ProbTrader_7")
        self.assertEqual(payload["adopt_token"], "anon12345")

        bad_payloads = (
            {"action": "signup", "handle": "1bad", "password": "correct horse"},
            {"action": "login", "handle": "okhandle", "password": "short"},
            {"action": "delete", "handle": "okhandle", "password": "correct horse"},
            {"action": "login", "handle": "okhandle", "password": "correct horse", "adopt_token": "bad"},
        )
        for bad_payload in bad_payloads:
            with self.subTest(payload=bad_payload):
                with self.assertRaises((TypeError, ValueError)):
                    normalize(bad_payload)

    def test_auth_password_hash_verifies_without_exposing_hash(self):
        auth = import_optional("api.auth")
        hash_password = helper(auth, "hash_password")
        verify_password = helper(auth, "verify_password")
        public_user = helper(auth, "public_user")

        stored = hash_password("correct horse battery", salt=b"1234567890abcdef", iterations=1000)
        self.assertTrue(verify_password("correct horse battery", stored))
        self.assertFalse(verify_password("wrong horse battery", stored))

        profile = public_user(
            {
                "handle": "probtrader",
                "handle_display": "ProbTrader",
                "token": "acct_1234567890abcdef",
                "password_hash": stored,
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
        self.assertEqual(profile["handle"], "ProbTrader")
        self.assertEqual(profile["token"], "acct_1234567890abcdef")
        self.assertNotIn("password_hash", profile)

    def test_auth_rate_limit_helper_blocks_repeated_failures(self):
        auth = import_optional("api.auth")
        limited = helper(auth, "login_is_limited")

        now = 1_000_000.0
        self.assertFalse(limited({"failed": 4, "first_failed_at": now - 60}, now=now))
        self.assertTrue(limited({"failed": 5, "first_failed_at": now - 60}, now=now))
        self.assertFalse(limited({"failed": 5, "first_failed_at": now - 700}, now=now))

    def test_auth_slug_merge_preserves_target_and_caps(self):
        auth = import_optional("api.auth")
        merge = helper(auth, "_merge_slugs")

        target = ["will-fed-cut-rates", "will-btc-hit-100k"]
        source = ["will-btc-hit-100k", "../secret", "will-eth-hit-10k"]
        self.assertEqual(
            merge(target, source, limit=3),
            ["will-fed-cut-rates", "will-btc-hit-100k", "will-eth-hit-10k"],
        )


class CommunityContractTests(unittest.TestCase):
    def test_community_payload_validates_slug_token_and_shape(self):
        community = import_optional("api.community")
        response_payload = helper(community, "response_payload")
        payload = response_payload("will-fed-cut-rates", "token123", [], {})

        self.assertEqual(payload["slug"], "will-fed-cut-rates")
        self.assertIn("vote_summary", payload)
        self.assertIn("messages", payload)
        self.assertIn("limits", payload)

        with self.assertRaises(ValueError):
            response_payload("../secret", "token123", [], {})
        with self.assertRaises(ValueError):
            response_payload("will-fed-cut-rates", "bad", [], {})

    def test_community_sanitizes_messages_and_blocks_abuse(self):
        community = import_optional("api.community")
        clean_alias = helper(community, "clean_alias")
        clean_message = helper(community, "clean_message")

        self.assertEqual(clean_alias(" Prob<>Degen<script> "), "ProbDegenscript")
        self.assertEqual(clean_message("  this market is insane   "), "this market is insane")
        self.assertLessEqual(len(clean_message("x" * 500)), 240)

        for bad_text in (
            "join http://example.com now",
            "<script>alert(1)</script>",
            "claim now free money",
            "kill yourself",
        ):
            with self.subTest(text=bad_text):
                with self.assertRaises(ValueError):
                    clean_message(bad_text)

    def test_community_keeps_last_100_messages(self):
        community = import_optional("api.community")
        append_message = helper(community, "append_message")
        public_messages = helper(community, "public_messages")
        records = []
        base = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc)

        for idx in range(105):
            records, _ = append_message(
                records,
                "will-fed-cut-rates",
                f"user{idx:03d}",
                {"alias": "Desk", "text": f"message {idx}"},
                now=base + dt.timedelta(seconds=idx),
            )

        visible = public_messages(records)
        self.assertEqual(len(records), 100)
        self.assertEqual(len(visible), 100)
        self.assertEqual(visible[0]["text"], "message 5")
        self.assertEqual(visible[-1]["text"], "message 104")

    def test_community_votes_are_one_per_user_and_aggregated(self):
        community = import_optional("api.community")
        upsert_vote = helper(community, "upsert_vote")
        vote_summary = helper(community, "vote_summary")
        my_vote = helper(community, "my_vote")
        votes = {}

        votes, _ = upsert_vote(votes, "will-fed-cut-rates", "token123", {"side": "YES", "conviction": "high"})
        votes, _ = upsert_vote(votes, "will-fed-cut-rates", "token123", {"side": "NO", "conviction": "low"})
        votes, _ = upsert_vote(votes, "will-fed-cut-rates", "token456", {"side": "YES", "conviction": "medium"})

        summary = vote_summary(votes)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["yes"], 1)
        self.assertEqual(summary["no"], 1)
        self.assertEqual(summary["yes_weight"], 2)
        self.assertEqual(summary["no_weight"], 1)
        self.assertEqual(my_vote(votes, "will-fed-cut-rates", "token123")["side"], "NO")

    def test_community_reports_hide_messages(self):
        community = import_optional("api.community")
        append_message = helper(community, "append_message")
        report_message = helper(community, "report_message")
        public_messages = helper(community, "public_messages")

        records, message = append_message(
            [],
            "will-fed-cut-rates",
            "author1",
            {"alias": "Desk", "text": "this is a normal hot take"},
            now=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        )
        for reporter in ("report1", "report2", "report3"):
            records = report_message(records, "will-fed-cut-rates", reporter, message["id"])

        self.assertEqual(public_messages(records), [])

    def test_community_rate_limit_rejects_fourth_recent_message(self):
        community = import_optional("api.community")
        append_message = helper(community, "append_message")
        records = []
        base = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)

        for idx in range(3):
            records, _ = append_message(
                records,
                "will-fed-cut-rates",
                "token123",
                {"alias": "Desk", "text": f"take {idx}"},
                now=base + dt.timedelta(seconds=idx),
            )

        with self.assertRaises(ValueError):
            append_message(
                records,
                "will-fed-cut-rates",
                "token123",
                {"alias": "Desk", "text": "one more"},
                now=base + dt.timedelta(seconds=30),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
