# 4-Panel Synthesis — Phase 3 Spec v1

**Date**: 2026-05-12 21:30 WITA (Gemini pending)
**Method**: cross-reference 3/4 reviews (Claude self-critique + DeepSeek + NB-1) and align findings

## Verdicts

| Reviewer          | Verdict                 |             Findings count |
| ----------------- | ----------------------- | -------------------------: |
| Claude self       | PROCEED WITH CONDITIONS |                          6 |
| DeepSeek Reasoner | PROCEED WITH CONDITIONS |                          7 |
| NotebookLM NB-1   | BLOCK                   | (invalid — stale snapshot) |
| Gemini 3.1 Pro    | pending                 |                          — |

**Aggregate verdict so far: PROCEED WITH CONDITIONS** with confluence on 4 substantive corrections.

## Convergent findings (multiple reviewers)

| #      | Severity | Finding                                                                                        | Reviewers                   | Resolution                                                                                                                  |
| ------ | -------- | ---------------------------------------------------------------------------------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| CORR-1 | HIGH     | Sync shim `CrmHGTPublisher.publish()` silently returns False inside running event loop         | Claude (F1) + DeepSeek (F1) | **REMOVE sync shim entirely**, raise DeprecationWarning. Migrate test_stubs.py to async.                                    |
| CORR-2 | HIGH     | TICKET B Redis URL: spec doesn't verify which Redis instance has cell:skills, risk split-brain | Claude (F2) + DeepSeek (F2) | Empirically verified: `cell:skills` is on **Pro localhost** (Pro=18, Mini=0). Add preflight check + explicit doc invariant. |
| CORR-3 | MEDIUM   | XLEN cell:skills 7-day target ≥28 not empirically calibrated                                   | Claude (F4) + DeepSeek (F3) | Lower target to "≥3 nights with positive delta" OR "≥5 new entries in 14 days" — robust to empty nights.                    |
| CORR-4 | MEDIUM   | Refusals list missing items (no edit cell-core, no edit intel.nightly plist, no direct XADD)   | Claude (F5) + DeepSeek (F7) | Add #9, #10, #11 to refusals + sequencing refusal (no C before B).                                                          |

## Single-reviewer findings (need spec v2 decision)

| #             | From     | Severity | Finding                                                         | Decision                                                                                                                                                            |
| ------------- | -------- | -------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F3-claude     | Claude   | MEDIUM   | A.1 acceptance criterion #4 ambiguous ("XLEN should remain 18") | ADOPT: replace with grep-based CI assertion                                                                                                                         |
| F6-claude     | Claude   | LOW      | TICKET C plist edit missing chmod 0444 restore step             | ADOPT: add 4-step operator workflow                                                                                                                                 |
| F5-deepseek   | DeepSeek | MEDIUM   | No hard gate enforcing TICKET B before TICKET C                 | ADOPT: add to §Refusals + add CI gate suggestion                                                                                                                    |
| F6-deepseek   | DeepSeek | LOW      | `CrmHGTBridge.from_redis(None)` behavior under-specified        | ADOPT: add HGTPublisher(None) integration test                                                                                                                      |
| F4-deepseek   | DeepSeek | MEDIUM   | line 46 for `create_sentinel_cell()` unverified                 | **REJECT** as false positive — empirically verified line 46 IS the factory (DeepSeek had no file access). Will add empirical evidence in v2 to silence the concern. |
| CORR-5-claude | Claude   | (meta)   | Decision table for Option A.α/β/γ/δ missing                     | ADOPT: add 4-row pros/cons table                                                                                                                                    |
| TICKET-A.0    | Claude   | (meta)   | Cell_name public property in HGTPublisher                       | DEFER to follow-up PR — not blocking A.1 (use protected access with TODO comment)                                                                                   |

## NB-1 useful signals (despite invalid BLOCK)

