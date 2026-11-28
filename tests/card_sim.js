/**
 * Card logic test suite — runs in plain Node, no DOM required.
 * Mirrors the school-schedule card test discipline: pure functions are
 * required() from the card file and verified in isolation.
 */

"use strict";

// --- node harness stubs (the card extends HTMLElement at definition time) ---
global.HTMLElement = class HTMLElement {};
global.customElements = {
  get: () => undefined,
  define: () => undefined,
};

const fs = require("fs");
const path = require("path");
const logic = require(path.join(__dirname, "..", "custom_components", "llm_usage_monitor", "llm-usage-card.js"));

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  PASS  ${name}`);
  } catch (err) {
    failed++;
    console.error(`  FAIL  ${name}\n        ${err && err.message ? err.message : err}`);
  }
}

function assertEq(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label || "assert"}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function assertTrue(value, label) {
  if (!value) {
    throw new Error(`${label || "assert"}: expected truthy, got ${JSON.stringify(value)}`);
  }
}

// ------------------------------------------------------------------ escapes --
test("escape: html special chars are neutralized", () => {
  const out = logic.llmUsageEscHtml('<script>alert("x")</script>');
  assertEq(out, "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", "escaped script");
  assertEq(logic.llmUsageEscHtml(null), "", "null -> empty");
  assertEq(logic.llmUsageEscHtml(undefined), "", "undefined -> empty");
});

test("escape: attribute injection is blocked", () => {
  const out = logic.llmUsageEscAttr('a" onmouseover="evil()');
  assertTrue(!out.includes('" a'), "raw quotes must not survive");
});

// --------------------------------------------------------------- discovery --
test("discover: marker entities are grouped by provider and kind", () => {
  const states = {
    "sensor.ollama_session_used": {
      entity_id: "sensor.ollama_session_used",
      state: "25",
      attributes: {
        llm_usage_monitor: true,
        llm_usage_provider: "ollama",
        llm_usage_kind: "ollama_session",
        resets_at: "2026-12-01T07:00:00+00:00",
      },
    },
    "sensor.nanogpt_weekly_tokens_used": {
      entity_id: "sensor.nanogpt_weekly_tokens_used",
      state: "12000000",
      attributes: {
        llm_usage_monitor: true,
        llm_usage_provider: "nanogpt",
        llm_usage_kind: "nanogpt_weekly",
      },
    },
    "sensor.unrelated": {
      entity_id: "sensor.unrelated",
      state: "42",
      attributes: { friendly_name: "Not ours" },
    },
  };
  const found = logic.llmUsageDiscover(states);
  assertTrue(found.ollama.ollama_session, "ollama session found");
  assertTrue(found.nanogpt.nanogpt_weekly, "nanogpt weekly found");
  assertEq(Object.keys(found.ollama).length, 1, "only ollama kinds");
  assertEq(Object.keys(found.nanogpt).length, 1, "only nanogpt kinds");
});

test("discover: empty and null states tolerated", () => {
  const found = logic.llmUsageDiscover(null);
  assertEq(Object.keys(found.ollama).length, 0, "no ollama");
  assertEq(Object.keys(found.nanogpt).length, 0, "no nanogpt");
});

// --------------------------------------------------------------- countdown --
test("countdown: future ISO timestamp renders d/h/m", () => {
  // The exact hour may shift by one minute due to test-execution latency
  // between computing the target and running the countdown — assert the
  // Nd Nh format, not a fragile to-the-minute value.
  const future = new Date(Date.now() + 3 * 86400000 + 5 * 3600000).toISOString();
  const out = logic.llmUsageCountdown(future, logic.LLM_USAGE_I18N.de);
  assertTrue(/^3d (4|5)h$/.test(out), `expected Nd Nh format, got ${out}`);
});

test("countdown: past timestamp renders resetting label", () => {
  const past = new Date(Date.now() - 3600000).toISOString();
  assertEq(logic.llmUsageCountdown(past, logic.LLM_USAGE_I18N.de), "Reset läuft", "de reset label");
  assertEq(logic.llmUsageCountdown(past, logic.LLM_USAGE_I18N.en), "Resetting", "en reset label");
});

test("countdown: epoch seconds and invalid values", () => {
  const out = logic.llmUsageCountdown(Date.now() / 1000 + 7200, logic.LLM_USAGE_I18N.en);
  assertTrue(/2h/.test(out), `epoch handled: ${out}`);
  assertEq(logic.llmUsageCountdown(null, logic.LLM_USAGE_I18N.en), null, "null tolerated");
});

// ---------------------------------------------------------------- formats --
test("format: tokens scaling k/M/B", () => {
  assertEq(logic.llmUsageFmtTokens(60000000), "60.00M", "60M tokens");
  assertEq(logic.llmUsageFmtTokens(1234), "1.2k", "1.2k");
  assertEq(logic.llmUsageFmtTokens(2500000000), "2.50B", "2.5B");
  assertEq(logic.llmUsageFmtTokens("abc"), "–", "garbage -> dash");
});

test("format: usd", () => {
  assertEq(logic.llmUsageFmtUsd(0.01718), "$0.0172", "small value 4dp");
  assertEq(logic.llmUsageFmtUsd(72.5), "$72.50", "large value 2dp");
  assertEq(logic.llmUsageFmtUsd(undefined), "–", "undefined -> dash");
});

// ------------------------------------------------------------- ring colors --
test("rings: threshold color mapping (default 50/80)", () => {
  assertEq(logic.llmUsageRingColor(10, 50, 80), "var(--llm-green)", "low");
  assertEq(logic.llmUsageRingColor(60, 50, 80), "var(--llm-amber)", "amber zone");
  assertEq(logic.llmUsageRingColor(95, 50, 80), "var(--llm-red)", "red zone");
  assertEq(logic.llmUsageRingColor(null, 50, 80), "var(--llm-muted)", "unknown");
});

// -------------------------------------------------------------------- i18n --
test("i18n: de and en expose identical keys", () => {
  const de = Object.keys(logic.LLM_USAGE_I18N.de).sort().join("|");
  const en = Object.keys(logic.LLM_USAGE_I18N.en).sort().join("|");
  assertEq(de, en, "key parity");
});

test("i18n: english is the fallback table", () => {
  assertTrue(logic.LLM_USAGE_I18N.en.weekly, "en weekly exists");
  assertTrue(logic.LLM_USAGE_I18N.de.weekly, "de weekly exists");
});

// ------------------------------------------------------- version consistency --
test("version: card version matches manifest.json", () => {
  const manifest = JSON.parse(
    fs.readFileSync(path.join(__dirname, "..", "custom_components", "llm_usage_monitor", "manifest.json"), "utf8")
  );
  assertEq(logic.LLM_USAGE_VERSION, manifest.version, "card version == manifest version");
});

// ------------------------------------------------ light mode + purchased --
test("theme: light mode detection from hass.themes.darkMode", () => {
  assertEq(logic.llmUsageIsLight({ themes: { darkMode: false } }), true, "darkMode false -> light");
  assertEq(logic.llmUsageIsLight({ themes: { darkMode: true } }), false, "darkMode true -> dark");
  assertEq(logic.llmUsageIsLight({ themes: {} }), false, "missing darkMode -> dark default");
  assertEq(logic.llmUsageIsLight({}), false, "missing themes -> dark default");
  assertEq(logic.llmUsageIsLight(null), false, "null hass -> dark default");
});

test("purchased: legacy plan reads the weekly sensor attribute", () => {
  const credits = { state: "unavailable", attributes: {} };
  const weekly = { state: "68", attributes: { purchased_balance_usd: 20 } };
  assertEq(logic.llmUsagePurchasedBalance(credits, weekly), 20, "legacy weekly attr");
});

test("purchased: credit plan prefers the credits sensor", () => {
  const credits = { state: "72.5", attributes: { purchased_balance_usd: 5.5 } };
  const weekly = { state: "unavailable", attributes: {} };
  assertEq(logic.llmUsagePurchasedBalance(credits, weekly), 5.5, "credits sensor attr");
});

test("purchased: zero is a value, garbage is not", () => {
  const zero = { state: "10", attributes: { purchased_balance_usd: 0 } };
  assertEq(logic.llmUsagePurchasedBalance(null, zero), 0, "zero is finite and shown");
  const broken = { state: "10", attributes: { purchased_balance_usd: "abc" } };
  assertEq(logic.llmUsagePurchasedBalance(null, broken), null, "garbage -> null");
  assertEq(logic.llmUsagePurchasedBalance(null, null), null, "nothing -> null");
  const un = { state: "unavailable", attributes: {} };
  assertEq(logic.llmUsagePurchasedBalance(un, un), null, "both unavailable -> null");
});

test("purchased: i18n labels exist in both languages", () => {
  assertTrue(logic.LLM_USAGE_I18N.de.purchasedBalance, "de label");
  assertTrue(logic.LLM_USAGE_I18N.en.purchasedBalance, "en label");
});

// -------------------------------------------------------------------- report --
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
