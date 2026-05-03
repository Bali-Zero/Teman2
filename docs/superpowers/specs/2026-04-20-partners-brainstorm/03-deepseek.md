<!-- REASONING -->

Hmm, this is a detailed CRM partners module brief with specific Indonesian business context. The user wants concise, opinionated answers to 10 open questions within strict technical constraints.

Okay, need to balance simplicity with compliance and scalability. Indonesian tax and data regulations are critical here. The architecture should be minimal but future-proof.

For Q1, a commission_rules table seems necessary but keep it simple with basic fields. Q2, cooling period makes sense given refund risks. Q3, manual ledger for v1 keeps things controllable. Q4, fiscal compliance can't be deferred in Indonesia - need withholding tax handling upfront.

Portal topology should use existing domain with role gates - separate subdomain is overkill. RBAC needs clear boundaries to prevent conflicts. Single owner per partner simplifies v1. Reassignment must stay manual per policy. Clawbacks require clear ledger reversals. Single referrer per process for v1 keeps it simple.

Need to flag the missing audit trail requirement - crucial for financial modules. Also partner vetting isn't addressed but important for quality control.

<!-- /REASONING -->

## Q1

Fixed percentage per service category (visa: 10%, company setup: 15%, etc.). A `commission_rules` table is minimal and correct: `id`, `service_category`, `commission_percent`, `effective_date`. Partners get a `default_commission_rule_id`, overridable by a `partner_specific_commission` table (`partner_id`, `rule_id`). This supports future variable rates and tiers without complexity. Avoid flat fees initially; they create accounting mismatches.
**Recommendation:** Implement a `commission_rules` table with service-based percentages, allowing optional partner-specific overrides.

## Q2

Accrue instantly on `completed + paid`, but mark as `pending_approval` (or `accrued`). Introduce a configurable `clearing_period_days` (default 30) before status changes to `approved` and payment email is sent. This creates a cooling-off buffer for refunds without complex retroactive ledger adjustments.
**Recommendation:** Accrue instantly but hold in a `pending_approval` state for a default 30-day clearing period before approval and notification.

## Q3

V1: Manual ledger only. Team marks `paid` in UI, which triggers a system-generated payment advice email. Bank/Xendit integration adds significant regulatory and operational overhead (validasi rekening, mismatch handling). Automate the _record_ of payment first, not the _transfer_. Manual disbursement is standard for <100 partners.
**Recommendation:** For v1, implement manual payment marking only, automating the notification and ledger update.

## Q4

Blocking for v1. Under Indonesian tax law (PPh 23), commissions are subject to 2% withholding tax on gross income (non-NPWP: 4%). Bali Zero must issue a **Bukti Potong PPh 23** (withholding tax slip) and report it in SPT Masa. The partner's NPWP is mandatory. You can defer the full e-bupot integration but must collect NPWP and calculate/record the withholding at the point of commission `approved`.
**Recommendation:** Collect NPWP upfront, calculate and record PPh 23 withholding at commission approval; generating the Bukti Potong can be a manual v1 process.

## Q5

Role-gated section within existing `portal.balizero.com`. A separate subdomain adds unnecessary complexity: separate auth, session management, duplicated components, and CORS. With 20-100 partners, RBAC and a dedicated `/partner/*` route group in the existing Next.js app is far simpler, secure, and maintainable. Use the same design tokens for consistency.
**Recommendation:** Use a role-gated route (`/portal/partner`) within the existing portal application.

## Q6

Reaffirm. Edge cases: 1) **Multi-level/partner referring partner**: For v1, disallow. A referrer must be a client, not another partner. 2) **Internal team as partner**: This is a conflict of interest and should be blocked at creation (`assigned_to` cannot be the partner's own email). The RBAC `verify_client_access` pattern will work if `client_id` is mapped to `partner_id` for the partner role.
**Recommendation:** Enforce strict hierarchy: partners refer clients only; block team members from being partners.

## Q7

Single `assigned_to` owner (one-to-one). This matches the informal current process and satisfies 95% of cases. Many-to-many adds junction table complexity for contact management, not commission tracking. If a partner needs multiple contacts, store a `secondary_contacts` JSON field or a simple `partner_contacts` table separate from team ownership.
**Recommendation:** Implement single `assigned_to` owner; handle multiple contacts via a separate, simple `partner_contacts` table.

## Q8

Manual workflow: When a team member's account is deactivated (`is_active=False`), their partners' `assigned_to` field is set to `NULL`. An EventBus notification (`partner_unassigned`) alerts admins (Zero, Asya, Antonello). An admin must manually reassign via the UI, which sends a reassignment notification email to the partner and new owner. No batch operations.
**Recommendation:** Deactivation sets owner to `NULL`, triggering an admin alert for manual reassignment via UI.

## Q9

Implement a ledger reversal. If a refund occurs after commission is `paid`, create a negative `clawback` commission entry linked to the original, moving the net balance owed. The partner's next payment is reduced by this amount. If no future payments, the ledger shows a receivable from the partner. Never automatically write off; this is a financial decision for the owner.
**Recommendation:** Handle clawbacks via negative ledger entries, creating an offsetting balance for future payments or a receivable.

## Q10

V1: Strictly 0-or-1 referrer per process. Splits add massive complexity to the ledger, approval workflow, and partner UI. The path to multi-referral: later add a `process_referrals` junction table with `partner_id` and `split_percent`. The `partner_commissions` table already supports multiple entries per `process_id`, so the ledger is future-proof.
**Recommendation:** Start with single referrer per process; prepare for splits by ensuring the commission ledger supports multiple entries per process_id.

## Additional concerns

1.  **Audit Trail:** The `partner_commissions` ledger must be immutable append-only with `created_by` (system or user ID) for every status change. Critical for disputes and PPh 23 auditing.
2.  **Partner Vetting:** The creation flow should include a mandatory "Agreed to T&C" checkbox and document upload (KTP, NPWP) before activating the portal login. This formalizes the relationship legally.
3.  **Deactivation:** Need a soft-delete/`is_active` flag for partners with an archive workflow, preserving historical ledger data but removing portal access.