1. SEO Cell at `apps/evaluator/seo_cell/` must regression-test when "crm" added to validate_domain → ADOPT in spec v2 hidden coupling
2. TICKET A.2 caller architecture: prefer co-location with crm-cell (not backend-rag) → ADOPT in TICKET A.2 caller decision matrix
3. validate_domain in `packages/cell-core/cell_core/hgt/domains.py` is the canonical registration point → ALREADY in spec v1, no change

## Spec v2 corrections summary

7 corrections to apply (in dependency order):

**CORR-1** — Sync shim removal:

- Remove `CrmHGTPublisher.publish()` implementation
- Replace class body with `raise DeprecationWarning("Use CrmHGTBridge")` in `__init__`
- Migrate `apps/crm-cell/tests/test_stubs.py` to use `CrmHGTBridge`
- Update test #8 in TICKET A.1 to assert DeprecationWarning raised

**CORR-2** — Redis instance invariant:

- Document explicit: cell:skills is on Pro localhost Redis 6379 (Phase 2.5 seed location preserved)
- Add `_make_cell_runner()` preflight: connect to Redis, verify XLEN cell:skills ≥18, abort if not
- Document `com.balizero.intel.nightly.plist` HAS NO REDIS_URL env var (verified 2026-05-12 21:30 WITA) → relying on default localhost is OK
- Reject Mini Redis path explicitly: REDIS_URL should NOT be set to 100.93.236.6 in plist (different scar than NLM feeder)

**CORR-3** — Soak calibration:

- Replace "XLEN cell:skills ≥28 in 7 days" with:
  - Primary: "≥3 nights with positive delta in 14 days" (more robust)
  - Secondary: "XLEN cell:skills ≥23 total in 14 days" (5 new patterns minimum, ~0.36/night which is below worst-case)
- Add daily monitoring query in TICKET B closure doc template

