---
date: 2026-07-18
domain: operations
adversarial_review: glm-5.2
---

# KG staging promotion job — design spec v2 (S5)

> Author: Kimi (Air-M5 session) · Status: **DESIGN v2, post-refuter** · Mandate: campaign S5 (Zero, 2026-07-18)
> Disease cured: superscar #2 ("Esiste ≠ Armato") — the quarantine pattern's second half was designed 2026-04-03 and never built.
> v2 changes: full rework of concurrency/transaction model + schema companion migration + conservative dedup, after GLM-5.2 CADE (see Adversarial review).

## 1. Problem (verified on disk this turn)

`kg_auto_expansion.py` writes auto-extracted entities/relationships to `kg_nodes_staging` / `kg_edges_staging` (migration_077, 2026-04-03) and its docstring promises: *"promoted to production by a batch validation job every 6h"*. **That job does not exist anywhere in the repo** (grep returns: the writer, the migration, tests, two design docs — zero promotion code). Staged rows accumulate as `promotion_status='pending'` forever. The KG auto-expansion loop is a write-only dead end.

Row counts on prod: **open measurement** — Phase 0 of the job censuses before anything else.

## 2. Contract already designed (§3.4 GRAPHRAG_EVOLUTION_ARCHITECTURE.md)

Panel-reviewed rules (Gemini/Codex/DeepSeek rounds 1-2) that this spec **arms, not redesigns**: batch cadence; confidence ≥ 0.65; rate limit 50 nodes/day; nodes BEFORE edges; checks (schema compliance, referential integrity, business-logic gates, provenance); retention prune 30d; alert on >100K rows or >5%/day growth.

## 3. Design v2

### 3.1 The job: `apps/backend-rag/backend/scripts/kg_staging_promotion.py`

Async script: `PYTHONPATH=. python -m backend.scripts.kg_staging_promotion [--dry-run|--apply] [--limit N]`.

**Concurrency model (rewritten after refuter FATAL-1/2 + SERIO-1):**

- **Singleton via advisory lock**: `SELECT pg_try_advisory_lock(770077)` at start; if not acquired, exit 0 ("another run in progress"). NO `FOR UPDATE` / `SKIP LOCKED` anywhere — the writer only appends new rows (`ON CONFLICT DO NOTHING`), which never conflicts with status updates on disjoint pending rows.
- **Chunked short transactions, never one big batch**: each chunk = ≤25 nodes in its own transaction (validate → promote → mark). Daily cap 50 nodes/run-day (§3.4). Each chunk is seconds-short → `statement_timeout`-safe, MVCC-friendly, resume-safe (processed rows are already marked if the run dies mid-way). A dropped fly-ssh connection kills at most one 25-row transaction, rolled back by Postgres on disconnect.
- **Dry-run is genuinely read-only**: plain SELECTs inside a read-only transaction, zero writes, zero explicit locks.

**Phases:**

- **Phase 0 — census (read-only):** counts by status, oldest pending age, growth/day; alert conditions (>100K rows, >5%/day) in the run report.
- **Phase 1 — node validation:** provenance (`extraction_source` set) · confidence ≥ 0.65 · normalized `entity_id` · **conservative dedup**: exact prod match → mark `promoted` + confidence-boost UPDATE on prod row; fuzzy name similarity >0.85 → **`rejected` with reason `fuzzy_ambiguous_review`** (NO auto-merge of provenance — a false positive would corrupt prod irreversibly; these surface for human review); no match → candidate.
- **Phase 2 — edge validation:** only edges whose source+target exist in prod KG after Phase 1 (no dangling). Edge dedup (source,target,type): exact duplicate → corroboration +0.05 cap 1.0.
- **Phase 3 — promotion (per chunk, atomic):** INSERT nodes → UPDATE prod confidences → INSERT edges → flip staging rows (`promoted` / `rejected` + reason). Exception → that chunk rolls back, staging untouched, run continues with next chunk, failures counted in the report.
- **Phase 4 — retention + report:** prune `rejected` older than 30d (uses new `updated_at`, §3.3). Report: `{census, validated, promoted, rejected(reasons), corroborated, pruned, chunks, failures}`.

**Shadow-first:** default `--dry-run`; `--apply` explicit. First week: dry-run only, reports reviewed; arming = operator GO (Legge 5 — writes the prod KG).

### 3.2 Placement: GitHub Actions cron → `fly ssh` (bounded by design)

