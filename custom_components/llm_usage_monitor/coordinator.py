"""DataUpdateCoordinator polling Ollama and NanoGPT usage endpoints.

Degraded-by-design: each provider is polled and validated independently —
if one provider fails, the other still delivers data. Provider errors are
stored in the data model (never raised) so the card can render a per-tile
error banner while the rest of the card stays alive.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import (
    NanoGptClient,
    OllamaClient,
    CannotConnectError,
    InvalidAuthError,
    LlmApiError,
    detect_ollama_plan,
)
from .const import (
    CONF_NANOGPT_API_KEY,
    CONF_OLLAMA_API_KEY,
    CONF_POLL_INTERVAL,
    DATA_BALANCE,
    DATA_ERROR,
    DATA_LAST_SYNC,
    DATA_NANOGPT,
    DATA_OLLAMA,
    DATA_PLAN,
    DATA_USAGE,
    DATA_USAGE_24H,
    DATA_USAGE_7D,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    LOGGER,
)

_LOGGER = logging.getLogger(__name__)


class LLMUsageCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator with one independent data island per provider."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.ollama_key: str | None = entry.data.get(CONF_OLLAMA_API_KEY) or None
        self.nanogpt_key: str | None = entry.data.get(CONF_NANOGPT_API_KEY) or None

        interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        interval = max(60, min(86400, interval))

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    def apply_new_interval(self) -> None:
        """Re-read the poll interval from entry options (called on options save)."""
        interval = int(self.entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        interval = max(60, min(86400, interval))
        self.update_interval = timedelta(seconds=interval)

    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            DATA_OLLAMA: {
                DATA_ERROR: None,
                DATA_LAST_SYNC: None,
                DATA_PLAN: None,
                DATA_BALANCE: None,
                DATA_USAGE_24H: None,
                DATA_USAGE_7D: None,
            },
            DATA_NANOGPT: {
                DATA_ERROR: None,
                DATA_LAST_SYNC: None,
                DATA_USAGE: None,
            },
        }
        now = datetime.now(timezone.utc).isoformat()

        tasks: dict[str, Any] = {}
        async with aiohttp.ClientSession() as session:
            if self.ollama_key:
                client = OllamaClient(self.ollama_key)
                tasks["ollama"] = asyncio.gather(
                    client.get_balance(session),
                    client.get_usage(session, range_="24h"),
                    client.get_usage(session, range_="7d", group_by_model=True),
                    return_exceptions=True,
                )
            if self.nanogpt_key:
                nclient = NanoGptClient(self.nanogpt_key)
                tasks["nanogpt"] = nclient.get_subscription_usage(session)

            results = await asyncio.gather(*tasks.values(), return_exceptions=True) if tasks else []

        by_name: dict[str, Any] = dict(zip(tasks.keys(), results))
        ollama_results = by_name.get("ollama")

        if self.ollama_key and isinstance(ollama_results, (list, tuple)):
            balance, usage_24h, usage_7d = ollama_results
            ok_parts: list[Any] = []
            err: str | None = None
            for part in (balance, usage_24h, usage_7d):
                if isinstance(part, BaseException):
                    err = _friendly_error(part)
                    _LOGGER.warning("Ollama update failed: %s", err)
                else:
                    ok_parts.append(part)
            if ok_parts:
                data[DATA_OLLAMA][DATA_LAST_SYNC] = now
            data[DATA_OLLAMA][DATA_ERROR] = err
            if not isinstance(balance, BaseException) and isinstance(balance, dict):
                data[DATA_OLLAMA][DATA_BALANCE] = balance
                data[DATA_OLLAMA][DATA_PLAN] = detect_ollama_plan(balance)
            if not isinstance(usage_24h, BaseException) and isinstance(usage_24h, dict):
                data[DATA_OLLAMA][DATA_USAGE_24H] = usage_24h
            if not isinstance(usage_7d, BaseException) and isinstance(usage_7d, dict):
                data[DATA_OLLAMA][DATA_USAGE_7D] = usage_7d

        nanogpt_result = by_name.get("nanogpt")
        if self.nanogpt_key:
            if isinstance(nanogpt_result, BaseException):
                err = _friendly_error(nanogpt_result)
                _LOGGER.warning("NanoGPT update failed: %s", err)
                data[DATA_NANOGPT][DATA_ERROR] = err
            elif isinstance(nanogpt_result, dict):
                data[DATA_NANOGPT][DATA_USAGE] = nanogpt_result
                data[DATA_NANOGPT][DATA_LAST_SYNC] = now

        return data


def _friendly_error(exc: BaseException) -> str:
    """Map exception classes to stable, key-free error codes the card renders."""
    if isinstance(exc, InvalidAuthError):
        return "invalid_auth"
    if isinstance(exc, CannotConnectError):
        return "cannot_connect"
    if isinstance(exc, LlmApiError):
        return "api_error"
    return "unknown_error"