**CORR-4** — Refusals expansion (add #9-#13):

- #9 No edits to `packages/cell-core/cell_core/hgt/{publisher,consumer,coordinator,domains}.py` without separate cross-cell review
- #10 No edits to `com.balizero.intel.nightly.plist` (production cron — operator-gated)
- #11 No direct `redis-cli XADD cell:skills` debug commands (would pollute substrate)
- #12 No TICKET C deployment before TICKET B in production (sequencing hard gate)
- #13 No edits to `apps/evaluator/seo_cell/` as part of Phase 3 (SEO cell is independent — regression-test only)

**CORR-5** — Option A decision table:

- 4-row pros/cons matrix for A.α (extend sync), A.β (mirror intel-scraper), A.γ (bridge wrapping HGTPublisher — recommended), A.δ (unified base class — deferred)

**CORR-6** — TICKET C plist workflow:

- 4-step explicit operator workflow (chmod u+w → plutil-replace → plutil-lint → chmod 0444 → bootout/bootstrap)

**CORR-7** — Hidden coupling notes additions:

- SEO cell regression test required (NB-1 signal)
- TICKET A.2 caller architecture: prefer crm-cell co-location not backend-rag

**TICKET-A.0** — Cell_name public property (DEFER to follow-up PR):

- Note in spec v2 as TODO with backlink to this review

## Spec v2 success criteria refinement

Original (v1):

1. XLEN cell:skills ≥28
2. sentinel-1 pending=0 + entries-read > 0
3. observatory.db cell_id='sentinel' hourly
4. HGT HALT revoked
5. hgt_coordinator graduation log ≥1

Revised (v2):

1. ✅ "≥3 nights with positive delta" OR "XLEN ≥23 in 14 days"
2. ✅ sentinel-1 pending=0 + entries-read > 0 (unchanged)
3. ✅ observatory.db cell_id='sentinel' hourly (unchanged)
4. ✅ HGT HALT revoked (unchanged)
5. ✅ `packages/cell-core/cell_core/hgt_coordinator/` graduation log ≥1 (path corrected from `apps/cell-core/`)

## Confidence in PROCEED WITH CONDITIONS verdict

3/3 non-stale reviewers (Claude self + DeepSeek + NB-1 useful signals minus invalid BLOCK) converge on PROCEED WITH CONDITIONS with 4 critical corrections + 3 minor. Pattern aligns with Phase 2 spec review history (Gemini BLOCK → DeepSeek WEAK → NB-1 PROCEED CON CONDIZIONI; 7 corrections applied).

Pending Gemini may flag 1-2 additional issues. If Gemini also says PROCEED WITH CONDITIONS, total findings reach ~10 and spec v2 is well-calibrated. If Gemini says BLOCK with valid reasons, escalate.

---

## Gemini 3.1 Pro update (landed 21:31 WITA)

**Verdict: PROCEED WITH CONDITIONS** — 4 findings, converges with Claude+DeepSeek on F1+F2.

### Gemini new findings (not in Claude/DeepSeek)

| #        | Severity                 | Finding                                                                                                        | Decision                                                                                   |
| -------- | ------------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| GEM-F3   | MEDIUM                   | `asyncio.all_tasks()` in run_sentinel_cell.py is anti-pattern — redis-py/httpx daemon tasks make 10s wait hang | ADOPT: replace with explicit task tracking or `asyncio.TaskGroup`; remove blanket wait     |
| GEM-F4   | LOW                      | `cell_name` should be public property on HGTPublisher                                                          | UPGRADE from Claude DEFER → ADOPT in spec v2 as TICKET A.0 inline (5min mechanical change) |
| GEM-Q1.3 | (architectural decision) | If `_make_cell_runner()` has try/except fallback to legacy, dry-run unnecessary                                | ADOPT: add fallback + drop 3-night dry-run; deploy direct to production                    |

### Updated CORR list (final)

After Gemini consolidation:

**CORR-1** Remove sync shim entirely (unanimous Claude+DeepSeek+Gemini critical)
**CORR-2** Redis instance invariant + preflight check (Claude+DeepSeek high)
**CORR-3** Soak calibration (Claude+DeepSeek medium)
**CORR-4** Refusals expansion #9-#13 + add #14 "no synchronous asyncio.run in HGT app code" (Gemini)
**CORR-5** Option A decision table A.α/β/γ/δ (Claude meta)
**CORR-6** TICKET C plist 4-step workflow (Claude low)
**CORR-7** Hidden coupling: SEO cell regression + TICKET A.2 caller location (NB-1 useful)
**CORR-8** TICKET B fallback to legacy + drop dry-run (Gemini Q1.3) — **STRUCTURAL CHANGE**
**CORR-9** TICKET C `asyncio.all_tasks()` replace with explicit task tracking (Gemini F3)
**CORR-10** Add `HGTPublisher.cell_name` public property as inline TICKET A.0 (Gemini F4, was Claude defer)

Plus:
**CORR-11** TICKET B effort revision: was 1 day + 3 dry-run nights → now 1 day + production direct (Gemini Q1.3)

## Final spec v2 aggregate verdict

**PROCEED with 11 corrections applied** — same blast pattern as Phase 2 (7 corrections), high confidence spec v2 is execution-ready post-merge.

Total findings: 11 (1 critical + 3 high + 5 medium + 2 low)

## Action plan v2

1. Open spec v1 file, modify in-place to v2 (preserve markdown structure)
2. Update §"4-panel review convergences applied" with CORR-1..11 table
3. Update §"Goal" + §"Empirical state" + §"Cross-file discoveries" minor additions
4. Rewrite TICKET A.1 (sync shim removal + cell_name public property TICKET A.0)
5. Rewrite TICKET B (fallback wrapper + Redis preflight + drop dry-run)
6. Rewrite TICKET C (asyncio.all_tasks fix + plist 4-step workflow)
7. Expand §"Refusals" to 14 items
8. Update §"Success criteria" with calibrated soak metrics
9. Add §"NB-1 staleness note" subsection in §"Hidden coupling"
10. Commit + PR + auto-merge SQUASH
