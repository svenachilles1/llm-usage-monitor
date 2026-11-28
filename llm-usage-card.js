/**
 * LLM Usage Monitor — Lovelace Card
 * Family design: Aurora / Glassmorphism (consistent with the School Schedule card family)
 *
 * - Auto-discovers its sensors (no hardcoded entity IDs): scans hass.states for
 *   the `llm_usage_monitor` marker attribute and groups by provider + kind.
 * - Works with Ollama only, NanoGPT only, or both — tiles vanish automatically.
 * - The card NEVER holds API keys: it renders sensor data only.
 * - All dynamic values are HTML/attribute-escaped.
 */

const LLM_USAGE_VERSION = "1.0.4";

const LLM_USAGE_I18N = {
  de: {
    title: "LLM Usage",
    session: "Session",
    weekly: "Wochenlimit",
    daily: "Tageslimit",
    requests24h: "Anfragen (24 h)",
    usage7d: "Verbrauch (7 Tage)",
    resetIn: "Reset in",
    resetNow: "Reset läuft",
    used: "genutzt",
    remaining: "übrig",
    tokens: "Token",
    requests: "Anfragen",
    topModels: "Top-Modelle (7 Tage)",
    credits: "Guthaben",
    purchasedBalance: "Gekauftes Guthaben",
    planLegacy: "Legacy-Plan",
    planCredits: "Credits-Plan",
    periodUntil: "Zeitraum bis",
    active: "Aktiv",
    inactive: "Inaktiv",
    degraded: "Gedrosselt",
    noEntities: "Keine LLM Usage Entitäten gefunden",
    noEntitiesHint: "Richte die LLM Usage Monitor Integration ein (Ollama und/oder NanoGPT API-Key).",
    errorInvalidAuth: "API-Key wurde abgelehnt — Integration prüfen.",
    errorCannotConnect: "Verbindung fehlgeschlagen — Netzwerk prüfen.",
    errorApi: "Anbieter-Fehler — wird erneut versucht.",
    errorUnknown: "Unbekannter Fehler.",
    updatedAt: "Stand",
  },
  en: {
    title: "LLM Usage",
    session: "Session",
    weekly: "Weekly limit",
    daily: "Daily limit",
    requests24h: "Requests (24 h)",
    usage7d: "Usage (7 days)",
    resetIn: "Resets in",
    resetNow: "Resetting",
    used: "used",
    remaining: "left",
    tokens: "tokens",
    requests: "requests",
    topModels: "Top models (7 days)",
    credits: "Credits",
    purchasedBalance: "Purchased balance",
    planLegacy: "Legacy plan",
    planCredits: "Credits plan",
    periodUntil: "Period until",
    active: "Active",
    inactive: "Inactive",
    degraded: "Degraded",
    noEntities: "No LLM Usage entities found",
    noEntitiesHint: "Set up the LLM Usage Monitor integration (Ollama and/or NanoGPT API key).",
    errorInvalidAuth: "API key rejected — check the integration.",
    errorCannotConnect: "Connection failed — check your network.",
    errorApi: "Provider error — retrying.",
    errorUnknown: "Unknown error.",
    updatedAt: "Updated",
  },
};

function llmUsageEscHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function llmUsageEscAttr(value) {
  return llmUsageEscHtml(value);
}

