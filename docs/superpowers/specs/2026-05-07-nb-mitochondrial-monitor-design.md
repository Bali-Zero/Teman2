# NB Mitochondrial Value Monitor — Design Doc

**Branch**: `feat/nb-mitochondrial-monitor-2026-05-07`
**Date**: 2026-05-07
**Author**: Antonello Siano (Zero) + Claude Opus 4.7
**Reference**: NB Lifecycle Round 2 memo (`project_nb_lifecycle_round2_2026_05_04.md`), SYMBIOSIS.md §145-160 Pilastro 7

---

## 1. Goal

Implement a daily cron monitor that measures **which NB produces value consumed downstream by Nuzantara**. Without this measurement, "keep/decommission" decisions for the 60+ NotebookLM notebooks are opinions; with the numbers, they become evidence-based.

Value definition (Round 2 metaphor): an NB has _mitochondrial value_ if its sources are queried, its insights are consumed by skills/cell layer, its citation chain appears in Zantara responses. **Value = downstream consumption**, not "size of the NB".

## 2. Scope

### In-scope

- Daily cron LaunchAgent `com.nuzantara.nb-mitochondrial-monitor.daily` (~02:30 WITA).
- SQLite metrics store at `~/.agent/nb-mitochondrial/metrics.db` (WAL mode, foreign keys, schema-versioned).
- Five metric collectors per NB (3 live today, 2 N/A pending FASE 1 + FASE 4 merge).
- Tier-based ranking (`ALIVE` / `IDLE` / `DYING`) + intra-tier ranking by `read_freq_7d`.
- Weekly markdown report at `~/Desktop/nuzantara/research/nb-monitor/report-YYYY-WW.md`, generated Sunday.
- CLI dashboard `scripts/nb-monitor/show.py` (table + delta vs last week).
- Three Telegram alerts with floor and cooldown (top-5 drop, lifecycle drop, dying-no-action).
- Bootstrap NB list at `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.yaml` (24 NB), with ADR migrate to `notebook_registry.py` post-FASE-2 merge.

### Out-of-scope (future work, follow-up PRs)

- `notebook_registry.py` SSOT itself (FASE 2 owns it; this PR consumes it).
- Auto-reconcile script (`reconcile_notebook_registry.py`) — separate follow-up.
- Cell-observatory monitoring of the monitor itself ("monitor down" alert).
- Backfill historical metrics for periods before deploy.
- Cross-machine metrics aggregation (Pro is the only collector).

## 3. Architecture

### 3.1 Component diagram

```
                  ┌──────────────────────────────────────────────┐
                  │  com.nuzantara.nb-mitochondrial-monitor.daily│
                  │  LaunchAgent — StartCalendarInterval 02:30   │
                  └─────────────────────┬────────────────────────┘
                                        │
                                        ▼
                  ┌──────────────────────────────────────────────┐
                  │  python -m mata_garuda.scripts.nb_monitor.run│
                  │  (or --once for ad-hoc)                      │
                  └─────────────────────┬────────────────────────┘
                                        │
                  ┌─────────────────────┼──────────────────────┐
                  │                     │                      │
                  ▼                     ▼                      ▼
      ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
      │ active_notebooks │  │ metric collectors│  │  alerts engine   │
      │ bootstrap.yaml   │  │  (5 collectors)  │  │  (cooldown, floor│
      │  → 24 UUIDs      │  │                  │  │  Telegram send)  │
      └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
               │                     │                      │
               └─────────────┬───────┴──────────────────────┘
                             ▼
                ┌──────────────────────────┐
                │  metrics.db (SQLite WAL) │
                │  - nb_metrics            │
                │  - alerts_sent           │
                │  - schema_version        │
                └────────────┬─────────────┘
                             │
                             ▼              ┌──────────────────────┐
              ┌──────────────────────┐      │ scripts/nb-monitor/  │
              │ weekly_report.py     │      │ show.py (CLI dash)   │
              │ (Sunday 03:00 WITA)  │      └──────────────────────┘
              └──────────┬───────────┘
                         │
                         ▼
            ~/Desktop/nuzantara/research/
            nb-monitor/report-YYYY-WW.md
```

