# Step 6: Failure Modes — Gemini Perspective (Comprehensive Failure Taxonomy + Circuit Breakers)

> Perspective: Gemini (Il Consigliere) — exhaustive failure catalog, detection-response tables, circuit breaker state machines, cascading failure analysis, recovery runbooks
> Date: 2026-03-28
> Depends on: Steps 1-5 (query design, sequencing, quality verification, source management, scraper integration)
> Complements: `06_failure_modes.md` (Codex perspective — invariants + defensive programming)
> Pattern reference: `scripts/circuit_breaker.py` (CLOSED/OPEN/HALF_OPEN), `apps/bali-intel-scraper/backend/core/circuit_breaker.py`

---

## 0. Design Philosophy

Six principles governing all failure responses:

1. **Degrade, never crash.** Every subsystem must produce a usable (even if reduced) output, or produce nothing silently. No subsystem failure propagates as an exception to another subsystem.
2. **Detection precedes response.** If we cannot measure it, we cannot fix it. Every failure mode has a concrete detection mechanism.
3. **Escalation is graduated.** Auto-recover first, then Telegram alert, then manual intervention. Never jump to human for something recoverable.
4. **State is sacred.** The three state files (`pipeline_state.json`, `sources.json`, `claims.jsonl`) must survive any failure. Corruption of any one is CRITICAL.
5. **Friday snapshots are insurance.** Every Friday creates a snapshot of all three state files. Recovery always starts from the most recent snapshot.
6. **Circuit breakers are per-subsystem.** NLM API, source management, and scraper integration have independent breakers. One subsystem failing does not pause the others unless cascading analysis demands it.

---

## 1. Full Failure Taxonomy (30 Failure Modes)

```
FAILURE TAXONOMY
|
+-- A. DATA QUALITY FAILURES (intelligence output is wrong or degraded)
|   +-- A1. Source Bloat (ACTIVE count exceeds targets)
|   +-- A2. Old-As-New (temporal confusion: old regulation presented as new)
|   +-- A3. Hallucination (NLM fabricates claims not supported by sources)
|   +-- A4. Stale Intelligence (sources remain active long past relevance)
|   +-- A5. Claim Drift (claim text evolves across runs, diverging from source)
|   +-- A6. Tier Misclassification (source assigned wrong authority tier)
|   +-- A7. Dedup False Negative (missed duplicate: two sources cover same content)
|   +-- A8. Dedup False Positive (wrongly merged: distinct sources consolidated)
|
+-- B. SYSTEM FAILURES (infrastructure/runtime breaks)
|   +-- B1. NLM API Error (HTTP 4xx/5xx from any NLM endpoint)
|   +-- B2. NLM API Timeout (research_status polling hangs indefinitely)
|   +-- B3. NLM Rate Limit / Throttle (silent quality degradation)
|   +-- B4. NLM Empty Result (deep research returns zero sources)
|   +-- B5. Pipeline State Corruption (pipeline_state.json unreadable)
|   +-- B6. Source Registry Corruption (nlm_nb2_sources.json unreadable)
|   +-- B7. Claims Ledger Corruption (nlm_nb2_claims.jsonl has bad lines)
|   +-- B8. Disk Full / Write Failure
|   +-- B9. OpenClaw Cron Misfire (double-fire or no-fire)
|   +-- B10. Python Runtime Error (uncaught exception in pipeline code)
|
+-- C. INTEGRATION FAILURES (cross-system handoff breaks)
|   +-- C1. Handoff File Missing (latest.json not written by pipeline)
|   +-- C2. Handoff File Corrupted (invalid JSON in latest.json)
|   +-- C3. Handoff File Stale (scraper reads old handoff)
|   +-- C4. Cross-Validation Feedback Loop (circular confidence amplification)
|   +-- C5. Scraper-to-NLM Signal Loss (scraper_to_nlm/ not read)
|   +-- C6. War Room Disconnection (NLM topics not picked up)
|   +-- C7. Symlink Race Condition (latest.json points to partial write)
|   +-- C8. Schema Version Mismatch (writer and reader disagree on format)
|
+-- D. OPERATIONAL FAILURES (budget/capacity/scheduling)
    +-- D1. API Budget Exhaustion (weekly 40-call cap hit early)
    +-- D2. Source Capacity Overflow (>70 ACTIVE despite management)
    +-- D3. Quarantine Overflow (>30 sources pending triage)
    +-- D4. Scheduling Conflict (NLM overlaps scraper or NB-1)
    +-- D5. Master Document Update Failure (source_add/delete fails for MD)
    +-- D6. Consolidation ILM Exceeds Threshold (>10% information loss)
    +-- D7. SVS Formula Drift (scoring no longer reflects real value)
    +-- D8. Cluster Rotation Skew (one or more clusters starved)
```

---

## 2. Detection-Response Tables

### 2.1 Category A: Data Quality Failures

#### A1. Source Bloat

| Attribute      | Detail                                                                                                                                                                                               |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | ACTIVE source count exceeds 70 cap or trends upward unchecked                                                                                                                                        |
| **Detection**  | `active_count` checked every pipeline run. Thresholds from Step 4 Section 5.2: SOFT at 56, HARD at 63, CAP at 70. Also: `trim_count > 30/week for 2+ weeks` = dedup broken                           |
| **Severity**   | WARNING at 56. CRITICAL at 70+                                                                                                                                                                       |
| **Impact**     | NLM synthesis quality degrades (irrelevant sources dilute context). `notebook_query` latency increases. At 600 NLM limit: `source_add` fails, pipeline halts                                         |
| **Response**   | 56: early consolidation + archive lowest-SVS Working. 63: emergency archive all Working >60d and all T5-T6 Working. 70: QUARANTINE holds, no promotions. 70+: force-archive to 55, Telegram CRITICAL |
| **Prevention** | Daily triage with strict promotion criteria. Active capacity management algorithm. Type-specific staleness decay. Weekly dedup                                                                       |

#### A2. Old-As-New (Temporal Confusion)

| Attribute      | Detail                                                                                                                                                                                                           |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | NLM returns a source about an old regulation as if it is breaking news                                                                                                                                           |
| **Detection**  | Compare `regulation_refs` against `known_regulations` set. Check `effective_date < 2024-01-01`. SimHash claims against `claims.jsonl` archive. Metric: `old_as_new_detections_per_week` -- healthy 0-2, alarm >5 |
| **Severity**   | WARNING                                                                                                                                                                                                          |
| **Impact**     | Wastes a daily query slot on known info. If not caught at triage: pollutes daily brief. Downstream: scraper may publish "breaking news" about old regulation                                                     |
| **Response**   | Automated: triage checks `known_regulations` before promotion. Source archived with reason `OLD_AS_NEW`. If escaped to brief: retract, demote, log to `query_history.jsonl`                                      |
| **Prevention** | Query templates include temporal qualifiers ("2025-2026", "terbaru"). `known_regulations` set in pipeline state. Pre-import filter rejects pub_date < 2024-01-01                                                 |

#### A3. Hallucination (NLM Fabrication)

| Attribute      | Detail                                                                                                                                                                                                                                          |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | NLM generates a finding that cites sources not actually supporting the claim, or fabricates regulation details                                                                                                                                  |
| **Detection**  | Post-query verification prompt (Step 3). Claim-source chain audit: does source actually contain the regulation ref? Cross-reference gazette: unknown regulation numbers after 48h. Metric: `hallucination_count_month` -- healthy 0-1, alarm >3 |
| **Severity**   | CRITICAL (if claim enters daily brief). WARNING (if caught at triage)                                                                                                                                                                           |
| **Impact**     | CRITICAL: false regulatory info delivered to team, possibly passed to clients. Reputational + legal risk. Scraper may amplify the hallucination                                                                                                 |
| **Response**   | Caught at triage: quarantine claim, tag `POSSIBLE_HALLUCINATION`, 72h verification window. Caught after brief: **immediate Telegram alert + retraction**. 2+ hallucinations/week: CB-NLM trips. All claims from that query run re-verified      |
| **Prevention** | Verification prompt mandatory. LEGAL_CHANGE claims without JDIH/official confirmation capped at PROVISIONAL. Cross-reference against `known_regulations`. Conservative confidence formula                                                       |

