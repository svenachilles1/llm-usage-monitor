"""Pytest bootstrap: stub the heavy deps so the pure logic tests run anywhere.

Importing ``custom_components.llm_usage_monitor.api`` triggers the package
``__init__`` — which imports homeassistant modules and (without HA installed)
fails. This conftest registers minimal stubs for every transitive import so
the test suite runs in bare environments and in CI (where hassfest validates
the full integration separately).
"""

from __future__ import annotations

import sys
import types


def _ensure_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


class _SubscriptableType(type):
    """Metaclass so stubbed generic classes accept ``Stub[int]``."""

    def __class_getitem__(cls, item):  # noqa: ANN001
        return cls


def _identity(value):
    return value


# --- aiohttp ---------------------------------------------------------------
try:  # pragma: no cover - aiohttp is normally installed
    import aiohttp  # noqa: F401
except ImportError:  # pragma: no cover
    aiohttp_mod = _ensure_module("aiohttp")

    class _ClientSession(metaclass=_SubscriptableType):
        pass

    class _ClientTimeout(metaclass=_SubscriptableType):
        def __init__(self, total=None):
            self.total = total

    class _ClientError(Exception):
        pass

    aiohttp_mod.ClientSession = _ClientSession
    aiohttp_mod.ClientTimeout = _ClientTimeout
    aiohttp_mod.ClientError = _ClientError

# --- voluptuous (only needed when config_flow is imported by a test) --------
if "voluptuous" not in sys.modules:  # pragma: no cover
    vol_mod = _ensure_module("voluptuous")

    class _Schema(dict):  # minimal stand-in — tests never evaluate schemas
        def __init__(self, value=None):
            super().__init__()
            self.value = value

    vol_mod.Schema = _Schema
    vol_mod.Required = _identity
    vol_mod.Optional = _identity
    vol_mod.All = _identity
    vol_mod.Coerce = _identity
    vol_mod.In = _identity
    vol_mod.Range = _identity
    vol_vol = _ensure_module("voluptuous.vol")  # internal module used by HA
    vol_vol.All = _identity

# --- homeassistant ---------------------------------------------------------
if "homeassistant" not in sys.modules:  # pragma: no cover
    ha = _ensure_module("homeassistant")
    ha.__path__ = []  # behave like a package for submodule imports

    ha_const = _ensure_module("homeassistant.const")
    ha_const.Platform = _SubscriptableType("Platform", (), {"SENSOR": "sensor"})
    ha.const = ha_const

    _ensure_module("homeassistant.config_entries").ConfigEntry = type(
        "ConfigEntry", (), {}
    )
    ce_mod = sys.modules["homeassistant.config_entries"]
    ce_mod.ConfigFlow = type("ConfigFlow", (), {})
    ce_mod.OptionsFlow = type("OptionsFlow", (), {})

    core_mod = _ensure_module("homeassistant.core")
    core_mod.HomeAssistant = type("HomeAssistant", (), {})
    core_mod.callback = _identity
    core_mod.ServiceCall = type("ServiceCall", (), {})

    _ensure_module("homeassistant.exceptions").HomeAssistantError = type(
        "HomeAssistantError", (Exception,), {}
    )

    ha_helpers = _ensure_module("homeassistant.helpers")
    dr_mod = _ensure_module("homeassistant.helpers.device_registry")
    dr_mod.DeviceEntryType = type("DeviceEntryType", (), {"SERVICE": "service"})
    ha_helpers.device_registry = dr_mod

    uc_mod = _ensure_module("homeassistant.helpers.update_coordinator")
    uc_mod.DataUpdateCoordinator = _SubscriptableType("DataUpdateCoordinator", (), {})
    uc_mod.CoordinatorEntity = _SubscriptableType("CoordinatorEntity", (), {})
    ha_helpers.update_coordinator = uc_mod

    _ensure_module("homeassistant.helpers.entity_platform").AddEntitiesCallback = object

    http_mod = _ensure_module("homeassistant.components.http")
    http_mod.StaticPathConfig = type("StaticPathConfig", (), {"__init__": lambda self, *a, **k: None})

    res_mod = _ensure_module("homeassistant.components.lovelace.resources")
    res_mod.ResourceStorageCollection = type("ResourceStorageCollection", (), {})

    sensor_mod = _ensure_module("homeassistant.components.sensor")
    sensor_mod.SensorEntity = _SubscriptableType("SensorEntity", (), {})
    sensor_mod.SensorDeviceClass = type("SensorDeviceClass", (), {"MONETARY": "monetary"})
    sensor_mod.SensorStateClass = type(
        "SensorStateClass", (), {"MEASUREMENT": "measurement", "TOTAL_INCREASING": "total_increasing"}
    )

    _ensure_module("homeassistant.data_entry_flow").FlowResult = object
