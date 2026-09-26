## Gear-3 Council Review — migration 322 / served_by (kimi-code/k3)

### (1) Deploy-window safety of the fenced UPDATE gaining a bind

**Verdict: ACCEPT-WITH-NOTES**

The premise is correct, and the mitigation is correctly engineered for the specific failure it targets:

- **Error class is right.** An UPDATE referencing a non-existent column raises SQLSTATE `42703`, which asyncpg surfaces as `asyncpg.exceptions.UndefinedColumnError` — at prepare time, before execution. Catching exactly that class (and nothing broader) is correct: anything else (lock timeout, serialization failure, a genuine syntax bug in a future edit) _should_ propagate, and does.
- **Transaction hygiene is right.** The failing attempt raises inside `async with conn.transaction()`, so asyncpg rolls back and re-raises the original error unwrapped; the connection returns to idle and the retry in `_finalize(include_served_by=False)` opens a genuinely fresh transaction. The `meta_inbox_messages` UPDATE and `_apply_pending_status` never ran in the failed attempt (they come after the `wa_outbox` fetchrow), so nothing partial leaks into the retry. The guilt test (`DROP COLUMN` mid-test, assert one Graph call, row lands `done`, then restore the column in `finally`) pins exactly this, including the no-double-send invariant.
- **No prepared-statement cache collision.** The two variants have distinct SQL strings (f-string clause), so asyncpg's per-connection statement cache keyed on query text cannot serve the column-referencing statement to the fallback or vice versa.
- **Scoping question — should it catch more?** No. The other candidates one might reach for don't apply: `UndefinedTableError` (42P01) isn't in play, `CheckViolationError` can't occur (no CHECK — see Q2), and `InvalidTextRepresentation` (22P02) on the `$6::text` cast is impossible for a `str | None` bind. Narrow is correct here.

Notes (non-blocking):

1. **Failed-transaction cost during the window.** Every completion inside the deploy window burns one aborted transaction plus a WARNING log before finalizing. On a ~450-row table over a rolling-deploy window this is noise, not load — fine, but the WARNING will page whoever watches logs if the window is ever long. That's acceptable for a once-per-deploy occurrence; just don't silence it, because post-window recurrence of this warning is the signal that migration 322 failed to apply.
2. **This is a symptom fix for a pipeline-ordering property that affects every migration, not just 322.** The pre-deploy `run-migrations` job executing against the _previous_ image's checkout means it can never apply migrations introduced by the very PR being deployed — so the new-code-before-new-column window exists for every future additive column+writer pair, not just this one. The `_finalize` guard is the right local mitigation; the systemic fix (apply pending migrations from the new image, or gate deploy on the migration job seeing the new checkout) is worth a follow-up ticket, not this PR.
3. **Alternative considered and correctly rejected:** a startup/per-connection `information_schema` probe with a cached flag would avoid exception-driven control flow, but adds staleness risk (flag cached before the column lands) for zero gain over a window this short. The exception path is the cleaner option here, not the dirtier one.
4. One masking edge worth naming: if someone later introduces a typo in a _shared_ clause (`status`, `abstained_at`, …), the first attempt raises `UndefinedColumnError`, the fallback raises it again, and the second exception propagates uncaught — which is the desired loud failure. No change needed.

### (2) Rollback safety of the column

**Verdict: ACCEPT**

- **Additive, catalog-only.** `ADD COLUMN IF NOT EXISTS ... TEXT NULL` with no default is a metadata-only change on Postgres ≥ 11 — no rewrite, no per-row work. The stated routine-rollback plan (revert the worker commit, let the column go quiet) is sound because the _old_ worker code never names `served_by`: its fenced UPDATE enumerates `status`/`abstained_at`/`evidence_score` explicitly, and the diff shows the new code does the same. Explicit column lists on both write and read sides are exactly what makes "revert the writer, keep the column" safe.
- **Two classic additive-column hazards, checked against the diff:** (a) `SELECT *` consumers whose row-shape assumptions break — none visible in the diff; `_fetch_carrier` in the tests names columns explicitly, and the worker's fence uses `RETURNING id`; (b) `INSERT INTO wa_outbox VALUES (...)` without a column list, which an extra column would break — none visible in the diff. Worth a one-time grep for `INSERT INTO wa_outbox` without a column list across the repo before merge, but nothing in this PR suggests one exists.
- **Destructive rollback ordering is coherent — and now self-protecting.** If a `DROP COLUMN` were ever run while the new writer was still live, the writer's own `_finalize` guard from Q1 degrades gracefully (finalize without `served_by`) instead of erroring every completion. The documented order (revert worker first, drop only as separately authorized cleanup) plus the guard is belt-and-suspenders. `lock_timeout = '5s'` on the DROP bounds the ACCESS EXCLUSIVE wait appropriately for a 450-row table.
- **No CHECK constraint — reasoning endorsed.** The PR's argument is the right priority ordering: this write happens _after_ the irreversible Graph send, so a bookkeeping abort is strictly worse than an out-of-vocabulary token landing in a free-text column. A CHECK would convert "future route ships before constraint widens" into "every completion on that route fails its terminal write and risks the double-send window" — precisely the failure Q1's guard exists to prevent. Vocabulary discipline belongs at the application layer (`wa_codex_leg.py`), where it already lives. The migration header and column COMMENT document this so a future reader doesn't "fix" it by adding the constraint.

### (3) PII

**Verdict: ACCEPT**

Grep of the diff confirms the claim with no counterexamples:

- The **only** producer of the bind value is `persist_served_by = leg.served_by` (worker, line in the `needs_generation` completion branch), and the only other writes to `persist_served_by` are `= None` (initialization and the non-leg reset branch). There is no concatenation, no formatting, no path where message text, phone number, thread content, or any client-supplied value can flow into this bind. The bind is `$6::text` — parameterized, so even a hostile value couldn't break out of the column.
- All five test stubs construct `CodexLegResult(served_by="codex" | "support_abstain" | ...)` with fixed tokens, consistent with the stated closed vocabulary, and the human-send test asserts the trailing bind is `None`.
- The migration COMMENT, the column COMMENT, and `docs/zantara-loop-state.md` all state the vocabulary and the NULL semantics consistently.

One residual note, inherent to the Q2 decision rather than a defect: because there is deliberately no CHECK, the _database_ will not stop a future `wa_codex_leg.py` change from putting something dynamic into `served_by`. That file is outside this diff, so I can confirm the wiring (verbatim, single-source, no user data adjacent to it) but not the dataclass itself. Cheap belt: declare `served_by` in `wa_codex_leg.py` as a `Literal["codex", "support_abstain", ...]` (if it isn't already) so the closed vocabulary is type-enforced at the single point of production. Non-blocking.

---

**Overall: ACCEPT-WITH-NOTES.** Ship it. The only follow-ups worth tickets are (a) the deploy-pipeline ordering that makes this class of window exist for every migration, and (b) a repo-wide check for column-list-less `INSERT INTO wa_outbox` / `SELECT *` consumers as a one-time hygiene pass.
