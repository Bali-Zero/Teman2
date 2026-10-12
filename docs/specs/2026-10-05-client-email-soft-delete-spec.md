# Client email on soft-delete — archive then NULL (trigger on delete, code on restore)

Status: prepare-only spec. No migration, no code, no data change in this PR.
Owner: Subhi (spec) · Antonello (decision, migration, backfill execution).
Supersedes: spec of 28 Sep 2026 (email + attached .md), which offered trigger vs. writer edits.

## 1. Problem

`clients.email` is unique (`clients_email_key`, `uq_clients_email_lower_not_blank`; neither filters on `deleted_at`).
A soft-deleted client keeps its email, so the address stays taken: a new client or a re-registration
with the same email fails. Same shape on the portal side: `team_members.email` is unique, and a
portal profile linked to a soft-deleted client keeps holding the address (case 12531: profile held by
10273, registration hit `team_members_email_key` → 500; fixed by owner-run relink on 2 Oct).

Baseline: 57 soft-deleted clients still hold a non-blank email (measured by Antonello, read-only,
30 Sep 2026). The earlier figure 53 (24 Sep) is superseded.

A partial unique index on `deleted_at IS NULL` was rejected (24 Sep): it breaks the
"one email = one row" invariant that four consumers rely on (`garuda_ops/adapters_pg.py` ON CONFLICT,
its fallback SELECT, `crm/assignment.py` find_client_by_email, the duplicate check).

## 2. Decision (Antonello, 30 Sep 2026)

Trigger for the delete direction, code for the restore direction.

## 3. Delete direction — trigger

`BEFORE UPDATE OF deleted_at ON clients`, firing when `OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL`:

1. If `NEW.email` is not blank: insert `(client_id, email, archived_at, reason='soft_delete')` into the archive table.
2. Set `NEW.email := NULL`.

Why a trigger: it covers every writer of `deleted_at`, including scripts, without editing each one.
Writers measured 5 Oct (origin/main 64e3858d0c, single-line probe): `crm_clients.py:1842`
(DELETE endpoint, `SET status = 'inactive', updated_at = NOW(), deleted_at = NOW()`).
Writers from the 24 Sep map not caught by that probe (likely multi-line SQL):
`crm_merge_duplicates.py`, `crm_b1_data_quality.py`, `intake_drive_contact_autocreate.py`.
The trigger makes the exact list non-blocking; it is kept here as a lower bound only.

Tests that write `deleted_at` directly will fire the trigger too and must not rely on the email
surviving soft-delete: `tests/integration/test_portal_message_followup.py:148`,
`tests/services/intake/test_intake_writer.py:305` and `:566`.

Repo convention to follow (measured 5 Oct, origin/main 64e3858d0c): triggers live in
`db/migrations_v2/NNN_*.sql`, written idempotently as
`CREATE OR REPLACE FUNCTION` + `DROP TRIGGER IF EXISTS` + `CREATE TRIGGER` (see migration 146).

Portal profile (same trigger function or a sibling): if a portal profile is linked to the client,
set it inactive and archive + NULL its `team_members.email` the same way, so the address is free
for a later invitation. Open question Q3.

## 4. Restore direction — code

One code path restores a client: `crm_clients.py`, flag `restore_if_archived` (default `True`, :1323;
branches at :1411 and :1429, measured 5 Oct). On restore:

- Read the latest archive row for the client.
- If the address is free in `clients` (and in `team_members`, if Q3 = yes): write it back, mark the archive row restored.
- If taken: restore the client WITHOUT the email and return 409 with a message staff can read
  ("email now belongs to client <id>"). Never overwrite the other row.

No trigger on restore: the conflict needs a human decision, and a trigger cannot show one.

## 5. Registration relink (from case 12531)

`complete_registration` must take the UPDATE branch when a portal profile with that email exists
but is linked to a soft-deleted client: relink to the new client instead of INSERT.
Once §3 lands this case should not recur; the relink is the guard for rows created before it.

## 6. Backfill

One-time, for the 57 rows: archive then NULL, same logic as the trigger. Store the id list for rollback.
Executed owner-side by Antonello after this spec is read (production write).

## 7. Open questions

- Q1. Archive table: reuse `client_email_reconciliation_archive` (created in
  `db/migrations_v2/166_reconcile_client_email_duplicates.sql:19`; columns seen 5 Oct include
  `archive_id`, `archived_at`, `migration_name`, `reason`, `client_id`, `new_email`) with
  `migration_name` / `reason` set to a soft-delete value — proposed — or a new table?
  Reuse keeps one place to look for "where did this email go"; the cost is that the table's
  name says reconciliation, not soft-delete.
- Q2. Restore conflict: 409 + client restored without email (proposed), or block the restore?
- Q3. Does the trigger also free `team_members.email` for a linked portal profile, or stays code-only?

## 8. Not in scope

Partial unique index · document soft-delete (PR #1) · role gate for soft delete (separate backend PR).
