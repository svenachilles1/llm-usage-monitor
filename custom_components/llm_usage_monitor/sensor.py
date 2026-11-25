"""Sensors for Ollama cloud and NanoGPT subscription usage.

Entities are created generically based on which API keys are configured —
an Ollama-only user gets only Ollama sensors, a NanoGPT-only user only
NanoGPT sensors. No account names, no hardcoded entity IDs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import (
    compact_buckets,
    nanogpt_has_daily_limit,
    parse_timestamp,
    remaining_to_used,
    top_models,
)
from .const import (
    ATTR_KIND,
    ATTR_LLM_MARKER,
    ATTR_PROVIDER,
    CONF_NANOGPT_API_KEY,
    CONF_OLLAMA_API_KEY,
    DATA_BALANCE,
    DATA_ERROR,
    DATA_LAST_SYNC,
    DATA_PLAN,
    DATA_USAGE,
    DATA_USAGE_24H,
    DATA_USAGE_7D,
    DOMAIN,
    KIND_NANOGPT_DAILY,
    KIND_NANOGPT_SUBSCRIPTION,
    KIND_NANOGPT_WEEKLY,
    KIND_OLLAMA_CREDITS,
    KIND_OLLAMA_REQUESTS_24H,
    KIND_OLLAMA_SESSION,
    KIND_OLLAMA_USAGE_7D,
    KIND_OLLAMA_WEEKLY,
    MANUFACTURER_NANOGPT,
    MANUFACTURER_OLLAMA,
    PLAN_CREDITS,
    PLAN_LEGACY,
    PROVIDER_NANOGPT,
    PROVIDER_OLLAMA,
)
from .coordinator import LLMUsageCoordinator


def _num(value: Any, cast=float) -> Any | None:
    """Safely cast an API value, tolerating missing/broken fields."""
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> str | None:
    dt = parse_timestamp(value)
    return dt.isoformat() if dt else None


def _next_monday_utc_iso() -> str:
    """Next Monday 00:00 UTC — NanoGPT's documented weekly reset point.

    NanoGPT subscription quotas reset on the calendar (Monday 00:00 UTC);
    the API sometimes reports ``resetAt: null`` mid-period. Calculating the
    documented reset keeps the countdown running instead of dropping it.
    """
    now = datetime.now(timezone.utc)
    days = (7 - now.weekday()) % 7 or 7  # Monday=0 -> next week (today's 00:00 has passed)
    target = (now + timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return target.isoformat()


class LlmUsageSensorEntity(CoordinatorEntity[LLMUsageCoordinator], SensorEntity):
    """Base: unique_id from entry hash + kind, deterministic entity_id,
    card discovery attributes and per-provider availability."""

    _attr_should_poll = False
    provider: str
    kind: str

    def __init__(
        self,
        coordinator: LLMUsageCoordinator,
        *,
        provider: str,
        kind: str,
        suggested_object_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.provider = provider
        self.kind = kind
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{kind}"
        self._attr_suggested_object_id = suggested_object_id

    @property
    def device_info(self) -> DeviceInfo:
        manufacturer = MANUFACTURER_OLLAMA if self.provider == PROVIDER_OLLAMA else MANUFACTURER_NANOGPT
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry.unique_id}_{self.provider}")},
            name=manufacturer,
            manufacturer=manufacturer,
            model="Cloud Subscription",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _provider_data(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        return data.get(self.provider) if isinstance(data, dict) else None

    @property
    def available(self) -> bool:
        pdata = self._provider_data
        if not pdata or pdata.get(DATA_ERROR) is not None:
            return False
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        attrs: dict[str, Any] = {
            ATTR_LLM_MARKER: True,
            ATTR_PROVIDER: self.provider,
            ATTR_KIND: self.kind,
            DATA_LAST_SYNC: pdata.get(DATA_LAST_SYNC),
            DATA_ERROR: pdata.get(DATA_ERROR),
        }
        attrs.update(self._kind_attributes())
        return attrs

    def _kind_attributes(self) -> dict[str, Any]:
        return {}


class OllamaSessionUsedSensor(LlmUsageSensorEntity):
    """Legacy plans: session (rolling ~5h window) limit used, in percent."""

    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:  # friendly name; device prefix is added by HA
        return "Session Used"

    @property
    def native_value(self) -> int | None:
        pdata = self._provider_data or {}
        if pdata.get(DATA_PLAN) != PLAN_LEGACY:
            return None
        balance = pdata.get(DATA_BALANCE) or {}
        included = balance.get("included") or {}
        session = included.get("session") or {}
        return remaining_to_used(session.get("remaining_percent"))

    def _kind_attributes(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        balance = pdata.get(DATA_BALANCE) or {}
        included = balance.get("included") or {}
        session = included.get("session") or {}
        return {
            "remaining_percent": _num(session.get("remaining_percent"), int),
            "resets_at": _iso(session.get("resets_at")),
        }


class OllamaWeeklyUsedSensor(LlmUsageSensorEntity):
    """Legacy plans: weekly limit used, in percent."""

    _attr_icon = "mdi:calendar-week"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "Weekly Used"

    @property
    def native_value(self) -> int | None:
        pdata = self._provider_data or {}
        if pdata.get(DATA_PLAN) != PLAN_LEGACY:
            return None
        balance = pdata.get(DATA_BALANCE) or {}
        included = balance.get("included") or {}
        weekly = included.get("weekly") or {}
        return remaining_to_used(weekly.get("remaining_percent"))

    def _kind_attributes(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        balance = pdata.get(DATA_BALANCE) or {}
        included = balance.get("included") or {}
        weekly = included.get("weekly") or {}
        purchased = balance.get("purchased") or {}
        return {
            "remaining_percent": _num(weekly.get("remaining_percent"), int),
            "resets_at": _iso(weekly.get("resets_at")),
            "purchased_balance_usd": _num(purchased.get("balance_usd")),
        }


class OllamaCreditsBalanceSensor(LlmUsageSensorEntity):
    """Credit plans: remaining included balance, in USD."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:cash"
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "Credits Balance"

    @property
    def native_value(self) -> float | None:
        pdata = self._provider_data or {}
        if pdata.get(DATA_PLAN) != PLAN_CREDITS:
            return None
        balance = pdata.get(DATA_BALANCE) or {}
        included = balance.get("included") or {}
        return _num(included.get("balance_usd"))

    def _kind_attributes(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        balance = pdata.get(DATA_BALANCE) or {}
        included = balance.get("included") or {}
        purchased = balance.get("purchased") or {}
        allowance = _num(included.get("allowance_usd"))
        current = _num(included.get("balance_usd"))
        percent_used = None
        if allowance and current is not None and allowance > 0:
            percent_used = round(max(0.0, min(100.0, (1.0 - current / allowance) * 100.0)), 1)
        period = included.get("period") or {}
        return {
            "allowance_usd": allowance,
            "percent_used": percent_used,
            "period_from": _iso(period.get("from")),
            "period_until": _iso(period.get("until")),
            "purchased_balance_usd": _num(purchased.get("balance_usd")),
        }


class OllamaRequests24hSensor(LlmUsageSensorEntity):
    """Requests in the last 24 hours, with a compact hourly sparkline."""

    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "Requests 24h"

    @property
    def native_value(self) -> int | None:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE_24H) or {}
        totals = usage.get("totals") or {}
        return _num(totals.get("request_count"), int)

    def _kind_attributes(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE_24H) or {}
        totals = usage.get("totals") or {}
        return {
            "usage_usd": _num(totals.get("usage_usd")),
            "input_tokens": _num(totals.get("input_tokens"), int),
            "cached_input_tokens": _num(totals.get("cached_input_tokens"), int),
            "output_tokens": _num(totals.get("output_tokens"), int),
            "buckets": compact_buckets(usage),
        }


