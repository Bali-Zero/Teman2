# Skill Registry — Operations Runbook

**System:** Mata Garuda Layer 4.5 — Curator Agent Sprint 5.2 Week 3-4
**Last updated:** 2026-04-16
**Owner:** Zero / Bali Zero AI Team

## Overview

The Skill Registry is the germline counterpart of the Experience Library. Where
Experience records **episodes** (trajectories of sense→think→act→reflect),
Skills record the **reusable procedures** those episodes distil into. Both
live in the same `cell_core.genome` SQLite, distinguished by `type`.

Week 3-4 introduced three additions on top of Week 1-2 foundations:

1. A `tier` column (`NULL | tier1 | tier2`) with monotonic auto-promotion
   (`Genome.promote_skills`) and finer-grained soft-decay
   (`Genome.silence_stale_skills_v2`).
2. `/api/skill/*` — a FastAPI surface symmetric to `/api/experience/*`.
3. Three offline jobs that **propose** changes (never auto-apply, per
   SYMBIOSIS Legge 5): skill seeding, merge-by-cosine, and
   Experience→Skill aggregation.

**Canonical store:** the same SQLite file as the Experience Library
(`~/.nuzantara/experience.db` by default, overridable via
`EXPERIENCE_DB_PATH`). A separate DB would split the inheritance graph.

**Why not a separate table?** The `type` column already segregates skills
from trajectories at query time, and sharing the table means a single
`valid_to`, a single `inherit_genome`, and one FTS5 index to maintain.

## Architecture

```
  Cell pulse records an episode
              │
              ▼
  POST /api/experience/record       (Week 1-2 — trajectories)
              │
              ▼ (weekly, dry-run)
  scripts/experience_to_skill_aggregator.py
              │
              ▼ writes proposals to
  ~/.nuzantara/skill_creation_proposals.jsonl
              │
              ▼ (Zero reviews)
  POST /api/skill/record            (Week 3-4 — canonical skills)
              │
              ▼
  SkillService.record → Genome.record_skill (type='skill')
              │
              ▼ (weekly cron, DOCUMENTED but NOT active)
  Genome.silence_stale_skills_v2 → Genome.promote_skills
              │                               │
              │                               ▼ tier1/tier2 surfaced at
              │                        GET /api/skill/top
              ▼ proposes merges via
  scripts/skill_merge_proposals.py
              │
              ▼ reads at
  GET /api/skill/merge-proposals
```

## Data Model

Additions to `cell_core.genome` in Week 3-4 (backward-compatible — legacy DBs
gain the `tier` column at first open):

| Column | Type | Notes                                            |
| ------ | ---- | ------------------------------------------------ |
| `tier` | TEXT | `tier1` \| `tier2` \| NULL (CHECK on fresh DB)   |

**Tier thresholds** (class constants on `Genome`):

| Tier  | Uses (≥) | Confidence (≥) | Promoted by |
| ----- | -------- | -------------- | ----------- |
| tier1 | 100      | 0.85           | `promote_skills()` — never downgrades |
| tier2 | 30       | 0.70           | `promote_skills()` — only promotes tier=NULL rows |

**Silencing rules** (`silence_stale_skills_v2`, type='skill' only):

1. `confidence < 0.3` → silenced (regardless of uses).
2. `uses < 5` AND `COALESCE(last_used, valid_from)` is more than
   `unused_days` (default 30) in the past → silenced.

Silencing sets `valid_to = today`; it is always reversible (set `valid_to =
NULL`) and never deletes the row.

## Relation to Experience Library

| Aspect          | `/api/experience/*`                             | `/api/skill/*`                                   |
| --------------- | ----------------------------------------------- | ------------------------------------------------ |
| Genome `type`   | `trajectory`                                    | `skill`                                          |
| Episode / Skill | Episode (outcome + tokens + duration)           | Reusable procedure (precondition + body + success) |
| Inherit         | NO (episodes stay on the cell that lived them)  | YES via `inherit_genome` when scope=Project      |
| Tier            | n/a                                             | `NULL | tier1 | tier2`                            |
| Auto-promotion  | n/a                                             | `Genome.promote_skills` (weekly cron, not active yet) |
| Auto-decay      | inherits legacy `silence_stale_skills`          | `silence_stale_skills_v2` (finer rules)          |

