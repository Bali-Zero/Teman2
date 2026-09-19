-- ============================================================================
-- 320_garuda_journal_admits_op_f08.sql
--
-- Admit OP-F08 to `garuda_order_journal.transition_id`.
--
-- WHY THIS MIGRATION EXISTS, AND WHY THE CODE PR CANNOT SHIP WITHOUT IT.
-- The companion change makes OP-04 reconciliation open a late case when the
-- provider reports a charge no webhook ever delivered, and it records that
-- with `transition_id = 'OP-F08'`. Measured on PRODUCTION this turn, the
-- CHECK on that column admits exactly:
--
--   OP-00 OP-01 OP-02 OP-03 OP-04 OP-05 OP-06 OP-07 OP-08 OP-09
--   OP-F04 OP-F05
--   PR-01 .. PR-12
--
--   scripts/pg.sh -c "select conname, pg_get_constraintdef(oid)
--                       from pg_constraint
--                      where conrelid = 'garuda_order_journal'::regclass
--                        and contype = 'c';"
--
-- OP-F08 is absent, so the INSERT would raise `check_violation` INSIDE the
-- reconciliation transaction. `reconciliation.py`'s per-row
-- `except Exception: logger.exception(...); continue` would swallow it, and
-- the net effect would be a cure that reports success and changes nothing —
-- the exact shape of the defect the code change exists to remove (superscar
-- #2). The constraint widening and its writer therefore travel together.
--
-- NOTE ON THE OTHER TWO TABLES THIS CHANGE TOUCHES, both checked this turn
-- so a later reader does not have to re-derive it:
--   * `garuda_order_outbox` has NO check constraint on `job_type`
--     (`pg_constraint` returns 0 rows for contype='c'), so the new
--     `staff_page_charge_without_webhook` job needs no DDL.
--   * `garuda_orders.late_case_open` / `late_case_charge_id` already exist
--     (migration 284) and their three-state CHECK permits
--     (open=TRUE, resolution IS NULL), which is exactly the row this writer
--     produces. No DDL needed there either.
--
-- OWNERSHIP. `garuda_order_journal` is owned by `backend_rag_v2`
--   (`select pg_get_userbyid(relowner) from pg_class where relname =
--     'garuda_order_journal'` -> backend_rag_v2, read this turn),
-- which is the role the release_command authenticates as. This migration
-- needs none of the cross-owner bracketing migration 304 required — a plain
-- DROP/ADD CONSTRAINT is within the running role's own rights.
--
-- NUMBERING, CHECKED THIS TURN.
--   Highest file on this branch: 318_wa_outbox_inbound_binding_and_terminal_reasons.sql
--   Highest applied in PRODUCTION (`select max(migration_number) from
--     _schema_versions`): 318.
--   Open PRs claiming a migrations_v2 number (`gh pr list --state open
--     --json number,files`): #6679 claims 319. Nothing claims 320.
-- 320 is therefore free against both main and the open queue.
--
-- LOCK PROFILE, CORRECTED after a cross-family review (Codex `gpt-5.6-sol`,
-- read-only) refuted the first draft of this comment. That draft claimed the
-- usual `ADD ... NOT VALID` then `VALIDATE` split bought a shorter exclusive
-- lock. It does not buy it HERE: `BaseMigration.apply` runs the whole file
-- inside one `conn.transaction()` (`migration_base.py:478`), so the ACCESS
-- EXCLUSIVE lock taken by the DROP is held until COMMIT regardless — the
-- VALIDATE's gentler SHARE UPDATE EXCLUSIVE never gets a chance to matter.
-- The split was ceremony that made a false promise, so it is gone: one DROP,
-- one validating ADD. Every existing row already satisfies the new predicate
-- (it is a strict superset of the old one), so the scan cannot fail; it is a
-- sequential read of a table that holds one row per order state change on a
-- product with 3 orders, which is why a lock held across it is acceptable
-- rather than merely unavoidable.
-- ============================================================================

ALTER TABLE public.garuda_order_journal
    DROP CONSTRAINT IF EXISTS garuda_order_journal_transition_id_check;

ALTER TABLE public.garuda_order_journal
    ADD CONSTRAINT garuda_order_journal_transition_id_check
    CHECK (transition_id = ANY (ARRAY[
        'OP-00', 'OP-01', 'OP-02', 'OP-03', 'OP-04',
        'OP-05', 'OP-06', 'OP-07', 'OP-08', 'OP-09',
        'OP-F04', 'OP-F05', 'OP-F08',
        'PR-01', 'PR-02', 'PR-03', 'PR-04', 'PR-05', 'PR-06',
        'PR-07', 'PR-08', 'PR-09', 'PR-10', 'PR-11', 'PR-12'
    ]));

COMMENT ON CONSTRAINT garuda_order_journal_transition_id_check
    ON public.garuda_order_journal IS
    'Closed vocabulary of STATE-MACHINE.md transition ids. OP-F08 added 2026-09-19: '
    'OP-04 reconciliation found a provider-confirmed charge for which no signed webhook '
    'ever arrived. OP-F01/F02/F03/F06/F07 are deliberately absent — they are refusals '
    'that write no journal business event.';

-- === ROLLBACK ===

-- Stays NOT VALID here for a DIFFERENT reason than above: by rollback time
-- the journal may already hold OP-F08 rows, and the journal is append-only by
-- trigger (UPDATE and DELETE both raise), so they cannot be rewritten away. A
-- VALIDATE would fail on them and take the rollback down with it. NOT VALID
-- narrows what may be written from here on without re-litigating history,
-- which is the only honest thing a rollback can do to an immutable log.

ALTER TABLE public.garuda_order_journal
    DROP CONSTRAINT IF EXISTS garuda_order_journal_transition_id_check;

ALTER TABLE public.garuda_order_journal
    ADD CONSTRAINT garuda_order_journal_transition_id_check
    CHECK (transition_id = ANY (ARRAY[
        'OP-00', 'OP-01', 'OP-02', 'OP-03', 'OP-04',
        'OP-05', 'OP-06', 'OP-07', 'OP-08', 'OP-09',
        'OP-F04', 'OP-F05',
        'PR-01', 'PR-02', 'PR-03', 'PR-04', 'PR-05', 'PR-06',
        'PR-07', 'PR-08', 'PR-09', 'PR-10', 'PR-11', 'PR-12'
    ])) NOT VALID;
