---
date: 2026-05-13
domain: symbiosis
client_case: SYMBIOSIS Phase 3 — TICKET B narrow spec v2 (post 4-panel)
status: spec-v2-execution-ready
empirical_survey_wita: 2026-05-13 00:55
review_completed_wita: 2026-05-13 01:08
---

# TICKET B — IntelScraperHGTBridge post-pipeline emit (narrow spec v2)

**Date**: 2026-05-13 00:55 WITA · **Revised**: 01:10 WITA post-review
**Predecessor**: TICKET A.2 EXECUTION merged (PR #636 → main `848e76a65` at 00:52 WITA)
**Author**: Claude Opus 4.7 max
**Mode**: Narrow spec — bounded blast via try/except fallback
**Estimated effort**: ~1.25 days code + tests
**Review status**: APPROVED with 7 corrections — Claude self PROCEED + Gemini PROCEED + DeepSeek PROCEED + NB-1 BLOCK addressable (schema-drift `source_name` fix absorbed; "use FastAPI routers" rejected as not-applicable-to-cron)

## Goal

Wire `IntelScraperHGTBridge` (from `apps/bali-intel-scraper/backend/cell/hgt_publisher.py:116`) into production cron entry `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` (2158 LOC, sync) via async post-emit sidecar. After TICKET B merge:

- `redis-cli XLEN cell:skills` increments with `intel.source.rss_feed_stable_<source>_<run_id>` entries per nightly cron when ≥1 source yields ≥3 articles
- Combined with A.2 (PR #636 crm-cell publisher), `cell:skills` has 2 production publishers feeding sentinel-1 consumer-group (when TICKET C ships)

## ARCHITECTURAL PIVOT (post-review)

Spec v1 proposed using `IntelScraperCellRunner` (which requires `event_bridge: IntelScraperEventBridge`). Empirical re-verify after Gemini/DeepSeek/NB-1 review:

- `IntelScraperEventBridge(bus)` constructor REQUIRES `ObservedShellBus`-like (which lives in `apps/backend-rag/backend/services/events/observed_shell.py`)
- Cross-package import from intel-scraper-cell to backend-rag is architecturally smelly
- `DATABASE_URL` is NOT set in `com.balizero.intel.nightly.plist` (verified plutil-extract)
- DeepSeek F1 HIGH: missing DATABASE_URL → silent no-op (preflight returns None)

**Pivot**: Use `IntelScraperHGTBridge` directly (no event_bridge needed). HGT-only path. Trade-off: lose observatory.db emission for intel-scraper-cell runs, but gain DATABASE_URL-independence + simpler dependency tree. Observatory emission deferred to TICKET B-followup PR.

This pivot satisfies CORR-B2 (DATABASE_URL optional) by making it irrelevant.

## 4-panel review convergences applied (7 corrections)

| #   | Original spec v1                                   | 4-panel verdict                                           | Correction in v2                                                                                 |
| --- | -------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 1   | Pattern emission deferred (counters only)          | Claude F1 + Gemini F1 + DeepSeek F4 HIGH unanimous        | SHIP ≥1 structural pattern `intel.source.rss_feed_stable_<source>_<run_id>`                      |
| 2   | Use IntelScraperCellRunner (requires event_bridge) | DeepSeek F1 HIGH DATABASE_URL missing → silent no-op      | PIVOT: use IntelScraperHGTBridge directly, skip event_bridge                                     |
| 3   | `art.get('source')` field                          | NB-1 BLOCK condition: schema drift, `source_name` primary | `art.get('source_name', art.get('source', art.get('url', 'unknown')))` (5 grep matches verified) |
| 4   | `asyncio.run(emit_pipeline_run(...))` unbounded    | Gemini F2 MEDIUM                                          | `asyncio.wait_for(emit_pipeline_run(...), timeout=60.0)` for cron safety                         |
| 5   | preflight exception no client.aclose               | Gemini F3 LOW + DeepSeek F2                               | `await client.aclose()` in except block                                                          |
| 6   | pipeline.state keys unknown                        | DeepSeek F3 LOW                                           | Log `pipeline_state_keys` on emit skip                                                           |
| 7   | NB-1 "use FastAPI router"                          | NB-1 misapplied                                           | REJECTED: cron invokes script directly, not HTTP endpoint                                        |

## Empirical state (2026-05-13 00:55 WITA — re-verified)

| Item                                                                 | Status                                                                                      |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| TICKET A.0 cell_name public property                                 | ✅ merged main `6e92046d8`                                                                  |
| TICKET A.1 CrmHGTBridge async                                        | ✅ merged main `84953041b`                                                                  |
| TICKET A.2 crm_hgt_handlers production caller                        | ✅ merged main `848e76a65`                                                                  |
| IntelScraperHGTBridge.from_redis                                     | ✅ exists at line 116                                                                       |
| `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` cell imports | ✅ 0 matches (target)                                                                       |
| plist REDIS_URL env var                                              | ✅ NOT SET (default localhost canonical)                                                    |
| plist DATABASE_URL env var                                           | ✅ NOT SET (informs HGT-only pivot)                                                         |
| `redis-cli -h 127.0.0.1 XLEN cell:skills`                            | ✅ 18 (Phase 2.5 seed)                                                                      |
| IntelPipeline.run() sync vs async                                    | SYNC (line 2019)                                                                            |
| Schema drift `source` vs `source_name`                               | EMPIRICAL: lines 429/959/1169/1475/1750 use `art.get('source_name', art.get('source', ''))` |

## Implementation (Option β HGT-only pivot)

### File 1: `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` (modify `main()`)

Add argparse flag (line ~2125):

```python
parser.add_argument('--no-cell-emit', action='store_true',
                   help='Disable Phase 3 cell-aware HGT post-emit (debug only)')
```

Modify last block of `main()` (line ~2155):

```python
    success = pipeline.run()

    # Phase 3 TICKET B — IntelScraperHGTBridge async post-emit (bounded blast).
    # See spec v2: research/symbiosis/2026-05-13-ticket-b-narrow-spec.md
    if not args.no_cell_emit:
        try:
            import asyncio
            from backend.cell.cell_post_emit import emit_pipeline_run

            asyncio.run(
                asyncio.wait_for(
                    emit_pipeline_run(pipeline.state),
                    timeout=60.0,
                )
            )
        except asyncio.TimeoutError:
            print("⚠️ cell post-emit timeout after 60s (non-fatal)",
                  file=sys.stderr)
        except Exception as cell_exc:
            print(f"⚠️ cell post-emit skipped (non-fatal): {cell_exc}",
                  file=sys.stderr)

    sys.exit(0 if success else 1)
```

### File 2: `apps/bali-intel-scraper/backend/cell/cell_post_emit.py` (NEW)

Module with `_build_hgt_bridge`, `_extract_source`, `emit_pipeline_run`. Key responsibilities:

1. **Preflight check**: XLEN cell:skills ≥18 signature; abort if wrong Redis instance
2. **Schema-drift handling**: `_extract_source` returns first of `source_name`/`source`/`url`/`'unknown'`
3. **Aggregate**: `source_counts` defaultdict counting articles per canonical source
4. **Threshold**: emit pattern only for sources with ≥3 articles
5. **Pattern build**: `StructuralPattern(pattern_id=f"rss_feed_stable_{source}_{run_id}", source=..., procedure=..., precondition="nightly intel-scraper crawl", success_criterion="...", confidence=0.8, domain="news")`
6. **Best-effort publish**: try/except per pattern, log per failure
7. **Resource cleanup**: `await client.aclose()` in preflight exception path

### File 3: `apps/bali-intel-scraper/tests/integration/test_cell_post_emit.py` (NEW, 6 tests)

| #   | Test                                                       | Verifies                                                                                            |
| --- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 1   | `test_build_hgt_bridge_succeeds_with_seed_signature`       | XLEN=18 → bridge instantiated, no exception                                                         |
| 2   | `test_build_hgt_bridge_fails_below_seed`                   | XLEN=0 → returns None + client.aclose called                                                        |
| 3   | `test_emit_pipeline_run_no_bridge_is_noop`                 | bridge=None → return without exception                                                              |
| 4   | `test_emit_pipeline_run_no_articles_skips`                 | articles=[] → log + return, no pattern                                                              |
| 5   | `test_emit_pipeline_run_publishes_pattern_above_threshold` | ≥3 articles/source → bridge.publish called with StructuralPattern, canonical 9-field shape verified |
| 6   | `test_extract_source_schema_drift`                         | source_name primary, source fallback, url last, 'unknown' final                                     |

## Acceptance criteria

1. ✅ CI tests green: `pytest apps/bali-intel-scraper/tests/integration/test_cell_post_emit.py -v` → 6/6
2. ✅ Regression: `pytest apps/bali-intel-scraper/tests/unit/cell/ -v` → 8/8 (existing tests preserved)
3. ✅ `grep "emit_pipeline_run\|cell_post_emit" apps/bali-intel-scraper/scripts/run_intel_pipeline.py` returns ≥1 match
4. ✅ Manual smoke (operator): `python scripts/run_intel_pipeline.py --mode dry-run --limit 5` exits 0; if articles yield ≥3 per source, `redis-cli XLEN cell:skills` increments
5. ✅ Production cron `com.balizero.intel.nightly` 03:00 WITA next night: log "intel_scraper.hgt_emit_complete strong_sources=N published=N"
6. ✅ No regression in pipeline.run() return code

## Refusals (Phase 3 spec v2 §14)

- ❌ No edits to `com.balizero.intel.nightly.plist` (refusal #10 — operator-gated; pivot to HGT-only sidesteps need for env var addition)
- ❌ No new PG_CHANNEL_MAP entries
- ❌ No edits to `packages/cell-core/cell_core/hgt/*` (A.0 only)
- ❌ No edits to seo_cell or compliance_handlers (additive)
- ❌ No HGT kill-switch lift
- ❌ No synchronous Redis calls in handler code
- ❌ No edits to `apps/backend-rag/backend/services/events/observed_shell.py`
- ❌ No edits to `apps/bali-intel-scraper/backend/cell/runner.py` or `event_bridge.py` (pivot avoids them)

## Pattern v1 spec

**`intel.source.rss_feed_stable_<source>_<run_id>`**:

- domain: `news`
- confidence: 0.8 (above floor)
- trigger: ≥3 articles from same source in nightly run
- procedure: "Source X consistently yields articles (N in nightly run Y)"
- precondition: "nightly intel-scraper crawl"
- success_criterion: "source X yields ≥3 articles in next nightly run"

**Deferred to TICKET B-followup**:

- `intel.source.rss_feed_unstable_<source>` (≤1 article/run for ≥3 runs)
- `intel.source.sitemap_pattern_<source>` (specific URL pattern discovered)
- `intel.scraper.runtime_baseline` (typical run duration distribution)

## Effort estimate

| Component                               | Hours                |
| --------------------------------------- | -------------------- |
| Spec v2 (this doc)                      | 1                    |
| cell_post_emit.py implementation        | 3                    |
| Modify run_intel_pipeline.py + argparse | 0.5                  |
| 6 integration tests                     | 3                    |
| Empirical verification + risks doc      | 0.5                  |
| **Total v2**                            | **~8h (~1.25 days)** |

## Sequencing

A.0 ✅ → A.1 ✅ → A.2 ✅ → **B v2** (this PR + execution) → C → 14d soak → FASE 4 lift.

## Risks

| Risk                                                  | Severity | Mitigation                                               |
| ----------------------------------------------------- | -------- | -------------------------------------------------------- |
| Wrong Redis (Mini split-brain)                        | HIGH     | XLEN ≥18 preflight signature                             |
| asyncio.run blocking sys.exit                         | LOW      | asyncio.wait_for 60s timeout                             |
| pipeline.state['articles'] schema drift               | MEDIUM   | \_extract_source fallback chain                          |
| Redis connection leak                                 | LOW      | client.aclose in except                                  |
| Pattern hash collision (same source same run_id)      | LOW      | run_id is ISO timestamp, unique per cron                 |
| HGTPublisher CONFIDENCE_THRESHOLD filter              | LOW      | confidence=0.8 above 0.7 floor                           |
| sentinel-1 consumer not yet wired (TICKET C deferred) | EXPECTED | Patterns accumulate in stream; consumer reads when ready |

## Brainstorm artifacts

Archived to `docs/audits/2026-05-13-ticket-b-spec-brainstorm/`:

- 00_briefing.md
- 01_claude.md (5 findings, PROCEED WITH CONDITIONS)
- 02_gemini.md (3 findings, PROCEED WITH CONDITIONS)
- 03_deepseek.md (6 findings, PROCEED WITH CONDITIONS)
- 04_nb1.md (BLOCK addressable, schema drift caught + 2 async wrappers noted)
- 05_synthesis.md (aggregate PROCEED WITH 7 CORRECTIONS)

## Sources

1. `apps/bali-intel-scraper/scripts/run_intel_pipeline.py:2019` (IntelPipeline.run() SYNC)
2. `apps/bali-intel-scraper/backend/cell/hgt_publisher.py:116` (IntelScraperHGTBridge.from_redis factory)
3. `apps/bali-intel-scraper/backend/cell/runner.py:175,189` (IntelScraperCellRunner constructor requires event_bridge — informs pivot AWAY from runner)
4. `apps/bali-intel-scraper/backend/cell/event_bridge.py:67` (constructor takes ObservedShellBus, no from_pg_dsn factory)
5. `~/Library/LaunchAgents/com.balizero.intel.nightly.plist` (plutil-extract: HOME+PATH only)
6. Schema drift `source_name`: `apps/bali-intel-scraper/scripts/run_intel_pipeline.py:429,959,1169,1475,1750`
7. `redis-cli -h 127.0.0.1 XLEN cell:skills` → 18 (Phase 2.5 seed)
8. Phase 3 spec v2: `docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md`
9. A.2 EXECUTION merge: PR #636 → main `848e76a65`
10. 4-panel brainstorm: `docs/audits/2026-05-13-ticket-b-spec-brainstorm/`
