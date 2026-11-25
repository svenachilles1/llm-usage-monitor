"""Config flow for LLM Usage Monitor.

Both API keys are optional individually — but at least one is required.
Keys are validated with a live API call before the entry is created so
users get immediate feedback.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import (
    NanoGptClient,
    OllamaClient,
    CannotConnectError,
    InvalidAuthError,
    LlmApiError,
)
from .const import (
    CONF_NANOGPT_API_KEY,
    CONF_OLLAMA_API_KEY,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    NANOGPT_BASE_URL,
    NANOGPT_USAGE_PATH,
    OLLAMA_BALANCE_PATH,
    OLLAMA_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)


def _entry_unique_id(ollama_key: str, nanogpt_key: str) -> str:
    """Stable unique id from the key combination — SHA-256, never the key itself."""
    material = f"ollama:{ollama_key.strip()}|nanogpt:{nanogpt_key.strip()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _entry_title(ollama_key: str, nanogpt_key: str) -> str:
    parts = []
    if ollama_key:
        parts.append("Ollama")
    if nanogpt_key:
        parts.append("NanoGPT")
    return " + ".join(parts) if parts else "LLM Usage Monitor"


async def _validate_keys(hass: Any, ollama_key: str, nanogpt_key: str) -> dict[str, str]:
    """Live-validate the provided keys. Returns a dict of errors (empty = ok)."""
    errors: dict[str, str] = {}
    results: dict[str, BaseException | dict] = {}

    async with aiohttp.ClientSession() as session:
        tasks: dict[str, Any] = {}
        if ollama_key:
            tasks["ollama"] = OllamaClient(ollama_key).get_balance(session)
        if nanogpt_key:
            tasks["nanogpt"] = NanoGptClient(nanogpt_key).get_subscription_usage(session)
        if tasks:
            gathered = await hass.async_create_task(_gather(*tasks.values()))
            results = dict(zip(tasks.keys(), gathered))

    for provider, result in results.items():
        if isinstance(result, InvalidAuthError):
            errors[f"{provider}_api_key"] = f"invalid_{provider}_key"
        elif isinstance(result, (CannotConnectError, LlmApiError)):
            errors["base"] = "cannot_connect"
        elif isinstance(result, BaseException):
            errors["base"] = "cannot_connect"
    return errors


async def _gather(*awaitables: Any) -> list[Any]:
    import asyncio

    return await asyncio.gather(*awaitables, return_exceptions=True)


class LlmUsageMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the LLM Usage Monitor config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 1: enter one or both API keys."""
        errors: dict[str, str] = {}

        if user_input is not None:
            ollama_key = str(user_input.get(CONF_OLLAMA_API_KEY) or "").strip()
            nanogpt_key = str(user_input.get(CONF_NANOGPT_API_KEY) or "").strip()

            if not ollama_key and not nanogpt_key:
                errors["base"] = "no_key"
            else:
                errors = await _validate_keys(self.hass, ollama_key, nanogpt_key)
                if not errors:
                    data = {
                        CONF_OLLAMA_API_KEY: ollama_key,
                        CONF_NANOGPT_API_KEY: nanogpt_key,
                    }
                    await self.async_set_unique_id(_entry_unique_id(ollama_key, nanogpt_key))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=_entry_title(ollama_key, nanogpt_key), data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_OLLAMA_API_KEY): str,
                    vol.Optional(CONF_NANOGPT_API_KEY): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LlmUsageMonitorOptionsFlow:
        return LlmUsageMonitorOptionsFlow(config_entry)


class LlmUsageMonitorOptionsFlow(OptionsFlow):
    """Options: poll interval (both APIs allow 10 req/min — 60s is the floor)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=current,
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
                }
            ),
        )
