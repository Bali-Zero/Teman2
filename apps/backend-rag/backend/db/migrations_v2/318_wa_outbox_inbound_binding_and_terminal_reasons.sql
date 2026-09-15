-- 318_wa_outbox_inbound_binding_and_terminal_reasons.sql
--
-- B2.5 PR-1 "one outbox row, one message" (design
-- evidence/2026-09/agent-nuzantara-backend-rag-b2-5-one-message-one-406b5577/
-- B2-5-design.md, base ad1dacc3b6, rulings I105/I107/I108).
--
-- THE DEFECTS this migration is half the cure for (measured live, thread
-- 394, 2026-09-14 ~04:25Z, no PII read or printed — bodies compared only
-- as booleans/md5):
--
-- D1: `wa_outbox.message_id` names the OUTBOUND stub
-- (`whatsapp_chat.py:1307-1327` inserts inbound, then the stub, then this
-- row, in one transaction) — no column ever named the INBOUND message a
-- row was created to answer. `wa_codex_leg._attempt` therefore asked
-- `_load_thread_context(pool, thread_id)` for "the query", which is
-- defined as the thread's LATEST inbound customer message
-- (`wa_inbox_bot.py`). Outbox row 439 (stub 831, bound inbound 830) was
-- retried 4x; by the 4th retry inbound 832 had arrived, and the retry's
-- "latest message" query answered 832 instead of 830 — stub 831 sent with
-- the body that actually answered 832, which had its own stub (833)
-- answer it a second time. One customer message got two different
-- replies; the row bound to 830 never got its own.
--
-- D2: `_coalesce_thread_bursts` (removed in this PR's Python half) marked
-- every OTHER pending bot-reply row of a thread `failed` the instant one
-- row was claimed, on the SAME belief — "the generator always answers the
-- latest message, so one send covers a whole burst" — with NO fall-off
-- reason recorded and no apology. Outbox rows 431/433/434/436 (thread
-- 394) were superseded this way; row 436's own inbound (824) was "talk to
-- a human" and was simply dropped.
--
-- Ruling (a): a customer message is never dropped without an answer, an
-- explicit handoff, or a loud recorded reason — every `failed` row must
-- carry a fall-off reason. Ruling (b): each generation is bound to the
-- message its row was created for; a burst is served each row in order
-- (B2.5 folds nothing).
--
-- THE CURE, two independent widenings converged in one file (same
-- discipline as 290/291/297/315 converging the CHECK, done here alongside
-- a genuinely new column because both changes are D1/D2's one root cause):
--
-- (i) `wa_outbox.inbound_message_id` — the missing column D1 exposes.
-- Nullable (existing rows carry no value; the Python-side reader derives
-- a legacy anchor from `id < message_id` for those, never a newer one —
-- see `wa_inbox_bot._load_bound_thread_context`). NULL, no default: an
-- ADD COLUMN with neither is a catalog-only change on Postgres >= 11 — no
-- table rewrite, no row touched (same rationale as migration 314's own
-- header). REFERENCES meta_inbox_messages(id) — the same table
-- `wa_outbox.message_id` already points at, just the other ledger row of
-- the pair the webhook transaction inserts.
--
-- (ii) Converge `wa_outbox_generation_fall_off_reason_check` (DROP
-- CONSTRAINT IF EXISTS + ADD, mirroring 290/291/297/315 exactly) with six
-- new terminal reasons the WORKER itself now records in the same
-- statement as every `status = 'failed'` write it makes on this table
-- (`thread_missing`, `aborted_human_takeover`,
-- `aborted_human_takeover_pre_send`, `window_closed_24h`,
-- `send_exhausted`, `generation_exhausted`) plus ONE reserved value,
-- `handoff_record_error`, for B2.5 PR-2 (`wa_escalations` write failure on
-- the handoff path) — declared here so PR-2 does not need its own
-- constraint-widening migration for a single value, but UNUSED by any
-- writer in this PR (grep `handoff_record_error` in this branch: zero
-- Python hits outside this comment).
--
-- (iii) A partial index serving the new FIFO-per-thread claim predicate
-- (`wa_outbox_worker.py`'s candidate SELECT): "is there an OLDER
-- needs_generation row of this thread still pending/claimed/generating".
-- `wa_outbox` is ~450 rows in production (measured 2026-09-13) — this
-- exists for predicate correctness under the planner, not because the
-- table is large enough to need it for latency.
--
-- CONVERGE, not create (ii): a CREATE-IF-NOT-EXISTS on the CHECK would be
-- a no-op on a DB that already carries the narrower constraint, leaving
-- the suite green over a migration that never ran (290's own rationale,
-- unchanged since).
--
-- LOCKS: ADD COLUMN and the DROP/ADD CONSTRAINT pair both take ACCESS
-- EXCLUSIVE on `wa_outbox`, and the index creation is a plain (non-
-- CONCURRENT) CREATE INDEX — all three are fast against ~450 rows, and the
-- whole file runs in the ONE transaction the runner already wraps every
-- migration in (`migration_base.py`), so there is nothing further to
-- bound with a `SET LOCAL lock_timeout` beyond what that transaction
-- already implies.
--
-- Ownership: `wa_outbox` carries no OWNER/GRANT statement anywhere in
-- migrations_v2, and 290/291/297/315 already ran this exact
-- DROP CONSTRAINT IF EXISTS / ADD CONSTRAINT pair against the same table
-- under the same runtime role, cleanly. No role/grant statement is needed.
--
-- FOREIGN KEY as NOT VALID + VALIDATE (Squawk `adding-foreign-key-
-- constraint`, first time this repo has added an FK to an existing table
-- via migrations_v2 — no prior exclusion covers it): a plain inline
-- REFERENCES on ADD COLUMN takes a SHARE ROW EXCLUSIVE lock on BOTH
-- tables for a full scan of the referenced table. Splitting into ADD
-- COLUMN (no FK) -> ADD CONSTRAINT ... NOT VALID -> VALIDATE CONSTRAINT
-- is the standard-safe shape; all three still run inside this file's one
-- transaction (unchanged from every other migration here), so this is a
-- lock-avoidance convention match, not a genuine multi-transaction split.

ALTER TABLE wa_outbox
    ADD COLUMN IF NOT EXISTS inbound_message_id BIGINT NULL;

ALTER TABLE wa_outbox
    ADD CONSTRAINT wa_outbox_inbound_message_id_fkey
    FOREIGN KEY (inbound_message_id) REFERENCES meta_inbox_messages(id)
    NOT VALID;
ALTER TABLE wa_outbox
    VALIDATE CONSTRAINT wa_outbox_inbound_message_id_fkey;

ALTER TABLE wa_outbox
    DROP CONSTRAINT IF EXISTS wa_outbox_generation_fall_off_reason_check;
ALTER TABLE wa_outbox
    ADD CONSTRAINT wa_outbox_generation_fall_off_reason_check
    CHECK (generation_fall_off_reason IS NULL OR generation_fall_off_reason IN (
        'provider_not_codex',
        'standing_autoreply_disabled',
        'standing_no_customer_message',
        'window_margin',
        'package_build_error',
        'package_unbuildable',
        'package_unbuildable_greeting_domain',
        'package_unbuildable_no_collections',
        'package_unbuildable_dlp_error',
        'build_contract_break',
        'offer_acquire_error',
        'offer_uncertain',
        'offer_refused',
        'offer_contract_break',
        'wait_error',
        'wait_failed',
        'stand_down_drift',
        'stand_down_fence_lost',
        'post_completion_error',
        'consume_lost',
        'finalize_defect',
        'finalize_internal_monologue_leak',
        'finalize_pricing_outside_package',
        'finalize_secret_egress',
        'finalize_empty_rag_answer',
        'finalize_persona_escalate_marker',
        'finalize_empty_after_escalate_strip',
        'finalize_workflow_only_output',
        'finalize_empty_after_channel_format',
        'finalize_oversized_output',
        'finalize_rag_abstain',
        'finalize_blank_send_text',
        'internal_error',
        'support_judge_absent',
        -- B2.5 PR-1 (this migration): every wa_outbox_worker.py writer of
        -- status='failed' now names a reason in the SAME UPDATE.
        'thread_missing',
        'aborted_human_takeover',
        'aborted_human_takeover_pre_send',
        'window_closed_24h',
        'send_exhausted',
        'generation_exhausted',
        -- Reserved for B2.5 PR-2 (wa_escalations write failure on the
        -- handoff path) — NOT written by any code in this PR.
        'handoff_record_error',
        'unknown'
    ));

-- FIFO-per-thread claim predicate (wa_outbox_worker.py candidate SELECT):
-- "does an OLDER needs_generation row of this thread still block me".
CREATE INDEX IF NOT EXISTS wa_outbox_thread_needs_generation_active_idx
    ON wa_outbox (thread_id, id)
    WHERE needs_generation = true AND status IN ('pending', 'claimed', 'generating');

-- === ROLLBACK ===
-- The CHECK rollback is NOT VALID on purpose, same reasoning as 315: rows
-- already stamped one of the six new terminal reasons (or, later,
-- 'handoff_record_error') are the durable ruling-(a) record and
-- wa_outbox is retained, never rewritten — the narrower CHECK must bind
-- only rows written AFTER the rollback, not fail on history.
--
-- `inbound_message_id` and the partial index are dropped: PR-1's Python
-- half (the bound loader, the FIFO claim predicate) is reverted in the
-- SAME rollback window in practice, so nothing reads either after this
-- runs. Column drop is safe uncoupled from the CHECK rollback ordering
-- below since neither statement depends on the other's outcome.

DROP INDEX IF EXISTS wa_outbox_thread_needs_generation_active_idx;

ALTER TABLE wa_outbox
    DROP CONSTRAINT IF EXISTS wa_outbox_generation_fall_off_reason_check;
ALTER TABLE wa_outbox
    ADD CONSTRAINT wa_outbox_generation_fall_off_reason_check
    CHECK (generation_fall_off_reason IS NULL OR generation_fall_off_reason IN (
        'provider_not_codex',
        'standing_autoreply_disabled',
        'standing_no_customer_message',
        'window_margin',
        'package_build_error',
        'package_unbuildable',
        'package_unbuildable_greeting_domain',
        'package_unbuildable_no_collections',
        'package_unbuildable_dlp_error',
        'build_contract_break',
        'offer_acquire_error',
        'offer_uncertain',
        'offer_refused',
        'offer_contract_break',
        'wait_error',
        'wait_failed',
        'stand_down_drift',
        'stand_down_fence_lost',
        'post_completion_error',
        'consume_lost',
        'finalize_defect',
        'finalize_internal_monologue_leak',
        'finalize_pricing_outside_package',
        'finalize_secret_egress',
        'finalize_empty_rag_answer',
        'finalize_persona_escalate_marker',
        'finalize_empty_after_escalate_strip',
        'finalize_workflow_only_output',
        'finalize_empty_after_channel_format',
        'finalize_oversized_output',
        'finalize_rag_abstain',
        'finalize_blank_send_text',
        'internal_error',
        'support_judge_absent',
        'unknown'
    )) NOT VALID;

ALTER TABLE wa_outbox DROP CONSTRAINT IF EXISTS wa_outbox_inbound_message_id_fkey;
ALTER TABLE wa_outbox DROP COLUMN IF EXISTS inbound_message_id;
