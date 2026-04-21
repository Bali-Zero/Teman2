# Multi-LLM Council Synthesis — Partners Module (2026-04-20)

**Members:** Gemini 2.5 Pro (CLI OAuth; 3.1-Pro-Preview rate-limited) ·
Codex (gpt-5.4 xhigh, research preview, with live web search) ·
DeepSeek-Reasoner · NotebookLM NB-2 (Immigration, partial scope).

**Methodology:** Same brief in parallel. Per-question: tabulate positions,
Jaccard-style overlap check, devil's advocate pass, final recommendation
with rationale. Conservative default when council is split.

Legend: ✅ = unanimous · 🟡 = majority with one divergence · 🔴 = split
(applies devil's advocate + conservative default).

---

## Q1 — Commission policy

| LLM      | Position                                                                                                                                                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gemini   | Single `default_commission_rate` field on `partners`. No rules table for v1.                                                                                                                                                                                        |
| Codex    | `partners.default_commission_type` + `default_commission_value` + **immutable snapshot** (`service_type`, `base_amount`, `rate_or_flat`, `calculated_amount`, `rule_source`) on each commission row. Add `commission_rules` only if ≥ 2 real rule dimensions exist. |
| DeepSeek | `commission_rules(service_type, default_percent, partner_id nullable)` with nullable partner_id for overrides.                                                                                                                                                      |
| NB-2     | N/A (out of scope).                                                                                                                                                                                                                                                 |

**Overlap:** 3/3 agree per-partner flexibility is needed; only disagreement
is where flexibility lives.

**Devil's advocate:** Gemini's single-field approach breaks the moment
Bali Zero wants "flat 2M IDR on company setup, 15% on visa, 10% default".
DeepSeek's rules table is correct long-term but adds a table before
Bali Zero has concrete need. Codex's immutable snapshot is the key insight
nobody else articulated: whatever rule engine you use, the computed
commission must be **frozen on the ledger row** so future rule changes
don't retroactively rewrite history.

**Decision:** Hybrid, closest to Codex.

- `partners` gets `default_commission_type` (enum: `percentage|flat`) and
  `default_commission_value` (decimal).
- `partner_commissions` stores an **immutable snapshot**: `base_amount`,
  `commission_type`, `commission_value`, `calculated_amount_idr`,
  `rule_source` (enum: `partner_default|manual_override`).
- **Defer** `partner_commission_rules` table to v2. When a team member
  needs a non-default rate for a single process, they enter it manually on
  the referral and the snapshot records `rule_source='manual_override'`.

**Rationale:** v1 ships with the partner-default + manual-override path.
v2 adds the rules engine when ≥ 2 real rule dimensions exist
(e.g., per-service tier + per-partner tier). Ledger snapshots mean we
never retroactively rewrite paid history.

---

## Q2 — Timing (accrual vs cooling-off)

| LLM      | Position                                                                                                 |
| -------- | -------------------------------------------------------------------------------------------------------- |
| Gemini   | Instant accrual on `completed + paid`. Handle refunds as separate clawback.                              |
| Codex    | Instant accrual → `accrued` status; 30-day `eligible_for_approval_at` cooling-off → `approved` → `paid`. |
| DeepSeek | Instant accrual → `pending` for 14 days → `accrued`.                                                     |
| NB-2     | N/A.                                                                                                     |

**Overlap:** 3/3 agree instant accrual for partner visibility. Split on
cooling-off length (0 / 14 / 30 days).

**Devil's advocate:** Gemini argues instant accrual + clawback is cleaner.
But clawbacks after bank transfer are socially painful (both Codex and
DeepSeek call this out in Q9). A cooling-off period eats the clawback
risk inside the ledger, avoiding the need to claw back real cash transferred.
30 days is the Indonesian refund window that Codex cites as common.

**Decision:** 3-state ledger with 30-day cooling-off.

- On process `completed + paid`: create `partner_commissions` row with
  `status = accrued`, `accrued_at = now()`,
  `eligible_for_approval_at = now() + interval '30 days'`.
- After 30 days, admin can transition to `approved` (manual finance gate,
  per Codex). Approved rows enter the payout batch queue.
- `approved → paid` is a manual UI action (Q3).

**Rationale:** 30 days covers Bali Zero's typical refund/dispute window
without hiding from partners that commission has been earned. The portal
shows "Earned 3M IDR, payable after 2026-05-20" which is transparent.

---

## Q3 — Payment rail

| LLM      | Position                                                                                                                          |
| -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Gemini   | Manual ledger v1, defer Xendit.                                                                                                   |
| Codex    | Manual ledger v1, store bank fields now (bank_name, account_holder, account_number, e-wallet, currency, notes, proof attachment). |
| DeepSeek | Manual ledger v1, plan Xendit for v2.                                                                                             |
| NB-2     | N/A.                                                                                                                              |

**Overlap:** ✅ Unanimous. Manual ledger v1.

**Decision:** Manual ledger. `partners` stores `bank_name`,
`bank_account_holder`, `bank_account_number`, `ewallet_type`,
`ewallet_number`, `payment_currency` (default `IDR`), `payment_notes`.
`partner_commissions` stores `paid_via` (free-text), `payment_reference`,
`paid_at`, and optional `payment_proof_url` (uploaded file reference).
No integration APIs in v1.

---

## Q4 — Fiscal receipt (PPh, kwitansi)

| LLM      | Position                                                                                                                                                                                                                                                                                              |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gemini   | **Non-negotiable**. Generate PDF `bukti potong` on payment. Collect NPWP. Apply PPh 21/23 at payout.                                                                                                                                                                                                  |
| Codex    | Not blocking for v1 UI, **blocking for first real payout**. Per DJP: individuals → PPh 21; corporate/PT → PPh 23 (2% gross); e-Bupot Unifikasi required. Store: legal_name, NIK/NPWP, entity_type, address, receipt_num, gross, withholding, net. Accountant sign-off before first production payout. |
| DeepSeek | Defer v1 but collect NPWP + tax status; design ledger to store withholding.                                                                                                                                                                                                                           |
| NB-2     | **Fiscal is out-of-scope for NB-2**. BUT NB-2 confirms: no Permenkumham prohibition on paying referral fee to third parties (as long as partner is NOT Garante/sponsor on the visa). Unlock: the business model itself is legal. The fiscal treatment is an accounting question.                      |

**Overlap:** 🟡 Split on "blocking vs deferrable". Codex (with web-verified
DJP sources) and NB-2 are aligned on the structural picture: the model is
legal, but the fiscal mechanics (which PPh, which receipt form) need an
accountant. Gemini wants full compliance from day 1.

**Devil's advocate:** Gemini's "day 1 PDF bukti potong generator" is
over-engineering — Bali Zero doesn't pay anyone until a process completes
AND 30 days pass. We have a month of runway before the first payout even
becomes eligible. Codex's "build the fields, defer the automation" is
correct: **collect everything at partner creation, calculate at payment
time manually for v1**.

**Decision:** Three-layer approach.

1. **v1 mandatory (ship now):** `partners.npwp`, `partners.nik`,
   `partners.entity_type` (enum:
   `individual|corporate_pt|corporate_cv|foreign`),
   `partners.tax_withholding_category` (enum: `pph21|pph23|exempt|tbd`),
   `partners.fiscal_address`. Optional fields
   (IBAN/rekening for foreign partners, BI-compliant).
2. **v1 ledger snapshot:** `partner_commissions` stores
   `gross_amount_idr`, `withholding_rate`, `withholding_amount_idr`,
   `net_amount_idr`. Calculated at `approved` transition, editable by
   admin until `paid`.
3. **v1 required before first production payout:** Accountant validation
   of the first three payouts (Asya). Blocking gate:
   `partners.tax_withholding_category = 'tbd'` prevents transition to
   `approved`.
4. **Kwitansi/invoice upload:** on `partner_commissions`, optional
   `receipt_type` (enum: `kwitansi|invoice|none`), `receipt_file_url`.
   Not blocking for `approved` but required before `paid` (enforced in
   UI, not DB).
5. **v2 (deferred):** PDF bukti potong generator, e-Bupot Unifikasi
   integration.

**NB-2 addition (UI guardrail):** partner form must warn and optionally
block if `partner.role` is "sponsor"/"garante" on a visa process. Only
Bali Zero PT PMA can be Garante on a visa (confirmed by NB-2 citing
Permenkumham 11/2024 and Permenimipas 5/2025).

---

## Q5 — Portal topology

| LLM      | Position                                                                 |
| -------- | ------------------------------------------------------------------------ |
| Gemini   | Role-gated section of existing portal.                                   |
| Codex    | Role-gated section; defer subdomain. RBAC is the boundary, not hostname. |
| DeepSeek | Role-gated section with `/portal/partner/*` routes.                      |
| NB-2     | N/A.                                                                     |

**Overlap:** ✅ Unanimous. Role-gate the existing portal.

**Decision:** Use `apps/mouth/app/portal/(authenticated)/partner/*` routes
for the partner view. Middleware in
`apps/mouth/middleware.ts` routes `role=partner` users to
`/portal/partner/dashboard` and blocks access to `/portal/clients`,
`/portal/processes`, `/portal/hr`, etc. `role=team` and `role=admin` see
`/portal/partners/*` (admin view) alongside normal team portal.

**Naming convention:** `/portal/partner/` (singular) = partner's own view;
`/portal/partners/` (plural) = team view of all partners.

---

## Q6 — RBAC edge cases

| LLM      | Position                                                                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Gemini   | Partner sees own; team sees assigned; admin sees all. No multi-level. Block team-member-as-partner (conflict of interest).                 |
| Codex    | Same. Finance actions (approve, mark paid) are a **separate permission** beyond ownership. Audit trail for all reassignment/approval/paid. |
| DeepSeek | Same. Block team-as-partner. Allow partner-referring-partner (circular ref) but NO multi-level commission chains.                          |
| NB-2     | N/A (but confirms: partner ≠ sponsor on visa — data model must reflect).                                                                   |

**Overlap:** ✅ on core RBAC. 🟡 on "partner referring partner":
DeepSeek allows it (no commission chain), Gemini/Codex exclude it from v1.

**Devil's advocate:** Allowing partner-referring-partner with no
commission chain is implicitly the case anyway (any person can tell
their friend about Bali Zero). The question is whether we **track** it.
v1 shouldn't.

**Decision:**

- Partner sees only own referrals + commissions
  (via API query scoping).
- Team member sees only partners where `partners.assigned_to = self`.
- Zero, Antonello, Asya (role `admin`) see all.
- **New permission bit:** `finance.approve_commission` and
  `finance.mark_paid` — granted to Zero, Antonello, Asya only.
  Team members CANNOT approve/pay even for their own partners.
- **Hard constraint:** `partners.email` must not match any
  `users.email` where `users.role IN ('team','admin')`. Enforced by
  service-layer validation (cross-table check).
- **v1 scope-out:** no multi-level referrals, no partner-to-partner
  tracking.
- **Audit log:** all `assigned_to` changes, status transitions, manual
  overrides append to `partner_audit_log` (new table, minimal columns:
  `id`, `partner_id`, `actor_user_id`, `action`, `before_json`,
  `after_json`, `at`).

---

## Q7 — Team↔partner cardinality

| LLM      | Position                                                                             |
| -------- | ------------------------------------------------------------------------------------ |
| Gemini   | Many-to-one (single `assigned_to`).                                                  |
| Codex    | Single `assigned_to` + optional `secondary_contact_id` + reassignment history audit. |
| DeepSeek | One-to-one. Add `partner_secondary_contacts` later.                                  |
| NB-2     | N/A.                                                                                 |

**Overlap:** ✅ Unanimous. Single `assigned_to` owner. Defer m2m.

**Decision:** `partners.assigned_to` is a single FK to `users(id)`,
NULLABLE (to support orphaned state from Q8). Reassignment history lives
in `partner_audit_log` (from Q6).

---

## Q8 — Reassignment on team member departure

| LLM      | Position                                                                                                                |
| -------- | ----------------------------------------------------------------------------------------------------------------------- |
| Gemini   | Set `assigned_to = NULL`. Admin dashboard alert "Orphaned Partners". Manual reassignment.                               |
| Codex    | Unassigned queue visible only to admins. Existing partner login stays active. Bulk reassignment UI with reason capture. |
| DeepSeek | Admin bulk reassignment via UI. Unassigned queue.                                                                       |
| NB-2     | N/A.                                                                                                                    |

**Overlap:** ✅ Unanimous. No auto-assignment (per `feedback_no_auto_assignment`
memory). Orphan state + admin UI.

**Decision:**

- When a team user transitions to `role=inactive` (or is deleted —
  check current user model), a service-layer hook sets
  `assigned_to = NULL` on all their partners **and** records a
  `partner_audit_log` entry `action='orphaned'`.
- Admin portal adds `/portal/partners?filter=orphaned` with bulk
  reassignment action: select N partners → pick new owner → enter
  reason (required) → confirm. Each reassignment writes
  `partner_audit_log`.
- Partner login remains active (owner change doesn't cut access).
- Historical commissions preserve the original `assigned_to_snapshot`
  on the ledger row (already in Q1 immutable snapshot). Reports
  filtered by team member honor the snapshot, not the current owner.

---

## Q9 — Clawback

| LLM      | Position                                                                                      |
| -------- | --------------------------------------------------------------------------------------------- | -------------- | ------ | ----------------------------------------- |
| Gemini   | Negative `partner_commissions` row, `type='CLAWBACK'`, auto-deduct from next payout.          |
| Codex    | **Append-only ledger**. Negative adjustment linked to original row. States: `clawback_pending | offset_applied | waived | repaid`. Default = offset against future. |
| DeepSeek | `reversed` status + negative entry. Offset against future, write-off < 2M IDR.                |
| NB-2     | N/A.                                                                                          |

**Overlap:** ✅ on append-only + negative adjustment + offset-first. 🟡
on threshold for auto-writeoff.

**Devil's advocate:** Auto-writeoff threshold is a business policy, not
engineering. Shouldn't be hardcoded. Make it a system setting.

**Decision:**

- `partner_commissions` is **append-only** (enforced at repository layer:
  only narrow status transitions allowed; no DELETE).
- Clawback creates a new row: `entry_type='clawback'`,
  `amount_idr < 0`, `related_commission_id` FK to original row.
  Status lifecycle: `clawback_pending → offset_applied | waived | repaid`.
- Offset logic: when a new accrued commission is approved for the same
  partner, offset against oldest `clawback_pending` row first.
- Manual waiver requires Zero/Asya role + reason note.
- `system_settings.partner_clawback_auto_writeoff_idr` (default 0 = off).
  If set > 0, clawbacks below this amount are auto-waived on creation.

---

## Q10 — Multi-referral per process

| LLM      | Position                                                                                                                                                     |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Gemini   | v1: 1 referrer per process. Use `partner_referrals` join table with unique constraint on `process_id`. Future: drop constraint + add `split_percentage`.     |
| Codex    | v1: strictly 0-or-1 per process. Keep `partner_referrals` as association table, store `share_percent=100` snapshot now. Future: multiple rows totaling 100%. |
| DeepSeek | v1: 1 referrer. Design junction table for future splits.                                                                                                     |
| NB-2     | N/A.                                                                                                                                                         |

**Overlap:** ✅ Unanimous. 1 referrer per process for v1.

**Decision:**

- `partner_referrals(id, partner_id FK, process_id FK,
share_percent DEFAULT 100, referred_at, referred_by_user_id)`.
- `UNIQUE (process_id)` constraint for v1 (drop in v2 when splits ship).
- UI dropdown populated with partners where `assigned_to = current_user`
  (team member) OR all partners (admin).
- Nullable FK from `processes` side — NOT added to `processes` table.
  Reference lives only in `partner_referrals` to keep `processes` lean.

---

## Additional concerns (from all LLMs, integrated)

From Gemini:

- **Partner onboarding status** (`pending_approval|active|inactive`).
  Partner cannot log in or accrue until `active`.
- In-portal messaging between team and partner (deferred to v2).

From Codex:

- Partner **agreement acceptance timestamp + version** (Partnership
  T&C v1 at creation, v2 if terms change). `partners.terms_accepted_at`,
  `partners.terms_version`.
- **Email delivery log** reuse existing `notification_log` (m111) with
  `ref` convention.
- **Commission email idempotency key** to prevent double-sends when
  EventBus redelivers.
- **Admin override reason** captured on every manual commission edit.
- **Monthly finance CSV export** endpoint
  `GET /api/partners/finance/export?from=&to=`.

From DeepSeek:

- Partner **soft delete** (`status='inactive'`) preserves history.
- Performance dashboard for team (deferred v2).

From NB-2:

- **Critical UI guardrail:** block partner role "sponsor/garante" on
  visa process. Visa sponsor is Bali Zero only.
- **UU PDP consent:** partner creation form includes explicit consent
  checkbox ("I authorize Bali Zero to store my data for referral
  tracking and commission payment purposes per UU 27/2022") with
  `partners.pdp_consent_at` timestamp + `partners.pdp_consent_version`.

---

## Consensus map (summary)

| Q                  | ✅/🟡/🔴 | Final choice                                                                 |
| ------------------ | -------- | ---------------------------------------------------------------------------- |
| Q1 Commission      | 🟡       | Partner default + immutable snapshot. Defer rules table.                     |
| Q2 Timing          | 🟡       | Instant accrue → 30d cooling-off → approve → pay.                            |
| Q3 Payment         | ✅       | Manual ledger. Store bank fields.                                            |
| Q4 Fiscal          | 🟡       | Collect NPWP/NIK/entity_type + withholding fields. Asya before first payout. |
| Q5 Portal          | ✅       | Role-gated in existing portal. No subdomain.                                 |
| Q6 RBAC            | 🟡       | Strict scope + separate `finance.*` permissions + audit log.                 |
| Q7 Cardinality     | ✅       | Single `assigned_to`. Defer m2m.                                             |
| Q8 Reassignment    | ✅       | Manual admin bulk reassign. Orphan state.                                    |
| Q9 Clawback        | 🟡       | Append-only ledger + negative adjustment + offset first.                     |
| Q10 Multi-referral | ✅       | 1 per process v1. Junction table ready for v2 splits.                        |

**Net:** 5 unanimous, 5 with one divergence resolved via devil's advocate

- conservative default. Zero hard splits (🔴). Council is strongly
  aligned.

---

## Open items — resolved by Antonello (2026-04-20)

1. **Commission default rate.** 10% placeholder
   (`partners.default_commission_value = 10.0`).
2. **Auto-writeoff threshold.** System setting, default 0 (off). Asya
   picks real value later.
3. **Accountant.** Asya. Gates first 3 real payouts via UI soft-gate.
4. **Partner onboarding approval required.** Yes. Default onboarding
   status `pending_approval`; partner cannot accrue or log in until admin
   calls `/activate`.
5. **PDP consent copy v1.** Provisional text ships in migration body;
   legal review may bump `pdp_consent_version` without schema change.
