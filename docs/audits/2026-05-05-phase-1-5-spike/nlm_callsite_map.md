# NLM CLI callsite map — Phase 1.5 migration target inventory

**Date**: 2026-05-05
**Source**: Explore subagent dispatch on
`/Users/nuzantara/Desktop/nuzantara/.worktrees/phase-1-5-spike/`.
**Total**: 24 files · 82 subprocess callsites · 0 direct
`mcp__notebooklm-mcp__*` invocations in production code.

## Distribution

| App | Callsites | Files |
|---|---|---|
| `evaluator/nlm_deep_research/` | 65 | 17 (PRIMARY MIGRATION TARGET) |
| `mata-garuda/` | 9 | 3 |
| `backend-rag/` | 4 | 2 |
| `bali-intel-scraper/` | 2 | 1 |
| `cell/` | 2 | 1 |
| `nuzantara-mcp/` | 0 | 0 (uses MCP tools directly) |

## Top 5 highest-impact files (priority for migration)

1. **`apps/evaluator/nlm_deep_research/nlm_bridge.py`** (2 callsites,
   both query) — Core query abstraction layer, called by
   NLMPipeline. Migrating this alone unblocks ~30 downstream callers.
2. **`apps/evaluator/nlm_deep_research/multimodal_pipeline.py`** (2
   callsites, create+download) — Weekly artifact generation
   (audio/infographic/mindmap/report).
3. **`apps/evaluator/nlm_deep_research/gap_scanner.py`** (3 callsites,
   query+add) — Gap detection & source ingestion (already fed by
   PR #450 keyword fast-path; chat.ask only on gap-found path so
   slow chat impact is bounded).
4. **`apps/evaluator/nlm_deep_research/freshness_monitor.py`** (5
   callsites, mixed) — Source freshness checks + research triggers.
5. **`apps/evaluator/nlm_deep_research/db_to_nlm_sync.py`** (3
   callsites, add+delete) — Database-to-notebook sync.

## Call type breakdown (production)

| nlm command | Callsite count | Adapter mapping |
|---|---|---|
| `nlm query notebook <id> <query>` | 18+ | `notebook_query()` |
| `nlm source add <id> <url>` | 6+ | `source_add(source_type="url", url=...)` |
| `nlm source delete <id> <sid>` | 4+ | `source_delete()` |
| `nlm audio/infographic/mindmap/report create <id>` | 4 | `client.artifacts.generate_*` (multimodal_pipeline only) |
| `nlm download <type> <id> --output <path>` | 2 | `client.artifacts.download_*` |
| `nlm notebook configure <id>` | 1 | `client.chat.configure` |
| `nlm research start <id> --query <q> --mode <m>` | 2 | `research_start()` + `research_status()` |

## Test infrastructure

20+ subprocess mocks in `tests/test_*.py`. These will need parallel
update to mock the adapter functions instead of `subprocess.run`.

## Migration tier strategy

- **Tier 1 — `evaluator/nlm_deep_research/`** (65 callsites, 17 files):
  Highest impact, lowest risk (cron-driven, off-peak). Migrate Week 2.
- **Tier 2 — `backend-rag/`** (4 callsites, 2 files): User-facing path
  through `cross_notebook_correlator.py`. Requires latency
  measurement post-migration. Week 3.
- **Tier 3 — `mata-garuda/` + `bali-intel-scraper/` + `cell/`** (13
  callsites, 5 files): Lowest priority — agent-side workers and
  effectors that already tolerate slow paths. Week 3-4.

## Files inventoried

```
apps/evaluator/nlm_deep_research/
├── nlm_bridge.py                  (2 callsites)
├── source_snapshot.py             (1 callsite)
├── yt_monitor.py                  (1 callsite)
├── multimodal_pipeline.py         (2 callsites)
├── ops_intelligence.py            (1 callsite)
├── persona_engine.py              (4 callsites)
├── cross_notebook_correlator.py   (1 callsite)
├── gap_scanner.py                 (3 callsites)
├── db_to_nlm_sync.py              (3 callsites)
├── freshness_monitor.py           (5 callsites)
├── heartbeat_monitor.py           (2 callsites)
├── synthesis_roller.py            (3 callsites)
└── tests/test_*.py                (~30 callsites — test mocks)

apps/backend-rag/
├── backend/services/oracle/cross_notebook_correlator.py  (1 callsite)
├── backend/tests/unit/services/oracle/test_cross_notebook_correlator.py  (5 mocks)
└── scripts/nlm_claims_extractor.py  (2 callsites)

apps/mata-garuda/
├── mata_garuda/tools/nlm_tools.py        (3 callsites)
├── mata_garuda/workers/nlm_feeder.py     (3 callsites)
├── mata_garuda/cells/actors/sentinel_actor.py  (3 callsites)
└── tests/test_nlm_expander_agent.py      (3 mocks)

apps/bali-intel-scraper/
└── scripts/nlm_research_step.py          (3 callsites)

apps/cell/
└── cell/effectors/nlm_effector.py        (2 callsites)
```
