"""Entity-module smoke tests: import sensor.py against the stubs and assert
the HA-2026.x entity-category discipline (Enum instance, never a string)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.llm_usage_monitor import sensor as sensor_mod  # noqa: E402


def test_sensor_module_imports():
    assert hasattr(sensor_mod, "NanogptSubscriptionSensor")
    assert hasattr(sensor_mod, "OllamaUsage7dSensor")
    assert hasattr(sensor_mod, "async_setup_entry")


def test_entity_category_is_enum_not_string():
    """HA 2026.x registry rejects plain strings at async_get_or_create."""
    from homeassistant.helpers.entity import EntityCategory

    cat = sensor_mod.NanogptSubscriptionSensor._attr_entity_category
    assert cat is EntityCategory.DIAGNOSTIC, "entity_category must be the Enum instance"


def test_next_monday_utc_iso_shape():
    value = sensor_mod._next_monday_utc_iso()
    assert value is not None
    assert value.endswith("+00:00")
    assert "T00:00:00" in value
    from datetime import datetime

    parsed = datetime.fromisoformat(value)
    assert parsed.weekday() == 0, "must be a Monday"


def test_percent_from_quota():
    """NanoGPT live finding: percentUsed arrives as 0-1 ratio — we compute
    the percent ourselves from used/limit."""
    assert sensor_mod._percent_from_quota(9288744, 60000000) == 15.48
    assert sensor_mod._percent_from_quota(0, 60000000) == 0.0
    assert sensor_mod._percent_from_quota(100, 0) is None
    assert sensor_mod._percent_from_quota(None, 100) is None
    assert sensor_mod._percent_from_quota("garbage", 100) is None
