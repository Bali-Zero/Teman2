-- ============================================================
-- 319_align_tax_consultant_allowlist_to_team_members.sql
-- Align clients.tax_consultant / lkpm_reports.lkpm_assigned_to with the
-- canonical staff table, team_members. Date: 2026-09-15 (mandate
-- SAETTA-20260915 / W-C, slice R-C).
--
-- NUMBERING NOTE: the mandate that specified this migration assigned it
-- "317". A live sibling check this session (`gh pr list --state open
-- --json number,files` + `git ls-tree origin/main -- .../migrations_v2`)
-- showed 316 already claimed by open PR #6474, 317 by open PR #6478, and
-- 318 by open PR #6558 -- none of them merged yet, so
-- `_assert_unique_migration_numbers` (migration_manager.py) would not have
-- caught the collision locally (it only sees files already on disk, not
-- numbers reserved by unmerged siblings -- cicatrix family W40). 319 is the
-- first free number as of this check; re-verify before merge, since two
-- other lanes are racing the same counter.
--
-- === THE DEFECT (measured live on the production database, 2026-09-15) ===
-- team_members is canonical for staff identity. The five real tax-team
-- addresses, read live from that table this session, are:
--   tax@balizero.com          -> Veronika, dept tax, active
--   angel.tax@balizero.com    -> Angel,    dept tax, active
--   kadek.tax@balizero.com    -> Kadek,    dept tax, active
--   dewaayu.tax@balizero.com  -> Dewa Ayu, dept tax, active
--   faysha.tax@balizero.com   -> Faisha,   dept tax, active   (note the Y)
--
-- But `clients_tax_consultant_check` and `lkpm_reports_assigned_to_check`
-- (both added by migration_093, `lkpm_reports_assigned_to_check` widened
-- once already by 110_lkpm_allowlist_krisna.sql) allow a DIFFERENT set:
-- 'veronika.tax@balizero.com' and 'faisha.tax@balizero.com' (with an I) --
-- neither of which exists in team_members. The two REAL addresses,
-- 'tax@balizero.com' and 'faysha.tax@balizero.com', are rejected by both
-- CHECK constraints today. Two of the five real tax staff cannot be
-- assigned under their own address, and two ghost addresses can.
--
-- Not cosmetic -- live row census this session:
--   clients.tax_consultant        = 'veronika.tax@balizero.com'  -> 2 rows
--   lkpm_reports.lkpm_assigned_to = 'faisha.tax@balizero.com'    -> 12 rows
-- and `lkpm_deadline_notifier.py::_send_assignee_reminder` emails
-- `to=assignee_email` VERBATIM -- 12 live LKPM deadline reminders currently
-- address a mailbox matching no staff record, and
-- `TAX_CONSULTANT_MANAGER = "veronika.tax@balizero.com"` makes the manager
-- CC a ghost too (fixed alongside this migration in the Python allowlist
-- module, not here -- this file is schema-only).
--
-- === THE CURE, AND WHY NOT VALID (used by 315 for the same shape of
--     problem) DOES NOT APPLY HERE ===
-- team_members is canonical; the two CHECK constraints follow it, not the
-- other way round (RULED, not reopened by this migration). 315 needed
-- `NOT VALID` because it could not fix the pre-existing rows that violated
-- the wider CHECK inside that same migration. THIS migration CAN and DOES
-- fix every offending row in the same transaction, so there is no
-- historical row left for a `NOT VALID` escape hatch to protect -- a fully
-- VALIDATED constraint is not just safe here, it is the proof that the
-- ghost rows are gone: if any row still carried a ghost address when the
-- ADD CONSTRAINT ran, this migration would abort instead of silently
-- leaving one behind.
--
-- === ORDER, AND WHY (measured on a local fixture, not assumed) ===
-- Per table, the order is DROP CONSTRAINT -> UPDATE rows -> ADD CONSTRAINT
-- -- not UPDATE-then-DROP/ADD, which was this migration's own first draft
-- and FAILED empirically on a local proof fixture: a CHECK constraint is
-- enforced on every row-level write, not only when the constraint is
-- (re)added, so writing a row to its new real address while the OLD
-- constraint (which does not yet allow that address) is still attached
-- fails immediately, before the ADD CONSTRAINT step is ever reached. Drop
-- first removes that enforcement for the duration of this transaction only
-- (no concurrent session can observe the gap); the ADD at the end then
-- validates every current row -- by then already on its real address --
-- against the new list.
--
-- The two UPDATEs are no-ops on re-run (their WHERE clause matches zero
-- rows once applied), so this migration is safe to re-apply.
--
-- === FOLDED IN: R-B's DB half, same table family (team_members) ===
-- A sibling PR (owner decision D6) deletes two portrait files from
-- apps/mouth/public/: /static/team/faisha.jpg and /static/team/sahira.jpg.
-- team_members.avatar currently points exactly two rows at those paths
-- (set by 229_team_avatars_align_roster.sql). Once the files are gone those
-- avatar values are 404s, so this migration NULLs them -- matching on BOTH
-- email AND the current avatar path, so a row someone has since repointed
-- is left untouched. The team UI (portal.py "avatar_url" consumer) falls
-- back to rendering initials when avatar IS NULL, so this is a display
-- degradation, not a break.
-- === FORWARD ===

