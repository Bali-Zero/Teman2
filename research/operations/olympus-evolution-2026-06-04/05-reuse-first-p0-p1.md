---
date: 2026-06-04
domain: operations
client_case: none (internal infra)
component: Olympus DB Guardian — reuse-first per implementazione P0+P1
sources:
  - skill reuse-first (~/.claude/skills/reuse-first)
  - internal grep apps/backend-rag (circuit_breaker, statement_timeout, partition DROP, AlertService)
  - WebSearch asyncpg statement_timeout pattern
  - spec 04 (decisioni Antonello: 1A, 2 sì, 3 sì, 4 solo P0+P1)
author: Claude Opus 4.8 (M5 session)
status: STEP 5 (pre-implementazione) — reuse map P0+P1, NIENTE codice ancora scritto
---

# 05 — Reuse-First: cosa esiste già per P0+P1

> Eseguita la skill reuse-first PRIMA di implementare il Safety Envelope (P0) + Consume (P1).
> Risultato: **6 mattoni su 8 esistono già nel NOSTRO repo** (licenza nostra, testati). Il codice
> nuovo si riduce al collante + 2 helper triviali. Settimane → giorni, di nuovo.
> Decisioni Antonello applicate: 1A (role-narrow via W38), 2 sì (restart PG ok, ma è P2), 3 sì
> (ordine confermato), 4 solo P0+P1 primo PR.

---

## 1. Scomposizione in 8 mattoni + esito ricerca

| #     | Mattone                                                  | Esito                       | Fonte riuso                                                                                                                                              |
| ----- | -------------------------------------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1    | per-statement `statement_timeout`/`lock_timeout` asyncpg | **[SCRIVI-NUOVO triviale]** | idioma già nel repo (`service_initializer.py:520` usa `SET statement_timeout='30s'`); WebSearch conferma: `SET LOCAL` in transaction, no lib serve       |
| M2/M8 | circuit breaker pool DB                                  | **[COPIA-DIRETTO interno]** | `backend/app/core/circuit_breaker.py` (191 LOC, CLOSED/OPEN/HALF_OPEN, soglie configurabili) + test `tests/unit/core/test_circuit_breaker.py` (229 LOC)  |
| M3    | action budget per pulse                                  | **[SCRIVI-NUOVO triviale]** | logica counter + time.monotonic (già usato in pulse.py per duration_ms)                                                                                  |
| M4    | kill-switch granulare via rule flags                     | **[RIUSO INTERNO]**         | `RulesEngine.get_threshold()` esiste; pattern `DISABLE_BACKGROUND_WORKERS` esiste; basta aggiungere regole bool                                          |
| M5    | self-retention (drop partizioni + prune righe)           | **[COPIA-DIRETTO interno]** | `pulse.py:134-181` `cleanup_audit_trail` fa GIÀ DETACH+DROP partizioni mensili + DELETE per età. Identico schema per olympus_heartbeats/actions/insights |
| M6    | insight dedup/supersede                                  | **[SCRIVI-NUOVO triviale]** | colonna `superseded_by` già in schema; query SELECT-before-INSERT                                                                                        |
| M7    | weekly Telegram digest                                   | **[RIUSO INTERNO]**         | `AlertService.send_alert()` (`monitoring/alert_service.py:108`) + `OlympusAlerts` wrapper già esistono                                                   |

**Solo M1, M3, M6 sono codice nuovo, e tutti e 3 sono triviali (<20 righe ciascuno).**

---

## 2. Dettaglio riuso (con prova)

### M2/M8 — Circuit breaker [COPIA-DIRETTO]

- File: `backend/app/core/circuit_breaker.py`. Classe `CircuitBreaker` con:
  - stati `CircuitState.{CLOSED,OPEN,HALF_OPEN}`
  - `failure_threshold` (default 5), `timeout` (OPEN→HALF_OPEN), success_threshold
  - transizioni complete CLOSED→OPEN→HALF_OPEN→CLOSED