If a cell needs "what episode happened" → Experience. If a cell needs "what's
the canonical way to do X" → Skill.

## Environment Variables

| Variable                        | Required | Description                                              |
| ------------------------------- | -------- | -------------------------------------------------------- |
| `EXPERIENCE_DB_PATH`            | ⚙️        | SQLite path (shared with Experience Library)             |
| `SKILL_MERGE_PROPOSALS_PATH`    | ⚙️        | jsonl target for `skill_merge_proposals.py` (default `~/.nuzantara/skill_merge_proposals.jsonl`) |
| `SKILL_CREATION_PROPOSALS_PATH` | ⚙️        | jsonl target for `experience_to_skill_aggregator.py`     |
| `OPENAI_API_KEY`                | ✅       | Required by the merge-proposals job (text-embedding-3-small) |
| `JWT_SECRET_KEY`, `API_KEYS`    | ✅       | Auth for the HTTP surface                                 |

### Path constraints (same as Experience Library)

Do NOT move the Genome SQLite under `shared/` or any git-tracked directory.
Binary WAL files do not merge. Pro and Air keep independent local files;
cross-machine sharing is via `Genome.export_genome()` / `import_genome()`
over the federation bus, not filesystem sync.

## API Endpoints

All require an authenticated user via `get_current_user`.

### `POST /api/skill/record`

Register or upsert a reusable skill.

```json
{
  "cell": "rag",
  "skill_id": "rag:chunk_with_overlap",
  "procedure": "Split documents into 10000-char windows with 800-char overlap.",
  "precondition": "Document pre-processed (OCR done, layout normalised).",
  "success_criterion": "No chunk loses context needed for its neighbour's question.",
  "confidence": 0.8,
  "scope": "Project"
}
```

Response: `{"action": "inserted|updated", "skill_id": "..."}`.
Idempotent by `skill_id`; the upsert preserves any existing `tier` and keeps
`MAX(confidence)`.

422 for empty procedure, out-of-range confidence, or scope ≠ Project|Personal.

### `POST /api/skill/query`

FTS5 full-text match on procedure/precondition/success_criterion with
optional tier + cell + min_confidence filters.

```json
{
  "query": "DLP",
  "cell": "safety",
  "tier": "tier1",
  "min_confidence": 0.7,
  "limit": 20
}
```

Response: `{"query": "...", "count": N, "results": [SkillResult, ...]}`.

### `GET /api/skill/stats`

```json
{
  "total": 32,
  "by_tier": {"tier1": 0, "tier2": 0, "untiered": 32},
  "by_cell": {"rag": 3, "crm": 3, "article_composer": 2, ...},
  "avg_confidence": 0.77
}
```

### `GET /api/skill/top?tier=tier1&limit=20`

Returns active skills at the requested tier, ordered by confidence then uses.
Defaults to `tier1`. `limit` capped at 100.

### `GET /api/skill/merge-proposals`

Reads `SKILL_MERGE_PROPOSALS_PATH` jsonl (written by the weekly merge job).
Empty response when the file doesn't exist yet.

```json
{
  "count": 2,
  "proposals": [
    {"pair": ["rag:rrf_v1", "rag:rrf_v2"], "cosine": 0.08, "rationale": "...", "procedures": {...}}
  ]
}
```

### `GET /api/skill/{skill_id}`

200 with the `SkillResult`, or 404 when the id doesn't match a skill row
(trajectory rows with the same id are filtered out).

## Offline Jobs

### Seed the Registry (one-off, curated)

`scripts/seed_initial_skills.py` ships 32 canonical skills (20+ cells,
average confidence ≈ 0.77). Run once on a fresh environment; idempotent
afterwards.

