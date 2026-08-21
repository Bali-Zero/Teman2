-- STAGED DRAFT — NOT a live migration file. Staged here because the M5/fleet-wide
-- guardrails hook (research/operations/specs/T1.2-guardrails-hook.md) blocks
-- ANY new .sql file (Write/Edit) whose content newly introduces
-- INSERT/UPDATE/DELETE/DROP/TRUNCATE patterns — by design, not a bug — and
-- requires the operator two-key bypass (GUARDRAILS_BYPASS=1 +
-- ~/.claude/state/operator-presence.flag) before that file can be created.
--
-- Provenance (renumbered TWICE, both times before this content ever shipped
-- as a live migration, both times verified on disk, not assumed):
--   276 (original adversarially-reviewed draft, PR #4468) -> 277 (same day,
--   276 had meanwhile been claimed by 276_garuda_voa_archive_comments.sql)
--   -> 278 (this file, same day again: 277 was reassigned to a SEPARATE,
--   smaller migration — see below — per team-lead's ruling that the
--   ari@balizero.com typo correction and this water-filling reassignment
--   are two different decisions and must not share one migration).
--
-- DEPENDENCY, LOAD-BEARING: this migration (278) MUST run AFTER migration
-- 277 (apps/backend-rag/backend/db/migrations_v2/277_correct_ari_email_typo.sql
-- once staged — see 2026-08-21-migration-277-STAGED-ari-typo-correction.sql.txt).
-- 277 corrects client_id 11500's assigned_to from a typo ('ari@balizero.com')
-- to the real active staff email ('ari.firda@balizero.com'); that client is
-- NOT an orphan in substance, only in form (per team-lead ruling, 2026-08-21:
-- "quel cliente non è un orfano ... includerlo significa far agire la
-- decisione dell'owner su qualcosa che orfano non è").
--
-- This is now BOTH documented AND enforced. Read the runner code (verified
-- 2026-08-21, not assumed from the filename convention): within one combined
-- apply-all run, ordering IS structurally guaranteed — `_apply_all_pending_locked`
-- sorts `pending` by the parsed integer migration NUMBER immediately before
-- a strictly sequential `for` loop with a single `await` per migration
-- (backend/db/migration_manager.py ~line 470: `for migration_info in
-- sorted(pending, key=lambda x: x["number"]): ... await self.apply_migration(...)`)
-- — not the alphabetical `sorted(migrations_dir.glob("*.sql"))` used earlier
-- only for discovery, and not asyncio.gather (no concurrency). BUT that same
-- loop does NOT stop on a prior migration's failure (`except Exception:
-- failed.append(...)`, loop continues) — so a failed/rolled-back 277 would
-- not by itself prevent 278 from attempting to run in the same batch. A
-- formal `dependencies: list[int]` mechanism exists on `BaseMigration`
-- (`_check_dependencies`, queries `schema_migrations` by `migration_number`)
-- but is unwired for migrations_v2/*.sql — the apply-all loop never supplies
-- it. Given both of those, this migration now carries its OWN inline guard
-- (the `DO $$ ... RAISE EXCEPTION ... END $$` block immediately below) that
-- queries `schema_migrations` (the table `_is_applied()` actually reads, not
-- `_schema_versions`) and refuses to run — inside this same transaction, so
-- it rolls back cleanly and 278 is correctly logged as failed, not applied —
-- if 277 has not landed. This also covers the split-deploy case (277 and 278
-- shipped/applied in separate invocations days apart): the guard is a live
-- database check each time 278 actually runs, not a one-time assumption.
--
-- Once the guardrails bypass's second key is armed: RE-VERIFY 278 is still
-- the first free number (another lane may have claimed it since — check
-- `ls apps/backend-rag/backend/db/migrations_v2/ | sort -t_ -k1 -n | tail -3`
-- and renumber + update every migration-identity literal below if taken),
-- confirm 277 is staged/applying first, then save this content, byte-for-byte,
-- as apps/backend-rag/backend/db/migrations_v2/278_reassign_orphaned_clients_setup_team.sql,
-- commit, push, PR, `gh pr merge <N> --auto` nudo, deploy, apply (after 277),
-- then invalidate cache per the verified procedure in the sibling
-- robustness-test document. Full reasoning + the water-filling criterion
-- this SQL implements: 2026-08-21-orphan-client-reassignment-plan.md.
--
-- ============================================================================

-- Migration 278: reassign clients with no valid owner across the six live
-- setup-team caseworkers, leveling total caseload instead of splitting evenly.
--
-- Context (owner decision 2026-08-20/21, verbatim: "spalmali tra surya adit
-- ari vino krisna damar"):
--   The RAW measurement at plan time was 324 live clients (deleted_at IS
--   NULL) with no valid owner in `assigned_to` — 163 pointing at
--   sahira@balizero.com (departed, active=false), 152 NULL, 5 blank
--   strings, 3 raw phone-number strings, 1 typo'd email
--   (ari@balizero.com). Full measurement + criterion writeup:
--   research/operations/2026-08-21-orphan-client-reassignment-plan.md.
--   BY THE TIME THIS MIGRATION RUNS, that raw 324 has been reduced to
--   **323**: migration 277 (see dependency note above) removes the 1 typo
--   row from the orphan pool by correcting it to its real owner instead of
--   distributing it — that row was never a genuine orphan, only
--   misclassified by a misspelled address, and per team-lead ruling
--   (2026-08-21) correcting a misclassification is a data repair, not a
--   water-filling target. This migration's SQL below is DATA-DRIVEN AT RUN
--   TIME regardless (it hardcodes neither 324 nor 323) — it will correctly
--   see whatever the live orphan pool and six recipients' loads actually
--   are when it executes, so the dependency on 277 having already run is
--   what makes that live count 323, not a number baked in here.
--
-- Criterion (explicit instruction: "il criterio giusto è pareggiare il
-- TOTALE, non dividere per sei"):
--   Water-filling on CURRENT caseload. Sort the six recipients by their
--   current live client count; find the smallest prefix (of the lowest-
--   loaded people) whose members can all be brought up to one common level
--   L using exactly the orphan pool available, while people already above
--   L get zero (this operation only ADDS clients — it never removes one
--   from an already-loaded person). Remainder from integer rounding goes
--   to the most-underloaded people first.
--
--   Re-verified live via a read-only SIMULATION this session (2026-08-21):
--   treating client 11500 as already corrected to ari.firda@balizero.com
--   (i.e. simulating migration 277 having already run, without writing
--   anything) reproduces an orphan pool of exactly 323 and gives:
--   Damar +200, Surya +77, Vino +27, Adit +19, Ari +0 (318, already above
--   the level), Krisna +0 (352, already above the level). This differs from
--   the original 324-pool figure only in Surya's allocation (78 -> 77) —
--   the single client that used to round into Surya's block is now
--   correctly kept with Ari instead. The computation below is data-driven
--   at RUN time, not the numbers above — if the orphan pool or the six
--   people's caseloads drift further before this migration actually
--   executes, the same algorithm re-derives the correct split against the
--   live numbers.
--
-- Which orphan client goes to whom: deterministic ROW_NUMBER() over orphan
-- client id, sliced into contiguous blocks sized by the levelled
-- allocation above (lowest-loaded person's block starts at the lowest
-- client id). No PII, no client-level judgment call — pure balance, since
-- the affinity check (nationality/language, historical practice
-- ownership) in the plan doc found no decisive signal.
--
-- Idempotent AND atomic: the `orphans` CTE re-selects only clients that are
-- STILL unowned, and the entire forward SQL below runs inside ONE Postgres
-- transaction (backend/db/migration_base.py::BaseMigration.apply() wraps
-- SQL execution + verification + logging in `async with conn.transaction()`)
-- — any interruption mid-run rolls back the whole block automatically, so
-- there is no partial state to recover from, only a clean retry. A second
-- run of this migration (or the runner's own re-apply skip via
-- `schema_migrations`/`_schema_versions`) is a safe no-op.

SET lock_timeout = '5s';
SET statement_timeout = '60s';

-- Dependency guard, load-bearing (added 2026-08-21 per team-lead review):
-- migration_manager.py's own apply-all loop DOES sort strictly by migration
-- number and DOES run migrations sequentially (`for migration_info in
-- sorted(pending, key=lambda x: x["number"]): await self.apply_migration(...)`,
-- backend/db/migration_manager.py ~line 470) — so ordering within one
-- combined apply-all run is structurally guaranteed, not just suggested by
-- filename. BUT that same loop does NOT abort the batch if a prior
-- migration fails (`except Exception: failed.append(...)` then continues to
-- the next migration_info) — so a failed/rolled-back 277 would not stop 278
-- from running. There is also a formal `dependencies: list[int]` mechanism
-- on `BaseMigration` (`_check_dependencies`, queries `schema_migrations` by
-- `migration_number`) — but `discover_migrations()`/the apply-all loop never
-- populate it for file-based migrations_v2/*.sql, so it is unwired for this
-- pipeline (verified, not assumed) and cannot be relied on without also
-- patching the runner, which is out of scope here. This inline guard is the
-- self-contained substitute: query `schema_migrations` (the table
-- `_is_applied()` actually reads, NOT `_schema_versions`) directly.
-- Kimi K3 refuter finding, round 2 (2026-08-21, CONFIRMED-minor, verified
-- independently): the guard below originally checked only the LOG (a
-- schema_migrations row), not the EFFECT -- W88/W106 class ("the proxy lies
-- about state"). A schema_migrations row without the matching data (e.g. a
-- hand-run INSERT, or a future rollback bug of this exact shape on 277
-- itself) would satisfy the log-only check while the real orphan predicate
-- below still sees the typo'd row. Both conditions are now required.
--
-- Kimi K3 round 3 (2026-08-21, CONFIRMED, our own regression from round 2's
-- fix -- team-lead's own diagnosis of the cure they dictated): the round-2
-- effect check asserted an ARBITRARY EXPECTED VALUE
-- (assigned_to='ari.firda@balizero.com'), not the actual invariant this
-- migration depends on ("client 11500 does not read as an orphan"). That
-- broke three legitimate states: a split-deploy reassignment of 11500 to a
-- DIFFERENT active operator after 277 ran (explicitly supported by this
-- file's own header), 11500 being merged/deleted, or ari.firda@'s roster
-- email changing -- all three leave the true invariant intact but would
-- have raised this exception permanently, fixable only by hand-editing a
-- shipped migration file. The check below now asserts the invariant itself:
-- client 11500 does not satisfy the SAME orphan predicate the `orphans` CTE
-- uses below, so it fails exactly when 278 would actually be wrong to run,
-- and passes under any legitimate drift.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM schema_migrations
        WHERE migration_name = '277_correct_ari_email_typo'
    ) THEN
        RAISE EXCEPTION 'Migration 278 requires migration 277 (ari@balizero.com typo correction for client_id 11500) to have already applied — schema_migrations has no row for 277_correct_ari_email_typo. Refusing to run: applying 278 before 277 would fold that client into the water-filling pool and assign it to Surya instead of leaving it with its real de-facto owner, Ari.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM clients c
        WHERE c.id = 11500
          AND c.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM team_members tm
              WHERE lower(BTRIM(tm.email)) = lower(BTRIM(c.assigned_to))
                AND tm.active = true
          )
    ) THEN
        RAISE EXCEPTION 'Migration 278 requires migration 277''s EFFECT, not just its log row: schema_migrations has a row for 277_correct_ari_email_typo, but client_id 11500 still satisfies the orphan predicate (no active team_members match). Refusing to run on a log/data mismatch.';
    END IF;
END $$;

-- Kimi K3 refuter finding (2026-08-21, round 3, finding 3.2, CONFIRMED): the six
-- water-filling recipients below (damar/surya/vino/adit/ari.firda/krisna) are
-- literals baked into the `team` CTE further down, never checked against
-- team_members. A stale or misspelled recipient email would silently receive
-- zero clients while the level computation still counts them as an active
-- bucket -- the level would be computed correctly on paper but the person who
-- should receive that share would get nothing, and nobody watching the run
-- would see an error. Cheap to close with the same "assert the true invariant"
-- pattern as the guard above (2.1's lesson: check existence+active, never an
-- arbitrary literal that can go stale on its own).
DO $$
DECLARE
    missing_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO missing_count
    FROM (VALUES
        ('damar@balizero.com'), ('surya@balizero.com'), ('vino@balizero.com'),
        ('adit@balizero.com'), ('ari.firda@balizero.com'), ('krisna@balizero.com')
    ) AS t(email)
    WHERE NOT EXISTS (
        SELECT 1 FROM team_members tm
        WHERE lower(BTRIM(tm.email)) = lower(BTRIM(t.email))
          AND tm.active = true
    );
    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Migration 278 requires all six water-filling recipients to be active team_members rows -- % of 6 are missing or inactive. Refusing to run: a stale/misspelled recipient would silently receive zero clients while the level computation still counts them as active.', missing_count;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS orphan_client_reassignment_archive (
    archive_id BIGSERIAL PRIMARY KEY,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    migration_name TEXT NOT NULL,
    client_id INTEGER NOT NULL,
    old_assigned_to TEXT,
    new_assigned_to TEXT NOT NULL,
    UNIQUE (migration_name, client_id)
);

-- Note: the ari@balizero.com typo (client_id 11500) is NOT special-cased
-- here — it doesn't need to be. Migration 277 (which must run first, see
-- dependency note above) already corrects that client's assigned_to to its
-- real owner, which means by the time the `orphans` CTE below evaluates,
-- client 11500 no longer satisfies the orphan predicate (it now matches an
-- active team_members row) and is automatically excluded from this pool.
-- This is a change from the original single-migration draft, which left the
-- typo'd row in the generic pool and flagged the resulting mis-assignment
-- as a follow-up; team-lead ruling (2026-08-21) closed that follow-up by
-- ordering the two migrations instead.
WITH team AS (
    -- SELECT DISTINCT: hardens against a duplicate literal row in the VALUES list
    -- (copy-paste, or a future rewrite that builds this CTE from a join/view instead
    -- of a literal list) silently double-counting that person's current_n and
    -- corrupting every downstream level/allocation computation with no error raised.
    -- Confirmed as a real corruption mode, not hypothetical — see Test 5 in
    -- 2026-08-21-orphan-reassignment-water-filling-robustness-test.md (PR #4473).
    SELECT DISTINCT tm_email FROM (VALUES
        ('damar@balizero.com'),
        ('surya@balizero.com'),
        ('vino@balizero.com'),
        ('adit@balizero.com'),
        ('ari.firda@balizero.com'),
        ('krisna@balizero.com')
    ) AS t(tm_email)
),
current_loads AS (
    SELECT team.tm_email, COUNT(c.id) AS current_n
    FROM team
    LEFT JOIN clients c
      ON lower(BTRIM(c.assigned_to)) = team.tm_email
     AND c.deleted_at IS NULL
    GROUP BY team.tm_email
),
orphans AS (
    SELECT c.id
    FROM clients c
    WHERE c.deleted_at IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM team_members tm
          -- Kimi K3 round 3 (2026-08-21, CONFIRMED, cheap fix): tm.email had no
          -- BTRIM -- a trailing/leading space on a roster email would make this
          -- comparison fail and read that person's ENTIRE book as orphaned.
          WHERE lower(BTRIM(tm.email)) = lower(BTRIM(c.assigned_to))
            AND tm.active = true
      )
),
orphan_count AS (
    SELECT COUNT(*)::numeric AS n FROM orphans
),
ranked AS (
    SELECT
        tm_email,
        current_n,
        ROW_NUMBER() OVER (ORDER BY current_n ASC, tm_email ASC) AS k,
        SUM(current_n) OVER (
            ORDER BY current_n ASC, tm_email ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cum_n
    FROM current_loads
),
level_candidates AS (
    -- Classic water-filling: level_k is the common target IF exactly the
    -- k lowest-loaded people participate. It's the correct k the first
    -- time level_k doesn't exceed the next (excluded) person's current
    -- load — including them would require giving that k+1'th person a
    -- negative allocation, which is invalid.
    SELECT
        r.tm_email,
        r.current_n,
        r.k,
        (oc.n + r.cum_n) / r.k AS level_k,
        LEAD(r.current_n) OVER (ORDER BY r.k) AS next_current_n
    FROM ranked r
    CROSS JOIN orphan_count oc
),
chosen AS (
    SELECT level_k AS lvl, k AS chosen_k
    FROM level_candidates
    WHERE next_current_n IS NULL OR level_k <= next_current_n
    ORDER BY k ASC
    LIMIT 1
),
allocations_raw AS (
    SELECT
        r.tm_email,
        r.k,
        CASE WHEN r.k <= c.chosen_k
             THEN GREATEST(c.lvl - r.current_n, 0)
             ELSE 0
        END AS raw_alloc,
        r.current_n
    FROM ranked r
    CROSS JOIN chosen c
),
allocations_floor AS (
    SELECT
        tm_email, k, current_n,
        FLOOR(raw_alloc)::int AS floor_alloc,
        (raw_alloc - FLOOR(raw_alloc)) AS frac
    FROM allocations_raw
),
remainder AS (
    SELECT
        (SELECT n FROM orphan_count)::int - COALESCE(SUM(floor_alloc), 0) AS rem
    FROM allocations_floor
),
allocations_final AS (
    -- Distribute the integer-rounding remainder to whoever is most
    -- underloaded (largest fractional deficit first, ties broken toward
    -- the lowest current caseload) so the leveling stays as tight as the
    -- integer constraint allows.
    SELECT
        af.tm_email,
        af.k,
        af.floor_alloc
          + CASE WHEN ROW_NUMBER() OVER (
                       ORDER BY af.frac DESC, af.current_n ASC, af.tm_email ASC
                   ) <= (SELECT rem FROM remainder)
                 THEN 1 ELSE 0
            END AS final_alloc
    FROM allocations_floor af
),
allocation_buckets AS (
    SELECT
        tm_email,
        final_alloc,
        SUM(final_alloc) OVER (
            ORDER BY k ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS upper_bound,
        SUM(final_alloc) OVER (
            ORDER BY k ASC ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS lower_bound_exclusive
    FROM allocations_final
),
orphans_ranked AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS rn
    FROM orphans
),
assignment AS (
    SELECT o.id AS client_id, ab.tm_email AS new_owner
    FROM orphans_ranked o
    JOIN allocation_buckets ab
      ON o.rn > COALESCE(ab.lower_bound_exclusive, 0)
     AND o.rn <= ab.upper_bound
)
INSERT INTO orphan_client_reassignment_archive (
    migration_name, client_id, old_assigned_to, new_assigned_to
)
SELECT
    '278_reassign_orphaned_clients_setup_team',
    a.client_id,
    c.assigned_to,
    a.new_owner
FROM assignment a
JOIN clients c ON c.id = a.client_id
ON CONFLICT (migration_name, client_id) DO NOTHING;

UPDATE clients c
SET
    assigned_to = archive.new_assigned_to,
    updated_at = NOW()
FROM orphan_client_reassignment_archive archive
WHERE archive.migration_name = '278_reassign_orphaned_clients_setup_team'
  AND archive.client_id = c.id
  AND c.assigned_to IS DISTINCT FROM archive.new_assigned_to;

INSERT INTO _schema_versions (
    migration_name,
    migration_number,
    description,
    applied_by,
    checksum
)
VALUES (
    '278_reassign_orphaned_clients_setup_team',
    278,
    'Reassign clients with no valid owner across the six setup-team caseworkers, leveling total caseload (runs after 277, which excludes the ari@balizero.com typo from this pool)',
    'migration-278',
    'tracked-by-migration-278'
)
ON CONFLICT (migration_name) DO NOTHING;

-- Note (2026-08-21, staging this copy): the INSERT above is redundant with
-- what backend/db/migration_base.py::BaseMigration._log_migration() already
-- writes automatically after a successful apply() (it writes to BOTH
-- `schema_migrations` — the table `_is_applied()` actually checks — AND
-- `_schema_versions`). Harmless due to ON CONFLICT DO NOTHING; kept as-is
-- from the adversarially-reviewed original rather than restructured here.

-- === ROLLBACK ===
SET lock_timeout = '5s';
SET statement_timeout = '60s';

UPDATE clients c
SET
    assigned_to = archive.old_assigned_to,
    updated_at = NOW()
FROM orphan_client_reassignment_archive archive
WHERE archive.migration_name = '278_reassign_orphaned_clients_setup_team'
  AND archive.client_id = c.id
  AND c.assigned_to = archive.new_assigned_to;

DELETE FROM _schema_versions
WHERE migration_name = '278_reassign_orphaned_clients_setup_team';

-- Kimi K3 refuter finding (2026-08-21, CONFIRMED, same defect as 277's rollback,
-- verified independently against migration_base.py::_is_applied()): clearing only
-- `_schema_versions` leaves `schema_migrations` (the table _is_applied() actually
-- reads, backend/db/migration_base.py:365) still saying 278 is applied -- the
-- runner will never re-apply it. (Corrected 2026-08-21, round 3: the original
-- version of this comment additionally claimed 278's own dependency guard above
-- would still pass after such a rollback -- that guard reads the row for
-- MIGRATION 277, which a 278 rollback never touches, so that specific claim was
-- false and has been removed; the schema_migrations DELETE below is justified by
-- 278's own re-applicability alone, which is sufficient on its own.)
DELETE FROM schema_migrations
WHERE migration_name = '278_reassign_orphaned_clients_setup_team';