- **Licenza**: repo nostro (Teman2) → riuso libero.
- **Test**: `tests/unit/core/test_circuit_breaker.py` (229 LOC) già verde.
- **Adattamento Olympus**: istanziare un `CircuitBreaker(name="olympus-pool", failure_threshold=3,
timeout=900)` in `OlympusGuardian`; avvolgere le pool.acquire; su OPEN sospendere heartbeat+pulse.
  Filtrare per `asyncpg.InterfaceError`/`ConnectionDoesNotExistError` (cicatrix W64 fix concomitante).
- **NON serve** `backend/self_healing/circuit_breaker.py` (85 LOC, variante più semplice) — l'app/core è più completa.

### M5 — Self-retention [COPIA-DIRETTO]

- `pulse.py:cleanup_audit_trail` fa già ESATTAMENTE il pattern che serve:
  - `SELECT relkind` per capire se partizionata
  - se 'p': trova partizioni vecchie via `to_date(right(c.relname,7),'YYYY_MM') < date_trunc('month', NOW() - interval)`
  - `ALTER TABLE ... DETACH PARTITION` + `DROP TABLE`
  - se non-partizionata: `DELETE WHERE created_at < NOW() - INTERVAL`
- **Nuova azione** `cleanup_olympus_self` = stesso codice generalizzato a 3 target:
  olympus_heartbeats (partizionata → DETACH/DROP), olympus_actions (DELETE per età),
  olympus_insights (DELETE superseded OR età).
- Generalizzare `cleanup_audit_trail` in un helper `_retain_partitioned_or_delete(table, retention,
date_col)` e chiamarlo per api*audit_trail + olympus*\*. Riduce duplicazione.

### M4 — Kill-switch granulare [RIUSO INTERNO]

- `RulesEngine.get_threshold(name, default)` legge già regole DB. Aggiungere regole bool
  `olympus_enabled`, `olympus_pulse_enabled`, `olympus_heartbeat_enabled` (category 'policy').
- A inizio di `_heartbeat_loop`/`_pulse_loop`: `if not self.rules_engine.get_threshold('olympus_pulse_enabled', default=True): skip`.
- Niente codice infra nuovo, solo seed regole + 2 if.

### M7 — Telegram digest [RIUSO INTERNO]

- `OlympusAlerts.send_alert()` già instrada a `AlertService.send_alert(title, message, level)`.
- Nuova func `OlympusAlerts.send_weekly_digest(insights_summary)`: formatta markdown + chiama send_alert.
- Trigger: o azione pulse condizionata al giorno (domenica), o nuovo metodo invocato da cron esterno.
  Preferenza: dentro Olympus (un check `if now.weekday()==6 and not sent_this_week`).

### M1 — statement_timeout/lock_timeout [SCRIVI-NUOVO triviale]

- Helper: context manager async che fa `SET LOCAL statement_timeout`/`lock_timeout` su una connection
  in transaction, poi yield. ~10 righe. Pattern confermato da WebSearch (canonico, no lib).
- Default da regole: `action_statement_timeout_s=300`, `action_lock_timeout_s=5`.
- Avvolge le azioni di scrittura del pulse (vacuum, cleanup, reindex, refresh, seq-repair).

### M3 — Action budget [SCRIVI-NUOVO triviale]

- In `run_full_pulse`: counter azioni + `t_start=time.monotonic()`; dopo ogni gruppo, se
  `len(actions) >= max_actions OR elapsed > max_runtime_s` → break + append action `budget_exceeded`.
- ~8 righe. Regole `max_actions_per_pulse=50`, `max_pulse_runtime_s=600`.

### M6 — Insight dedup/supersede [SCRIVI-NUOVO triviale]