#### A4. Stale Intelligence

| Attribute      | Detail                                                                                                                                                                                                         |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Sources remain ACTIVE long after intelligence value decayed, because SVS masks staleness via early citations                                                                                                   |
| **Detection**  | Weekly audit: ACTIVE sources with `staleness_score < 0.30` but `SVS > 0.45`. Check `last_confirmed_valid` > 45 days for Working category. Metric: `avg_source_age_days` -- healthy <30, warning >45, alarm >60 |
| **Severity**   | WARNING                                                                                                                                                                                                        |
| **Impact**     | Daily briefs reference outdated operational info. MD-2 Operations Status unreliable. Stale sources waste ACTIVE slots                                                                                          |
| **Response**   | `t_effective = min(days_since_publication, days_since_last_confirmed)` catches non-cited sources. If avg_age >45: early capacity sweep. Working sources auto-archive at `S(t) < 0.20` regardless of SVS        |
| **Prevention** | Type-specific half-life decay. SVS freshness weight (0.20). Friday consolidation reviews ages. `last_confirmed_valid` reset on re-citation                                                                     |

#### A5. Claim Drift

| Attribute      | Detail                                                                                                                                                                                                                                             |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Same claim evolves across runs -- NLM paraphrases slightly each time, until final version diverges from original source                                                                                                                            |
| **Detection**  | Track claim text hash across runs in `claims.jsonl`. Same `claim_id` (regulation_ref + category + assertion_direction) with >20% edit distance from first version = `CLAIM_DRIFT`. Quarterly: sample 10 VERIFIED claims, compare to source content |
| **Severity**   | WARNING                                                                                                                                                                                                                                            |
| **Impact**     | Subtle inaccuracies accumulate in Master Documents. Confidence scores unreliable. Cross-validation unreliable                                                                                                                                      |
| **Response**   | Flag as `DRIFTED`. Pin first extracted version as canonical. Re-extract from original source in next consolidation. >5 drifted claims in same MD: trigger MD rebuild from source chain                                                             |
| **Prevention** | Claims append-only in JSONL. Consolidation uses source chain quotes, not claim paraphrases. Metadata preserves `original_extraction_date` and `original_claim_text`                                                                                |

#### A6. Tier Misclassification

| Attribute      | Detail                                                                                                                                                                                 |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Source assigned a tier higher or lower than it deserves (e.g., law firm blog as T1 instead of T5)                                                                                      |
| **Detection**  | Domain-to-tier mapping table at triage (`.go.id` must be T0-T2). If `detected_tier` vs `confirmed_tier` differ by 2+ levels: `TIER_MISMATCH`. Weekly metric: count of tier corrections |
| **Severity**   | INFO (single). WARNING (systemic, >5/week)                                                                                                                                             |
| **Impact**     | Overclassified sources inflate confidence scores. Underclassified sources prematurely archived. SVS rankings incorrect                                                                 |
| **Response**   | Automated: domain lookup overrides NLM-assigned tier. If correction changes VERIFIED to PROVISIONAL: re-issue brief correction. If systemic: review NLM metadata patterns              |
| **Prevention** | Deterministic tier for 50+ known domains. Unknown domains default T5 (conservative). NLM tier always overridden by domain lookup                                                       |

#### A7. Dedup False Negative (Missed Duplicate)

| Attribute      | Detail                                                                                                                                              |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Two sources covering same regulation from different URLs both promoted to ACTIVE                                                                    |
| **Detection**  | Weekly claim overlap analysis (Szymkiewicz-Simpson >= 0.70 between ACTIVE sources). Metric: `weekly_dedup_rate` -- if >35%: WARNING                 |
| **Severity**   | INFO (occasional). WARNING (rate >35%)                                                                                                              |
| **Impact**     | Source bloat (A1). Corroboration inflation (same article counted twice). Consolidation overhead                                                     |
| **Response**   | Weekly consolidation catches these. Rate >35%: review query templates for overlapping terms. Rate >50%: Telegram alert, emergency template redesign |
| **Prevention** | 4-level dedup (URL, title similarity, SimHash, claim overlap). Pre-import URL dedup. Title threshold 0.85                                           |

#### A8. Dedup False Positive (Wrongly Merged)

| Attribute      | Detail                                                                                                                                                                               |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**       | Two genuinely distinct sources merged because they share surface similarity but contain different intelligence                                                                       |
| **Detection**  | If `ILM > 0.05` after consolidation: claims were dropped. Post-archive audit: VERIFIED claim now has only 1 source chain after archiving the unique one. Quarterly manual spot-check |
| **Severity**   | WARNING (unique claims lost). CRITICAL (sole T0-T2 backing archived)                                                                                                                 |
| **Impact**     | Loss of unique intelligence. Claim confidence should decrease but doesn't. Master Documents may lose critical details                                                                |
| **Response**   | ILM hard gate at 0.10 prevents execution. Sole T0-T2 backing archived: immediate re-import from ARCHIVE. Claims with BONUS +0.10 protected                                           |
| **Prevention** | ILM < 0.05 as hard gate. `enforcement_divergence: true` claims never consolidated. COMPETING_INTERPRETATION tag prevents same-reg different-analysis merges                          |

---

### 2.2 Category B: System Failures

#### B1. NLM API Error (HTTP 4xx/5xx)

| Error Type          | Retries | Backoff              | Fallback               | Escalation                                             |
| ------------------- | ------- | -------------------- | ---------------------- | ------------------------------------------------------ |
| 401 Unauthorized    | 0       | N/A                  | Skip entire run        | CRITICAL Telegram: "NLM auth expired. Run `nlm login`" |
| 403 Forbidden       | 0       | N/A                  | Skip entire run        | CRITICAL Telegram: "NLM access denied"                 |
| 404 Not Found       | 0       | N/A                  | Skip operation, log    | WARNING: notebook may be deleted                       |
| 429 Rate Limited    | 3       | `Retry-After` header | Skip remaining queries | WARNING Telegram if >2x/week                           |
| 500 Server Error    | 2       | 30s exponential      | Skip query, try next   | CB-NLM if 3+ in same run                               |
| 502/503 Unavailable | 3       | 60s exponential      | Skip entire run        | CB-NLM if 2 consecutive days                           |
| Network Timeout     | 2       | 30s exponential      | Skip query             | CB-NLM if 3+ timeouts in same run                      |

**Detection:** HTTP status code != 200/201 from any NLM MCP tool call. Metric: `nlm_api_errors_today` -- threshold 3 in same run.

**Prevention:** Auth token refresh at pipeline start. Budget tracking prevents exceeding rate limits. Health check ping (`notebook_list`) at 01:00 before research calls.

#### B2. NLM API Timeout (research_status Hangs)

| Attribute      | Detail                                                                                                                                                                                                                           |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | `research_start` succeeds but `research_status` never transitions to COMPLETED                                                                                                                                                   |
| **Detection**  | Polling exceeds 10 min (600s) for deep mode. Pipeline Phase 2 or 4 exceeds 25-min hard timeout. `pipeline_state.json` shows `l1_status: RUNNING` for >30 min                                                                     |
| **Severity**   | WARNING (single). CRITICAL (2 consecutive days)                                                                                                                                                                                  |
| **Impact**     | Query produces no results. If L1 hangs past 01:30: L2 skipped or fast mode. Entire pipeline past 02:20: no handoff                                                                                                               |
| **Response**   | At 25 min: kill polling, log `task_id`. Set status `TIMED_OUT`. If L1 timed out: attempt L2 anyway. If both timeout: `pipeline_status: FAILED`. Write partial handoff if partial results exist. 2 consecutive days: CB-NLM opens |
| **Prevention** | Hard timeout at 25 min per query. Crash recovery via `task_id` polling. Budget for only 2 queries/day                                                                                                                            |

