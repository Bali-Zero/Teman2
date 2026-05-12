# Claude Opus 4.7 max — Self-brainstorm TICKET B

**Date**: 2026-05-13 00:58 WITA
**Method**: adversarial reading of spec v1 + look for hidden assumptions.

## Recommendation: PROCEED WITH CONDITIONS (Option β async sidecar)

### Why β

1. **Lowest blast radius**: ~150 LOC additive (new `cell_post_emit.py` ~120 LOC + ~30 LOC modifying `main()`). NO touches to existing 8 steps + 2158 LOC pipeline.run().

2. **Bounded failure**: all cell-layer failures caught by try/except around `asyncio.run()` → "⚠️ cell post-emit skipped (non-fatal)" warning + normal exit code. Production cron unaffected.

3. **Preflight check** prevents Mini/Pro Redis split-brain — XLEN cell:skills ≥18 signature confirms canonical Pro localhost instance.

4. **Pattern emission deferral is acceptable**: v1 ships counters only (sources_attempted + articles_found). Patterns require per-source structural analysis (RSS stability, sitemap pattern, source_reliability) — separate scope. Counters alone validate the pipeline end-to-end.

### Why NOT α/γ/δ

**α (refactor IntelPipeline to async)**: 2158 LOC + 8 subprocess shells. High risk of breaking the cron. Forces async coroutines into every step including those calling subprocess.run(). Bad cost/benefit.

**γ (subprocess IPC after pipeline)**: adds inter-process serialization fragility. State file JSON parse errors, missing keys, IPC timeouts — too many failure modes. β does the equivalent in-process with simpler error semantics.

**δ (skip IntelScraperCellRunner, emit directly via HGTBridge)**: loses 3 features:

- Scar recording (failures aggregated into Genome)
- Event bridging (intel.scraper.run row in observed_shell)
- Deterministic status computation (failed/degraded/ok)
  These are valuable for FASE 4 sentinel cell consumer reasoning. Don't bypass.

## 5 Findings

### F1 (HIGH): Pattern emission deferral leaves XLEN gate empty

**Spec v1 ships counters only**. The Phase 3 spec v2 §"Success criteria" requires XLEN cell:skills to increment from 18 (after seed) via TICKET B + A.2 publishers. If TICKET B publishes ZERO patterns (only counters), the FASE 4 lift criteria depends entirely on A.2's practice + lkpm thresholds, which require ≥20 practice transitions in 7d OR ≥10 LKPM in 90d.

**Impact**: 14-day soak could miss XLEN increment if A.2 thresholds don't fire frequently enough. B contributes 0 to XLEN.

**Mitigation**: ship at least 1 pattern in v1:

- `intel.source.rss_feed_stable` — emit per nightly run when ≥80% sources succeed
- Pattern_id `intel.source.<source_name>_reliability`
- Confidence: 0.8 (above floor)
- Window: 7-day rolling (matches A.2 practice cadence)

Add to v2 spec: 1 minimal pattern in v1, full catalog (sitemap, rss, scraping success rate) in v2.

### F2 (MEDIUM): `pipeline.state['articles']` source field reliability unverified

Spec v1 reads `article.get('source')` from state, but pipeline goes through 8 steps with subprocess shells. Each step may transform the article shape. Need to verify the field survives.

**Mitigation**: in v2, add `article.get('source') or article.get('url', 'unknown')` fallback + LOG when `unknown` is used → operator can detect state corruption empirically.

### F3 (MEDIUM): `IntelScraperEventBridge.from_pg_dsn` requires DATABASE_URL env

Cron context (LaunchAgent) sources `~/.nuzantara-secrets.env`. If DATABASE_URL is not in that file, `from_pg_dsn` will fail or get None, and the event bridge can't emit. But the cell runner constructor REQUIRES event_bridge — if None, may crash.

**Mitigation**: in v2, check DATABASE_URL existence in `_make_cell_runner_with_preflight()` → return None on missing. Better: have IntelScraperEventBridge fail gracefully on None DSN.

### F4 (LOW): `asyncio.run()` followed by `sys.exit()` semantics

The flow is `pipeline.run()` (sync, returns bool) → `asyncio.run(emit_pipeline_run(...))` (async) → `sys.exit()`. asyncio.run() blocks until completion, then control returns. No event loop policy issues IF nothing else creates a loop.

**Mitigation**: add `--no-cell-emit` CLI flag for debugging to bypass cell emission entirely if needed.

### F5 (LOW): IntelScraperScarRecorder.from_genome_path() may fail if path missing

`GENOME_DB_PATH` defaults to `~/.intel_scraper/genome.db`. If this file doesn't exist on the cron host, the scar recorder may fail to init.

**Mitigation**: scar_recorder should auto-create the file/directory. v2 spec verifies behavior or adds explicit fallback.

## Convergent corrections for spec v2

**CORR-B1**: Ship ≥1 structural pattern in v1 (e.g. `intel.source.rss_feed_stable`) to satisfy XLEN gate condition.

**CORR-B2**: Add fallback for `article.get('source')` reading + log "unknown" source occurrences.

**CORR-B3**: Verify DATABASE_URL env in preflight; return None if missing.

**CORR-B4**: Add `--no-cell-emit` CLI flag for emergency bypass.

**CORR-B5**: Verify IntelScraperScarRecorder auto-creates genome.db; explicit fallback if not.

## Effort revised

Add ~2h for pattern emission (CORR-B1) + ~30min for fallback/checks (CORR-B2/3/4/5) → total ~10h (~1.25 days).

## Sequencing

A.2 already merged (PR #636). B is independent of C (publisher vs consumer). Ship B next, then C, then 14-day soak.

## Confidence

**70%** Option β is right. The 30% uncertainty is around:

- Pattern emission CORR-B1 readiness (need clear structural pattern definition)
- DATABASE_URL availability in cron context (untested empirically)
- IntelScraperEventBridge.emit_run behavior with edge-case pipeline.state (empty articles, partial steps)

Awaiting 3 external reviewers.
