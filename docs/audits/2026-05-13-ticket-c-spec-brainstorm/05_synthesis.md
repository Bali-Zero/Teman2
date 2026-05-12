# TICKET C — 4-Panel Synthesis

**Date**: 2026-05-13 01:50 WITA

## Verdicts

| Reviewer          | Verdict                 | Notes                                                                                                             |
| ----------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Claude self       | PROCEED WITH CONDITIONS | 5 findings (F1 HIGH asyncio cleanup)                                                                              |
| Gemini 3.1 Pro    | PROCEED WITH CONDITIONS | F1 CRITICAL telemetry loss + F2 method name typo + F3 missing teardown pattern                                    |
| DeepSeek Reasoner | PROCEED WITH CONDITIONS | 7 findings (F1 CRITICAL + F2 HIGH gap + F3-F7)                                                                    |
| NB-1 NotebookLM   | PROCEED WITH CONDITIONS | **CRITICAL signal**: MUST clone `apps/evaluator/seo_cell/run_seo_cell.py` canonical pattern, NOT write naive shim |

**Aggregate: 4/4 UNANIMOUS PROCEED WITH CONDITIONS** + **NB-1 ground truth changes the architecture entirely**.

## CRITICAL discovery from NB-1 (game changer)

**`apps/evaluator/seo_cell/run_seo_cell.py` ALREADY EXISTS** (111 LOC, verified empirically at 01:50 WITA) with the **canonical pattern**:

- argparse `--verbose` flag
- `_configure_logging()` LaunchAgent-aware (stdout + stderr merge)
- `_run_one_pulse()` async function with try/except + structured logging
- `_run_one_pulse()` returns int exit code
- `main()` wraps `asyncio.run(_run_one_pulse())` with KeyboardInterrupt handler returning 130
- Uses `python -m apps.evaluator.seo_cell.run_seo_cell` import path
- **GAP 1 Layer 2 fix (2026-05-12)**: explicitly uses `asyncio.all_tasks()` blanket wait with 10s timeout AFTER single*pulse() because *"cell*core.pulse:265 schedules the observatory emit as fire-and-forget asyncio.create_task. Without this cleanup wait, asyncio.run() exits before the emit task can finish its PG INSERT + NOTIFY"*

## CORR-9 OVERRIDE (Phase 3 spec v2)

Phase 3 spec v2 §CORR-9 says: _"NO asyncio.all_tasks() blanket wait"_.

**This is WRONG**. Empirical: seo_cell uses it explicitly as Gap 1 Layer 2 fix. The asyncio.run() shutdown DOES cancel pending tasks (DeepSeek F1 + Q2.3 confirmed), so the fire-and-forget observatory emit IS lost without the blanket wait.

**TICKET C spec v2 OVERRIDES CORR-9**: use `asyncio.all_tasks()` blanket wait with 10s timeout, exactly as seo_cell does. Reference comment: "Gap 1 Layer 2 fix 2026-05-12 (see seo_cell precedent)".

## Convergent TRUE findings

| #      | Severity | Finding                                                              | Source                  | Resolution                                                                                                                                                                                                                                                                                                                                                |
| ------ | -------- | -------------------------------------------------------------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TRUE-1 | CRITICAL | asyncio.run() cancels fire-and-forget observatory emit tasks         | ALL 4 reviewers         | **CLONE seo_cell pattern** — `asyncio.all_tasks()` blanket wait with 10s timeout (OVERRIDES Phase 3 spec v2 CORR-9)                                                                                                                                                                                                                                       |
| TRUE-2 | HIGH     | Method name `cell.tick()` is wrong; correct is `cell.single_pulse()` | Gemini F2 + DeepSeek F2 | Use `single_pulse()` (already in spec v1)                                                                                                                                                                                                                                                                                                                 |
| TRUE-3 | HIGH     | Must follow `run_seo_cell.py` boilerplate, not naive shim            | NB-1 + Gemini F3        | **CLONE seo_cell architecture** (`_configure_logging`, `_run_one_pulse`, `main` with KeyboardInterrupt return 130)                                                                                                                                                                                                                                        |
| TRUE-4 | HIGH     | sleep_hours 02-06 creates 4h gap vs success criterion >2h            | Claude F2 + DeepSeek F2 | Relax success criterion to "no >2h gap except during configured sleep window 02-06 WITA"                                                                                                                                                                                                                                                                  |
| TRUE-5 | MEDIUM   | HGTConsumer.ensure_group + consume_once unverified                   | DeepSeek F3             | **EMPIRICAL VERIFIED**: ensure_group at consumer.py:50, consume_once at consumer.py:61 — REJECT this concern                                                                                                                                                                                                                                              |
| TRUE-6 | MEDIUM   | plist swap workflow lacks log verification after reload              | DeepSeek F4             | Add step 7: check launchctl print state + log first 10s after bootstrap                                                                                                                                                                                                                                                                                   |
| TRUE-7 | MEDIUM   | sys.path manipulation fragile in shim                                | DeepSeek F5             | **REJECTED**: seo_cell uses package import `from apps.evaluator.seo_cell import create_seo_cell`. For mata-garuda, use `python -m mata_garuda.scripts.run_sentinel_cell` if package-installed, OR keep relative path fallback. Since the plist already invokes `.venv/bin/python -u path/to/script.py`, the sys.path manipulation is reasonable. KEEP it. |
| TRUE-8 | LOW      | Test stubs incomplete                                                | DeepSeek F6             | Provide concrete mock implementations in spec v2                                                                                                                                                                                                                                                                                                          |
| TRUE-9 | LOW      | plist EnvironmentVariables overwrite risk                            | DeepSeek F7             | Modify ONLY ProgramArguments, leave EnvironmentVariables untouched                                                                                                                                                                                                                                                                                        |

