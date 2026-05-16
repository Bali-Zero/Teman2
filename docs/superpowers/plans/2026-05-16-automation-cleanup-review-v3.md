---
date: 2026-05-16 (3-LLM panel, Gemini failed quota 429)
parent_plan: docs/superpowers/plans/2026-05-16-automation-cleanup-plan-v3.md
review_method: 4-LLM panel attempt (Codex empirical, Gemini quota-failed, DeepSeek empty-output, NotebookLM via sub-agent)
panelists_completed: 2 of 4 (Codex empirical + NotebookLM)
review_outcome: BLOCK (Codex 4 KILLER) but NotebookLM PASS_ARCHITECTURE — conflict on Test:-stub interpretation
total_findings: 4 KILLER + 2 NEW regression (Codex) + 2 non-blocking notes (NotebookLM)
---

# Review v3 — 3-LLM panel (1 quota-failed, 1 empty)

## Verdetto

**MIXED**:

- **Codex** (empirical filesystem access): **BLOCK** — 4 KILLER + 2 NEW regression
- **NotebookLM NB-1** (architecture authority): **PASS_ARCHITECTURE → PROCEED** con 2 non-blocking annotations
- **Gemini 3.1 Pro**: failed con 429 quota exhausted (cloudcode-pa.googleapis.com)
- **DeepSeek V4 Pro**: ha consumato tutti 8000 reasoning_tokens senza emettere testo (output vuoto, $0.01 sprecato)

Solo Codex e NB-1 hanno prodotto verdict utile. **Codex BLOCK è authoritative** perché ha verificato empirical filesystem + cita line numbers exatti.

## Codex BLOCK findings (4 KILLER + 2 regression)

### K-v3-1 — F1.2 enumeration broken (HIGH severity, blocks K6/H7)

**Trauma**: v3:226 usa `launchctl list` per enumerare LaunchAgent labels. Codex empirical check 2026-05-16: `launchctl list` ritorna 0 lines su questa macchina. Il fallback giusto è `launchctl print gui/$(id -u)` che mostra 138 scoped live agents.
**Empirical**: Codex ha enumerato via plist files + `PlistBuddy` → **19 Telegram-direct LaunchAgent pairs**, NON 25 come v3 hardcoded a riga 293.
**Fix**: sostituire enumeration source da `launchctl list` a `launchctl print gui/$(id -u)` o plist scan; aggiungere `[ $(wc -l < $TELEGRAM_DIRECT) -gt 0 ] || abort "enumeration returned 0 — check fallback"`.

### K-v3-2 — F1.3 `silent` mode INVALID, internally contradictory

**Trauma**: `FederationAlertMode` enum (verificato `apps/backend-rag/backend/services/federation_alerts/models.py:37`) accetta SOLO `observe | dry_deliberate | dry_action | production`. **`silent` non esiste**.

- v3:291 dice "no mode change"
- v3:333 e v3:335 aspettano `silent`
  **Fix**: rimuovere ogni riferimento `silent` da F1.3. Decisione architecturalmente corretta è: NESSUN cambio di `federation_alert_mode` durante cleanup (lasciare `observe`); la "pause-alerts" semantica deve essere implementata in modo diverso (es. `production` → `observe` se attualmente production; oppure non toccare il mode e lasciare che i 19 watchdog continuino direct-to-Telegram).

### K-v3-3 — F1.2 produces telegram-direct-senders.txt; F1.3 reads telegram-direct-labels.txt

**Trauma**: v3:239 scrive `$DATED_BACKUP/state/telegram-direct-senders.txt`. v3:326 legge `$DATED_BACKUP/state/telegram-direct-labels.txt`. **File path mismatch** → F1.3 legge file inesistente, output vuoto.
**Fix**: unificare in unico filename canonical (es. `telegram-direct-mapping.txt`) + label extraction esplicita (`awk -F'|' '{print $1}'`).

### K-v3-4 — F2.3 watchdog Telegram URL malformed

**Trauma**: v3:467 e v3:489 hanno `bot$TELEGRAM_BOT_TOKEN/sendMessage`. **Manca le graffe** `${...}`. Bash espande `$TELEGRAM_BOT_TOKEN/sendMessage` come variabile completa → variabile undefined → URL diventa `bot/sendMessage` → curl 404.
**Fix**: `bot${TELEGRAM_BOT_TOKEN}/sendMessage` in entrambi i punti.

### K-v3-5 — F2.3 Redis lag parsing ambiguous

**Trauma**: v3:475-482 parsa stream ID da `redis-cli XREVRANGE` output senza `--raw`. Default output di `redis-cli` ha quoting e markup che possono rompere il parsing `${LAST_ID%%-*}`.
**Fix**: `redis-cli --raw -h ... XREVRANGE organism:events + - COUNT 1 | head -1`.

### NEW regression R-v3-1 (HIGH) — PG channels count 14 vs realtà 15

**Trauma**: v3:13 + v3:708 dicono `pg_channels_total=14`. Codex empirical: `event_bus.py:46-140` mostra **15 entries** in PG_CHANNEL_MAP incluso `intel_lake_event` (presente nel codice corrente — la NB session ha contato male di 1).
**Severità**: HIGH perché F6.2 follow-up PR "13→14" sarebbe wrong direction; corretto è "13→15".

### NEW regression R-v3-2 (MEDIUM) — F0.6 `at +4h` / atrun stale