#### B3. NLM Rate Limit / Throttle (Silent Degradation)

| Throttle Signal                                 | Flag                 |
| ----------------------------------------------- | -------------------- |
| Source count < 3 on deep query (expected 15-40) | `POSSIBLY_THROTTLED` |
| Response < 100 words                            | `POSSIBLY_EMPTY`     |
| Identical response hash to yesterday            | `POSSIBLY_CACHED`    |

| Flags/Week           | Action                                               |
| -------------------- | ---------------------------------------------------- |
| 1                    | Log. No action                                       |
| 2                    | Reduce to 1 query/day for 3 days. `THROTTLE_BACKOFF` |
| 3+                   | CB-NLM opens. Pipeline PAUSED. Telegram alert        |
| After 48h pause      | CB-NLM HALF_OPEN. Run 1 test query                   |
| Test normal          | CB-NLM closes. Resume 2/day                          |
| Test still throttled | OPEN extended to 96h. Telegram alert                 |

**Prevention:** Conservative budget 2/day, never >40/week. Weekend OFF. Budget tracked in pipeline state.

#### B4. NLM Empty Result (Zero Sources Returned)

| Attribute      | Detail                                                                                                                                                                                               |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Deep Research finds zero relevant sources                                                                                                                                                            |
| **Detection**  | `research_import` returns 0. `notebook_query` returns generic/empty. Metric: `empty_results_this_week` -- healthy 0-1, alarm >2                                                                      |
| **Severity**   | INFO (single -- topic may have no news). WARNING (2+ same week)                                                                                                                                      |
| **Impact**     | No intelligence for that cluster/day. Persistent: cluster becomes dead zone                                                                                                                          |
| **Response**   | Single empty: log, proceed to L2. Both L1+L2 empty: `NO_SIGNAL_DAY`, status PARTIAL. 3+ empty in same cluster: redesign templates, Telegram INFO. All 5 clusters empty (full rotation): CB-NLM opens |
| **Prevention** | Dual-language queries (60% Bahasa, 30% English). Signal-driven follow-ups. Cluster rotation diversity                                                                                                |

#### B5. Pipeline State Corruption

| Attribute      | Detail                                                                                                                                                                                     |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**       | `nlm_nb2_pipeline_state.json` has invalid JSON, missing fields, or inconsistent state                                                                                                      |
| **Detection**  | `json.loads()` fails. Schema validation fails. Internal inconsistency (e.g., `l1_status: COMPLETED` but `l1_task_id: null`). File size 0 bytes                                             |
| **Severity**   | CRITICAL                                                                                                                                                                                   |
| **Impact**     | Cannot determine current state. Crash recovery impossible. `known_regulations` lost (A2 detection fails). Budget tracking lost (D1 risk). Cluster rotation lost (D8 risk). Hot topics lost |
| **Cascading**  | See Section 4.4                                                                                                                                                                            |
| **Response**   | Restore from Friday snapshot. If no snapshot: cold restart (Section 5.1). Telegram CRITICAL                                                                                                |
| **Prevention** | Atomic writes via temp + `os.replace()`. Pre-write JSON validation. Friday snapshots. `.bak` on every write                                                                                |

#### B6. Source Registry Corruption

| Attribute      | Detail                                                                                                                                                    |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | `nlm_nb2_sources.json` unreadable or internally inconsistent                                                                                              |
| **Detection**  | `json.loads()` fails. Count mismatch vs pipeline state. Source IDs in claims not in registry. NLM source list vs registry desync                          |
| **Severity**   | CRITICAL                                                                                                                                                  |
| **Impact**     | **Cascading chain:** dedup fails (A7) -> source bloat (A1) -> capacity overflow (D2). SVS impossible. Consolidation blocked. Master Document IDs orphaned |
| **Cascading**  | See Section 4.1                                                                                                                                           |
| **Response**   | CB-SOURCE opens immediately. Restore from Friday snapshot. Reconcile with NLM. Recalculate SVS. Process QUARANTINE backlog. Manual close of CB-SOURCE     |
| **Prevention** | Atomic writes. Friday snapshots. SHA-256 checksum in pipeline_state.json. Mutation log in `nlm_nb2_source_mutations.jsonl`                                |

#### B7. Claims Ledger Corruption

| Attribute      | Detail                                                                                                                                                                                                                          |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | `nlm_nb2_claims.jsonl` has corrupted lines, truncated entries, or inconsistent IDs                                                                                                                                              |
| **Detection**  | Line-by-line parse: any line failing `json.loads()`. Claim ID sequence gap. Claim refs nonexistent source. File size decreased                                                                                                  |
| **Severity**   | WARNING (bad lines can be skipped). CRITICAL (truncated/replaced)                                                                                                                                                               |
| **Impact**     | Corrupted lines: individual claims lost. Many lost: dedup Level 4 unreliable. Consolidation ILM unreliable. Cross-validation history incomplete                                                                                 |
| **Response**   | Bad lines: skip, log count. <5% bad: WARNING, continue. Truncated: restore Friday snapshot, re-append claims from `today` block. Missing: recreate empty, disable historical analysis until data accumulates. Telegram CRITICAL |
| **Prevention** | Append-only. `fsync()` after each append. Friday snapshots. Each line self-contained JSON                                                                                                                                       |

#### B8. Disk Full / Write Failure

| Attribute      | Detail                                                                                                                        |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Pipeline cannot write any file due to insufficient disk space                                                                 |
| **Detection**  | `OSError: [Errno 28] No space left on device`. Pre-check at start: `shutil.disk_usage()` -- warn if <500MB                    |
| **Severity**   | CRITICAL                                                                                                                      |
| **Impact**     | All state persistence fails. No handoff. Partial writes cause corruption (B5/B6/B7)                                           |
| **Response**   | Pipeline PAUSED. Auto-cleanup: delete handoff >14 days, prune mutation log >30 days. If space freed: retry. Telegram CRITICAL |
| **Prevention** | Start check: abort if <500MB, warn at <1GB. 30-day retention on handoff files. Snapshots capped at 8                          |

#### B9. OpenClaw Cron Misfire

| Misfire Type              | Detection                                             | Response                                                                               |
| ------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Double-fire               | `dedup_key` guard (hash template+cluster+date)        | Second invocation exits immediately with `DUPLICATE_RUN_BLOCKED`                       |
| No-fire                   | System Doctor (08:00) checks `last_run.date != today` | Telegram WARNING. Manual: `python nlm_nb2_pipeline.py --manual-run`                    |
| Late-fire (start > 01:30) | `started_at` in state file                            | Compressed timeouts (fast mode). If start > 02:00: skip entirely, `LATE_START_ABORTED` |

**Prevention:** Dedup guard. System Doctor 08:00 check. OpenClaw watchdog every 60s.

#### B10. Python Runtime Error

| Attribute      | Detail                                                                                                                                                                           |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Uncaught exception anywhere in pipeline Python code                                                                                                                              |
| **Detection**  | Try/except around `main()`. Exit code != 0. State shows `RUNNING` with no `completed_at`                                                                                         |
| **Severity**   | CRITICAL (persistent). WARNING (one-off)                                                                                                                                         |
| **Response**   | Outer catch writes `pipeline_status: FAILED` to state, sends Telegram with traceback. Next run: crash recovery from last consistent point. Same error 2+ days: CB-PIPELINE opens |
| **Prevention** | Per-phase try/except with phase-specific cleanup. Unit tests for all phases                                                                                                      |

