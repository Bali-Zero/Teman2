## DeepSeek Reasoner — Verdict

**PROCEED WITH CONDITIONS**

---

### Answers to Q2.1, Q2.2, Q2.3

**Q2.1 — Verify file:line numbers**

- `run_intel_pipeline.py:2019` — Line 2019 for `def run(self):` is plausible given 2158 LOC procedural script. Cannot inspect live file, but counts align with Phase 3 spec v2 survey. **No contradiction found.**
- `runner.py:175` — `IntelScraperCellRunner` class definition. Spec v2 says line 175; this v1 spec says line 175. Consistent.
- `hgt_publisher.py:116` — `IntelScraperHGTBridge.from_redis` exists. Phase 2 empirical survey confirmed. Accept.

**Verdict on Q2.1**: Reliable.

**Q2.2 — pipeline.state['articles'] source field reliability**

- No empirical evidence of the exact field path across all 8 steps. The pipeline may drop or rename `source` in intermediate processing (e.g., URL normalization, dedup). The spec uses `article.get('source') or article.get('url', 'unknown')` — acceptable for v1 counters. **For v2 pattern emission, this field mapping is insufficient**; need explicit schema contract.
- The `_make_cell_runner_with_preflight` assembles a runner but never calls `publish_pattern` — only `note_source_attempted` and `note_articles_found`. These do not rely on `source` being a valid domain or canonical name. The `source` string is purely observational for observatory metrics.

**Verdict on Q2.2**: Low risk for v1 counters. Mitigated by fallback to `url` and `'unknown'`.

**Q2.3 — Hidden coupling with `DATABASE_URL` env missing in cron context**

- `InteScraperEventBridge.from_pg_dsn(None, channel="intel_event")` **will raise** because it expects a valid asyncpg DSN. The `_make_cell_runner_with_preflight` wraps everything in `try/except Exception` → returns `None` → `emit_pipeline_run` becomes no-op. **So the cell post-emit silently disables itself** when `DATABASE_URL` is missing.
- This is acceptable per spec’s “best-effort” design, but it means **no observatory pulses** and **no scar/event bridging** unless the plist is updated. The current `com.balizero.intel.nightly.plist` has no `DATABASE_URL` (only HOME+PATH). **Real effect**: TICKET B on its own will emit _only if_ the operator adds `DATABASE_URL` to the plist. The spec v1 does not call this out as a prerequisite.
- If the cron runs without `DATABASE_URL`, the pipeline succeeds, but `cell_post_emit` returns silently → `XLEN cell:skills` does **not** increment from intel-scraper-cell. The consumer (sentinel) sees nothing. This risks the soak criteria (“≥3 nights positive delta”) being unmet, even though code is correct.

**Verdict on Q2.3**: Real gap — spec v1 must either (a) require plist update (operator-gated) or (b) make `DATABASE_URL` optional with a no-op bridge. Current code is safe but misleading: `cell_post_emit_ok` never logged.

---

### Numbered Findings

**F1 — `DATABASE_URL` missing from cron context disables cell emission silently**

- **Severity**: HIGH for production outcome, LOW for blast radius
- **Evidence**: Plist has no `DATABASE_URL`, `IntelScraperEventBridge.from_pg_dsn(None)` raises, preflight returns `None`, emit is no-op.
- **Action**: Either document this as an operator pre-requisite OR modify `emit_pipeline_run` to allow event-bridge to be None and degrade gracefully (still use runner with HGT bridge only). Recommend the latter for autonomous shipping.

**F2 — `asyncio.run()` cleanup with long-lived async resources**

- **Severity**: MEDIUM
- **Evidence**: `IntelScraperCellRunner.run()` holds Redis client and potentially other connections. `asyncio.run()` closes the loop and cancels pending tasks; `__aexit__` of the context manager should close the client. However, `redis.asyncio.Redis` may have background reconnection tasks that produce warnings. Also, `IntelScraperScarRecorder` may use sqlite3 (sync), no issue.
- **Action**: Add explicit `await client.aclose()` in `__aexit__` of runner (if not already). Or accept warnings as non-fatal. **Test on a dry-run pipeline before production.**