class OllamaUsage7dSensor(LlmUsageSensorEntity):
    """Usage over the last 7 days.

    Credit-metered plans report a USD cost; legacy flat-rate plans have no
    USD accounting at all (usage_usd comes back null/0 for every bucket) —
    there the sensor reports the request count instead, with unit and device
    class following the reported values.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "Usage 7d"

    @property
    def _totals(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE_7D) or {}
        totals = usage.get("totals")
        return totals if isinstance(totals, dict) else {}

    @property
    def _is_usd(self) -> bool:
        return self._totals.get("usage_usd") is not None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        return SensorDeviceClass.MONETARY if self._is_usd else None

    @property
    def native_unit_of_measurement(self) -> str:
        return "USD" if self._is_usd else "requests"

    @property
    def icon(self) -> str:
        return "mdi:currency-usd" if self._is_usd else "mdi:counter"

    @property
    def native_value(self) -> float | int | None:
        totals = self._totals
        if totals.get("usage_usd") is not None:
            return _num(totals.get("usage_usd"), float)
        return _num(totals.get("request_count"), int)

    def _kind_attributes(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE_7D) or {}
        totals = self._totals
        attrs: dict[str, Any] = {
            "request_count": _num(totals.get("request_count"), int),
            "usage_usd": _num(totals.get("usage_usd")),
            "usage_basis": "usd" if self._is_usd else "requests",
            "top_models": top_models(usage),
            "buckets": compact_buckets(usage),
        }
        if not self._is_usd:
            attrs.pop("usage_usd", None)
        return attrs


class NanogptWeeklyTokensSensor(LlmUsageSensorEntity):
    """Weekly input token usage against the subscription quota."""

    _attr_icon = "mdi:chart-bell-curve"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "Weekly Tokens Used"

    @property
    def native_value(self) -> int | None:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE) or {}
        weekly = usage.get("weeklyInputTokens") or {}
        return _num(weekly.get("used"), int)

    def _kind_attributes(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE) or {}
        weekly = usage.get("weeklyInputTokens") or {}
        limits = usage.get("limits") or {}
        api_reset = _iso(weekly.get("resetAt"))
        return {
            "remaining": _num(weekly.get("remaining"), int),
            "percent_used": _num(weekly.get("percentUsed")),
            "limit": _num(limits.get("weeklyInputTokens"), int),
            "reset_at": api_reset or _next_monday_utc_iso(),
            "reset_at_source": "api" if api_reset else "calculated",
            "degraded": bool(weekly.get("degraded", False)),
        }


class NanogptDailyTokensSensor(LlmUsageSensorEntity):
    """Daily input token usage — only created when a daily quota exists."""

    _attr_icon = "mdi:calendar-today"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "Daily Tokens Used"

    @property
    def native_value(self) -> int | None:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE) or {}
        daily = usage.get("dailyInputTokens") or {}
        return _num(daily.get("used"), int)

    def _kind_attributes(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE) or {}
        daily = usage.get("dailyInputTokens") or {}
        limits = usage.get("limits") or {}
        return {
            "remaining": _num(daily.get("remaining"), int),
            "percent_used": _num(daily.get("percentUsed")),
            "limit": _num(limits.get("dailyInputTokens"), int),
            "reset_at": _iso(daily.get("resetAt")),
            "degraded": bool(daily.get("degraded", False)),
        }


class NanogptSubscriptionSensor(LlmUsageSensorEntity):
    """Subscription state and billing-routing advice (diagnostic)."""

    _attr_icon = "mdi:card-account-details-outline"
    # HA 2026.x entity registry REQUIRES the Enum instance — a plain
    # "diagnostic" string is rejected at async_get_or_create time.
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self) -> str:
        return "Subscription"

    @property
    def native_value(self) -> str | None:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE) or {}
        state = usage.get("state")
        return str(state) if state else None

    def _kind_attributes(self) -> dict[str, Any]:
        pdata = self._provider_data or {}
        usage = pdata.get(DATA_USAGE) or {}
        period = usage.get("period") or {}
        routing = usage.get("routing") or {}
        return {
            "active": bool(usage.get("active", False)),
            "period_end": _iso(period.get("currentPeriodEnd")),
            "routing_mode": routing.get("recommendedMode"),
            "routing_reason": routing.get("reason"),
            "subscription_quota_available": bool(routing.get("subscriptionQuotaAvailable", False)),
            "paid_spend_policy_allows_balance": bool(routing.get("paidSpendPolicyAllowsBalance", False)),
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors for every configured provider."""
    coordinator: LLMUsageCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[LlmUsageSensorEntity] = []

    if coordinator.ollama_key:
        entities.extend(
            [
                OllamaSessionUsedSensor(coordinator, provider=PROVIDER_OLLAMA, kind=KIND_OLLAMA_SESSION, suggested_object_id="session_used"),
                OllamaWeeklyUsedSensor(coordinator, provider=PROVIDER_OLLAMA, kind=KIND_OLLAMA_WEEKLY, suggested_object_id="weekly_used"),
                OllamaCreditsBalanceSensor(coordinator, provider=PROVIDER_OLLAMA, kind=KIND_OLLAMA_CREDITS, suggested_object_id="credits_balance"),
                OllamaRequests24hSensor(coordinator, provider=PROVIDER_OLLAMA, kind=KIND_OLLAMA_REQUESTS_24H, suggested_object_id="requests_24h"),
                OllamaUsage7dSensor(coordinator, provider=PROVIDER_OLLAMA, kind=KIND_OLLAMA_USAGE_7D, suggested_object_id="usage_7d"),
            ]
        )

    if coordinator.nanogpt_key:
        entities.extend(
            [
                NanogptWeeklyTokensSensor(coordinator, provider=PROVIDER_NANOGPT, kind=KIND_NANOGPT_WEEKLY, suggested_object_id="weekly_tokens_used"),
                NanogptSubscriptionSensor(coordinator, provider=PROVIDER_NANOGPT, kind=KIND_NANOGPT_SUBSCRIPTION, suggested_object_id="subscription"),
            ]
        )
        nanogpt_usage = (coordinator.data or {}).get(PROVIDER_NANOGPT, {}).get(DATA_USAGE)
        if nanogpt_has_daily_limit(nanogpt_usage):
            entities.append(
                NanogptDailyTokensSensor(coordinator, provider=PROVIDER_NANOGPT, kind=KIND_NANOGPT_DAILY, suggested_object_id="daily_tokens_used")
            )

    async_add_entities(entities)