### 3.2 File layout

```
apps/mata-garuda/mata_garuda/scripts/nb_monitor/
├── __init__.py
├── run.py                     # entrypoint: daily run + --once flag
├── registry.py                # bootstrap YAML loader + (future) registry adapter
├── collectors/
│   ├── __init__.py
│   ├── log_scraper.py         # JSONL scraper for Claude Code sessions
│   ├── nlm_freshness.py       # nlm CLI batch source-age (best-effort weekly)
│   ├── feeder_log.py          # ~/logs/matagaruda-nlm-feeder-stream.log parser
│   ├── skill_derivation.py    # Qdrant local query (placeholder pre-FASE-1)
│   └── cite_rate.py           # Oracle log query (placeholder pre-FASE-4)
├── tier.py                    # tier classifier (ALIVE/IDLE/DYING)
├── alerts.py                  # alert evaluator + cooldown + Telegram dispatch
├── persist.py                 # SQLite WAL helpers, schema migration
├── report.py                  # weekly markdown report generator
└── tests/
    ├── fixtures/
    │   ├── jsonl_sample/      # sanitized JSONL fixtures (50 sessions)
    │   ├── feeder_log.jsonl
    │   └── bootstrap.yaml
    ├── test_log_scraper.py
    ├── test_feeder_log.py
    ├── test_tier.py
    ├── test_alerts.py
    ├── test_persist.py
    ├── test_report.py
    └── test_integration_e2e.py # one end-to-end test

scripts/nb-monitor/
└── show.py                    # CLI dashboard, reads metrics.db

~/.agent/nb-monitor/
├── active_notebooks_bootstrap_2026-05-07.yaml   # 24 NB UUIDs + metadata
├── metrics.db                                    # SQLite WAL
└── logs/
    └── nb-monitor.log
```

### 3.3 Data flow per cron run

1. **Load registry**: read `active_notebooks_bootstrap_2026-05-07.yaml` → list of 24 `(uuid, name, family, lifecycle_stage, ...)`.
2. **For each UUID**, call collectors in parallel (asyncio.gather):
   - `log_scraper.read_freq(uuid, window=7d)` → int
   - `log_scraper.read_freq(uuid, window=30d)` → int
   - `feeder_log.push_success_rate(uuid, window=7d)` → float (0.0-1.0)
   - `nlm_freshness.median_age(uuid)` → int days OR `None` if cookie expired
   - `skill_derivation.count(uuid)` → `None` (placeholder pre-FASE-1)
   - `cite_rate.compute(uuid)` → `None` (placeholder pre-FASE-4)
3. **Per-UUID error isolation**: any single collector failure → log WARN, set field to `NULL`, continue other collectors. Global failure (e.g. SQLite locked) → log ERROR, no Telegram alert (see §7.4).
4. **Compute tier** via `tier.classify(uuid, metrics)` — see §4.2.
5. **Persist** snapshot row to `nb_metrics` (one row per uuid per run).
6. **Evaluate alerts** vs last-week snapshot — see §6.
7. **If Sunday**, generate weekly report.
8. **Exit code 0** even on partial failures (the monitor never alerts on itself).

## 4. Data model

### 4.1 SQLite schema (versioned)

