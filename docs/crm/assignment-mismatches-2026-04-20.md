# Assignment mismatches report — 2026-04-20

## What this is

14 active practices (status NOT IN cancelled/completed) where
`practice.assigned_to` diverges from `client.assigned_to`. These are
**not auto-corrected** because cross-specialization is legitimate
(e.g. Asya handles payments/accounting, Krisna handles KITAS work)
and rewriting `practice.assigned_to = client.assigned_to` would
misassign the work.

## Impact

- RBAC: a team member viewing `/clients` sees clients by
  `client.assigned_to`, but viewing `/process` filters by
  `practice.assigned_to`. Mismatches mean the same human may see
  a client in one list and not the other.
- Ownership reporting (`dashboard_summary.py`) can double-count
  or miss these practices depending on which column it joins on.

## The list

| practice_id | type                        | status            | practice owner | client owner | client                         |
| ----------- | --------------------------- | ----------------- | -------------- | ------------ | ------------------------------ |
| 248         | company_revision            | on_process        | asya@          | surya@       | RICKY LEE GORDON               |
| 247         | company_revision            | on_process        | asya@          | surya@       | RICKY LEE GORDON               |
| 52          | kitas                       | on_process        | krisna@        | adit@        | Marine Colette T. H. Gralepois |
| 204         | kitas_retirement_offshore   | on_process        | asya@          | adit@        | Scott O Bain                   |
| 220         | company_revision            | on_process        | surya@         | krisna@      | Christia Simanjuntak           |
| 223         | kitas_investor_2yr_offshore | on_process        | surya@         | adit@        | Anil Vinayak Patel             |
| 47          | extension_visa              | sending_invoice   | zero@          | vino@        | Genya Benrobi                  |
| 49          | visa                        | sending_invoice   | zero@          | vino@        | Alessandro Vasapollo           |
| 46          | visa                        | sending_invoice   | zero@          | vino@        | Tevita Tama Hallett Taualii    |
| 227         | visa_c1_tourism             | sending_invoice   | sahira@        | damar@       | Emma Jane Yeadon               |
| 22          | visa                        | inquiry           | zero@          | ari.firda@   | Carlie Jean Leslie Flavell     |
| 48          | accessories                 | waiting_documents | zero@          | vino@        | Genya Benrobi                  |
| 224         | kitas_investor_2yr_offshore | inquiry           | surya@         | sahira@      | SHREEYA PATEL                  |
| 219         | kitas_investor_2yr_offshore | inquiry           | surya@         | ari.firda@   | MIKKA ALEXANDRA HENDRAWIDJAJA  |

## Action required

- Zero (owner): review each row and decide per-case whether the
  practice owner is correct (specialist) or should follow the
  client owner (reassignment was forgotten).
- After the triage, a simple `UPDATE practices SET assigned_to=…`
  per practice_id closes this.

## Prevention

Adding a UI hook on the client-reassignment flow: when a user
changes `client.assigned_to` via the client edit modal, prompt
"Also reassign N active practices?" with a list.

This lives as an open follow-up; not in scope for the current
payment_status/invoice cleanup PR.