**Trauma**: v3:38 + v3:342 + v3:852 ancora citano `at +4h` + atrun daemon check. Codex empirical: `system/com.apple.atrun` NOT FOUND (modern macOS può non avere atrun loaded). v3 stesso dovrebbe quindi usare LaunchAgent runOnce. Mismatch tra "prosa F0" e "implementation reale".
**Fix**: sostituire tutto il TTL sentinel `at` con LaunchAgent `StartCalendarInterval` one-shot (pattern già usato in v3 F3.1 per pg-proxy cluster recheck).

## NotebookLM NB-1 findings (PASS con 2 non-blocking)

**Conferme architettoniche**:

1. **federation_alert_mode è canonical** — NB-1 ha negato esistenza (bundle 2026-03-23 stale) ma cross-check disk conferma `migrations_v2/147_federation_alert_proposals.sql` seeds la key. v3 corretto.
2. **25 watchdog operational guardians = NO bootout architettoricamente giusto**. NB-1 verbatim: _"Operational watchdogs and LaunchAgents send Telegram alerts DIRECTLY. If a disk-monitor or fly-restart-loop-detector attempted to route its SOS signal through the federation_alerts dispatcher during a backend outage, the alert would be silently swallowed by 503."_ Cita `heartbeat_monitor.py`, `core_guardian/watchdog.py`, `post_publish_poller.py`.
3. **F2.3 polling con TDD stub è canonicalmente accettabile**. NB-1: heartbeat-stream consumer sarebbe **anti-pattern** (SPOF su silent consumer crash), NON solo L3 grandfathering. La mia idea heartbeat-substrate è quindi architettoricamente sbagliata. v3 ha scelto giusto.
4. **F6.2 deferral è decisione corretta**.

**Non-blocking annotations**:

1. **Terminology fix**: v3 cita "L4 audit gate" ma Symbiosis Law 4 = **Graceful degradation**, NON "audit trail / Test: citations required". Corretto framing: "`lint_symbiosis_promises.py` Test: citation gate" (è uno script enforcement specifico, non Law 4 stricto sensu).
2. **F1.3 CTE+FOR UPDATE over-engineered**. Canonical pattern in `research_control.py` è `_UPSERT_SQL` (INSERT...ON CONFLICT). v3 defensive ma non idiomatic. Non-blocking: works, just inefficient on non-contended table.

## Conflict tra Codex e NB-1

| Issue                         | Codex                             | NB-1                                                          |
| ----------------------------- | --------------------------------- | ------------------------------------------------------------- |
| `silent` mode                 | INVALID — enum non lo accetta     | (non testato — NB-1 ha bundle stale, non visto migration 147) |
| F2.3 `@pytest.mark.skip` stub | FAKE-FIX L4 (non è evidence)      | TDD stub gate è acceptable per future implementation          |
| K6 strategia                  | Plan internamente contraddittorio | Decisione 25 watchdog corretta                                |

**Risoluzione**: Codex è authoritative su empirical contradiction (mode `silent` invalid, file path mismatch). NB-1 è authoritative su architectural strategy (25 watchdog, F6.2 deferral). Le conclusioni sono **compatibili** se v3 viene patched per fix le 4 KILLER mentre mantiene le 3 strategic decisions.

## Cosa fare

**v3 è BLOCKED** ma vicino al goal. Fix richiesti:

1. **K-v3-2** è il più grave: tutto F1.3 K6 va riscritto perché `silent` non è valore valido. La strategia "no mode change" è già documentata da v3 stesso → coerentizzare: cancellare ogni UPDATE su `federation_alert_mode`, lasciare `observe`, fare solo bootout-manifest documentation per i 19 (NOT 25) Telegram-direct senders.
2. **K-v3-1**: enumeration via `launchctl print gui/$(id -u)` con count fail-safe.
3. **K-v3-3**: unificare filename canonical telegram-direct-\*.txt.
4. **K-v3-4**: `${TELEGRAM_BOT_TOKEN}` braces nelle curl URL.
5. **K-v3-5**: `redis-cli --raw`.
6. **R-v3-1**: PG_CHANNEL_MAP recount → 15 (con `intel_lake_event`), F6.2 follow-up "13→15".
7. **R-v3-2**: cleanup F0.6 testo `at +4h` → LaunchAgent runOnce coerente.

**Non-blocking** (NB-1):

- Rename "L4 audit gate" → "lint_symbiosis_promises.py Test: citation gate"
- Aggiungere one-liner rationale F1.3 CTE+FOR UPDATE OR revert to UPSERT

## Costi panel v3

| Panelist        | Status         | Tokens  | Cost           | Findings                                      |
| --------------- | -------------- | ------- | -------------- | --------------------------------------------- |
| Codex GPT-5.5   | OK             | 165.814 | $0 (Plus)      | 4 KILLER + 2 regression + 5 RIGHT             |
| Gemini 3.1 Pro  | **FAIL 429**   | 0       | $0             | (quota exhausted)                             |
| DeepSeek V4 Pro | **FAIL empty** | 32.266  | $0.01 sprecato | (8000 reasoning, 0 output)                    |
| NotebookLM NB-1 | OK             | 143.618 | $0 (OAuth)     | 4 confirmed + 2 contradicted + 2 non-blocking |

## Prossimo step

**v4 plan** con 4 fix Codex KILLER + 2 regression + 2 NB-1 non-blocking integrati. Stima: 30 min lavoro (small targeted edits, NON refactor strutturale).

Oppure: **execute v3 PRO-only fases low-risk** (F4 + F5 + F2.1 + F2.2 read-only) e differire F1+F2.3+F6 al v4 fix. AIL Antonello decision.
