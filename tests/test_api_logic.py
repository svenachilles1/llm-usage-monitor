"""Pure-logic tests for the API layer — including the security proof that
API keys never leak into exception messages, logs or returned data."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.llm_usage_monitor.api import (  # noqa: E402
    CannotConnectError,
    InvalidAuthError,
    LlmApiError,
    NanoGptClient,
    OllamaClient,
    compact_buckets,
    detect_ollama_plan,
    nanogpt_has_daily_limit,
    parse_timestamp,
    remaining_to_used,
    top_models,
)

FAKE_OLLAMA_KEY = "fake-ollama-key-000000000"
FAKE_NANOGPT_KEY = "fake-nanogpt-key-0000000000"


# ---------------------------------------------------------------- fixtures --
class _FakeResponse:
    def __init__(self, status: int, body: dict | None = None, bad_json: bool = False):
        self.status = status
        self._body = body
        self._bad_json = bad_json

    async def json(self, content_type=None):
        if self._bad_json:
            raise ValueError("no json")
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.captured_headers: dict | None = None

    def get(self, url, headers=None, timeout=None):
        self.captured_headers = headers
        return self._response


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if sys.version_info < (3, 10) else asyncio.run(coro)


# ------------------------------------------------------------------- tests --
def test_detect_ollama_plan_legacy():
    balance = {"included": {"session": {"remaining_percent": 75}, "weekly": {"remaining_percent": 40}}}
    assert detect_ollama_plan(balance) == "legacy"


def test_detect_ollama_plan_credits():
    balance = {"included": {"balance_usd": 72.5, "allowance_usd": 100, "period": {}}}
    assert detect_ollama_plan(balance) == "credits"


def test_detect_ollama_plan_robustness():
    assert detect_ollama_plan(None) == "credits"
    assert detect_ollama_plan({}) == "credits"
    assert detect_ollama_plan({"included": None}) == "credits"


def test_remaining_to_used():
    assert remaining_to_used(75) == 25
    assert remaining_to_used(100) == 0
    assert remaining_to_used(0) == 100
    assert remaining_to_used(-5) == 100  # clamp
    assert remaining_to_used(150) == 0  # clamp
    assert remaining_to_used("83") == 17
    assert remaining_to_used(None) is None
    assert remaining_to_used("garbage") is None


def test_compact_buckets():
    usage = {
        "buckets": [
            {"from": "2026-11-24T00:00:00Z", "request_count": 4, "usage_usd": 0.0052},
            {"from": "2026-11-24T01:00:00Z", "request_count": None, "usage_usd": None},  # tolerated
            "garbage",  # skipped
        ]
    }
    out = compact_buckets(usage)
    assert len(out) == 2
    assert out[0] == {"from": "2026-11-24T00:00:00Z", "requests": 4, "usd": 0.0052}
    assert out[1]["requests"] == 0
    assert compact_buckets(None) == []
    assert compact_buckets({}) == []


def test_top_models_sorted_and_limited():
    usage = {
        "totals": {
            "groups": [
                {"model": "b", "request_count": 2, "usage_usd": 0.01},
                {"model": "a", "request_count": 12, "usage_usd": 0.03},
                {"model": "c", "request_count": 5, "usage_usd": 0.02},
                {"model": "d", "request_count": 1, "usage_usd": 0.001},
                {"model": "e", "request_count": 1, "usage_usd": 0.002},
                {"model": "f", "request_count": 1, "usage_usd": 0.003},
                {"model": "g", "request_count": 1, "usage_usd": 0.004},
            ]
        }
    }
    models = top_models(usage, limit=5)
    assert len(models) == 5
    assert models[0]["model"] == "a"  # highest usd first
    assert top_models(None) == []
    assert top_models({"totals": {}}) == []


def test_parse_timestamp_iso_and_epoch():
    iso = parse_timestamp("2026-12-01T07:00:00Z")
    assert iso is not None and iso.year == 2026
    epoch = parse_timestamp(1733031600)
    assert epoch is not None
    assert epoch.year >= 2024
    assert parse_timestamp("not-a-date") is None
    assert parse_timestamp(None) is None


def test_nanogpt_has_daily_limit():
    assert nanogpt_has_daily_limit({"limits": {"dailyInputTokens": 1000000}}) is True
    assert nanogpt_has_daily_limit({"limits": {"dailyInputTokens": 0}}) is False
    assert nanogpt_has_daily_limit({"limits": {"dailyInputTokens": None}}) is False
    assert nanogpt_has_daily_limit({"limits": {}}) is False
    assert nanogpt_has_daily_limit(None) is False


def test_security_401_never_leaks_key():
    """The core security proof: rejected keys never appear in error messages."""
    session = _FakeSession(_FakeResponse(401))
    client = OllamaClient(FAKE_OLLAMA_KEY)
    try:
        _run(client.get_balance(session))
        raise AssertionError("expected InvalidAuthError")
    except InvalidAuthError as exc:
        msg = str(exc)
        assert FAKE_OLLAMA_KEY not in msg
        assert "Bearer" not in msg

    session2 = _FakeSession(_FakeResponse(403))
    client2 = NanoGptClient(FAKE_NANOGPT_KEY)
    try:
        _run(client2.get_subscription_usage(session2))
        raise AssertionError("expected InvalidAuthError")
    except InvalidAuthError as exc:
        assert FAKE_NANOGPT_KEY not in str(exc)
        assert "Bearer" not in str(exc)


def test_security_headers_carry_key_only_to_wire():
    """The key goes to the wire — but the wire object stays inside the call."""
    session = _FakeSession(_FakeResponse(200, body={}))
    client = OllamaClient(FAKE_OLLAMA_KEY)
    _run(client.get_balance(session))
    assert session.captured_headers == {"Authorization": f"Bearer {FAKE_OLLAMA_KEY}"}


def test_error_mapping_429_and_5xx():
    client = OllamaClient(FAKE_OLLAMA_KEY)
    try:
        _run(client.get_balance(_FakeSession(_FakeResponse(429))))
        raise AssertionError("expected LlmApiError")
    except LlmApiError as exc:
        assert not isinstance(exc, InvalidAuthError)
        assert FAKE_OLLAMA_KEY not in str(exc)

    try:
        _run(client.get_balance(_FakeSession(_FakeResponse(500))))
        raise AssertionError("expected LlmApiError")
    except LlmApiError:
        pass


def test_invalid_json_maps_to_api_error():
    client = NanoGptClient(FAKE_NANOGPT_KEY)
    try:
        _run(client.get_subscription_usage(_FakeSession(_FakeResponse(200, bad_json=True))))
        raise AssertionError("expected LlmApiError")
    except LlmApiError as exc:
        assert FAKE_NANOGPT_KEY not in str(exc)


def test_connect_error_sanitized():
    import aiohttp

    class _ExplodingSession:
        def get(self, url, headers=None, timeout=None):
            raise aiohttp.ClientError("boom")

    client = OllamaClient(FAKE_OLLAMA_KEY)
    try:
        _run(client.get_balance(_ExplodingSession()))
        raise AssertionError("expected CannotConnectError")
    except CannotConnectError as exc:
        assert FAKE_OLLAMA_KEY not in str(exc)
        assert "boom" not in str(exc)  # only the exception class name travels