```sql
CREATE TABLE schema_version (
    version  INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL  -- unix timestamp
);

CREATE TABLE nb_metrics (
    uuid                       TEXT NOT NULL,
    ts_capture                 INTEGER NOT NULL,      -- unix timestamp of run
    tier                       TEXT NOT NULL,         -- ALIVE | IDLE | DYING
    read_freq_7d               INTEGER,
    read_freq_30d              INTEGER,
    skill_derivation_count     INTEGER,               -- nullable (pre-FASE-1)
    downstream_cite_rate       REAL,                  -- nullable (pre-FASE-4)
    source_freshness_age_days  INTEGER,               -- nullable if cookie expired
    push_success_rate          REAL,                  -- nullable if no feeder events
    instrumentation_status     TEXT,                  -- pending_qdrant_local |
                                                      -- pending_oracle_logging |
                                                      -- cookie_refresh_pending |
                                                      -- parse_failure |
                                                      -- ok
    PRIMARY KEY (uuid, ts_capture)
);
CREATE INDEX idx_uuid_ts ON nb_metrics(uuid, ts_capture DESC);
CREATE INDEX idx_ts_capture ON nb_metrics(ts_capture DESC);

CREATE TABLE alerts_sent (
    uuid       TEXT NOT NULL,
    condition  TEXT NOT NULL,    -- top5_drop_50pct | tier_transition | dying_no_action
    sent_at    INTEGER NOT NULL,
    payload    TEXT,             -- JSON: snapshot of values that triggered alert
    PRIMARY KEY (uuid, condition, sent_at)
);
CREATE INDEX idx_alert_lookup ON alerts_sent(uuid, condition, sent_at DESC);
```

WAL mode: `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;` set at connect time.

Schema versioning: `persist.py::ensure_schema()` checks `schema_version` table; if missing or version < current, applies migration. v1 = initial schema above.

### 4.2 Bootstrap registry YAML

```yaml
# ~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.yaml
# ADR: MIGRATE TO apps/mata-garuda/mata_garuda/notebook_registry.py ON FASE 2 MERGE
schema_version: 1
generated_at: 2026-05-07
source: round2_memory + config.py NLM_NOTEBOOKS + manual curation

notebooks:
  - uuid: "d9438180-xxxx-xxxx-xxxx-xxxxxxxxxxxx" # NB-INTEL-Property
    name: "NB-INTEL-Property"
    family: "INTEL" # INTEL | MATA-GARUDA | CORE | RESEARCH | SUBHI | META
    lifecycle_stage: "TAC" # DM | TAC | SENESCENT | KILL_PENDING | APOPTOSIS_DONE | ORPHAN_REVIEW
    active_routing: true
    first_audited: "2026-05-04"
    last_audited: "2026-05-07"
    round2_classification: "Curated High Value"
  # ... 23 more entries, derived from:
  #   - 6 from config.py NLM_NOTEBOOKS (NB-INTEL family + Self-Evolving)
  #   - 17 APOPTOSIS_DONE planned by FASE 2
  #   - 1+ Core curated (NB-2..8 visa/KBLI/tax/property/ops/editorial/expat)
```

`registry.py::load()` returns `list[NotebookEntry]` dataclass instances. If `notebook_registry.py` exists at runtime (post-FASE-2), load from there instead with a one-line warning logged on first use to confirm migration.

## 5. Tier classifier (§4.2 of decision memo)

Decision matrix (from question 3/4 final answer):

```python
def classify(metrics: NBMetrics) -> Tier:
    age = metrics.age_days
    rf7 = metrics.read_freq_7d or 0
    psr = metrics.push_success_rate     # may be None

    # ALIVE: high engagement + healthy push + matured
    if rf7 >= 5 and (psr is None or psr >= 0.95) and age > 7:
        return Tier.ALIVE

    # DYING: idle for sustained period + push trouble
    if rf7 < 1 and age > 14 and (psr is None or psr < 0.7):
        return Tier.DYING

    # IDLE: everything else (includes bootstrap NB age <= 7)
    return Tier.IDLE
```

