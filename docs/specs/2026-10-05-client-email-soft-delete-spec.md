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
for a later invitation. Resolved: yes (§7 Q3).

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

One-time, same logic as the trigger, id lists stored for rollback. Re-measured 15 Oct 2026 (read-only):
59 soft-deleted clients still hold a non-blank email (was 57 on 30 Sep), and 45 portal profiles
(`team_members`) linked to a soft-deleted client still hold one, 40 of them `active = true`.
The backfill covers both sets. Executed owner-side (production write), not by a migration.

## 7. Questions — resolved 2026-10-15

Antonello delegated the three calls to the owner-side session; decided on PROD measurements (read-only, 15 Oct).

- Q1 → **reuse `client_email_reconciliation_archive`.** Columns measured 15 Oct: `archive_id`,
  `archived_at`, `migration_name`, `client_id` (NOT NULL), `old_email`, `new_email`, `reason`,
  `client_snapshot` (jsonb, NOT NULL). Client row: `old_email` = archived address, `new_email` NULL,
  `reason = 'soft_delete'`, `migration_name` = the migration file name, `client_snapshot` = a minimal
  `{client_id, deleted_at}` (not a full row copy). Portal-profile row: `client_id` = the soft-deleted
  client, `reason = 'soft_delete_portal_profile'`, `client_snapshot` = `{team_member_id, linked_client_id, deleted_at}`.
- Q2 → **as proposed:** restore the client without the email and return 409 naming the client that
  now owns the address. Never block the restore, never overwrite the other row.
- Q3 → **yes, the trigger also frees the linked portal profile.** 45 profiles linked to soft-deleted
  clients still hold their address (40 still active), so code-only would leave the invitation failure
  of case 12531 in place. `team_members.email` is NOT NULL, so the address is replaced, not NULLed:
  set `active = false`, archive the old address, write the tombstone `soft-deleted+tm<id>@invalid`
  (RFC 2606 reserved TLD, unique per row). On restore (§4) the address goes back to the profile only
  if it is free in both tables; the profile is not reactivated automatically.

Note for the A10 report: clients 11677 and 12542 are NOT blocked by this case — each already has its
own portal profile linked to itself (measured 15 Oct). Their invitation failure has another cause.

## 8. Not in scope

Partial unique index · document soft-delete (PR #1) · role gate for soft delete (separate backend PR).