- In `_persist_insight`: prima dell'INSERT, `SELECT id FROM olympus_insights WHERE source=$1 AND
title=$2 AND superseded_by IS NULL`. Se esiste con stessa evidence → UPDATE timestamp; se evidence
  diversa → INSERT nuovo + UPDATE vecchio SET superseded_by=new_id. ~15 righe.

---

## 3. Gate licenze (passo 4 skill)

- TUTTO il riuso è **interno** (repo Teman2, licenza nostra) → nessun rischio copyleft.
- WebSearch M1: solo pattern PG documentazione ufficiale (public domain idiom), nessun codice copiato.
- **Zero dipendenze esterne nuove.** Niente lib da installare. $0.

---

## 4. Stima codice nuovo (post-riuso)

| Componente                | Righe nuove stimate         | Riuso                  |
| ------------------------- | --------------------------- | ---------------------- |
| M1 timeout helper         | ~10                         | idioma esistente       |
| M2 circuit breaker wiring | ~25 (istanzia+avvolgi)      | classe 191 LOC riusata |
| M3 budget                 | ~8                          | —                      |
| M4 kill-switch            | ~6 + seed regole            | RulesEngine            |
| M5 self-retention         | ~30 (generalizza esistente) | cleanup_audit_trail    |
| M6 dedup                  | ~15                         | colonna esistente      |
| M7 digest                 | ~20                         | AlertService           |
| migration regole nuove    | ~15 SQL                     | —                      |
| **TOTALE codice nuovo**   | **~130 righe**              | + test                 |

Senza reuse-first avrei riscritto circuit breaker (191), retention partition logic (~50), alert
plumbing (~40) = ~280 righe in più, non testate. **Reuse-first taglia ~70% come nell'esempio della skill.**

---

## 5. Piano implementazione P0+P1 (primo PR, decisione #4)

Worktree dedicato `db/olympus-safety-envelope`. Ordine:

1. Migration: regole nuove (timeout, budget, retention days, enabled flags). [M1/M3/M4/M5 config]
2. M1 timeout helper + avvolgere azioni write in pulse.py. Test PG reale.
3. M3 budget in run_full_pulse. Test (200 tabelle fittizie → stop a 50).
4. M2 circuit breaker wiring in guardian.py + W64 InterfaceError fix in TUTTI gli except. Test.
5. M4 kill-switch granulare (2 if + seed). Test.
6. M5 cleanup_olympus_self (generalizza cleanup_audit_trail). Test.
7. M6 dedup in \_persist_insight. Test (2 pulse → 1 insight).
8. M7 weekly digest. Test (markdown, no PII, ≤4000 char).
9. INV: query confidence loop, 1 paragrafo verità nel PR.
10. pytest olympus/ verde + e2e PG reale throwaway (Pro) + deploy rolling + post-deploy verify.

**Fuori da questo PR** (decisione #4 = solo P0+P1): pgss (P2.1, serve restart PG — decisione #2 sì
ma fase dopo), pgstattuple, qualify, extract. Role-narrowing M (P0.6) → decisione #1 = A = legato a
W38, quindi **non in questo PR**, si coordina con la finestra W38 (che ha anche la rotazione password
del P0 SECURITY 2026-06-03). Il PR P0+P1 NON tocca privilegi → può andare prima di W38.

---

## 6. Provenienza (passo 7 skill)

| Riuso                       | Da                  | Licenza | File                                                  |
| --------------------------- | ------------------- | ------- | ----------------------------------------------------- |
| CircuitBreaker              | repo interno Teman2 | nostra  | backend/app/core/circuit_breaker.py                   |
| retention partition pattern | repo interno        | nostra  | backend/services/olympus/pulse.py:cleanup_audit_trail |
| AlertService                | repo interno        | nostra  | backend/services/monitoring/alert_service.py          |
| RulesEngine flags           | repo interno        | nostra  | backend/services/olympus/rules_engine.py              |
| statement_timeout idiom     | PG docs (public)    | —       | (pattern, non codice)                                 |

> Pronto a implementare al via. Nessun codice scritto in questo step — solo mappa di riuso.
