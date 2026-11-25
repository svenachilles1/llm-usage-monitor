"""API clients for Ollama cloud and NanoGPT subscription usage.

Security rule of this module: API keys live ONLY in HTTP headers and in the
config entry storage — never in exception messages, log statements or any
value returned by these clients.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import (
    API_TIMEOUT_SECONDS,
    NANOGPT_BASE_URL,
    NANOGPT_USAGE_PATH,
    OLLAMA_BALANCE_PATH,
    OLLAMA_BASE_URL,
    OLLAMA_USAGE_PATH,
    PLAN_CREDITS,
    PLAN_LEGACY,
)

_LOGGER = logging.getLogger(__name__)


class LlmApiError(Exception):
    """Base error for provider API failures."""


class InvalidAuthError(LlmApiError):
    """The API key was rejected (401/403)."""


class CannotConnectError(LlmApiError):
    """Network / timeout / server error."""


class _BaseClient:
    """Shared JSON GET logic with sanitized error handling."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def _get_json(self, session: aiohttp.ClientSession, path: str) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS)
            ) as resp:
                status = resp.status
                if status in (401, 403):
                    # Deliberately message-less about the key material itself.
                    raise InvalidAuthError(f"{self._base_url} rejected the request (HTTP {status})")
                if status == 429:
                    # Rate limited — far below our poll cadence, retry next tick.
                    raise LlmApiError(f"{self._base_url} rate limited the request (HTTP 429)")
                if status >= 400:
                    raise LlmApiError(f"{self._base_url} returned HTTP {status}")
                try:
                    return await resp.json(content_type=None)
                except ValueError as err:
                    raise LlmApiError(f"{self._base_url} returned invalid JSON") from err
        except InvalidAuthError:
            raise
        except LlmApiError:
            raise
        except asyncio.TimeoutError as err:
            raise CannotConnectError(f"{self._base_url} timed out") from err
        except aiohttp.ClientError as err:
            # aiohttp exceptions never contain request headers — but keep the
            # message to the error class name anyway, defense in depth.
            raise CannotConnectError(
                f"{self._base_url} connection failed ({err.__class__.__name__})"
            ) from err


class OllamaClient(_BaseClient):
    """Client for Ollama's official cloud usage/balance endpoints."""

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key, OLLAMA_BASE_URL)

    async def get_balance(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        return await self._get_json(session, OLLAMA_BALANCE_PATH)

    async def get_usage(
        self,
        session: aiohttp.ClientSession,
        range_: str = "24h",
        group_by_model: bool = False,
    ) -> dict[str, Any]:
        path = f"{OLLAMA_USAGE_PATH}?range={range_}"
        if group_by_model:
            path += "&group_by=model"
        return await self._get_json(session, path)


class NanoGptClient(_BaseClient):
    """Client for NanoGPT's official subscription usage endpoint."""

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key, NANOGPT_BASE_URL)

    async def get_subscription_usage(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        return await self._get_json(session, NANOGPT_USAGE_PATH)


def detect_ollama_plan(balance: dict[str, Any] | None) -> str:
    """Detect the plan type from the balance response structure.

    Legacy plans return ``included.session`` / ``included.weekly`` with
    ``remaining_percent`` values; credit plans return ``included.balance_usd``
    and ``allowance_usd``.
    """
    if not isinstance(balance, dict):
        return PLAN_CREDITS
    included = balance.get("included") or {}
    if not isinstance(included, dict):
        return PLAN_CREDITS
    if "session" in included or "weekly" in included:
        return PLAN_LEGACY
    return PLAN_CREDITS


def remaining_to_used(remaining_percent: Any) -> int | None:
    """Convert Ollama's remaining_percent (0–100) to a used percent, clamped."""
    try:
        rem = int(float(remaining_percent))
    except (TypeError, ValueError):
        return None
    used = 100 - rem
    if used < 0:
        return 0
    if used > 100:
        return 100
    return used


def compact_buckets(usage: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Shrink Ollama usage buckets to the fields the card actually renders."""
    if not isinstance(usage, dict):
        return []
    out: list[dict[str, Any]] = []
    for bucket in usage.get("buckets") or []:
        if not isinstance(bucket, dict):
            continue
        try:
            out.append(
                {
                    "from": str(bucket.get("from", "")),
                    "requests": int(bucket.get("request_count", 0) or 0),
                    "usd": float(bucket.get("usage_usd", 0.0) or 0.0),
                }
            )
        except (TypeError, ValueError):
            continue
    return out


def top_models(usage: dict[str, Any] | None, limit: int = 5) -> list[dict[str, Any]]:
    """Extract the top models from a group_by=model usage response."""
    if not isinstance(usage, dict):
        return []
    totals = usage.get("totals") or {}
    groups = totals.get("groups") if isinstance(totals, dict) else None
    if not isinstance(groups, list):
        return []
    models: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        try:
            models.append(
                {
                    "model": str(group.get("model", "")),
                    "requests": int(group.get("request_count", 0) or 0),
                    "usd": float(group.get("usage_usd", 0.0) or 0.0),
                }
            )
        except (TypeError, ValueError):
            continue
    models.sort(key=lambda m: m["usd"], reverse=True)
    return models[:limit]


def parse_timestamp(value: Any) -> datetime | None:
    """Parse ISO-8601 strings or epoch seconds into an aware UTC datetime.

    NanoGPT's ``resetAt`` may be an epoch number or an ISO string depending on
    API version — handle both defensively.
    """
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str) and value:
        text = value.strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def nanogpt_has_daily_limit(usage: dict[str, Any] | None) -> bool:
    """True if the NanoGPT account actually has a daily input token limit.

    The API always exposes ``dailyInputTokens`` fields — but on subscriptions
    without a daily quota they carry no usable limit. Only surface the daily
    ring when a real limit exists.
    """
    if not isinstance(usage, dict):
        return False
    limits = usage.get("limits")
    if not isinstance(limits, dict):
        return False
    daily = limits.get("dailyInputTokens")
    try:
        return daily is not None and float(daily) > 0
    except (TypeError, ValueError):
        return False