-- 1. clients_tax_consultant_check: drop before the row rewrite below, or
--    the still-attached OLD constraint rejects the new real address.
ALTER TABLE clients
  DROP CONSTRAINT IF EXISTS clients_tax_consultant_check;

-- 2. clients.tax_consultant: BOTH ghosts -> BOTH reals, not just the one
--    the live census found here. GHOST_2 (Faisha's ghost) has 0 known
--    rows in THIS table today, but the ADD CONSTRAINT below admits only
--    the five real addresses -- if a row somehow carries the other
--    table's ghost, this catches it too instead of aborting the migration
--    at step 3. No-op on re-run either way.
UPDATE clients
SET tax_consultant = 'tax@balizero.com'
WHERE tax_consultant = 'veronika.tax@balizero.com';

UPDATE clients
SET tax_consultant = 'faysha.tax@balizero.com'
WHERE tax_consultant = 'faisha.tax@balizero.com';

-- 3. Re-validate over the five REAL addresses -- every current row,
--    including the ones just rewritten, must satisfy this or the
--    migration aborts.
ALTER TABLE clients
  ADD CONSTRAINT clients_tax_consultant_check
  CHECK (
    tax_consultant IS NULL
    OR tax_consultant IN (
      'tax@balizero.com',
      'angel.tax@balizero.com',
      'kadek.tax@balizero.com',
      'dewaayu.tax@balizero.com',
      'faysha.tax@balizero.com'
    )
  );

-- 4. lkpm_reports_assigned_to_check: same reasoning, same order.
ALTER TABLE lkpm_reports
  DROP CONSTRAINT IF EXISTS lkpm_reports_assigned_to_check;

-- 5. lkpm_reports.lkpm_assigned_to: BOTH ghosts -> BOTH reals, same
--    symmetry as step 2 (GHOST_1, Veronika's ghost, has 0 known rows in
--    THIS table today). No-op on re-run.
UPDATE lkpm_reports
SET lkpm_assigned_to = 'faysha.tax@balizero.com'
WHERE lkpm_assigned_to = 'faisha.tax@balizero.com';

UPDATE lkpm_reports
SET lkpm_assigned_to = 'tax@balizero.com'
WHERE lkpm_assigned_to = 'veronika.tax@balizero.com';

-- 6. Re-validate over the five REAL addresses plus krisna@balizero.com
--    (110_lkpm_allowlist_krisna.sql -- he has no .tax@ sub-alias and keeps
--    his main inbox).
ALTER TABLE lkpm_reports
  ADD CONSTRAINT lkpm_reports_assigned_to_check
  CHECK (
    lkpm_assigned_to IS NULL
    OR lkpm_assigned_to IN (
      'tax@balizero.com',
      'angel.tax@balizero.com',
      'kadek.tax@balizero.com',
      'dewaayu.tax@balizero.com',
      'faysha.tax@balizero.com',
      'krisna@balizero.com'
    )
  );

-- 7. team_members.avatar: NULL the two rows whose portrait file D6 deletes.
--    Matched on (email, avatar) together so a repointed row is never touched.
UPDATE team_members
SET avatar = NULL
WHERE (email, avatar) IN (
  ('faysha.tax@balizero.com', '/static/team/faisha.jpg'),
  ('sahira@balizero.com', '/static/team/sahira.jpg')
);

-- === ROLLBACK ===
-- Mirrors the forward section's own rule (DROP before the row rewrite that
-- would otherwise violate the constraint still in place, ADD after), tables
-- in the opposite order.
--
-- HONESTY ABOUT WHAT THIS CANNOT RESTORE:
-- * Row reversion is VALUE-based (it matches on the current real address, in
--   BOTH tables and for BOTH addresses), not row-identity-based: any row in
--   either table that legitimately started using 'tax@balizero.com' or
--   'faysha.tax@balizero.com' AFTER this migration deployed -- the intended,
--   correct, ongoing use of those addresses -- is indistinguishable from a
--   pre-migration row still on that value, and this rollback reverts it to
--   the matching ghost address too, the same way the forward migration would
--   mis-map a row in reverse; there is no column recording "was this row
--   touched by migration 319", so this is a real, stated loss of precision,
--   not an oversight.
-- * team_members.avatar is NOT restored to '/static/team/faisha.jpg' /
--   '/static/team/sahira.jpg'. The sibling PR (D6) deletes those files from
--   apps/mouth/public/ independently of this migration's lifecycle;
--   writing the old path back would just re-point at a 404. If D6 is ever
--   reverted too, restoring these two avatar values is a manual follow-up,
--   not something this rollback can determine on its own.

