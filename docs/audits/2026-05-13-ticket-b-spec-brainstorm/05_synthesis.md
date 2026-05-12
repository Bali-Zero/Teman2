# TICKET B — 4-Panel Synthesis

**Date**: 2026-05-13 01:08 WITA

## Verdicts

| Reviewer          | Verdict                   | Effort | Notes                                                                          |
| ----------------- | ------------------------- | ------ | ------------------------------------------------------------------------------ |
| Claude self       | PROCEED WITH CONDITIONS   | 1.25d  | 5 findings, 5 corrections                                                      |
| Gemini 3.1 Pro    | PROCEED WITH CONDITIONS   | 1.5d   | 3 findings (F1 HIGH pattern emission, F2 MEDIUM timeout, F3 LOW client.aclose) |
| DeepSeek Reasoner | PROCEED WITH CONDITIONS   | 1.5d   | 6 findings (F1 HIGH DATABASE_URL silent disable)                               |
| NB-1 NotebookLM   | **BLOCK** with conditions | —      | 1 BLOCK condition (schema drift `source_name`), 2 async wrappers found         |

**Aggregate**: PROCEED WITH 7 CORRECTIONS (NB-1 BLOCK addressable via field-name fix, not actual block).

## Convergent findings (multi-reviewer)

| #      | Severity | Finding                                                      | Reviewers                           | Resolution                                                                            |
| ------ | -------- | ------------------------------------------------------------ | ----------------------------------- | ------------------------------------------------------------------------------------- |
| TRUE-1 | HIGH     | Pattern emission deferred — soak XLEN gate empty             | Claude F1 + Gemini F1 + DeepSeek F4 | **MANDATORY**: ship ≥1 structural pattern in v1 (e.g. `intel.source.rss_feed_stable`) |
| TRUE-2 | HIGH     | DATABASE_URL missing in plist → silent no-op                 | DeepSeek F1                         | Make event_bridge OPTIONAL in runner; runner publishes to HGT even without PG bridge  |
| TRUE-3 | HIGH     | Schema drift: `source_name` is primary, `source` is fallback | NB-1 BLOCK condition                | Use `art.get('source_name', art.get('source', art.get('url', 'unknown')))`            |
| TRUE-4 | MEDIUM   | `asyncio.run()` unbounded — cron stall risk                  | Gemini F2                           | `asyncio.wait_for(emit_pipeline_run(...), timeout=60)`                                |
| TRUE-5 | LOW      | Redis connection leak on assembly failure                    | Gemini F3                           | `await client.aclose()` in except block                                               |
| TRUE-6 | LOW      | pipeline.state structure may have unknown keys               | DeepSeek F3+F5                      | Add log of available keys on failure                                                  |
| TRUE-7 | LOW      | runner **aexit** may not aclose redis                        | DeepSeek F2                         | Verify or wrap                                                                        |

## Rejected findings

- **NB-1 BLOCK verdict per se** — invalid. NB-1 itself shows 2 async FastAPI wrappers exist but those aren't applicable to cron context (script invocation, not HTTP). NB-1's recommendation "hoist into existing async router" wouldn't ship to cron. The schema drift finding (TRUE-3) is valid and absorbed.

- **NB-1 suggestion to use FastAPI router** — out of scope. The cron invokes script directly. Refactoring cron to call HTTP endpoint adds more complexity than Option β sidecar.

## Spec v2 corrections (7 total)

**CORR-B1** (HIGH unanimous): Ship `intel.source.rss_feed_stable` structural pattern in v1. Computed from `pipeline.state` — count successful articles per source domain in the run. Emit if ≥1 source had ≥3 articles → confidence=0.8, domain="news".

**CORR-B2** (HIGH DeepSeek): Make `event_bridge` OPTIONAL in `_make_cell_runner_with_preflight`. If `DATABASE_URL` missing/None → log info "DATABASE_URL not configured, observatory events disabled, HGT-only mode" → instantiate runner with `event_bridge=None`. Modify `IntelScraperCellRunner` to accept `event_bridge: IntelScraperEventBridge | None` and skip emit_run if None.

**Wait** — this requires editing `apps/bali-intel-scraper/backend/cell/runner.py` which is outside refusal #9 scope? NO — runner.py is in `apps/bali-intel-scraper/backend/cell/`, NOT in `packages/cell-core/cell_core/hgt/*`. The refusal #9 only restricts cell-core/hgt edits. So editing intel-scraper-cell/runner.py is OK.

**CORR-B3** (HIGH NB-1): Use `art.get('source_name', art.get('source', art.get('url', 'unknown')))` for source extraction.

**CORR-B4** (MEDIUM Gemini): Wrap `asyncio.run(emit_pipeline_run(...))` with `asyncio.wait_for(..., timeout=60.0)`.

**CORR-B5** (LOW Gemini): Add `await client.aclose()` in `_make_cell_runner_with_preflight` exception block.

**CORR-B6** (LOW DeepSeek): Add `logger.debug("pipeline_state keys: %s", list(pipeline_state.keys()))` on emit failure.

**CORR-B7** (LOW DeepSeek): Verify `IntelScraperCellRunner.__aexit__` calls `await redis_client.aclose()`; if not, wrap manually in `emit_pipeline_run`.

## Pattern v1 minimal (CORR-B1 detail)

```python
# In emit_pipeline_run, after session.note_articles_found:
from collections import defaultdict
source_counts = defaultdict(int)
for art in articles:
    src = art.get('source_name', art.get('source', art.get('url', 'unknown')))
    source_counts[src] += 1

# Emit pattern if ≥1 source had ≥3 articles
strong_sources = [src for src, n in source_counts.items() if n >= 3]
if strong_sources:
    from backend.cell.hgt_publisher import StructuralPattern
    pattern = StructuralPattern(
        pattern_id=f"rss_feed_stable_{strong_sources[0]}",
        source=strong_sources[0],
        procedure=(
            f"Source {strong_sources[0]} consistently yields ≥3 articles "
            f"per nightly run ({source_counts[strong_sources[0]]} this run)"
        ),
        precondition="nightly intel-scraper crawl",
        success_criterion=(
            f"source {strong_sources[0]} yields ≥3 articles in next nightly run"
        ),
        confidence=0.8,
        domain="news",
    )
    await session.publish_pattern(pattern)
```

## Effort revision

| Component                                        | Hours                |
| ------------------------------------------------ | -------------------- |
| Spec v2 (this synthesis applied)                 | 1                    |
| cell_post_emit.py implementation                 | 3                    |
| Modify run_intel_pipeline.py main()              | 0.5                  |
| 6 integration tests (5 + 1 for pattern emission) | 3                    |
| Edit runner.py for optional event_bridge         | 1                    |
| Doc update + risk assessment                     | 0.5                  |
| **Total v2**                                     | **~9h (~1.25 days)** |

## Aggregate verdict

**PROCEED WITH 7 CORRECTIONS APPLIED IN SPEC V2** — execution-ready post merge. Pattern operativo confirmed.

## Sequencing

A.0 ✅ → A.1 ✅ → A.2 ✅ → **B v2** (with pattern emission + DATABASE_URL optional + source_name fix) → C → 14d soak → FASE 4 lift.
