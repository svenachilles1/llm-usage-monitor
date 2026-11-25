"""The LLM Usage Monitor integration — Ollama cloud + NanoGPT subscription."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .card_resource import async_setup_card_resource
from .const import DOMAIN, PLATFORMS
from .coordinator import LLMUsageCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LLM Usage Monitor from a config entry."""
    coordinator = LLMUsageCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Serve the bundled Lovelace card and register the dashboard resource.
    try:
        await async_setup_card_resource(hass)
    except Exception:  # noqa: BLE001 — card registration must never block setup
        _LOGGER.exception("Failed to set up LLM Usage card resource")

    # Apply poll-interval changes from the options flow without a restart.
    def _options_updated(_entry: ConfigEntry) -> None:
        coordinator.apply_new_interval()
        coordinator.async_request_refresh()

    entry.async_on_unload(entry.add_update_listener(_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
