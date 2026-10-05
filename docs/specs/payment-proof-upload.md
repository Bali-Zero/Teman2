# Spec — Client payment proof upload via portal (v1)

**Status:** DRAFT — spec only, no implementation in this PR
**Requested by:** Asya (accounting) — clients' transfer proofs are currently collected outside the portal
**Decision:** Antonello, email 1 Oct 2026 — direction approved, not this sprint, queued after backend debt part C. Spec (a–f) first.
**Source of names below:** Antonello's read-only check on `origin/main` `bafd07d270`, 1 Oct 2026. Re-measured by Subhi on `origin/main` `623c7c270f`, 5 Oct 2026: `confirm_payment` 11, `_notify_lead_about_document` 11, `sanitizeRedirect` 76, `is_crm_admin` 234, `INV-` 186, `paid_date` 8, `payment-proof` 0 (line counts, `git grep -F | wc -l`). Same counts again on `35ebafcc3c` (after PR #7861), 5 Oct 2026 12:16 WITA.
**Zone:** GIALLO (new table + new endpoint). Frontend badge work only after this spec is accepted.

## Baseline (Antonello's measurement, prod read-only, 1 Oct 2026)

895 invoices · 0 with `paid_date` · 13 practices partially paid. Not re-measured by Subhi.

## Scope v1

**(a) Data.** A new table holds each proof. Proposed fields: `invoice_id`, `document_id`, `status` (`received` | `verified` | `rejected`), `verified_by`, `verified_at`, `note`. Table name and migration are backend's call.
`invoices` has no status column, so the client-facing badge is **derived**, never stored. Add one screen for `rejected`, showing the reason from `note`.

**(b) Endpoint.** `POST /api/portal/billing/{invoice_id}/payment-proof`. Reuse the existing Vault upload validation; no second validator. The upload modal states the limits up front: 10 uploads per 15 minutes, and a 409 for the same file name within 1 hour.

**(c) Verification.** Only through `reconcile_service.confirm_payment`. No separate "mark as verified" path.

**(d) Notification.** Through `_notify_lead_about_document`, to accounting. No outbound integration in v1.

**(e) Test.** `sanitizeRedirect` with `&` in the URL.

**(f) Out of v1.** "Download receipt".

## Fixed facts (corrections to the earlier mockup)

| Earlier mockup        | Correct                                                                                                                                                                                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `INV-2026-0142`       | `INV-YYYYMM-NNNNN`, suffix = `practice_id` zero-padded to 5 (`services/invoicing/invoice_generator.py:142-144`, `623c7c270f`)                                                                                                                                           |
| role `finance`        | no such role; staff access = `is_crm_admin`                                                                                                                                                                                                                             |
| n8n webhook           | Bali Zero does not use n8n; use (d). On `35ebafcc3c`, `git grep -I` finds `n8n` only in 10 text files (docs, research notes, `.gitignore`, one base64 image `.txt`), none in application source; the other hits of the earlier 78-line count are binary/SVG image bytes |
| invoice status column | does not exist; badge is derived (a)                                                                                                                                                                                                                                    |

## Open questions for Antonello (answer before backend starts)

1. Badge derivation when an invoice has more than one proof: latest proof wins, or any `verified` wins?
2. Does `confirm_payment` set `paid_date`? With 0 of 895 invoices carrying it, the badge must not depend on `paid_date` until this is known.
3. Client ownership check on the new endpoint: which existing portal billing guard should it reuse?
4. Can a client upload again after `rejected` (new row), or is the rejected row reopened?

## Delivery order

1. This spec, docs-only PR.
2. Frontend: derived badge + upload modal + rejected screen, against the agreed contract.
3. Backend: table, endpoint, wiring to (c) and (d), after backend debt part C.

## Done when (v1)

A client uploads proof on an invoice in the portal; accounting is notified via (d); an `is_crm_admin` user verifies through (c) or rejects with a reason; the client sees the matching badge or the rejected screen. Tested only on a test portal account, never a real client.

## Pre-commit check (read-only, run on Subhi's machine)

```
cd ~/Teman2 && git fetch origin && git rev-parse --short origin/main && for p in 'confirm_payment' '_notify_lead_about_document' 'sanitizeRedirect' 'is_crm_admin' 'INV-' 'paid_date' 'payment-proof' 'n8n'; do printf '%s: ' "$p"; git grep -I -F "$p" origin/main | wc -l; done
```

Expected: first six > 0 (`paid_date` is the positive control), `payment-proof` = 0 (not built yet). Any first-six name at 0 means the spec cites a name that no longer exists: fix the spec before commit. `-I` skips binary files; without it, short strings such as `n8n` match random bytes inside images.