---

### 2.3 Category C: Integration Failures

#### C1. Handoff File Missing

| Attribute      | Detail                                                                                          |
| -------------- | ----------------------------------------------------------------------------------------------- |
| **What**       | Pipeline ran but handoff not written (failed before Phase 6 or Phase 6 failed)                  |
| **Detection**  | Scraper: `load_nlm_handoff()` returns None. System Doctor: mtime check                          |
| **Severity**   | INFO                                                                                            |
| **Impact**     | Scraper IGNORE mode -- identical to pre-NLM behavior. **This is designed graceful degradation** |
| **Response**   | No action. Log `NLM_HANDOFF_MISSING`. If 3+ consecutive days: investigate pipeline              |
| **Prevention** | Even PARTIAL pipeline writes partial handoff                                                    |

#### C2. Handoff File Corrupted

| Attribute      | Detail                                                                                                    |
| -------------- | --------------------------------------------------------------------------------------------------------- |
| **What**       | `latest.json` exists but invalid JSON                                                                     |
| **Detection**  | `json.JSONDecodeError` in `load_nlm_handoff()`. File size <100 bytes                                      |
| **Severity**   | INFO (same fallback as C1)                                                                                |
| **Response**   | Returns None. Pipeline logs `HANDOFF_WRITE_VERIFY_FAILED` if post-write parse fails. Attempt rewrite once |
| **Prevention** | Atomic write with post-write JSON verification                                                            |

#### C3. Handoff File Stale

| Attribute     | Detail                                                                                |
| ------------- | ------------------------------------------------------------------------------------- |
| **What**      | `latest.json` valid but from previous day                                             |
| **Detection** | `file_age_hours > 24` in `load_nlm_handoff()`. Also checks `generated_at` inside JSON |
| **Severity**  | INFO                                                                                  |
| **Response**  | Returns None. Scraper IGNORE mode. 24h check is the safeguard                         |

#### C4. Cross-Validation Feedback Loop

| Attribute      | Detail                                                                                                                                                                                                                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | NLM cites a Bali Zero scraper article that was originally based on NLM findings -- circular amplification                                                                                                                                                                                         |
| **Detection**  | Pre-import: `balizero.com` in EXCLUDE_DOMAINS. Provenance: trace `original_sources` back to NLM `pipeline_run_id`. Post-hoc: convergence where all confirming articles have `nlm_finding_id` = `FEEDBACK_LOOP_DETECTED`. `is_independent_article()` excludes NLM-seeded articles from convergence |
| **Severity**   | CRITICAL                                                                                                                                                                                                                                                                                          |
| **Impact**     | Confidence becomes circular. 0.63 PROVISIONAL boosted to VERIFIED from its own derivatives. If original claim was wrong: loop entrenches error                                                                                                                                                    |
| **Response**   | `FEEDBACK_LOOP_ALERT`. All boosts from loop reverted. Affected claims revert to pre-cross-validation confidence. Telegram WARNING                                                                                                                                                                 |
| **Prevention** | `balizero.com` in domain exclusion. Provenance tagging on all claims/articles. `is_independent_article()` check. `scraper_to_nlm/` used only for query priority, never evidence                                                                                                                   |

#### C5. Scraper-to-NLM Signal Loss

| Attribute      | Detail                                                                                                 |
| -------------- | ------------------------------------------------------------------------------------------------------ |
| **What**       | `scraper_to_nlm/YYYY-MM-DD.json` not read by NLM next morning                                          |
| **Detection**  | NLM Phase 1 logs whether signal file found. If exists but `scraper_signals_read: false`: `SIGNAL_LOSS` |
| **Severity**   | INFO                                                                                                   |
| **Response**   | Continue. NLM queries work without signals. If persistent >3 days: check path, permissions             |
| **Prevention** | Well-known path. Atomic writes. Signal file optional                                                   |

#### C6. War Room Disconnection

| Attribute     | Detail                                                                                          |
| ------------- | ----------------------------------------------------------------------------------------------- |
| **What**      | War Room doesn't read NLM suggested_topics even when available and fresh                        |
| **Detection** | War Room logs NLM selection. If `NLM_AVAILABLE=true` but `NLM_TOPIC=""` for >5 consecutive days |
| **Severity**  | INFO                                                                                            |
| **Response**  | Gemini fallback. Review NLM topic quality if persistent                                         |

#### C7. Symlink Race Condition

| Attribute      | Detail                                                                          |
| -------------- | ------------------------------------------------------------------------------- |
| **What**       | Scraper reads `latest.json` while NLM updates symlink, hitting a partial write  |
| **Detection**  | `json.JSONDecodeError` plus file mtime within last 60s                          |
| **Severity**   | INFO (extremely rare)                                                           |
| **Response**   | Returns None. 40-minute buffer makes this nearly impossible in practice         |
| **Prevention** | Write dated file -> `fsync()` -> update symlink (last operation). 40-min buffer |

#### C8. Schema Version Mismatch

| Attribute      | Detail                                                                                                         |
| -------------- | -------------------------------------------------------------------------------------------------------------- |
| **What**       | NLM writes handoff v2 but scraper expects v1                                                                   |
| **Detection**  | `version` field check in `load_nlm_handoff()`                                                                  |
| **Severity**   | WARNING (first). CRITICAL (persists)                                                                           |
| **Response**   | Telegram WARNING. Dual-write: `latest.json` (v2) + `latest_v1.json` (v1 compat) for 30 days                    |
| **Prevention** | Additive-only schema changes. Reader tolerance (ignores unknown fields). 30-day dual-write on breaking changes |

---

### 2.4 Category D: Operational Failures

#### D1. API Budget Exhaustion

| Attribute      | Detail                                                                                                                                       |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Weekly 40-call or monthly 160-call limit reached                                                                                             |
| **Detection**  | `budget.week_calls >= 40` at pipeline start. Proactive: `week_calls >= 35` on Wednesday = `BUDGET_WARNING`                                   |
| **Severity**   | WARNING                                                                                                                                      |
| **Response**   | Auto-skip queries, `pipeline_status: BUDGET_EXHAUSTED`. If hit by Wednesday: review (too many overrides?). Reset: weekly Monday, monthly 1st |
| **Prevention** | Conservative 2/day (10/week << 40 cap). Afternoon follow-ups conditional. Override replaces, doesn't add                                     |

#### D2. Source Capacity Overflow (>70 ACTIVE)

| Attribute      | Detail                                                                                                                            |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | ACTIVE exceeds 70 despite capacity management                                                                                     |
| **Detection**  | `active_count > 70`. Should never happen if management works                                                                      |
| **Severity**   | CRITICAL (indicates capacity management bug)                                                                                      |
| **Response**   | Force-archive all EXPENDABLE. Force-archive all Working >60d. Force lowest-SVS until N <= 55. Telegram CRITICAL. Review algorithm |
| **Prevention** | CAP at 70 prevents promotion. HARD at 63 triggers emergency. SOFT at 56 triggers early consolidation                              |

#### D3. Quarantine Overflow (>30 Pending)

| Attribute      | Detail                                                                                   |
| -------------- | ---------------------------------------------------------------------------------------- |
| **What**       | >30 sources in QUARANTINE awaiting triage                                                |
| **Detection**  | Quarantine count > 30 at pipeline start                                                  |
| **Severity**   | WARNING                                                                                  |
| **Response**   | Oldest-first extended triage. Sources >48h: auto-discard with `QUARANTINE_SLA_BREACH`    |
| **Prevention** | Daily triage (weekdays). Monday handles weekend backlog. Pre-import filter catches noise |

#### D4. Scheduling Conflict