```bash
cd apps/backend-rag
source .venv/bin/activate

# Dry-run — see the distribution.
PYTHONPATH=. python backend/scripts/seed_initial_skills.py

# Actually write into ~/.nuzantara/experience.db.
PYTHONPATH=. python backend/scripts/seed_initial_skills.py --apply
```

### Catalog (discovery, NOT used for Week 3-4 PR)

`scripts/catalog_initial_skills.py` performs an AST scan across
`apps/backend-rag` and `apps/mata-garuda`, proposing thousands of candidates.
Kept as a diagnostic tool — the `--dry-run` output is inherently noisy
(~1,100 candidates on the full tree). Not used in production until we have a
better filtering heuristic.

### Merge proposals (weekly, NOT scheduled yet)

`scripts/skill_merge_proposals.py` embeds every active skill with
`text-embedding-3-small` (1536 dims, FROZEN), computes pairwise cosine
distance, and writes pairs under the threshold to a jsonl:

```bash
PYTHONPATH=. python backend/scripts/skill_merge_proposals.py \
    --db-path ~/.nuzantara/experience.db \
    --out ~/.nuzantara/skill_merge_proposals.jsonl \
    --threshold 0.15
```

Never merges — only suggests. Zero reads via `GET /api/skill/merge-proposals`
and decides.

### Experience → Skill aggregation (weekly, NOT scheduled yet)

`scripts/experience_to_skill_aggregator.py` clusters successful trajectories
by (cell, sorted tags) inside a rolling window. When a cluster hits
`--min-cluster-size` entries, it writes a proposal (with confidence=0.45,
below the curated seed default of 0.6):

```bash
PYTHONPATH=. python backend/scripts/experience_to_skill_aggregator.py \
    --min-cluster-size 10 --window-days 7
```

Never creates — only suggests. Zero reviews and either recorded the skill
manually via `POST /api/skill/record` or ignores the proposal.

## Daily Operations

### Inspect the canonical store

```bash
sqlite3 ~/.nuzantara/experience.db \
  "SELECT id, cell_origin, tier, confidence, uses, valid_from
   FROM genome WHERE type='skill' ORDER BY confidence DESC LIMIT 20;"
```

### Stats via the API

```bash
curl -s http://localhost:8000/api/skill/stats \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Tier1 drilldown

```bash
curl -s "http://localhost:8000/api/skill/top?tier=tier1&limit=10" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Fresh proposals

```bash
cat ~/.nuzantara/skill_merge_proposals.jsonl | jq -c '{pair, cosine}' | head
cat ~/.nuzantara/skill_creation_proposals.jsonl | jq -c '{cell, skill_id, n_trajectories}' | head
```

## Maintenance

### Soft-decay (implemented, weekly cron NOT active yet)

`Genome.silence_stale_skills_v2()` is called in-process by the planned
Sunday 06:00 WITA cron (see `docs/ACTIVE_AUTOMATIONS.md` → **PLANNED**
section). The cron is documented but intentionally not wired: we need ≥4
weeks of real `/api/skill/record` usage before we trust the thresholds.

### Promotion (implemented, weekly cron NOT active yet)

Same schedule. `Genome.promote_skills()` runs after decay. Promotion is
monotonic (a tier1 skill never drops to tier2 or NULL by this call).

### Vacuum (manual)

Skills silenced for more than 90 days can be removed from disk via
`Genome.vacuum(days_silenced=90)`. Not scheduled; revisit once the table
grows past ~10k rows.

## Troubleshooting

| Symptom                                          | Likely cause                                              | Fix                                                                                 |
| ------------------------------------------------ | --------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `/api/skill/record` returns 500                  | SkillService exception                                    | check backend logs for `skill.record failed`                                       |
| `action: "skipped"` / `"genome_unavailable"`     | `cell-core` not installed editable in the backend-rag venv | `pip install -e packages/cell-core` inside `apps/backend-rag/.venv`                 |
| `/api/skill/stats` shows 0 skills after boot     | `EXPERIENCE_DB_PATH` points to an empty file              | verify the env var; `sqlite3 $EXPERIENCE_DB_PATH "SELECT COUNT(*) FROM genome WHERE type='skill'"` |
| 422 on every record                              | client sending empty precondition/success_criterion        | both fields are required by Pydantic — enforce upstream                             |
| Merge proposals file stays empty                 | fewer than 2 active skills, or threshold too tight        | lower `--threshold`, check `/api/skill/stats.total`                                 |
| Aggregator proposals file stays empty            | no (cell, tags) cluster hits `--min-cluster-size`         | lower the threshold temporarily for inspection; `--window-days` can widen the lens  |

