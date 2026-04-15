# Experience Library — Operations Runbook

**System:** Mata Garuda Layer 4.5 — Curator Agent Sprint 5.2
**Last updated:** 2026-04-15
**Owner:** Zero / Bali Zero AI Team

## Overview

The Experience Library records **execution trajectories** — episodes of
sense→think→act→reflect — so future pulses of any cell can search prior
outcomes before reasoning from scratch. It is the substrate for the SYMBIOSIS
Pilastro 2 (Accumulazione): "skill library ... nella stessa SQLite KB".

**Canonical store:** a single SQLite file containing the shared
`cell_core.genome.Genome` table. Trajectories coexist there with skill /
pattern / scar / insight entries, distinguished by `type='trajectory'`.

**Why not a separate Qdrant collection?** Two sources of truth, double
migration surface, and it would duplicate everything Genome already provides
(FTS5 search, confidence decay, valid_from/valid_to, inherit_genome). If
semantic vector search proves necessary later, the roadmap is a Qdrant
projection on top of the canonical Genome row — no breaking change.

## Architecture

```
  Cell pulse (sensor → thinker → actor → reflect)
              │
              ▼
  POST /api/experience/record         (FastAPI, auth required)
              │
              ▼
  ExperienceService.record()
    ├─ validates Pydantic contract (outcome whitelist, limits)
    ├─ calls Genome.record_trajectory()
    │     └─ UPSERT into genome WHERE type='trajectory'
    │         (write_lock, MAX(confidence), scope=Personal on failure)
    └─ invalidate_cache("zantara:experience:*")

  Thinker query (before reasoning from scratch)
              │
              ▼
  POST /api/experience/query
              │
              ▼
  ExperienceService.query()
    └─ Genome.search_trajectories()   (FTS5 + outcome/cell/tag filters)
```

## Data Model

Schema additions to `cell_core.genome` (Sprint 5.2, backward-compatible):

| Column        | Type    | Notes                                                |
| ------------- | ------- | ---------------------------------------------------- |
| `type`        | TEXT    | widened CHECK to include `'trajectory'`              |
| `outcome`     | TEXT    | `success|failure|partial` (nullable for non-traj)    |
| `tokens`      | INTEGER | nullable                                             |
| `duration_ms` | INTEGER | nullable                                             |
| `tags`        | TEXT    | JSON array of strings                                |

**Scope rule** (set automatically by `record_trajectory`):
- `outcome='failure'` → `scope='Personal'` (somatic, never germline)
- `outcome IN ('success', 'partial')` → `scope='Project'`

`inherit_genome()` excludes `type='trajectory'` regardless of scope —
episodes stay local to the cell that lived them. Only skills/patterns
transfer at fork time.

## Relation to `/api/memory/lam/episodes`

Superficial overlap — both accept `content`, `agent/cell`, `tags`, `outcome`
and persist episodes. They are deliberately separate:

| Aspect            | `/api/memory/lam/*`                           | `/api/experience/*`                              |
| ----------------- | --------------------------------------------- | ------------------------------------------------ |
| Store             | Qdrant `lam_episodes` (vector)                | SQLite Genome (`type='trajectory'`)              |
| Purpose           | Semantic recall for user-facing questions     | Episodic reflection for cell thinkers            |
| `outcome` shape   | Free-text string                              | Enum `success|failure|partial` (enforced 422)    |
| Inheritable       | No (user-scoped)                              | No (trajectories are never germline)             |
| Ownership         | LAM agent runtime                             | Cell post-pulse reflection                       |

If a cell needs to ask "what did user X do last Tuesday?" → LAM. If a cell
needs "have I ever tried this action and what happened?" → Experience.

Week 3 may introduce a unified index; until then, keep the boundary
explicit when calling.

## Environment Variables

| Variable               | Required | Description                                         |
| ---------------------- | -------- | --------------------------------------------------- |
| `EXPERIENCE_DB_PATH`   | ⚙️        | SQLite path (default: `~/.nuzantara/experience.db`) |
| `JWT_SECRET_KEY`       | ✅       | Required by backend-rag for auth middleware         |
| `API_KEYS`             | ✅       | Required by backend-rag for auth middleware         |

### ⚠️ Path constraints for Pro/Air dual-machine setup

**Do NOT** set `EXPERIENCE_DB_PATH` to anything under `shared/` or any
git-tracked directory. The Genome file is a binary WAL-mode SQLite and two
machines writing concurrent local copies synced by git would split-brain
(unmergeable binary conflicts — see `docs/AUTOMATION_AUTONOMY_SYSTEM_V3_3.md`
ADR-3/4 for the precedent on `escalations.jsonl`).

Safe defaults:
- **Pro**: `~/.nuzantara/experience.db` (default)
- **Air**: `~/.nuzantara/experience.db` (default, independent file)
- **Fly.io**: each worker starts its own temp file; a shared-store decision
  belongs in Week 3+ and should go through Postgres via `asyncpg` (see the
  same ADR-4 for the reasoning).

If Pro and Air must share knowledge in a future sprint, the path is
export/import via `Genome.export_genome()` / `Genome.import_genome()`
over the federation bus — NOT filesystem sync.

### Tag slug constraint

Tags accepted by `/record` and `/query` must match `[A-Za-z0-9_-]+`
(Pydantic validator). Quotes, backslashes, or whitespace in a tag are
rejected with 422. The reason is implementation-level: tags are stored
as a JSON array and the filter does `LIKE '%"<tag>"%'` against the
serialised form, which is exact-match for slugs but would silently miss
escaped characters. See `services/experience/models.py` for the pattern.

Optional: the service runs in **degraded mode** (is_available=False, record
and query become no-ops) if `cell_core` cannot be imported. This is an
intentional safety net per SYMBIOSIS Legge 4 — graceful degradation.

