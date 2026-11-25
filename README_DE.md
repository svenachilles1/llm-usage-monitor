# LLM Usage Monitor

[English](README.md) · **[Deutsch](README_DE.md)**

Überwache deine **Ollama**-Cloud- und **NanoGPT**-Abo-Limits direkt in Home Assistant — Session- und Wochenlimits, Guthaben, Token-Quoten, Reset-Countdowns und Verbrauchsverlauf auf einer schönen Glassmorphism-Dashboard-Karte.

## Funktionen

### Ollama (Legacy-Pläne — Session- und Wochenlimit)

- **Session-Limit**-Ring mit genutzten Prozent und live Reset-Countdown
- **Wochenlimit**-Ring mit genutzten Prozent und live Reset-Countdown
- Gekauftes Guthaben als Sensor-Attribut

### Ollama (Credits-Pläne)

- **Guthaben** (USD) mit Allowance, genutzten Prozent und Countdown bis zum Monatsende
- Wird automatisch aus der API-Antwortstruktur erkannt — keine Konfiguration nötig

### Ollama (alle Pläne)

- **Anfragen der letzten 24 Stunden** mit stündlicher Sparkline
- **Verbrauchskosten über 7 Tage** mit Top-Modell-Aufschlüsselung

### NanoGPT

- **Wöchentliche Input-Token-Quote** — genutzt / übrig / Prozent, Reset-Countdown
- Tages-Ring nur, wenn dein Abo tatsächlich ein Tageslimit hat (die meisten haben keins — die Karte blendet es automatisch aus)
- Abo-Status-Badge, Countdown zur Abrechnungsperiode und **Gedrosselt**-Warnung

### Karte

- **Automatisch registrierte Lovelace-Karte** — keine manuelle Resource-Einrichtung, direkt aus dem Integrationsverzeichnis mit Version-Cache-Busting
- **Findet ihre Sensoren automatisch** — keine hartcodierten Entity-IDs
- Funktioniert mit **nur Ollama, nur NanoGPT oder beiden** — Kacheln erscheinen und verschwinden automatisch
- Mehrere Accounts möglich (ein Config Entry pro Key-Kombination)
- Aurora-/Glassmorphism-Familiendesign, animierter Hintergrund, Fortschrittsringe, Sparklines
- In **Deutsch und Englisch** lokalisiert (folgt der Home-Assistant-Sprache)
- Visueller Karten-Editor mit optionalen Entity-Overrides
- Fehler-Banner pro Anbieter (ungültiger Key, Verbindungsprobleme) im selben Design

## Sicherheit

Deine API-Keys werden wie Zugangsdaten behandelt, denn genau das sind sie:

- Keys liegen **ausschließlich** im Config-Entry-Storage von Home Assistant (`.storage/`, nur vom Home-Assistant-System lesbar)
- Karte und Frontend bekommen **niemals** Keys — es werden ausschließlich Sensordaten gerendert
- Keys erscheinen nie in Entity-Attributen, Logs oder Fehlermeldungen
- Home-Assistant-**Diagnose-Exporte werden automatisch redigiert**
- Alle Unit-Tests verwenden ausschließlich Fake-Keys; ein dedizierter Testfall beweist, dass abgelehnte Keys nie in Fehlermeldungen landen

## Installation

### HACS (empfohlen)

1. Füge dieses Repository in HACS als benutzerdefiniertes Repository hinzu (Kategorie: **Integration**)
2. Installiere **LLM Usage Monitor**
3. Starte Home Assistant neu

### Manuell

1. Kopiere `custom_components/llm_usage_monitor/` in dein `<config>/custom_components/`-Verzeichnis
2. Starte Home Assistant neu

## Einrichtung

1. Gehe zu **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Suche nach **LLM Usage Monitor**
3. Gib einen oder beide API-Keys ein:
   - **Ollama**: API-Key unter [ollama.com](https://ollama.com) in den Einstellungen erstellen (optional)
   - **NanoGPT**: API-Key unter [nano-gpt.com](https://nano-gpt.com) in den Einstellungen erstellen (optional)
4. Mindestens ein Key ist erforderlich; Keys werden beim Einrichten live validiert

Das Abfrage-Intervall lässt sich im **Konfigurieren**-Menü (Optionen) der Integration ändern — Standard sind 300 Sekunden, beide APIs erlauben 10 Anfragen pro Minute, sogar 60-Sekunden-Polling ist sicher.

## Karten-Setup

Füge eine manuelle Karte zum Dashboard hinzu und wähle **LLM Usage Card** (Typ: `llm-usage-card`) — sie findet ihre Sensoren automatisch. Optionale Einstellungen:

| Einstellung | Beschreibung |
| --- | --- |
| `title` | Kartentitel (Standard: *LLM Usage*) |
| `entities.ollama` | Override für den Ollama-Sensor (standardmäßig Auto-Discovery) |
| `entities.nanogpt` | Override für den NanoGPT-Sensor (standardmäßig Auto-Discovery) |

## Sensoren

| Entity | Beschreibung |
| --- | --- |
| `sensor.ollama_session_used` | Session-Limit genutzt in % (Legacy-Pläne) |
| `sensor.ollama_weekly_used` | Wochenlimit genutzt in % (Legacy-Pläne) |
| `sensor.ollama_credits_balance` | Verbleibendes Guthaben in USD (Credits-Pläne) |
| `sensor.ollama_requests_24h` | Anfragen der letzten 24 Stunden |
| `sensor.ollama_usage_7d` | Verbrauchskosten über 7 Tage in USD |
| `sensor.nanogpt_weekly_tokens_used` | Wöchentlich genutzte Input-Token |
| `sensor.nanogpt_daily_tokens_used` | Täglich genutzte Input-Token (nur wenn Tageslimit vorhanden) |
| `sensor.nanogpt_subscription` | Abo-Status (Diagnose) |

Sensor-Attribute enthalten Reset-Zeitpunkte, Restwerte, Limits, Degraded-Flags, Sparkline-Buckets und Top-Modelle — alles für Historie und Automationen.

## API-Quellen

- Ollama: Endpunkte [Cloud usage](https://docs.ollama.com/api/cloud-usage) und [Balance](https://docs.ollama.com/api/balance) (offizielle API-Keys)
- NanoGPT: Endpunkt [Subscription usage](https://docs.nano-gpt.com/api-reference/endpoint/subscription-usage) (offizielle API-Keys)

## Voraussetzungen

- Home Assistant **2024.7** oder neuer

## Lizenz

[MIT](LICENSE)
