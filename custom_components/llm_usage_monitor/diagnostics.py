"""Diagnostics for LLM Usage Monitor.

SECURITY: API keys are redacted in every diagnostics export. Coordinator
data contains only provider API responses (no credentials by construction),
the config entry data is redacted key-by-key.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_NANOGPT_API_KEY,
    CONF_OLLAMA_API_KEY,
    DATA_NANOGPT,
    DATA_OLLAMA,
    DOMAIN,
)

_REDACTED = "**REDACTED**"
_KEYS_TO_REDACT = (CONF_OLLAMA_API_KEY, CONF_NANOGPT_API_KEY)


def _redact(value: Any) -> Any:
    """Recursively redact configured key fields, wherever they hide."""
    if isinstance(value, dict):
        return {
            k: (_REDACTED if k in _KEYS_TO_REDACT else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data: dict[str, Any] = {"entry": {"data": _redact(dict(entry.data)), "options": _redact(dict(entry.options))}}
    if coordinator is not None and coordinator.data:
        # Only the two provider islands exist; neither stores credentials.
        data["providers"] = {
            key: coordinator.data.get(key)
            for key in (DATA_OLLAMA, DATA_NANOGPT)
            if isinstance(coordinator.data.get(key), dict)
        }
        # Defense in depth: run the redaction over the payload anyway.
        data["providers"] = _redact(data["providers"])
    return data