## Rejected findings

- **DeepSeek F5 sys.path hack**: rejected on empirical grounds. seo_cell uses `python -m` invocation; mata-garuda plist uses direct script invocation. sys.path fallback is necessary and acceptable.

## Spec v2 corrections (9 corrections final)

**CORR-C1** (CRITICAL, ALL 4): **CLONE `run_seo_cell.py` architecture verbatim**:

- argparse --verbose
- `_configure_logging()` with stdout+stderr handlers
- `_run_one_pulse()` async with try/except
- `main()` with KeyboardInterrupt → return 130
- **Gap 1 Layer 2 fix**: `asyncio.all_tasks()` blanket wait with 10s timeout

**CORR-C2** (HIGH, Gemini+DeepSeek): Method name `cell.single_pulse()` (NOT `tick()`).

**CORR-C3** (HIGH, Claude+DeepSeek): Relax Phase 3 success criterion to allow >2h gap during configured sleep_hours window 02-06 WITA.

**CORR-C4** (MEDIUM, DeepSeek): Add step 7 to plist workflow — post-bootstrap log verification.

**CORR-C5** (LOW, DeepSeek): Provide concrete test mock implementations in spec v2.

**CORR-C6** (LOW, DeepSeek): Modify ONLY ProgramArguments, leave EnvironmentVariables untouched.

**CORR-C7** (EMPIRICAL, DeepSeek F3 resolved): HGTConsumer.ensure_group at consumer.py:50, consume_once at consumer.py:61 — verified.

**CORR-C8** (OVERRIDE Phase 3 spec v2 CORR-9): use asyncio.all_tasks() blanket wait. Phase 3 spec v2 CORR-9 was incorrect — empirical evidence from seo_cell Gap 1 Layer 2 fix confirms necessity.

**CORR-C9** (NEW shim file location): use `apps/mata-garuda/scripts/run_sentinel_cell.py` (matches existing run_sentinel_py.py location, not inside the package). Cron invokes via `.venv/bin/python -u scripts/run_sentinel_cell.py` — same pattern as legacy.

## Effort estimate (revised)

| Component                                         | Hours                 |
| ------------------------------------------------- | --------------------- |
| Spec v2 (this synthesis applied)                  | 1                     |
| run_sentinel_cell.py (clone seo_cell boilerplate) | 1.5                   |
| 4 unit tests (concrete mocks)                     | 2                     |
| plist swap workflow update (7 steps)              | 0.5                   |
| Empirical verification                            | 0.25                  |
| **Total v2**                                      | **~5.25h (~0.7 day)** |

Lower than v1 estimate (5.5h → 5.25h) because cloning seo_cell pattern is faster than writing from scratch.

## Aggregate verdict

**PROCEED WITH 9 CORRECTIONS APPLIED IN SPEC V2** — execution-ready post merge. Pattern operativo confirmed.

## Sequencing

A.0 ✅ → A.1 ✅ → A.2 ✅ → B ✅ → **C v2** (code + tests) → operator plist swap → first hourly tick → 14d soak → FASE 4 lift.

C code can ship NOW with autonomous merge. Operator plist swap remains gated (refusal #1 chmod 0444 antibody workflow).
