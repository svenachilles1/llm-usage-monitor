"""Constants for the LLM Usage Monitor integration."""

from __future__ import annotations

import logging
from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceEntryType

LOGGER = logging.getLogger(__package__)

DOMAIN = "llm_usage_monitor"
PLATFORMS = [Platform.SENSOR]

MANUFACTURER_OLLAMA = "Ollama"
MANUFACTURER_NANOGPT = "NanoGPT"

# --- Config keys ---
CONF_OLLAMA_API_KEY = "ollama_api_key"
CONF_NANOGPT_API_KEY = "nanogpt_api_key"
CONF_POLL_INTERVAL = "poll_interval"

DEFAULT_POLL_INTERVAL = 300  # seconds; Ollama allows 10 req/min, NanoGPT 60 req/min per key — plenty of headroom

# --- API endpoints (official, documented) ---
OLLAMA_BASE_URL = "https://ollama.com"
OLLAMA_BALANCE_PATH = "/api/balance"
OLLAMA_USAGE_PATH = "/api/usage"

NANOGPT_BASE_URL = "https://api.nano-gpt.com"
NANOGPT_USAGE_PATH = "/api/subscription/v1/usage"

API_TIMEOUT_SECONDS = 15

# --- Data keys (coordinator) ---
DATA_OLLAMA = "ollama"
DATA_NANOGPT = "nanogpt"
DATA_ERROR = "error"
DATA_LAST_SYNC = "last_sync"
DATA_PLAN = "plan"
DATA_BALANCE = "balance"
DATA_USAGE_24H = "usage_24h"
DATA_USAGE_7D = "usage_7d"
DATA_USAGE = "usage"

# --- Plan types (detected from balance response structure) ---
PLAN_LEGACY = "legacy"      # included.session + included.weekly (remaining_percent)
PLAN_CREDITS = "credits"    # included.balance_usd + allowance_usd + period

# --- Sensor kinds ---
KIND_OLLAMA_SESSION = "ollama_session"
KIND_OLLAMA_WEEKLY = "ollama_weekly"
KIND_OLLAMA_CREDITS = "ollama_credits"
KIND_OLLAMA_REQUESTS_24H = "ollama_requests_24h"
KIND_OLLAMA_USAGE_7D = "ollama_usage_7d"
KIND_NANOGPT_WEEKLY = "nanogpt_weekly"
KIND_NANOGPT_DAILY = "nanogpt_daily"
KIND_NANOGPT_SUBSCRIPTION = "nanogpt_subscription"

# --- Card discovery attributes (the card scans states for these) ---
ATTR_LLM_MARKER = "llm_usage_monitor"      # always True on our entities
ATTR_PROVIDER = "llm_usage_provider"       # "ollama" | "nanogpt"
ATTR_KIND = "llm_usage_kind"               # one of the KIND_* strings

PROVIDER_OLLAMA = "ollama"
PROVIDER_NANOGPT = "nanogpt"

# --- Card resource ---
CARD_FILE_NAME = "llm-usage-card.js"
CARD_URL_BASE = "/llm-usage-card.js"