## Design Notes (from DeepSeek R1 federation review, 2026-04-16)

### Confidence growth: why aggregated skills CAN reach tier1

Aggregated skills start at `confidence=0.45` (below the seed default 0.6). The
tier1 threshold is `confidence ≥ 0.85 AND uses ≥ 100`. The growth path is
implicit in `Genome.use_skill`: each successful invocation bumps confidence by
`+0.02` (clamped at 1.0). Arithmetic: by the time a skill has accumulated 100
uses, its confidence is at least `0.45 + 100*0.02 = 2.45` — clamped to 1.0,
well past the `≥ 0.85` bar. So aggregate skills *do* converge to tier1 under
sustained real usage; no manual confidence bump is required.

If `use_skill` is not being called on a Skill Registry entry, the registry is
effectively cold regardless of tier. Hook it in whenever a cell actually acts
on a recalled skill — else promotion will stall by design.

### Aggregator ↔ Merge-proposals overlap is intentional

`experience_to_skill_aggregator.py` creates proposals for NEW skills from
successful trajectory clusters (exact-tag match). `skill_merge_proposals.py`
proposes MERGES between already-recorded skills (embedding similarity on the
full `precondition | procedure | success_criterion` triple). The two can both
fire on the same skill family — e.g. an aggregate gets recorded, then the
merge job flags it as near-duplicate of an older seed. This is by design:
both are propose-only, both land in different jsonl files, and Zero decides
the order. Deduplication at the proposal layer would hide context the human
needs to judge (was this an aggregation good enough to supplant the seed, or
should it be merged into it?).

### Merge embedding uses the FULL triple, not just procedure

`find_merge_candidates` in `skill_merge_proposals.py` embeds
`f"{precondition} | {procedure} | {success_criterion}"` — not just
`procedure`. Two skills that share a procedure body but apply to different
contexts (tourist vs business visa, for example) keep distinct vectors and do
not get proposed as a merge. Regression test:
`test_embedder_receives_full_precondition_procedure_success_triple` in
`backend/tests/unit/scripts/test_skill_merge_proposals.py`.

## Open Questions (Week 5+)

- Activation of the weekly cron (Sunday 06:00 WITA) once we have 4 weeks of
  production use-count data.
- Real-world thresholds: the `TIER1_MIN_USES=100` assumption came from a
  rough estimate of Curator+RAG daily pulses. If real traffic is ≤ 20/day
  per skill, tier1 would be unreachable — then we lower the bar.
- Qdrant projection of active skills for semantic search (not FTS). Held for
  Week 5+ on the same reasoning as the Experience Library runbook.
- Endpoint `POST /api/skill/merge-apply` for Zero to approve a single
  merge from the proposals jsonl (atomic, reversible via `valid_to`).

## References

- Design rationale: SYMBIOSIS.md Pilastro 2 (Accumulazione) + Legge 5 (Zero
  ultima istanza).
- Companion runbook: `docs/EXPERIENCE_LIBRARY_OPS.md`.
- Genome implementation: `packages/cell-core/cell_core/genome.py`.
- Router: `apps/backend-rag/backend/app/routers/skill.py`.
- Service: `apps/backend-rag/backend/services/skill/service.py`.
- Seed script: `apps/backend-rag/backend/scripts/seed_initial_skills.py`.
- Merge proposals: `apps/backend-rag/backend/scripts/skill_merge_proposals.py`.
- Aggregator: `apps/backend-rag/backend/scripts/experience_to_skill_aggregator.py`.