| Attribute      | Detail                                                                                         |
| -------------- | ---------------------------------------------------------------------------------------------- |
| **What**       | NLM pipeline overlaps with scraper (03:00) or NB-1 (04:30)                                     |
| **Detection**  | Start check: is scraper running? Completion check: done by 02:20?                              |
| **Severity**   | WARNING (overruns buffer). CRITICAL (overlaps scraper)                                         |
| **Response**   | Not done by 02:20: hard abort, write partial handoff. Scraper already running: pipeline yields |
| **Prevention** | 40-min buffer. Hard timeout at 02:20. NB-1 at 04:30 -- no overlap by design                    |

#### D5. Master Document Update Failure

| Attribute      | Detail                                                                                                                                             |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Cannot update MD-1 through MD-4 (source_add/delete fails)                                                                                          |
| **Detection**  | API error on MD operations. MD `last_updated > 7 days`                                                                                             |
| **Severity**   | WARNING (single MD). CRITICAL (MD-1 Change Log, 2+ consecutive days)                                                                               |
| **Response**   | Retry once at 30s. If fails: keep OLD version (never delete without replacement). Next run: prioritize MD update. MD-1 fails 2d: Telegram CRITICAL |
| **Prevention** | Update: add new -> verify -> delete old. Never delete before add confirmed. MD sources have ESSENTIAL SVS, never auto-archived                     |

#### D6. Consolidation ILM Exceeds Threshold

| Attribute      | Detail                                                                                                                                                           |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | >10% of unique claims would be lost in consolidation                                                                                                             |
| **Detection**  | `ILM = 1 - (digest_claims / original_claims)` calculated pre-execution                                                                                           |
| **Severity**   | WARNING                                                                                                                                                          |
| **Impact**     | Consolidation blocked. Originals stay ACTIVE. Persistent: capacity grows (cascading to D2)                                                                       |
| **Response**   | ILM 0.05-0.10: proceed with logging. >0.10: REJECT, originals stay. 2+ consecutive Fridays: Telegram WARNING. 3+: CB-SOURCE trips                                |
| **Prevention** | Hard gate at 0.10. VERIFIED/PROVISIONAL claims always preserved. `enforcement_divergence` claims always preserved. Consolidation requires N>=4, age>=14d, cooled |

#### D7. SVS Formula Drift

| Attribute      | Detail                                                                                                                                                                               |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**       | SVS no longer accurately reflects source value                                                                                                                                       |
| **Detection**  | Quarterly: SVS rankings vs manual expert assessment. Signal: ESSENTIAL sources never cited (V_citations=0 for 30+d). Signal: EXPENDABLE sources are sole backing for VERIFIED claims |
| **Severity**   | INFO (quarterly review)                                                                                                                                                              |
| **Response**   | Recalibrate weights. If ESSENTIAL uncited: reduce V_tier weight, increase V_citations. If EXPENDABLE sole-backing: increase V_uniqueness                                             |
| **Prevention** | NHS includes diversity and citation metrics. Weekly Telegram surfaces patterns. Balanced weights                                                                                     |

#### D8. Cluster Rotation Skew

| Attribute      | Detail                                                                                                                                       |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**       | Clusters consistently skipped due to overrides, failures, or budget exhaustion                                                               |
| **Detection**  | `last_cluster_run` -- any cluster >14 days ago = `CLUSTER_STARVED`. Weekly: all 5 clusters should run                                        |
| **Severity**   | WARNING                                                                                                                                      |
| **Response**   | Starved >14d: force-schedule next available day. Override auto-decays 72h (prevents permanent skew). Pushed queries rescheduled, not dropped |
| **Prevention** | 72h auto-decay on overrides. Pushed queries rescheduled. Friday reviews cluster coverage                                                     |

---

## 3. Circuit Breaker State Machines

### 3.1 Architecture: Three Independent Breakers

```
+---------------------------------------------------------------------+
|                    NLM NB-2 CIRCUIT BREAKERS                         |
|                                                                      |
|  +----------------+    +------------------+    +-------------------+ |
|  |  CB-NLM        |    |  CB-SOURCE       |    |  CB-INTEGRATION   | |
|  |  NLM API       |    |  Source Mgmt     |    |  Scraper Handoff  | |
|  |  health        |    |  state files     |    |  cross-validation | |
|  |  Auto-test 48h |    |  MANUAL close    |    |  Auto-test 48h    | |
|  +----------------+    +------------------+    +-------------------+ |
|                                                                      |
|  State file: ~/.agent/decisions/circuit_breakers.json                |
|  (shared with Drive polling and other pipeline breakers)             |
+---------------------------------------------------------------------+
```

### 3.2 CB-NLM: NLM API Health

**Protects:** All NLM API calls (research_start, research_status, research_import, notebook_query, source_add, source_delete).

**State machine:**

```
                      success
            +------------------------+
            |                        |
            v                        |
      +----------+             +----------+
 +--->|  CLOSED  |-- trip ---->|   OPEN   |
 |    | (normal) |             | (paused) |
 |    +----------+             +----+-----+
 |         ^                        |
 |         | test succeeds     48h timeout
 |         |                        |
 |    +----+------+                 |
 |    | HALF_OPEN |<----------------+
 |    | (testing) |
 |    +----+------+
 |         |
 |    test fails --> OPEN (extend to 96h)
 +---------+
   (after subsequent test success)
```

**Trip conditions (CLOSED -> OPEN):**

| #   | Condition                       | Threshold                                       |
| --- | ------------------------------- | ----------------------------------------------- |
| 1   | API errors in same pipeline run | 3+ errors (4xx/5xx)                             |
| 2   | Consecutive daily timeouts      | 2 consecutive days with research_status timeout |
| 3   | Throttle confirmed              | 3+ throttle flags in same week                  |
| 4   | Hallucination cluster           | 2+ hallucination detections in same week        |
| 5   | Auth failure                    | Any 401/403 (immediate OPEN)                    |
| 6   | Empty results full rotation     | All 5 weekday clusters return empty             |

**OPEN behavior:**