## API Endpoints

All require an authenticated user via `get_current_user`.

### `POST /api/experience/record`

```json
{
  "trajectory_id": "run_2026_04_15_abc",
  "cell": "curator_war_room",
  "outcome": "success",
  "procedure": "Published IG carousel cleanly.",
  "tokens": 1420,
  "duration_ms": 8750,
  "tags": ["ig", "carousel"],
  "confidence": 0.8
}
```

Response: `{"action": "inserted|updated", "trajectory_id": "..."}`.
Idempotent by `trajectory_id`; re-posting updates procedure/tags and keeps
`MAX(confidence)`.

422 for invalid outcome / empty procedure / `tokens < 0`.

### `POST /api/experience/query`

```json
{ "query": "DLP", "outcome": "failure", "cell": "curator", "tag": "ig", "limit": 20 }
```

Response: `{"query": "...", "count": N, "results": [TrajectoryResult, ...]}`.
FTS5 match on `procedure`. `limit` hard-capped at 100 by the Pydantic schema.

### `GET /api/experience/stats?cell=...`

Returns `{"total": N, "by_outcome": {"success": X, "failure": Y, "partial": Z}}`.

### `GET /api/experience/{trajectory_id}`

200 with the `TrajectoryResult`, or 404 when the id does not match a
trajectory row (skill/scar/pattern rows with the same id are rejected).

## Daily Operations

### Inspect the canonical store

```bash
sqlite3 ~/.nuzantara/experience.db \
  "SELECT id, cell_origin, outcome, confidence, valid_from
   FROM genome WHERE type='trajectory' ORDER BY valid_from DESC LIMIT 20;"
```

### Counts by outcome

```bash
curl -s http://localhost:8000/api/experience/stats \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Top failures from a given cell

```bash
curl -s -XPOST http://localhost:8000/api/experience/query \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"*","outcome":"failure","cell":"curator","limit":10}' | jq
```

### Back up the SQLite file

The Genome is a single WAL-mode SQLite file. Use the standard SQLite online
backup (safe while the backend is running):

```bash
sqlite3 ~/.nuzantara/experience.db ".backup /backups/experience_$(date +%F).db"
```

Restore is a file copy. Keep at least 7 dailies.

## Backfill from LAM Episodes

The script `backend/scripts/backfill_lam_to_experience.py` promotes LAM
episodes to trajectories **only when the outcome is unambiguous**
(`success|failure|partial`). Everything else is skipped — quality over
volume.

```bash
cd apps/backend-rag
source .venv/bin/activate

# Dry run first: surface how many LAM episodes have usable outcomes.
PYTHONPATH=. python backend/scripts/backfill_lam_to_experience.py --dry-run

# Actual run (idempotent via trajectory_id = "lam:{episode_id}").
PYTHONPATH=. python backend/scripts/backfill_lam_to_experience.py --limit 1000
```

Report format:

```json
{
  "total_seen": N,
  "recorded": N,
  "would_record": N,          # dry-run only
  "skipped_ambiguous": N,     # "completed", "done", unknown tokens
  "skipped_empty": N,         # no content
  "skipped_unknown_id": N,
  "errors": N
}
```

**Known ambiguous outcomes** (documented in `AMBIGUOUS_OUTCOMES` in the
script, with a matching test): `""`, `"unknown"`, `"completed"`, `"done"`,
`"finished"`, `"n/a"`, `"?"`, `"maybe"`. Re-run is safe — same ids upsert
into the same rows.

## Maintenance

### Silence stale trajectories

Trajectories with `confidence < 0.4` that have not been used in 30 days are
soft-silenced (`valid_to = today`) by the existing Genome hook
`silence_stale_skills(cell=..., unused_days=30)`. No separate cron needed
for Week 1-2 — this runs from cell pulses at DREAM phase.

### Vacuum

Rows silenced more than 90 days ago can be removed permanently via
`Genome.vacuum(days_silenced=90)`. Not scheduled in Week 1-2; revisit after
the corpus grows past ~5k rows.

## Troubleshooting

| Symptom                                 | Likely cause                                          | Fix                                                                  |
| --------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------- |
| `/api/experience/record` returns 500    | ExperienceService exception                           | check backend logs for `experience.record failed`                    |
| `action: "skipped"`                     | `cell-core` not importable in the deployed env        | ensure `cell-core` is installed editable in the backend-rag venv     |
| All queries return `count=0` after boot | `EXPERIENCE_DB_PATH` points to an empty / new file    | verify the env var; inspect with `sqlite3 … 'SELECT count(*) …'`     |
| 422 on every record                     | client sending `outcome` outside `success|failure|partial` | client must normalise first — see `normalize_outcome()` in the backfill script |

## Open Questions (Week 3+)

- Cron schedule for a periodic backfill as LAM episodes accumulate — do
  **not** add a cron without first running `--dry-run` on prod and reviewing
  the distribution of `outcome` values. If "completed" dominates, the
  upstream LAM vocabulary needs tightening before bulk backfill.
- Redis event on high-confidence failure trajectories (`rag.experience_failure`)
  so sibling cells can react in real time. Intentionally omitted in Week 1-2
  to avoid spam until the signal shape is understood.
- Qdrant projection (Option C from the design brainstorm) — only if FTS5
  plateaus on recall during Week 3 usage.

## References

- Design rationale: see SYMBIOSIS.md Pilastro 2 (Accumulazione) + Legge 4
  (Graceful degradation).
- Genome implementation: `packages/cell-core/cell_core/genome.py`.
- Router: `apps/backend-rag/backend/app/routers/experience.py`.
- Service: `apps/backend-rag/backend/services/experience/service.py`.
- Backfill: `apps/backend-rag/backend/scripts/backfill_lam_to_experience.py`.