`age_days` = days since `first_audited` in registry YAML. The `psr is None` branches treat missing data as neutral (don't downgrade to DYING just because cookie expired).

Intra-tier ranking: by `read_freq_7d` desc, ties broken by `read_freq_30d` desc.

## 6. Alerts

Three independent alert types, each with its own cooldown. All send via existing `~/.claude/scripts/hotfix-notify.sh` style — POST to Telegram bot API, chat_id `1125336968`. Reuse the same env vars `TELEGRAM_BOT_TOKEN` / `TELEGRAM_ADMIN_CHAT_ID` already present in `.nuzantara-secrets.env`.

### 6.1 alert_top_5_drop

```
Trigger:
    tier_lastweek == ALIVE
  AND read_freq_7d_now < 0.5 * read_freq_7d_lastweek
  AND (read_freq_7d_lastweek - read_freq_7d_now) >= 10        # absolute floor
  AND uuid IN top_5_alive_lastweek                            # ranked subset

Cooldown: 86400s for (uuid, 'top5_drop_50pct').

Message format:
    🔻 NB drop alert
    {name} ({family}) — read_freq_7d {prev} → {now} (-{drop} / -{pct}%)
    tier_lastweek={ALIVE}, tier_now={tier}
    Investigate: dashboard show.py | weekly report
```

### 6.2 alert_lifecycle_drop

```
Trigger:
    tier_now degrades vs tier_lastweek (ALIVE→IDLE→DYING; not the inverse)
  AND age_days > 14                                           # skip bootstrap

Cooldown: 86400s for (uuid, 'tier_transition').

Message:
    📉 NB tier transition
    {name} {tier_lastweek} → {tier_now}
    read_freq_7d {prev} → {now}
    Reason hint: {first failing condition}
```

### 6.3 alert_dying_no_action

```
Trigger:
    tier == DYING for >= 14 consecutive daily snapshots
  AND skill_derivation_count == 0                             # post FASE-1 only
  AND last 30d has no nb_metrics row with rf7 > 0

Suggestion (NOT auto-action): "Propose APOPTOSIS — requires Zero approval".
Cooldown: 7 days for (uuid, 'dying_no_action').

Note: this alert is naturally suppressed pre-FASE-1 because
skill_derivation_count is NULL. Self-gating per design.
```

### 6.4 Cooldown logic

```python
def can_send(uuid, condition, now=None):
    now = now or int(time.time())
    last = db.execute(
        "SELECT MAX(sent_at) FROM alerts_sent WHERE uuid=? AND condition=?",
        (uuid, condition)
    ).fetchone()[0]
    if last is None:
        return True
    cooldown = COOLDOWNS[condition]   # 86400 or 604800
    return (now - last) >= cooldown
```

## 7. Operational concerns

### 7.1 Read-only on existing pipeline

Hard constraint from prompt: NO modifications to existing pipeline (NLM feeder, Oracle, Qdrant). Only READ:

- JSONL session files (read-only filesystem access).
- nlm-feeder log file (read-only tail).
- nlm CLI batch query (READ-only — `notebook_get` style, no mutation).
- Qdrant local read (post-FASE-1, when ready) — read-only point lookup.

The single permitted exception (Oracle citation log injection in `apps/backend-rag/backend/services/oracle/`) is **deferred to FASE 4** — this PR does NOT touch backend-rag.

### 7.2 Graceful degrade

| Failure                                                                          | Behavior                                                                                       |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Single collector raises for one UUID                                             | log WARN, set field NULL, continue other collectors and other UUIDs                            |
| Single collector raises for ALL UUIDs (e.g. nlm cookie expired across the board) | log WARN, set instrumentation_status=`cookie_refresh_pending`, persist row anyway              |
| Global failure (SQLite locked, disk full)                                        | log ERROR, exit 0, NO Telegram alert (escalation prevention)                                   |
| Telegram POST fails                                                              | log WARN, retry once after 5s, then drop. Alert NOT recorded in alerts_sent if delivery failed |

### 7.3 First-14-days banner

Every weekly report's header includes:

> **Baseline period — first 14 days post-deploy. Score reliability degraded:**
>
> - `read_freq_7d/30d`: live (Claude Code JSONL scraper).
> - `source_freshness_age`: best-effort (nlm cookie 5min TTL).
> - `push_success_rate`: live (matagaruda-nlm-feeder-stream.log).
> - `skill_derivation_count`: **N/A pending FASE 1 merge**.
> - `downstream_cite_rate`: **N/A pending FASE 4 merge**.

### 7.4 No backpressure on critical path

Cron runs at 02:30 WITA, off-peak. Total runtime budget ~10-15s on Pro M4. All file reads are O(MB), no rsync or large I/O. SQLite writes are batched in a single transaction. No process spawns into critical pipeline.

Pre-merge review prompt for Gemini 3.1 Pro: _"Did this PR introduce backpressure on a critical path? The monitor must be read-only and run during off-peak. Verify no new processes spawn into NLM pipeline, Qdrant, Postgres, or Oracle."_

## 8. Test plan

Coverage target: **≥80% line coverage** on `apps/mata-garuda/mata_garuda/scripts/nb_monitor/**`.

### 8.1 Unit tests (deterministic, no I/O)

- `test_log_scraper.py` — fixture: 50-session sanitized JSONL set, ~100 NLM tool_use events. Validate: UUID extraction from both `notebook_id` and `notebookId` fields, mtime window filter, count aggregation, `parse_failure` vs `0 events` distinction.
- `test_feeder_log.py` — fixture: synthetic feeder log with mix of success/fail rows. Validate: per-UUID push_success_rate calculation, malformed rows skipped with WARN.
- `test_tier.py` — table-driven test of `classify()` covering all branches (ALIVE/IDLE/DYING + None handling for psr).
- `test_alerts.py` — table-driven test of all three triggers including floor (8→3 = 62% drop, 5 absolute → NO alert) and cooldown logic (within window → suppressed).
- `test_persist.py` — schema migration v0→v1, WAL mode pragma, transaction rollback on partial failure.
- `test_report.py` — fixture metrics → snapshot markdown, validate columns, diagnostic collapsible block, banner present.

### 8.2 Integration test (one end-to-end)

`test_integration_e2e.py`:

1. Setup tmpdir with bootstrap YAML (3 fake UUIDs), JSONL fixtures, feeder log fixture.
2. Patch `nlm_freshness` to return mock data, `skill_derivation` and `cite_rate` to return None.
3. Run `run.execute_once(config_dir=tmpdir)`.
4. Assert: `metrics.db` exists, contains 3 rows for current ts_capture, tier values match expectation, no exception raised.
5. Re-run with mutated JSONL (one UUID dropped to 0 events) → assert tier transition alert evaluated (but Telegram dispatch is mocked).

### 8.3 Smoke (post-deploy manual)

After LaunchAgent load:

```bash
python -m mata_garuda.scripts.nb_monitor.run --once
sqlite3 ~/.agent/nb-mitochondrial/metrics.db \
  "SELECT uuid, tier, read_freq_7d, instrumentation_status FROM nb_metrics ORDER BY ts_capture DESC LIMIT 24;"
python scripts/nb-monitor/show.py
```

Success criterion (from prompt): non-zero metrics for ≥18/24 NBs (75%) on first run.

## 9. Build sequence (4 commits)

1. **Commit 1 — bootstrap registry + LaunchAgent skeleton**
   - `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.yaml` (24 entries)
   - `apps/mata-garuda/mata_garuda/scripts/nb_monitor/__init__.py`
   - `apps/mata-garuda/mata_garuda/scripts/nb_monitor/registry.py` (loader + dataclass)
   - `apps/mata-garuda/mata_garuda/scripts/nb_monitor/persist.py` (schema + migrations)
   - `apps/mata-garuda/mata_garuda/scripts/nb_monitor/run.py` (skeleton with `--once` + load registry only)
   - LaunchAgent plist at `infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist`
   - `test_persist.py`, `test_registry.py`

2. **Commit 2 — three live metric collectors**
   - `collectors/log_scraper.py` (Claude Code JSONL parsing)
   - `collectors/feeder_log.py` (matagaruda-nlm-feeder-stream.log parsing)
   - `collectors/nlm_freshness.py` (best-effort nlm CLI batch)
   - Wire into `run.py`
   - `test_log_scraper.py`, `test_feeder_log.py`, `test_nlm_freshness.py`

3. **Commit 3 — tier classifier + alerts + weekly report**
   - `tier.py`, `alerts.py`, `report.py`
   - `scripts/nb-monitor/show.py` (CLI dashboard)
   - `test_tier.py`, `test_alerts.py`, `test_report.py`, `test_integration_e2e.py`

4. **Commit 4 — docs + ADR**
   - `docs/operations/nb-mitochondrial-monitor.md` (operational runbook)
   - `docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-yaml.md` (migration plan post-FASE-2)
   - Placeholder collectors `collectors/skill_derivation.py` + `collectors/cite_rate.py` returning None with `instrumentation_status` markers
   - README in `apps/mata-garuda/mata_garuda/scripts/nb_monitor/README.md`

Each commit pushed to `feat/nb-mitochondrial-monitor-2026-05-07`. **WIP-commit cadence**: every ~10 min while untracked files exist (cicatrix-scars 2026-04-29 STRUCTURAL "branch hijack antibody"). Pattern:

```bash
if git ls-files --others --exclude-standard | grep -q .; then
  git add -A apps/mata-garuda/mata_garuda/scripts/nb_monitor/
  git commit -m "WIP(nb-monitor): checkpoint $(date +%H:%M)"
  git push origin feat/nb-mitochondrial-monitor-2026-05-07
fi
```

Push within 30s of every commit. After commit 4: open PR titled `feat(nb-monitor): mitochondrial value monitor cron + weekly report (Round 2)`.

## 10. ADR — bootstrap YAML vs notebook_registry.py

### Context

FASE 2 is concurrently building `apps/mata-garuda/mata_garuda/notebook_registry.py` as the SSOT (Phase 0.5 of plan A STRIP-DOWN). FASE 5 (this PR) needs the same data NOW.

### Decision

FASE 5 uses `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.yaml` as a temporary SSOT until FASE 2 merges. `registry.py::load()` is written so that if `notebook_registry.py` exists at runtime it reads from there instead, with a one-line WARN logged on first use confirming migration. The YAML file is deleted in a follow-up PR after migration is verified.

### Consequences

- Two registry sources transiently coexist for ≤7 days.
- FASE 2 PR landing produces no breakage — `registry.py` auto-detects.
- Drift risk: if FASE 5 merges before FASE 2 and the team adds an NB to the YAML manually, that addition will not propagate to `notebook_registry.py` automatically. Mitigation: the cron logs a WARN line listing UUIDs in YAML but missing in `notebook_registry.py` post-FASE-2, allowing manual reconciliation.

### Alternatives considered and rejected

- _MCP `nlm notebook list` at runtime_: cookie 5min TTL is too fragile for daily cron.
- _config.py NLM_NOTEBOOKS only (6 UUIDs)_: too narrow — 8% of total — produces incomplete picture of mitochondrial value.
- _Wait for FASE 2 merge before starting FASE 5_: blocks this PR for unknown duration; FASE 2 is independent work.

## 11. Success criteria

- [ ] LaunchAgent loaded, first cron run produces non-zero metrics for ≥18/24 NB.
- [ ] Weekly report markdown generated correctly on first Sunday post-deploy.
- [ ] Zero impact on NB query latency (read-only verification, manual smoke).
- [ ] Telegram alerts not noisy (cooldown verified by simulating duplicate trigger in integration test).
- [ ] Test coverage ≥80% on `nb_monitor/**`.
- [ ] Gemini 3.1 Pro pre-merge review confirms no backpressure introduced.
- [ ] PR body includes: SQLite schema, sample report output, plist content, alert+cooldown logic.