- Pipeline starts but skips ALL NLM API calls
- `pipeline_status: CIRCUIT_BREAKER_OPEN`
- No handoff generated. Scraper in IGNORE mode.
- Budget counter frozen (paused days don't count)
- Telegram: "CB-NLM OPEN: {trip_reason}. Auto-test in 48h."

**HALF_OPEN test (after 48h):**

1. Single L1 query in fast mode
2. Pass criteria: >= 3 sources AND >= 100 words AND no API errors
3. Pass -> CLOSED. Resume normal 2-query schedule tomorrow.
4. Fail -> OPEN extended to 96h. Telegram update.

**Maximum OPEN:** 7 days. After 7 days without successful test: Telegram CRITICAL for manual investigation.

### 3.3 CB-SOURCE: Source Management Health

**Protects:** Source registry integrity, SVS, capacity management, consolidation, dedup.

**Trip conditions:**

| #   | Condition                                 |
| --- | ----------------------------------------- |
| 1   | Registry corruption (B6)                  |
| 2   | Registry-NLM desync (delta > 5 sources)   |
| 3   | Capacity overflow despite management (D2) |
| 4   | ILM > 0.10 for 3 consecutive Fridays (D6) |

**OPEN behavior:**

- NLM queries still run (CB-NLM is independent)
- Source triage DISABLED -- all sources stay in QUARANTINE
- No consolidation, no archival, no SVS calculations
- Telegram CRITICAL: "CB-SOURCE OPEN: Manual intervention required."

**Recovery (requires manual close):**

1. Restore registry from Friday snapshot
2. Reconcile with NLM source list
3. Full SVS recalculation
4. Triage accumulated QUARANTINE
5. Operator confirms: close CB-SOURCE

**Why manual?** Source registry corruption can cause silent data quality issues. Auto-close risks resuming with inconsistent state.

### 3.4 CB-INTEGRATION: Scraper Integration Health

**Protects:** Handoff integrity, cross-validation, feedback loop prevention.

**Trip conditions:**

| #   | Condition                                        |
| --- | ------------------------------------------------ |
| 1   | Feedback loop detected (C4)                      |
| 2   | Handoff corruption 3+ consecutive days (C2)      |
| 3   | Cross-validation overflow (scores > 0.95 or < 0) |

**OPEN behavior:**

- Pipeline runs normally but skips Phase 6 (handoff)
- Scraper permanent IGNORE mode
- Cross-validation disabled
- War Room uses Gemini-only
- Telegram WARNING

**HALF_OPEN test (after 48h):**

1. Write test handoff package
2. Verify JSON valid and schema correct
3. Verify provenance tagging active
4. If loop triggered: verify `balizero.com` in EXCLUDE_DOMAINS
5. Pass -> CLOSED

### 3.5 Interaction Matrix

| CB-NLM | CB-SOURCE | CB-INTEGRATION | Pipeline Behavior                                                              |
| ------ | --------- | -------------- | ------------------------------------------------------------------------------ |
| CLOSED | CLOSED    | CLOSED         | **Normal operation**                                                           |
| OPEN   | CLOSED    | CLOSED         | No queries. Source mgmt on existing. No handoff                                |
| CLOSED | OPEN      | CLOSED         | Queries run. Sources pile in QUARANTINE. Handoff has findings but no lifecycle |
| CLOSED | CLOSED    | OPEN           | Queries run. Sources managed. No handoff. Scraper IGNORE                       |
| OPEN   | OPEN      | \*             | **Pipeline effectively dead.** Telegram CRITICAL                               |
| \*     | OPEN      | OPEN           | Source + integration down. Only queries produce output                         |
| OPEN   | OPEN      | OPEN           | **Full stop.** Telegram CRITICAL: "All breakers open"                          |

**Cascading rules:**

- CB-NLM OPEN >5 days -> CB-SOURCE should trip (no new sources, lifecycle stalls)
- CB-SOURCE OPEN >7 days -> CB-INTEGRATION should trip (stale registry makes handoff unreliable)
- CB-INTEGRATION OPEN does NOT cascade (integration is independent enrichment)

### 3.6 State Storage

In existing `~/.agent/decisions/circuit_breakers.json`:

```json
{
  "nlm_nb2_api": {
    "state": "CLOSED",
    "failure_count": 0,
    "opened_at": null,
    "last_test_at": null,
    "trip_reason": null,
    "trip_count_total": 0,
    "last_trip_at": null,
    "open_timeout_s": 172800
  },
  "nlm_nb2_source": {
    "state": "CLOSED",
    "failure_count": 0,
    "opened_at": null,
    "last_test_at": null,
    "trip_reason": null,
    "requires_manual_close": true,
    "trip_count_total": 0,
    "last_trip_at": null
  },
  "nlm_nb2_integration": {
    "state": "CLOSED",
    "failure_count": 0,
    "opened_at": null,
    "last_test_at": null,
    "trip_reason": null,
    "trip_count_total": 0,
    "last_trip_at": null,
    "open_timeout_s": 172800
  }
}
```

---

## 4. Cascading Failure Analysis

### 4.1 Cascade: Source Registry Corrupted (B6)

```
B6: nlm_nb2_sources.json corrupted
 |
 +-> A7: Dedup fails (no existing sources to compare)
 |    +-> A1: Source bloat (all quarantine promoted blindly)
 |         +-> D2: Capacity overflow (>70, eventually >600)
 |
 +-> D5: Master Document update fails (can't find MD source IDs)
 |    +-> A4: Stale Master Documents
 |         +-> Degraded notebook_query responses
 |
 +-> D6: Consolidation blocked (can't identify candidates)
 |    +-> D2: Capacity overflow (no archival via consolidation)
 |
 +-> SVS calculations impossible
 |    +-> Capacity management disabled
 |         +-> D2: Capacity overflow (third path)
 |
 +-> Cross-validation unreliable (can't trace source chains)
      +-> C4 risk: feedback loop detection disabled

CASCADE DEPTH: 3 levels
TIME TO CRITICAL: 2-3 days (once bloat starts)
MITIGATION: CB-SOURCE trips immediately. Friday snapshot recovery.
```

**Recovery sequence:**

1. CB-SOURCE opens (automatic)
2. Pipeline continues queries, holds all sources in QUARANTINE
3. Restore registry from Friday snapshot
4. Reconcile NLM source list vs restored registry
5. Recalculate SVS for all sources
6. Process QUARANTINE backlog
7. Operator closes CB-SOURCE

### 4.2 Cascade: NLM API Empty Results for 5 Days

```
B4 x 5: Empty results Monday-Friday
 |
 +-> No new Working sources for any cluster
 |    +-> Working sources age without replacement
 |         +-> A4: Stale intelligence (avg_source_age grows)
 |              +-> MD-2 Operations Status becomes unreliable
 |
 +-> No handoff packages for 5 days
 |    +-> Scraper IGNORE mode all week (acceptable)
 |    +-> War Room Gemini-only topics all week (acceptable)
 |
 +-> CB-NLM trips after full rotation empty (5 days)
 |    +-> Pipeline paused 48h
 |         +-> 7 total days without queries
 |              +-> D8: All clusters starved equally
 |
 +-> Budget saved (10 queries unused)
      +-> Positive: budget available for catch-up

CASCADE DEPTH: 2 levels
TIME TO CRITICAL: 7 days
MITIGATION: CB-NLM opens at day 5. HALF_OPEN test at day 7.
CLIENT IMPACT: Moderate -- stale operational info but canonical sources still valid.
```

**Recovery sequence:**

1. CB-NLM HALF_OPEN at day 7
2. Test query fast mode
3. If still empty: investigate NLM account (auth, quotas, service status)
4. If normal: CLOSED, all clusters prioritized for catch-up
5. After recovery: forced Master Document refresh in first consolidation

### 4.3 Cascade: Persistent Consolidation ILM Failure

```
D6 x 3: ILM > 0.10 for 3 consecutive Fridays
 |
 +-> Consolidation blocked 3 weeks
 |    +-> No sources archived via consolidation
 |         +-> A1: Source bloat (only staleness archival active)
 |
 +-> Working sources accumulate without merging
 |    +-> A7: Increased duplicates (should-merge sources stay separate)
 |         +-> D2 risk: Capacity approaches 70
 |
 +-> Master Digests not updated with new intelligence
 |    +-> Notebook queries miss consolidated view
 |
 +-> CB-SOURCE trips (consolidation cascade trigger)

CASCADE DEPTH: 2 levels
TIME TO CRITICAL: 4 weeks (capacity pressure)
MITIGATION: CB-SOURCE trips at 3rd failure. Manual consolidation review.
```

**Root cause investigation:**

- Digest template too aggressive? (Losing nuance)
- Source claim sets too diverse? (N=4 sources with non-overlapping claims)
- Claim matching too strict? (Paraphrases treated as different claims)

**Resolution options:**

- Temporarily raise ILM threshold to 0.15
- Reduce minimum N from 4 to 3
- Improve claim matching for paraphrases

### 4.4 Cascade: Pipeline State Corrupted on Monday

```
B5: pipeline_state.json corrupted at 01:00 Monday
 |
 +-> No known_regulations set
 |    +-> A2: Old-As-New detection disabled
 |         +-> Stale regulations in daily brief
 |
 +-> No hot_topics
 |    +-> Breaking news override disabled
 |
 +-> No budget tracking
 |    +-> D1 risk: May exceed weekly/monthly limits
 |
 +-> No cluster rotation state
 |    +-> D8 risk: May repeat last week's clusters
 |
 +-> No crash recovery (no task_ids)
 |    +-> Orphaned NLM task (wastes budget)
 |
 +-> Friday snapshot recovery restores to last Friday
      +-> Loss: Sat-Sun override state, hot_topics updates
      +-> Acceptable: pipeline idle over weekend

CASCADE DEPTH: 1 level
TIME TO CRITICAL: Immediate (if no snapshot)
MITIGATION: Friday snapshot + cold restart procedure
```

### 4.5 Cascade: Feedback Loop Undetected for 2 Weeks

```
C4 undetected: NLM citing scraper articles derived from NLM
 |
 +-> Confidence inflation on 3-5 claims
 |    +-> Claims graduate from PROVISIONAL to VERIFIED incorrectly
 |         +-> False VERIFIED claims enter daily briefs
 |              +-> Scraper publishes articles based on false VERIFIED
 |                   +-> Loop amplifies further
 |
 +-> Master Documents updated with inflated claims
 |    +-> MD-1 Change Log contains false regulatory changes
 |         +-> All NB-2 queries polluted
 |
 +-> Cross-validation appears healthy (convergence rate up)
 |    +-> False positive on KPI monitoring
 |
 +-> If original claim was hallucination (A3 + C4):
      +-> Entrenched false regulation info
      +-> Potential client advisory based on nonexistent rule

CASCADE DEPTH: 4 levels
TIME TO CRITICAL: 1-2 weeks
MITIGATION: Provenance tagging is PRIMARY defense. Domain exclusion is SECONDARY.
WORST CASE: Manual audit of all VERIFIED claims against gazette originals.
```

**This is the most dangerous cascade** because it compounds a quality failure (hallucination) with an integration failure (feedback loop), and the existing monitoring (convergence rate) shows FALSE HEALTHY signals.

**Defense layers (all must fail for cascade to propagate):**

1. `balizero.com` in EXCLUDE_DOMAINS (NLM query level)
2. Provenance tagging on all claims
3. `is_independent_article()` in cross-validation
4. Manual quarterly audit (10 sampled VERIFIED claims)

---

## 5. Recovery Runbooks

### 5.1 Cold Restart (No Valid Snapshot)

**When:** Both `pipeline_state.json` AND all Friday snapshots corrupted or missing.

**Steps:**

```
1. CREATE FRESH STATE
   - Initialize pipeline_state.json with safe defaults
   - Seed known_regulations with minimum set: ["UU 6/2023", "Permenkumham 22/2023"]
   - All counters to zero, status IDLE, no cluster rotation history

2. REBUILD KNOWN REGULATIONS (if claims.jsonl available)
   - Parse claims.jsonl for all regulation_refs
   - Inject into known_regulations set
   - This prevents A2 (Old-As-New) for previously tracked regulations

3. RECONCILE SOURCE REGISTRY
   - If sources.json also corrupt: query NLM for current NB-2 source list
   - Rebuild registry from NLM source metadata
   - SVS defaults to 0.50 for all sources (recalculated on first full run)

4. RESET CIRCUIT BREAKERS
   - Set all three breakers to CLOSED
   - Reset failure counts

5. VERIFY
   - Run one L1 query in fast mode
   - Check state file written correctly
   - Check handoff generated
   - If all pass: operational. If any fail: investigate specific failure
```

**Expected data loss:** All pipeline state from last Friday to corruption. Cluster rotation, hot topics, override state, budget tracking for current week. Acceptable because pipeline is idle over weekends.

### 5.2 Source Registry Recovery

**When:** B6 detected, Friday snapshot exists.

**Steps:**

```
1. IDENTIFY LATEST VALID SNAPSHOT
   ls apps/evaluator/snapshots/nlm_nb2_sources_*.json
   # Pick most recent

2. VALIDATE SNAPSHOT
   python3 -c "
   import json
   data = json.load(open('apps/evaluator/snapshots/nlm_nb2_sources_YYYYMMDD.json'))
   active = [s for s in data['sources'] if s['stage'] == 'ACTIVE']
   print(f'Snapshot: {len(active)} ACTIVE, {len(data[\"sources\"])} total')
   "

3. RESTORE
   cp apps/evaluator/snapshots/nlm_nb2_sources_YYYYMMDD.json \
      apps/evaluator/nlm_nb2_sources.json

4. RECONCILE WITH NLM
   - Query NLM source list for NB-2
   - Sources in NLM but not in registry: add to registry (imported Mon-Thu)
   - Sources in registry but not in NLM: mark ARCHIVED (deleted between snapshot and corruption)

5. RECALCULATE SVS
   - Pipeline does this automatically on next run with RECALCULATE flag

6. PROCESS QUARANTINE BACKLOG
   - Any sources that accumulated during CB-SOURCE OPEN period
   - Extended triage: process all, oldest first

7. CLOSE CB-SOURCE
   - Operator confirms registry consistent
   - Set CB-SOURCE to CLOSED
```

### 5.3 NLM Notebook Recovery (Accidental Source Deletion)

**When:** Bug or operator error bulk-deletes sources from NB-2.

**Steps:**

```
1. IDENTIFY DELETED SOURCES
   grep '"action": "delete"' apps/evaluator/nlm_nb2_source_mutations.jsonl | tail -20

2. PRIORITIZE RE-IMPORT
   Priority 1: Canonical sources (T0 regulations) -- critical for all queries
   Priority 2: Master Documents (MD-1 through MD-4) -- regenerate from templates + claims
   Priority 3: Working sources with SVS >= 0.45 (VALUABLE+)
   Skip: Working sources >30 days old with SVS < 0.45 (not worth re-importing)

3. RE-IMPORT CANONICAL
   For each: source_add(source_type=url, url=<original_url>)
   Update registry with new NLM source IDs

4. REBUILD MASTER DOCUMENTS
   For each MD: generate content from claims archive + templates
   source_add(source_type=text, text=<content>, title="[NB2-MD] ...")
   Update registry

5. RE-IMPORT VALUABLE WORKING
   Only if age < 30 days and SVS >= 0.45
   source_add(source_type=url, url=<original_url>)

6. UPDATE REGISTRY
   All new NLM source IDs recorded
   SVS recalculated
```

### 5.4 Handoff Recovery

**When:** C2 persistent (3+ days corrupted).

**Steps:**

```
1. CHECK DATED FILE
   cat ~/.agent/decisions/nlm_to_scraper/$(date +%Y-%m-%d).json | python3 -m json.tool

2. IF DATED FILE VALID, SYMLINK BROKEN:
   cd ~/.agent/decisions/nlm_to_scraper/
   ln -sf $(date +%Y-%m-%d).json latest.json

3. IF DATED FILE ALSO CORRUPTED:
   Nothing to recover. Scraper runs IGNORE mode.
   Next pipeline run writes fresh handoff.

4. IF PERSISTENT (3+ days):
   Check disk health, file permissions
   Check pipeline write code for bugs
   CB-INTEGRATION may trip
   Review atomic write implementation
```

### 5.5 Manual Intervention Checklist

For any CRITICAL alert:

```
IMMEDIATE (within 1 hour)
  [ ] Read Telegram alert details
  [ ] Identify which circuit breaker(s) are OPEN
  [ ] Check pipeline_state.json for last successful run date
  [ ] If auth error: run `nlm login`

DIAGNOSIS (within 4 hours)
  [ ] Identify failure category (A/B/C/D) from alert
  [ ] Check cascading failures (Section 4)
  [ ] Determine if Friday snapshot available and valid
  [ ] Determine if cold restart needed

RECOVERY (within 8 hours)
  [ ] Execute appropriate runbook (5.1-5.4)
  [ ] Verify: test query, state files, handoff
  [ ] Close circuit breaker(s) if manual required (CB-SOURCE)
  [ ] Monitor next pipeline run for recurrence

POST-INCIDENT (within 24 hours)
  [ ] Document in query_history.jsonl
  [ ] Update prevention measures if gap found
  [ ] Review if taxonomy needs new entry
  [ ] Consider code changes to prevent recurrence
```

---

## 6. Monitoring Summary

### 6.1 Daily Health Metrics

| Metric                          | Healthy | Warning    | Alarm      |
| ------------------------------- | ------- | ---------- | ---------- |
| `active_source_count`           | 45-65   | <15 or >65 | <10 or >70 |
| `quarantine_count`              | 0-15    | 16-25      | >30        |
| `daily_dedup_rate`              | 0-20%   | 20-30%     | >30%       |
| `avg_confidence`                | >0.55   | 0.45-0.55  | <0.45      |
| `empty_results_this_week`       | 0-1     | 2          | >2         |
| `throttle_flags_this_week`      | 0       | 1-2        | 3+         |
| `api_errors_today`              | 0       | 1-2        | 3+         |
| `hallucination_count_month`     | 0-1     | 2          | 3+         |
| `avg_source_age_days` (Working) | <30     | 30-45      | >45        |
| `old_as_new_per_week`           | 0-2     | 3-4        | >5         |
| `trim_count_per_week`           | <15     | 15-30      | >30        |
| `cluster_max_gap_days`          | <10     | 10-14      | >14        |

### 6.2 Telegram Alert Levels

| Level     | When                             | Example                                  | Response Time |
| --------- | -------------------------------- | ---------------------------------------- | ------------- |
| INFO      | Non-critical event               | "Handoff not available. Scraper IGNORE." | None needed   |
| WARNING   | Degraded but functional          | "CB-NLM OPEN. Auto-test in 48h."         | 24h           |
| CRITICAL  | Data at risk or pipeline stopped | "Registry corrupted. CB-SOURCE OPEN."    | 4h            |
| EMERGENCY | Multiple breakers open           | "All breakers OPEN. Full stop."          | Immediate     |

### 6.3 Weekly Health Report Template

```
NB-2 IMMIGRATION INTELLIGENCE -- WEEKLY HEALTH
Week of YYYY-MM-DD to YYYY-MM-DD

PIPELINE:    X/5 days operational
QUERIES:     X executed, X failed, X skipped
BUDGET:      X/40 weekly (X%)

SOURCES:     X ACTIVE (target: 55-70)
  Canonical: X, Working: X, Master: X, Reference: X
  Imported:  X this week
  Archived:  X this week (staleness: X, dedup: X, capacity: X)
  Quarantine: X pending

INTELLIGENCE:
  Findings:  X total (X VERIFIED, X PROVISIONAL, X MONITORING)
  Claims:    X new (X accepted, X quarantined, X rejected)
  Clusters:  A:Xd B:Xd C:Xd D:Xd E:Xd (coverage: X%)

INTEGRATION:
  Handoff:   X/5 days delivered
  Scraper mode: PRIORITIZE xX, ENRICH xX, IGNORE xX
  Cross-validated: X claims boosted
  War Room: X topics from NLM, X from Gemini

DATA QUALITY:
  Old-As-New: X detections
  Dedup rate: X%
  Hallucinations: X
  Avg source age: X days (Working)

CIRCUIT BREAKERS: CB-NLM X | CB-SOURCE X | CB-INTEGRATION X
HEALTH SCORE: X.XX/1.00 (HEALTHY/DEGRADED/CRITICAL)
```

---

## 7. Quick Reference Table (All 30 Failure Modes)

| ID  | Failure             | Sev | Detection                          | Auto-Response               | Manual?          |
| --- | ------------------- | --- | ---------------------------------- | --------------------------- | ---------------- |
| A1  | Source bloat        | W/C | active_count thresholds            | Archive lowest-SVS          | No               |
| A2  | Old-as-new          | W   | known_regulations check            | Discard + log               | No               |
| A3  | Hallucination       | C   | Verification prompt + source audit | Quarantine, CB-NLM if 2x/wk | If in brief      |
| A4  | Stale intelligence  | W   | avg_source_age_days                | Staleness decay             | No               |
| A5  | Claim drift         | W   | Text hash comparison               | Pin canonical version       | Quarterly        |
| A6  | Tier misclass       | I/W | Domain lookup table                | Override tier               | No               |
| A7  | Dedup false neg     | I/W | Weekly claim overlap               | Friday consolidation        | No               |
| A8  | Dedup false pos     | W/C | ILM + sole-backing audit           | ILM gate 0.10               | If sole T0-T2    |
| B1  | NLM API error       | W/C | HTTP status codes                  | Retry + backoff, CB-NLM     | If 401/403       |
| B2  | NLM timeout         | W/C | 25-min hard timeout                | Kill + skip, CB-NLM if 2d   | No               |
| B3  | NLM throttle        | W/C | Source count + response            | Reduce to 1/day, CB-NLM     | No               |
| B4  | NLM empty           | I/W | Zero sources                       | Log, try L2                 | If full rotation |
| B5  | State corrupt       | C   | JSON parse fail                    | Friday snapshot             | If no snapshot   |
| B6  | Registry corrupt    | C   | Parse + consistency                | CB-SOURCE, snapshot         | Yes (reconcile)  |
| B7  | Claims corrupt      | W/C | Line parse                         | Skip bad / snapshot         | If truncated     |
| B8  | Disk full           | C   | OSError + pre-check                | Auto-cleanup                | If insufficient  |
| B9  | Cron misfire        | I/W | Dedup guard + Doctor               | Skip dup / alert            | If no-fire       |
| B10 | Python error        | W/C | Try/except + exit                  | Write FAILED, CB if 2d      | If persistent    |
| C1  | Handoff missing     | I   | File check                         | Scraper IGNORE              | No               |
| C2  | Handoff corrupt     | I   | JSON parse                         | Scraper IGNORE              | No               |
| C3  | Handoff stale       | I   | Age check 24h                      | Scraper IGNORE              | No               |
| C4  | Feedback loop       | C   | Provenance + domain                | Revert boosts, CB-INT       | Yes (verify)     |
| C5  | Signal loss         | I   | Phase 1 log                        | Continue                    | No               |
| C6  | War Room disconnect | I   | War Room logs                      | Gemini fallback             | No               |
| C7  | Symlink race        | I   | Parse error + mtime                | Scraper IGNORE              | No               |
| C8  | Schema mismatch     | W/C | Version field                      | Dual-write compat           | Yes (deploy)     |
| D1  | Budget exhaustion   | W   | Budget counter                     | Skip queries                | Review if early  |
| D2  | Capacity overflow   | C   | active_count > 70                  | Force-archive to 55         | Review algo      |
| D3  | Quarantine overflow | W   | count > 30                         | Extended triage, 48h SLA    | No               |
| D4  | Schedule conflict   | W/C | Timing checks                      | Hard abort 02:20            | No               |
| D5  | MD update fail      | W/C | API error on MD ops                | Retry, keep old             | If MD-1 2d       |
| D6  | ILM exceeds         | W   | ILM calc                           | Reject consolidation        | If 3x consec     |
| D7  | SVS drift           | I   | Quarterly audit                    | Recalibrate weights         | Quarterly        |
| D8  | Cluster skew        | W   | last_cluster_run                   | Force-schedule              | No               |

**Summary statistics:**

- 30 failure modes cataloged
- 8 data quality, 10 system, 8 integration, 4 operational
- 3 independent circuit breakers
- 5 cascading scenarios analyzed (including worst-case: hallucination + feedback loop)
- 5 recovery runbooks (cold restart, registry, notebook, handoff, manual checklist)
- 12 daily health metrics, 4 alert levels, weekly report template