**F3 — `pipeline.state` structure unknown; `run_id` may not exist**

- **Severity**: LOW
- **Evidence**: `pipeline_state.get('run_id', 'unknown')` — acceptable fallback. But `pipeline_state` keys not documented.
- **Action**: Add log of available keys if emit fails, for future debugging.

**F4 — Pattern emission deferred to v2; soak criteria may not be met without it**

- **Severity**: MEDIUM
- **Evidence**: Phase 3 success criterion includes “XLEN cell:skills ≥23 total” and “≥3 nights positive delta”. Without pattern emission, intel-scraper-cell contributes **zero** entries to `cell:skills` (counters are local to observatory, not published). Only crm-cell from A.2 contributes. So if crm-cell patterns are sparse, soak may fail purely due to deferred scope.
- **Action**: Adjust Phase 3 soak criteria to account for this, OR ship at least one structural pattern in v1 (e.g., `source_reliability` based on `pipeline.state['error_counts']`). Recommend either lowering the required delta or shipping a simple pattern.

**F5 — Test scope missing `pipeline.state` mock realism**

- **Severity**: LOW
- **Evidence**: Proposed tests mock `emit_pipeline_run` with simple dicts but do not verify that the actual `pipeline.state` structure (which may be deep or contain nested dicts) is correctly read.
- **Action**: Add a test that uses a realistic `pipeline.state` snapshot (captured from a real dry run) to ensure no KeyError on typical keys.

**F6 — `source` field may be ephemeral across pipeline steps**

- **Severity**: LOW for v1, MEDIUM for v2
- **Evidence**: The 8 pipeline steps may transform article objects: normalizers could rename `source` to `origin` or drop it. The spec fallback to `url` is decent but `url` might be absent after dedup.
- **Action**: For v2 pattern emission, require an explicit contract with pipeline maintainer on the final `pipeline.state` schema. For v1, it's fine.

---

### Top Corrections for Spec v2

1. **Make `DATABASE_URL` optional in `_make_cell_runner_with_preflight`** — if missing, create `IntelScraperEventBridge` as a no-op or `None` and let `IntelScraperCellRunner` accept optional event bridge. Current code raises and falls back entirely, disabling also HGT publishing (which does not need `DATABASE_URL`). The runner should still be able to publish to `cell:skills` even without event bridge. **Critical fix.**

2. **Add explicit `redis_client.aclose()` in `__aexit__` of `IntelScraperCellRunner`** (or verify it's already there). `asyncio.run()` will close the loop but not necessarily call `aclose` on the client if the runner context manager does not. Without this, Redis connection may be leaked until GC.

3. **Adjust soak criterion or ship one pattern in v1** — Without any `publish_pattern` calls, the `cell:skills` stream does not grow from intel-scraper-cell. Either document that `XLEN` incremement will only come from crm-cell (A.2) and possibly from v2 of B, or ship a simple pattern like `source_reliability` computed from pipeline error counts.

---

### Effort Estimate

| Item                                                           | Hours                |
| -------------------------------------------------------------- | -------------------- |
| Fix `DATABASE_URL` optional (correction #1)                    | 0.5                  |
| Verify and fix runner `aclose`                                 | 0.5                  |
| Add optional pattern emission or document scope change         | 1                    |
| Existing implementation (modify main + cell_post_emit + tests) | 8                    |
| Adjust tests for optional event bridge                         | 1                    |
| **Total**                                                      | **~11h (~1.5 days)** |

---

### Sequencing

- A.0, A.1, A.2 merged. B can ship now **as soon as corrections #1 is applied**.
- Without correction #1, TICKET B will effectively be a no-op in production (preflight returns None because `DATABASE_URL` missing). **Operator will see zero cell:skills growth and may misdiagnose**.
- Recommended order: implement correction #1 → ship B as PR #637 → operator manually adds `DATABASE_URL` to `com.balizero.intel.nightly.plist` (operator-gated step, but should be documented) → next nightly cron activates cell path.
- TICKET C (sentinel consumption) can proceed in parallel or after B is verified in production.