ALTER TABLE lkpm_reports
  DROP CONSTRAINT IF EXISTS lkpm_reports_assigned_to_check;

UPDATE lkpm_reports
SET lkpm_assigned_to = 'faisha.tax@balizero.com'
WHERE lkpm_assigned_to = 'faysha.tax@balizero.com';

UPDATE lkpm_reports
SET lkpm_assigned_to = 'veronika.tax@balizero.com'
WHERE lkpm_assigned_to = 'tax@balizero.com';

ALTER TABLE lkpm_reports
  ADD CONSTRAINT lkpm_reports_assigned_to_check
  CHECK (
    lkpm_assigned_to IS NULL
    OR lkpm_assigned_to IN (
      'veronika.tax@balizero.com',
      'kadek.tax@balizero.com',
      'dewaayu.tax@balizero.com',
      'angel.tax@balizero.com',
      'faisha.tax@balizero.com',
      'krisna@balizero.com'
    )
  );

ALTER TABLE clients
  DROP CONSTRAINT IF EXISTS clients_tax_consultant_check;

UPDATE clients
SET tax_consultant = 'veronika.tax@balizero.com'
WHERE tax_consultant = 'tax@balizero.com';

UPDATE clients
SET tax_consultant = 'faisha.tax@balizero.com'
WHERE tax_consultant = 'faysha.tax@balizero.com';

ALTER TABLE clients
  ADD CONSTRAINT clients_tax_consultant_check
  CHECK (
    tax_consultant IS NULL
    OR tax_consultant IN (
      'veronika.tax@balizero.com',
      'kadek.tax@balizero.com',
      'dewaayu.tax@balizero.com',
      'angel.tax@balizero.com',
      'faisha.tax@balizero.com'
    )
  );

-- team_members.avatar: deliberately not restored (see HONESTY note above).