function llmUsageParseTs(value) {
  if (value == null) return null;
  if (typeof value === "number") {
    const ms = value > 1e12 ? value : value * 1000;
    const d = new Date(ms);
    return isNaN(d.getTime()) ? null : d;
  }
  const s = String(value).trim();
  if (!s) return null;
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

function llmUsageCountdown(target, t) {
  const d = llmUsageParseTs(target);
  if (!d) return null;
  let ms = d.getTime() - Date.now();
  if (ms <= 0) return t.resetNow;
  const totalMin = Math.floor(ms / 60000);
  const days = Math.floor(totalMin / 1440);
  const hours = Math.floor((totalMin % 1440) / 60);
  const minutes = totalMin % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function llmUsageFmtTokens(value) {
  const n = Number(value);
  if (!isFinite(n)) return "–";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(Math.round(n));
}

function llmUsageFmtUsd(value) {
  const n = Number(value);
  if (!isFinite(n)) return "–";
  return "$" + n.toFixed(n < 10 ? 4 : 2);
}

function llmUsageRingColor(percent, amberAt, redAt) {
  if (percent == null) return "var(--llm-muted)";
  if (percent >= redAt) return "var(--llm-red)";
  if (percent >= amberAt) return "var(--llm-amber)";
  return "var(--llm-green)";
}

function llmUsageIsLight(hass) {
  // HA exposes the active mode as hass.themes.darkMode; when it is absent
  // (very old frontends) the card keeps its dark-family default.
  return !!(hass && hass.themes && hass.themes.darkMode === false);
}

function llmUsagePurchasedBalance(credits, weekly) {
  // Credit plans carry purchased_balance_usd on the credits sensor, legacy
  // plans on the weekly sensor — take whichever sensor is available.
  const sources = [];
  if (credits && credits.state !== "unavailable") sources.push(credits.attributes || {});
  if (weekly && weekly.state !== "unavailable") sources.push(weekly.attributes || {});
  for (const a of sources) {
    const n = Number(a.purchased_balance_usd);
    if (isFinite(n)) return n;
  }
  return null;
}

// --- Pure discovery helper (also used by the node test suite) ---
function llmUsageDiscover(states) {
  const found = { ollama: {}, nanogpt: {} };
  if (!states) return found;
  for (const entityId of Object.keys(states)) {
    const st = states[entityId];
    const attrs = st && st.attributes ? st.attributes : {};
    if (attrs.llm_usage_monitor !== true) continue;
    const provider = attrs.llm_usage_provider;
    const kind = attrs.llm_usage_kind;
    if (provider === "ollama" || provider === "nanogpt") {
      found[provider][kind] = st;
    }
  }
  return found;
}

class LlmUsageCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  static getConfigElement() {
    const el = document.createElement("llm-usage-card-editor");
    return el;
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._timer = null;
  }

  setConfig(config) {
    this._config = config ? Object.assign({}, config) : {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  connectedCallback() {
    // Keep reset countdowns ticking even between state updates.
    if (!this._timer) {
      this._timer = setInterval(() => this._render(), 30000);
    }
  }

  disconnectedCallback() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }

  _t(key) {
    const lang = this._hass && this._hass.locale && this._hass.locale.language
      ? String(this._hass.locale.language).slice(0, 2).toLowerCase()
      : "en";
    const table = LLM_USAGE_I18N[lang] || LLM_USAGE_I18N.en;
    return table[key] || LLM_USAGE_I18N.en[key] || key;
  }

  _num(value) {
    const n = Number(value);
    return isFinite(n) ? n : null;
  }

  _ring(percent, big, small) {
    const p = percent == null ? null : Math.max(0, Math.min(100, percent));
    const color = percent >= (this._config.red_threshold || 80)
      ? "var(--llm-red)"
      : percent >= (this._config.amber_threshold || 50)
        ? "var(--llm-amber)"
        : "var(--llm-green)";
    const valueHtml = big != null ? llmUsageEscHtml(big) : "–";
    return `
      <div class="ring" style="--p:${p == null ? 0 : p};--ring:${color}">
        <div class="ring-inner">
          <div class="ring-value">${valueHtml}</div>
          ${small ? `<div class="ring-sub">${llmUsageEscHtml(small)}</div>` : ""}
        </div>
      </div>`;
  }

  _sparkline(buckets, colorVar) {
    if (!buckets || !buckets.length) return "";
    const values = buckets.map((b) => this._num(b.requests != null ? b.requests : b.usd));
    const max = Math.max.apply(null, values);
    const bars = buckets.map((b, i) => {
      const v = values[i] == null ? 0 : values[i];
      const h = max > 0 ? Math.round((v / max) * 100) : 0;
      return `<div class="spark-bar" title="${llmUsageEscAttr(b.from || "")}: ${llmUsageEscAttr(v)}" style="height:${Math.max(h, 2)}%;"></div>`;
    }).join("");
    return `<div class="sparkline" style="--spark:${colorVar}">${bars}</div>`;
  }

  _errorBanner(t, code) {
    const map = {
      invalid_auth: t.errorInvalidAuth,
      cannot_connect: t.errorCannotConnect,
      api_error: t.errorApi,
      unknown_error: t.errorUnknown,
    };
    const text = map[code] || t.errorUnknown;
    return `<div class="banner banner-error"><ha-icon icon="mdi:alert-circle-outline"></ha-icon><span>${llmUsageEscHtml(text)}</span></div>`;
  }

  _ollamaTile(tile, t) {
    const session = tile.ollama_session;
    const weekly = tile.ollama_weekly;
    const credits = tile.ollama_credits;
    const requests = tile.ollama_requests_24h;
    const usage7d = tile.ollama_usage_7d;

    const hasLegacy = !!(session && session.state !== "unavailable") || !!(weekly && weekly.state !== "unavailable");
    const hasCredits = !!(credits && credits.state !== "unavailable");

    let rings = "";
    if (hasLegacy && session) {
      const p = this._num(session.state);
      const cd = session.attributes ? llmUsageCountdown(session.attributes.resets_at, t) : null;
      rings += `
        <div class="ring-block">
          ${this._ring(p, p != null ? p + "%" : null, t.session)}
          <div class="ring-meta">${cd ? `${llmUsageEscHtml(t.resetIn)} <b>${llmUsageEscHtml(cd)}</b>` : ""}</div>
        </div>`;
    }
    if (hasLegacy && weekly) {
      const p = this._num(weekly.state);
      const cd = weekly.attributes ? llmUsageCountdown(weekly.attributes.resets_at, t) : null;
      rings += `
        <div class="ring-block">
          ${this._ring(p, p != null ? p + "%" : null, t.weekly)}
          <div class="ring-meta">${cd ? `${llmUsageEscHtml(t.resetIn)} <b>${llmUsageEscHtml(cd)}</b>` : ""}</div>
        </div>`;
    }

    let creditsBlock = "";
    if (hasCredits && credits) {
      const a = credits.attributes || {};
      const bal = this._num(credits.state);
      const allowance = this._num(a.allowance_usd);
      const pct = allowance && bal != null && allowance > 0
        ? Math.max(0, Math.min(100, (1 - bal / allowance) * 100)) : null;
      const color = llmUsageRingColor(pct, this._config.amber_threshold || 50, this._config.red_threshold || 80);
      creditsBlock = `
        <div class="credits">
          <div class="credits-head">
            <span>${llmUsageEscHtml(t.credits)}</span>
            <b>${llmUsageEscHtml(llmUsageFmtUsd(bal))}${allowance ? ` <small>/ ${llmUsageEscHtml(llmUsageFmtUsd(allowance))}</small>` : ""}</b>
          </div>
          <div class="bar"><div class="bar-fill" style="width:${pct == null ? 0 : pct}%;background:${color};"></div></div>
          ${a.period_until ? `<div class="ring-meta">${llmUsageEscHtml(t.periodUntil)}: <b>${llmUsageEscHtml(llmUsageCountdown(a.period_until, t) || "–")}</b></div>` : ""}
        </div>`;
    }

    let statsBlock = "";
    const purchased = llmUsagePurchasedBalance(credits, weekly);
    if (purchased != null) {
      statsBlock += `
        <div class="stat-row">
          <div class="stat-label">${llmUsageEscHtml(t.purchasedBalance)}</div>
          <div class="stat-value">${llmUsageEscHtml(llmUsageFmtUsd(purchased))}</div>
        </div>`;
    }
    if (requests && requests.state !== "unavailable") {
      const a = requests.attributes || {};
      const buckets = Array.isArray(a.buckets) ? a.buckets : [];
      const usdSuffix = a.usage_usd != null ? " · " + llmUsageEscHtml(llmUsageFmtUsd(a.usage_usd)) : "";
      statsBlock += `
        <div class="stat-row">
          <div class="stat-label">${llmUsageEscHtml(t.requests24h)}</div>
          <div class="stat-value">${llmUsageEscHtml(requests.state)} ${llmUsageEscHtml(t.requests)}${usdSuffix}</div>
        </div>`;
      statsBlock += this._sparkline(buckets, "var(--llm-spark-1)");
    }
    if (usage7d && usage7d.state !== "unavailable") {
      const a = usage7d.attributes || {};
      const isUsd = a.unit_of_measurement === "USD";
      const valueHtml = isUsd
        ? llmUsageEscHtml(llmUsageFmtUsd(usage7d.state))
        : llmUsageEscHtml(usage7d.state) + " " + llmUsageEscHtml(t.requests);
      const models = Array.isArray(a.top_models) ? a.top_models : [];
      let modelsHtml = "";
      if (models.length) {
        modelsHtml = `<div class="stat-sub">${llmUsageEscHtml(t.topModels)}: ` +
          models.slice(0, 3).map((m) => llmUsageEscHtml(m.model || "?")).join(" · ") + "</div>";
      }
      statsBlock += `
        <div class="stat-row">
          <div class="stat-label">${llmUsageEscHtml(t.usage7d)}</div>
          <div class="stat-value">${valueHtml}${!isUsd ? "" : ` · ${llmUsageEscHtml(a.request_count != null ? a.request_count : "–")} ${llmUsageEscHtml(t.requests)}`}</div>
        </div>${modelsHtml}`;
    }

    const planBadge = hasLegacy ? t.planLegacy : t.planCredits;

    return `
      <div class="tile">
        <div class="tile-head">
          <div class="tile-title"><ha-icon icon="mdi:robot-outline"></ha-icon><span>${llmUsageEscHtml("Ollama")}</span></div>
          <div class="badge">${llmUsageEscHtml(planBadge)}</div>
        </div>
        ${tile.error ? this._errorBanner(t, tile.error) : ""}
        ${rings ? `<div class="ring-row">${rings}</div>` : ""}
        ${creditsBlock}
        ${statsBlock}
      </div>`;
  }

  _nanogptTile(tile, t) {
    const weekly = tile.nanogpt_weekly;
    const daily = tile.nanogpt_daily;
    const subscription = tile.nanogpt_subscription;

    let rings = "";
    if (weekly && weekly.state !== "unavailable") {
      const a = weekly.attributes || {};
      const pct = this._num(a.percent_used);
      const limit = this._num(a.limit);
      const used = this._num(weekly.state);
      const cd = llmUsageCountdown(a.reset_at, t);
      const degraded = !!a.degraded;
      rings += `
        <div class="ring-block">
          ${this._ring(pct, pct != null ? Math.round(pct) + "%" : null, t.weekly)}
          <div class="ring-meta">
            ${used != null ? `${llmUsageFmtTokens(used)} / ${llmUsageEscHtml(limit != null ? llmUsageFmtTokens(limit) : "∞")} ${llmUsageEscHtml(t.tokens)}` : ""}
          </div>
          ${cd ? `<div class="ring-meta">${llmUsageEscHtml(t.resetIn)} <b>${llmUsageEscHtml(cd)}</b></div>` : ""}
          ${degraded ? `<div class="banner banner-warn"><ha-icon icon="mdi:speedometer-slow"></ha-icon><span>${llmUsageEscHtml(t.degraded)}</span></div>` : ""}
        </div>`;
    }
    if (daily && daily.state !== "unavailable") {
      const a = daily.attributes || {};
      const pct = this._num(a.percent_used);
      const cd = llmUsageCountdown(a.reset_at, t);
      rings += `
        <div class="ring-block">
          ${this._ring(pct, pct != null ? Math.round(pct) + "%" : null, t.daily)}
          <div class="ring-meta">${llmUsageEscHtml(t.resetIn)} <b>${llmUsageEscHtml(cd || "–")}</b></div>
        </div>`;
    }

    let subBadge = "";
    let footHtml = "";
    if (subscription && subscription.state) {
      const a = subscription.attributes || {};
      const active = !!a.active;
      const stateLabel = active ? t.active : t.inactive;
      const period = a.period_end ? llmUsageCountdown(a.period_end, t) : null;
      subBadge = `<div class="badge ${active ? "badge-ok" : "badge-off"}">${llmUsageEscHtml(stateLabel)}</div>`;
      footHtml = period
        ? `${llmUsageEscHtml(t.periodUntil)}: <b>${llmUsageEscHtml(period)}</b>`
        : "";
    }

    return `
      <div class="tile">
        <div class="tile-head">
          <div class="tile-title"><ha-icon icon="mdi:atom"></ha-icon><span>${llmUsageEscHtml("NanoGPT")}</span></div>
          <div class="tile-badges">${subBadge}</div>
        </div>
        ${tile.error ? this._errorBanner(t, tile.error) : ""}
        ${rings ? `<div class="ring-row ring-row-center">${rings}</div>` : ""}
        ${footHtml ? `<div class="tile-foot">${footHtml}</div>` : ""}
      </div>`;
  }

  _render() {
    const t = this._t && this._hass ? this._t({}) : null;
    // i18n shortcut: build the full table via _t for every key we use
    const lang = this._hass && this._hass.locale && this._hass.locale.language
      ? String(this._hass.locale.language).slice(0, 2).toLowerCase() : "en";
    const T = LLM_USAGE_I18N[lang] || LLM_USAGE_I18N.en;

    const states = this._hass ? this._hass.states : null;
    const cfg = this._config || {};
    const discovered = llmUsageDiscover(states);

    // Optional explicit entity overrides (power users) — validated against markers.
    function pick(provider, overrideKey) {
      if (cfg.entities && cfg.entities[overrideKey] && states && states[cfg.entities[overrideKey]]) {
        const st = states[cfg.entities[overrideKey]];
        const attrs = st.attributes || {};
        if (attrs.llm_usage_monitor === true && attrs.llm_usage_provider === provider) {
          const merged = Object.assign({}, discovered[provider]);
          merged[attrs.llm_usage_kind] = st;
          return merged;
        }
      }
      return discovered[provider];
    }

    const ollama = pick("ollama", "ollama");
    const nanogpt = pick("nanogpt", "nanogpt");

    // Per-provider error: take it from any discovered entity of that provider.
    function providerError(provider) {
      const kinds = Object.keys(discovered[provider] || {});
      for (const kind of kinds) {
        const st = discovered[provider][kind];
        const err = st && st.attributes ? st.attributes.error : null;
        if (err) return String(err);
      }
      return null;
    }

    const ollamaError = providerError("ollama");
    const nanogptError = providerError("nanogpt");

    const hasOllama = Object.keys(ollama).length > 0;
    const hasNanogpt = Object.keys(nanogpt).length > 0;

    const title = cfg.title != null ? String(cfg.title) : T.title;

    let body = "";
    if (!hasOllama && !hasNanogpt) {
      body = `
        <div class="tile tile-empty">
          <ha-icon icon="mdi:chart-donut" class="empty-icon"></ha-icon>
          <div class="empty-text">${llmUsageEscHtml(T.noEntities)}</div>
          <div class="empty-hint">${llmUsageEscHtml(T.noEntitiesHint)}</div>
        </div>`;
    } else {
      let tiles = "";
      if (hasOllama) tiles += this._ollamaTile(Object.assign({ error: ollamaError }, ollama), T);
      if (hasNanogpt) tiles += this._nanogptTile(Object.assign({ error: nanogptError }, nanogpt), T);
      body = `<div class="grid">${tiles}</div>`;
    }

    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card class="aurora">
        <div class="aurora-bg"><div class="blob blob-1"></div><div class="blob blob-2"></div><div class="blob blob-3"></div></div>
        <div class="card-content${llmUsageIsLight(this._hass) ? " light" : ""}">
          <div class="header">
            <h1 class="title">${llmUsageEscHtml(title)}</h1>
          </div>
          ${body}
        </div>
      </ha-card>`;
  }

  _styles() {
    return `
      :host {
        display: block;
        --llm-green: #22c55e;
        --llm-amber: #f59e0b;
        --llm-red: #ef4444;
        --llm-muted: rgba(255,255,255,.28);
        --llm-spark-1: #38bdf8;
        --llm-spark-2: #a78bfa;
      }
      ha-card { display: block; border-radius: var(--ha-card-border-radius, 20px); overflow: hidden; position: relative; background: transparent; border: none; }
      * { box-sizing: border-box; }

      .aurora { position: relative; }
      .aurora-bg { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
      .blob { position: absolute; border-radius: 50%; filter: blur(48px); opacity: .45; animation: llm-drift 22s ease-in-out infinite alternate; }
      .blob-1 { width: 240px; height: 240px; background: #6366f1; top: -60px; left: -40px; }
      .blob-2 { width: 260px; height: 260px; background: #06b6d4; bottom: -80px; right: -60px; animation-delay: -7s; }
      .blob-3 { width: 200px; height: 200px; background: #a855f7; top: 30%; right: 25%; animation-delay: -14s; }
      @keyframes llm-drift {
        0% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(24px, -18px) scale(1.12); }
        100% { transform: translate(-18px, 22px) scale(.94); }
      }

      .card-content { position: relative; z-index: 1; padding: 18px; color: var(--primary-text-color, #e6edf3); }
      .header { margin-bottom: 10px; }
      .title {
        margin: 0; font-size: 1.45em; font-weight: 800; letter-spacing: .01em;
        background: linear-gradient(135deg, #7dd3fc, #a855f7 55%, #f472b6);
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent; color: transparent;
      }

      .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }

      .tile {
        background: rgba(255,255,255,.09);
        border: 1px solid rgba(255,255,255,.16);
        border-radius: 18px; padding: 14px;
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        box-shadow: 0 8px 24px rgba(0,0,0,.18);
        display: flex; flex-direction: column; gap: 10px;
      }
      :host([dark]) .tile, ha-card .tile { transition: border-color .2s ease, box-shadow .2s ease; }
      .tile:hover { border-color: rgba(255,255,255,.34); box-shadow: 0 10px 28px rgba(0,0,0,.26); }

      .tile-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
      .tile-title { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 1.05em; }
      .tile-badges { display: flex; gap: 6px; }
      .badge {
        font-size: .72em; font-weight: 700; padding: 4px 10px; border-radius: 999px;
        background: rgba(125,211,252,.18); border: 1px solid rgba(125,211,252,.35); color: var(--primary-text-color);
        white-space: nowrap;
      }
      .badge-ok { background: rgba(74,222,128,.18); border-color: rgba(74,222,128,.4); }
      .badge-off { background: rgba(248,113,113,.15); border-color: rgba(248,113,113,.4); }

      .ring-row { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }
      .ring-row-center { flex: 1 1 auto; align-items: center; }
      .ring-block { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1 1 120px; min-width: 120px; }
      .ring {
        width: 104px; height: 104px; border-radius: 50%; position: relative;
        background: conic-gradient(var(--ring) calc(var(--p) * 1%), rgba(255,255,255,.10) 0);
        display: flex; align-items: center; justify-content: center;
        transition: background .4s ease;
      }
      .ring::before {
        content: ""; position: absolute; inset: 9px; border-radius: 50%;
        background: rgba(15,18,30,.88);
      }
      .ring-inner { position: relative; z-index: 1; text-align: center; line-height: 1.15; }
      .ring-value { font-size: 1.5em; font-weight: 800; color: #f8fafc; }
      .ring-sub { font-size: .7em; margin-top: 2px; color: rgba(248,250,252,.82); }
      .ring-meta { font-size: .8em; opacity: .9; text-align: center; }
      .ring-meta b { font-weight: 700; }

      .credits { display: flex; flex-direction: column; gap: 6px; }
      .credits-head { display: flex; justify-content: space-between; align-items: baseline; font-size: .9em; }
      .bar { height: 10px; border-radius: 999px; background: rgba(255,255,255,.12); overflow: hidden; }
      .bar-fill { height: 100%; border-radius: 999px; transition: width .4s ease; }

      .stat-row { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; font-size: .85em; }
      .stat-label { opacity: .8; }
      .stat-value { font-weight: 700; text-align: right; }
      .stat-sub { font-size: .72em; opacity: .7; }

      .sparkline {
        display: flex; align-items: flex-end; gap: 2px; height: 44px;
        padding: 4px; border-radius: 10px; background: rgba(255,255,255,.06);
      }
      .spark-bar { flex: 1 1 auto; max-width: 12px; border-radius: 3px 3px 0 0; background: var(--spark); opacity: .9; min-height: 2px; }
      .spark-bar:hover { opacity: 1; }

      .banner {
        display: flex; align-items: center; gap: 8px; font-size: .8em;
        border-radius: 10px; padding: 8px 10px;
      }
      .banner-error { background: rgba(248,113,113,.16); border: 1px solid rgba(248,113,113,.38); }
      .banner-warn { background: rgba(251,191,36,.14); border: 1px solid rgba(251,191,36,.36); }

      .tile-empty { align-items: center; text-align: center; padding: 26px 18px; gap: 8px; }
      .empty-icon { --mdc-icon-size: 34px; opacity: .65; }
      .empty-text { font-weight: 700; }
      .empty-hint { font-size: .8em; opacity: .75; }

      .tile-foot { font-size: .8em; opacity: .9; }

      /* ---- Light theme (HA light mode): dark glass tint + light ring disc
             with dark percent text — keeps every value readable. ---- */
      .card-content.light { --llm-muted: rgba(15,18,30,.25); --llm-spark-1: #0284c7; }
      .card-content.light .tile {
        background: rgba(15,18,30,.05);
        border-color: rgba(15,18,30,.14);
        box-shadow: 0 8px 24px rgba(15,23,42,.10);
      }
      .card-content.light .tile:hover { border-color: rgba(15,18,30,.32); box-shadow: 0 10px 28px rgba(15,23,42,.16); }
      .card-content.light .title {
        background: linear-gradient(135deg, #0284c7, #9333ea 55%, #db2777);
        -webkit-background-clip: text; background-clip: text;
      }
      .card-content.light .ring { background: conic-gradient(var(--ring) calc(var(--p) * 1%), rgba(15,18,30,.14) 0); }
      .card-content.light .ring::before { background: rgba(248,250,252,.94); }
      .card-content.light .ring-value { color: #0f172a; }
      .card-content.light .ring-sub { color: rgba(15,23,42,.72); }
      .card-content.light .ring-meta { opacity: 1; }
      .card-content.light .sparkline { background: rgba(15,18,30,.06); }
      .card-content.light .bar { background: rgba(15,18,30,.12); }

      @media (max-width: 480px) {
        .grid { grid-template-columns: 1fr; }
      }
    `;
  }
}

class LlmUsageCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    // Fokus-Diebstahl-Guard: re-render nur einmal, danach nur Werte pflegen.
    this._config = config ? Object.assign({}, config) : {};
    this._render();
  }

  _changed(ev) {
    ev.stopPropagation();
    const value = ev.target.value;
    const key = ev.target.getAttribute("data-key");
    if (!key) return;
    const cfg = Object.assign({}, this._config);
    if (key === "title") {
      if (value && value.trim()) cfg.title = value.trim();
      else delete cfg.title;
    } else if (key === "ollama" || key === "nanogpt") {
      if (value && value.trim()) {
        cfg.entities = Object.assign({}, cfg.entities);
        cfg.entities[key] = value.trim();
      } else if (cfg.entities) {
        cfg.entities = Object.assign({}, cfg.entities);
        delete cfg.entities[key];
        if (!Object.keys(cfg.entities).length) delete cfg.entities;
      }
    }
    this._config = cfg;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: cfg },
        bubbles: true,
        composed: true,
      })
    );
  }

  _render() {
    if (this._shadow) return;
    this._shadow = true;
    const cfg = this._config;
    const esc = llmUsageEscAttr;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; padding: 12px; }
        .field { margin-bottom: 12px; display: flex; flex-direction: column; gap: 4px; }
        label { font-size: .85em; font-weight: 600; }
        input {
          padding: 8px; border-radius: 8px; border: 1px solid var(--input-border-color, #ccc);
          background: var(--input-background-color, inherit); color: var(--primary-text-color, inherit);
          font-size: .95em;
        }
      </style>
      <div class="field">
        <label for="title">Title (optional)</label>
        <input id="title" data-key="title" value="${esc(cfg.title || "")}" placeholder="LLM Usage">
      </div>
      <div class="field">
        <label for="ollama">Ollama sensor entity override (optional)</label>
        <input id="ollama" data-key="ollama" value="${esc((cfg.entities && cfg.entities.ollama) || "")}" placeholder="sensor.ollama_session_used">
      </div>
      <div class="field">
        <label for="nanogpt">NanoGPT sensor entity override (optional)</label>
        <input id="nanogpt" data-key="nanogpt" value="${esc((cfg.entities && cfg.entities.nanogpt) || "")}" placeholder="sensor.nanogpt_weekly_tokens_used">
      </div>`;
    this.shadowRoot.querySelectorAll("input").forEach((input) => {
      input.addEventListener("input", (ev) => this._changed(ev));
    });
  }
}

// Guard against double registration (HMR, partial reloads; node test harness)
if (typeof customElements !== "undefined" && !customElements.get("llm-usage-card")) {
  customElements.define("llm-usage-card", LlmUsageCard);
}
if (typeof customElements !== "undefined" && !customElements.get("llm-usage-card-editor")) {
  customElements.define("llm-usage-card-editor", LlmUsageCardEditor);
}

// Expose pure logic for the node-based test suite (no DOM required).
if (typeof module !== "undefined" && module.exports != null) {
  module.exports = {
    llmUsageEscHtml,
    llmUsageEscAttr,
    llmUsageParseTs,
    llmUsageCountdown,
    llmUsageFmtTokens,
    llmUsageFmtUsd,
    llmUsageRingColor,
    llmUsageDiscover,
    llmUsageIsLight,
    llmUsagePurchasedBalance,
    LLM_USAGE_I18N,
    LLM_USAGE_VERSION,
  };
} else if (typeof window !== "undefined") {
  window.LlmUsageCardLogic = {
    llmUsageEscHtml,
    llmUsageEscAttr,
    llmUsageParseTs,
    llmUsageCountdown,
    llmUsageFmtTokens,
    llmUsageFmtUsd,
    llmUsageRingColor,
    llmUsageDiscover,
    llmUsageIsLight,
    llmUsagePurchasedBalance,
    LLM_USAGE_I18N,
    LLM_USAGE_VERSION,
  };
}

if (typeof window !== "undefined") {
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "llm-usage-card",
    name: "LLM Usage Card",
    description: "Ollama cloud and NanoGPT subscription usage limits — session, weekly and credits at a glance.",
    preview: true,
  });
}
