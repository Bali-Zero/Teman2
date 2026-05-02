# intel-scraper-cell — light promotion (Sprint 1)

**Sprint:** 1 (PR-1.1 cell definition; PR-1.2 emit instrumentation tracked separately)
**Reference:** brainstorm 2026-05-02 round 2 § "8. intel-scraper-cell ⭐ LEGGERA"
**Cell file:** `packages/cell-core/cells/intel_scraper_cell.yaml`

## What this cell IS (and is NOT)

This is a **LIGHT** cell promotion. Concretely:

- ✅ Genome scar registry (cell-core SQLite — `cell_core/genome.py`)
- ✅ HGT publisher contract (`domain=news`, publisher_only)
- ✅ ObservedShellBus emit at lifecycle points *(Sprint 1 PR-1.2)*
- ❌ NO PulseLoop (no continuous heartbeat reasoning)
- ❌ NO Homeostasis (no autonomic feedback control)
- ❌ NO HGT consumer (does not pull skills from other cells)
- ❌ NO new runtime — wraps existing production runners

## Three production runners → one cell

The cell consolidates three already-running production paths under a single
declarative envelope. **None of these runners change behavior** as a result
of the cell promotion — the YAML definition is a registry entry that future
admission tests (Sprint 4+) and HGT publishing (Sprint 5+) can reference.

| Runner | Cell role | Cadence | Source path |
|---|---|---|---|
| `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` | **Body** — 8-step daily pipeline | 03:00 WITA via OpenClaw cron on Pro | `apps/bali-intel-scraper/` |
| `cron-agent-python intel-radar` | **HGT publisher** — multi-source aggregator, INSERTs `trend_signals` (mig 113) → DB trigger fires `intel_event` channel | hourly | `~/.cron-agent-python/strategies/intel_radar.py` |
| `cron-agent-python intel-feed-processor` | **Light sensor** — crawl + parse, feeds raw signals to body's enricher | every 2h | `~/.cron-agent-python/strategies/intel_feed_processor.py` |

The trigger-based emission to `intel_event` channel is what satisfies Law 3
(Event-driven). The cell itself does NOT call `pg_notify` — the existing
`trend_signals` INSERT trigger does that on data write. From the
admission-test perspective `publishes_via: pg_trigger`.

## 7 Leggi admission status

Verified via `cell_core.cell_loader.load_cell_definition()` →
`AdmissionTest().run_all()`:

| Legge | Status | Note |
|---|---|---|
| 1. CLI-only | ✅ | `llm_invocation: cli` (Claude CLI subprocess via `CLAUDE_CODE_OAUTH_TOKEN`) |
| 2. OSINT blindato | ✅ | `external_sources` declared, `client_data_access: false` — no contamination |
| 3. Event-driven | ✅ | `publishes_via: pg_trigger` (existing `trend_signals` mig 113) |
| 4. Graceful degradation | ✅ | 3 fallback modes (LLM down → Ollama, Qdrant down → JSONL, Drive OAuth → 5-min CB) |
| 5. Zero final instance | ✅ | `kill_switch: true`, `auto_publishes: false` (Telegram review gate) |
| 6. Local sovereignty | ✅ | `depends_on_other_cell_decisions: false` |
| 7. Numbers first | ✅ | 5 metrics declared (articles_processed, dedup_filtered, qdrant_upsert_count, p99_latency_ms, llm_provider_fallback_rate) |

The full assertion lives in `packages/cell-core/tests/test_cell_loader.py`
`test_intel_scraper_cell_passes_admission`.

## What's in scope for THIS PR (Sprint 1 PR-1.1)

1. `packages/cell-core/cells/intel_scraper_cell.yaml` — declarative def
2. `packages/cell-core/cell_core/cell_loader.py` — YAML → dict loader
3. `packages/cell-core/tests/test_cell_loader.py` — 8 tests (incl admission PASS)
4. `pyyaml>=6.0` added to `packages/cell-core/pyproject.toml` deps
5. This doc

## What's NOT in scope (deferred to Sprint 1 PR-1.2)

1. `apps/backend-rag/backend/app/routers/observed_shell.py` — HTTP endpoint
   `POST /api/observed-shell/emit` for shell wrappers
2. `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` instrumentation —
   call the endpoint at lifecycle points (start, success, error)
3. cron-agent-python intel-radar / intel-feed-processor instrumentation
4. Full integration test that spawns the bash wrapper + asserts the row
   lands in `observed_shell_events` table

The split is intentional: PR-1.1 lands the cell registration with no
runtime code-path change. PR-1.2 wires the actual emit, which has a larger
blast radius (touches manifest + 2 router_registration include functions
+ public_endpoints registry, per Sprint 1.B cicatrix).

## Why split

Sprint 1.B Era Post-Agentica (cicatrix 2026-05-02) showed that adding a
new HTTP endpoint requires touching 5 files in lockstep: router file,
manifest, 2 registration functions, public_endpoints. Bundling that with
the cell declaration would mix two different review surfaces and risk a
3-PR hotfix chain like Sprint 1.B did. Cell-side declaration first, HTTP
plumbing second.

## References

- `packages/cell-core/cells/intel_scraper_cell.yaml` (definition)
- `packages/cell-core/cell_core/admission_test.py` (Sprint 0 framework)
- `docs/cell-core/admission-test-rubric.md` (Sprint 0 rubric)
- `docs/cell-core/observed-shell-tier.md` (Sprint 0 — HTTP endpoint plan)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md`
  § "Sprint 1 — Intel Scraper light + HGT quarantine"
- `apps/organism/organism/genome.yaml` `pro.intel_nightly` (Innervation organ)
- `apps/backend-rag/backend/db/migrations_v2/113_intel_radar_findings.sql`
  (existing trigger that emits `intel_event`)