(a) new Pro launchd — **rejected** (modus AMENDMENTS: "No new cron/daemon"; W84). (b) new Fly worker/endpoint — rejected (deploy surface for a 5-min/6h job). (c) **GH Actions cron 6h** running `flyctl ssh console -C 'PYTHONPATH=. python -m backend.scripts.kg_staging_promotion --dry-run'` — chosen: same pattern as deploy migrations; short bounded runs make SSH fragility harmless (worst case: one 25-row chunk rolls back, next run resumes); a `KG_PROMOTION_MODE=dry-run|apply` secret flips arming without redeploy. Workflow failure alert = existing Telegram pattern from fly-deploy (not `tg_notify` inside the script — refuter MINOR-2).

### 3.3 Companion migration: `247_kg_staging_status_integrity.sql` (after refuter SERIO-2)

`kg_*_staging.promotion_status` is free TEXT (typo-prone) with no `updated_at` (30d retention unimplementable). Add: `CHECK (promotion_status IN ('pending','promoted','rejected','merged'))` (after a normalizing UPDATE of any stragglers) + `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` (backfilled from `created_at`), with `-- === ROLLBACK ===` marker. Migration PR: **auto-merge OFF**, manual merge after Squawk/migration gates (corner rule), then probe the applied constraint on prod.

### 3.4 Tests

- Unit (mock asyncpg): every validation rule guilt+innocence; exact-dedup boost; fuzzy → rejected-not-merged; dangling edge rejection; confidence cap 1.0; chunk boundary; advisory-lock busy path; dry-run zero-write assertion.
- Contract (tmpfs PG, docker-compose.test.yml): migration_077 + 247 applied; end-to-end stage→chunk→promote→verify; resume after mid-chunk kill.
- Shadow prove-live: first dry-run census matches manual `SELECT count(*)` on prod.

### 3.5 Acceptance criteria (pre-registered, falsifiable)

1. `pytest backend/tests/scripts/test_kg_staging_promotion*.py` green (guilt+innocence per rule).
2. Dry-run on prod: exit 0, report with census + per-verdict counts; `kg_nodes` count **unchanged** before/after.
3. After operator arms: pending count strictly decreases run-over-run; integrity query (staging `promoted` rows without a prod counterpart) = 0.
4. Docstring lie cured: `kg_auto_expansion.py` header references the real runner + schedule.

## 4. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Garbage into prod KG | shadow-first week; confidence ≥0.65; 50/day cap; reason-coded rejections (auditable) |
| False fuzzy merge corrupts provenance | v1 NEVER auto-merges: fuzzy → `rejected(fuzzy_ambiguous_review)` for human review |
| Long transaction bloat/timeout | chunked ≤25-row transactions; advisory-lock singleton |
| SSH drop mid-run | at most one small chunk rolls back; resume is natural (rows marked per chunk) |
| jsonb double-encoding (scar 242/243) | pool-level jsonb codecs (service_initializer pattern); never hand-serialize |
| Silent failure of the cron | workflow failure-alert job (fly-deploy Telegram pattern), not in-script notify |

## Adversarial review

**Reviewer seat: `glm-5.2` (probed live 2026-07-18) — generator≠grader (author: Kimi). Verdict on v1: CADE — 2 FATAL, 3 SERIO, 2 MINOR. All findings re-verified before handling (W65: even the refuter hallucinates); one FATAL was technically wrong but operationally load-bearing.**

1. **FATAL — "SKIP LOCKED + single giant transaction = concurrency contradiction, deadlocks."** VALID. v2 drops SKIP LOCKED entirely: singleton via `pg_try_advisory_lock`, writer appends are conflict-free by construction; transactions are small chunks, never one giant batch.
2. **FATAL — "fly ssh drop mid-transaction hangs locks indefinitely."** TECHNICALLY WRONG (Postgres releases all locks when a session dies; the transaction rolls back) — but the operational concern is real and v2 designs around it: chunked short transactions + natural resume make an SSH drop cost ≤25 rolled-back rows.
3. **SERIO — "single transaction hits statement_timeout/MVCC bloat on backlog."** VALID → chunked model + 50/day cap (already in §3.4 contract) + oldest-first; backlog drains over days, not one run.
4. **SERIO — "schema lacks CHECK constraint + updated_at; retention unimplementable."** VALID → companion migration 247 added to the design (auto-merge OFF per migration rule).
5. **SERIO — "blind fuzzy-merge can permanently corrupt prod provenance."** VALID → v1 never auto-merges; fuzzy candidates become `rejected(fuzzy_ambiguous_review)` for human review.
6. **MINOR — "dry-run acquiring locks is a lie."** VALID nit → dry-run is plain-SELECT read-only, stated explicitly.
7. **MINOR — "tg_notify from inside a GH runner is brittle."** VALID → failure alerting moved to the workflow level (existing deploy pattern).

**Net disposition:** v1 CADE accepted in full; v2 incorporates every correction. The refuter's strongest frame — "you cannot combine queue-incremental locking with a monolithic atomic batch" — is now the design's load-bearing constraint.
