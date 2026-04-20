# CRM data-quality snapshot — 2026-04-20

Output of the `/clients` & `/process` audit (items #10-13 from the big list).
These CSVs are **actionable but not code bugs** — they need team triage.

## `dq_clients_no_email.csv` — 76 rows

Clients that have at least one practice but no email on file. They cannot
receive invoices, portal notifications, nor reminders. Suggested action:

- During the next interaction (WhatsApp/phone/in-person) ask for email.
- For completed practices where the client is no longer responsive,
  accept and move on.

CSV columns: `client_id, full_name, phone, assigned_to, active_practices, created_at`

## `dq_orphan_clients.csv` — 18 rows

Clients without `assigned_to`. These fall through every per-team-member
query (including the round-robin in `crm_automation_engine.run_lead_assignment`
which only picks `status='inquiry'` rows). Suggested action:

- Re-assign each row to a lead via the UI, or bulk-update if they share
  a common origin (e.g. web form leads all to ari.firda).

CSV columns: `client_id, full_name, email, phone, created_at`

## `mismatches.csv` — 14 rows

Active practices where `practice.assigned_to` ≠ `client.assigned_to`.
See `../assignment-mismatches-2026-04-20.md` for the full narrative.

## Not exported — lead-only clients (1090 rows)

Clients without any practice. Mostly legitimate (inquiries that didn't
convert, or manually imported contacts). Too many rows for a CSV; use
the dashboard `/clients?status=lead` filter instead if pruning is
needed.

## Not exported — 31 pre-logging practices (2026-03-28 bulk import)

All `completed`, no activity_log history. Accepted as historical
imports; no action needed. These were imported *before*
migration_041b_team_activity_logging.py added the audit table.
