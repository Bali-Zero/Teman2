Truncating MCP tool name "mcp_google-maps-platform-code-assist_retrieve-google-maps-platform-docs" to fit within the 64 character limit. This tool may require user approval.
Discarding invalid hook definition for SessionStart from project: {
type: 'command',
command: '~/.gemini/hooks/session-context.sh',
description: 'Inject git/env context at session start'
}

## Q1. Commission policy

A hybrid model offers the best balance for V1. Start with a `default_commission_rate` (decimal) field on the `partners` table. This is the simplest approach that allows for partner-specific rates. To support future flexibility without immediate over-engineering, add a `commission_rules` (JSONB) field to the `partners` table. For V1, this field can be unused, but its existence provides a clear path to implementing more complex tier- or service-based rules later without a schema migration. This avoids a separate `commission_rules` table initially but prepares for it. The system logic would first check for specific rules in the JSON field and fall back to the `default_commission_rate` if none apply.

**Recommendation:** Use a `default_commission_rate` column on the `partners` table for V1, and include an empty `commission_rules` JSONB column for future use.

## Q2. Timing

The commission should not accrue instantly. To handle potential refunds and clawbacks gracefully, a delay is essential. When a referred process is marked as `completed` and `paid`, the corresponding commission should enter a `pending` state in the `partner_commissions` ledger. A configurable "cooling-off" period (e.g., 30 days, stored as an environment variable or system setting) should then begin. After this period expires without a refund, an automated job or event listener should transition the commission status from `pending` to `accrued`, making it eligible for payout. This protects Bali Zero from paying commissions on revenue that is not final.

**Recommendation:** Implement a 30-day cooling-off period where commissions are in a 'pending' state before becoming 'accrued' and payable.

## Q3. Payment rail

For V1, a manual ledger is the most pragmatic choice, adhering to the YAGNI principle. Full payment gateway integration (Xendit, etc.) is a significant undertaking involving complex security, transaction management, and third-party dependencies. A manual system, where an authorized team member marks commissions as `paid` through the admin UI, provides complete functionality and control with minimal engineering effort. This allows the finance team to handle payouts using their existing banking methods. The UI should record the payment date, amount, and method for auditing purposes. Automation can be a fast-follow feature in V2 if the manual workload becomes significant.

**Recommendation:** Use a manual ledger for V1 where team members mark commissions as paid in the UI.

## Q4. Fiscal receipt

This is a blocking requirement for V1 and cannot be deferred if the goal is true formalization. Given the Indonesian context, Bali Zero is responsible for withholding tax (PPh 21 for individuals, PPh 23 for companies) from commission payments. The system must accommodate this. The `partners` table needs a field for the partner's tax ID (NPWP). The `partner_commissions` ledger must track `gross_commission`, `tax_withheld` (calculated based on NPWP status), and `net_payable`. Upon payment, the system should be able to generate a formal receipt (`Kwitansi`) and the withholding tax slip (`bukti potong`) for the partner's records, which can be sent via the Brevo email integration.

**Recommendation:** Integrate PPh 21/23 tax withholding calculations and `Kwitansi` generation into the commission ledger from V1.

## Q5. Portal topology

A role-gated section within the existing `portal.balizero.com` is the superior choice. Creating a new subdomain (`partners.balizero.com`) would introduce unnecessary overhead: a separate Vercel project, duplicated authentication logic, and potential drift in UI/UX from the main portal. By integrating into the existing Next.js application, the Partners module can reuse the established authentication flow, design system (`bz-tokens.css`), layout components, and API client. Access can be controlled by checking for the `role='partner'` on the user object, which then renders a filtered, partner-specific view of the portal pages. This is more efficient for development and maintenance.

**Recommendation:** Implement the partner portal as a role-gated section of the existing `portal.balizero.com` application.

## Q6. RBAC

The specified RBAC model is correct: partners see only their own data, team members see data related to partners assigned to them, and admins (Zero, Asya) have global visibility. For V1, edge cases should be explicitly forbidden by policy and system logic. A user's email cannot exist in both the `users` (team) and `partners` table. Multi-level marketing (a partner referring another partner) should be disallowed; the referral mechanism should only link to active client processes. This keeps the model clean and avoids significant complexity around hierarchical commissions. The existing `verify_client_access` pattern should be adapted to `verify_partner_access` for API endpoints.

**Recommendation:** Enforce the simple RBAC model and explicitly prevent team members from being partners or partners from referring other partners in V1.

## Q7. Team↔partner cardinality

A single `assigned_to` owner per partner is the best model for V1. This establishes a clear, accountable point of contact for each partner relationship, simplifying communication and notifications (e.g., who gets the CC on a commission email). This one-to-many relationship (one team member can own many partners) is simple to implement with a foreign key on the `partners` table. A many-to-many relationship (`partner_team_members` junction table) introduces ambiguity regarding ownership and responsibility, violating the YAGNI principle. If a partner requires support from multiple team members, the single assigned owner can coordinate this internally without needing a formal system relationship.

**Recommendation:** Use a strict one-to-many relationship with a single `assigned_to` team member per partner for V1.

## Q8. Reassignment

The "no auto-reassignment" policy requires a robust manual workflow. When a team member's user account is deactivated, any partners assigned to them should be considered "orphaned." A dedicated dashboard widget or filtered list, visible only to admins, should display these orphaned partners. From this interface, an admin can manually reassign each partner to a new active team member. The reassignment action must be logged in an audit trail, capturing who made the change, when, and from which previous owner to which new owner. This ensures accountability while respecting the policy.

**Recommendation:** Create an admin-only UI for manually reassigning "orphaned" partners from deactivated team members to new owners.

## Q9. Clawback

When a client process is refunded after a commission has already been paid, the system must create a "clawback" transaction. This should be a new, separate entry in the `partner_commissions` ledger with a negative value, linked to the original commission. This creates a debit balance on the partner's account. This debit should then be automatically deducted from the sum of their next `accrued` commissions before a payout is calculated. The system should not attempt to issue a cash refund request from the partner. An automated email should be sent to the partner and their assigned owner explaining the clawback event and the resulting adjustment.

**Recommendation:** Implement clawbacks as negative transactions in the commission ledger that are automatically deducted from future payouts.

## Q10. Multi-referral per process

For V1, the system must enforce a strict zero-or-one referrer per process. This is the simplest model, implemented with a single nullable `referrer_id` foreign key on the `processes` table. It avoids the significant complexity of building UI and logic for splitting commissions. The path to supporting multi-referral would be a schema migration: drop the `referrer_id` foreign key and create a new junction table, `process_referrals` (`process_id`, `partner_id`, `split_percentage`). This table would allow multiple partners to be associated with a single process. However, for initial launch, the simplicity and clarity of the single-referrer model is strongly preferred.

**Recommendation:** For V1, allow only a single referrer per process; design for a future junction table to enable commission splitting.

## Additional concerns

- **Data Onboarding:** A plan is needed to migrate existing informal partners into this new system. A simple CSV import tool for admins would be essential to avoid laborious manual entry for the initial 20-100 partners.
- **T&C Management:** The welcome email includes Terms & Conditions. A simple versioning system for these legal terms should be considered. When T&Cs are updated, the system will eventually need a way to notify partners and track their acceptance of the new terms.
- **Commission Rate Changes:** The policy for when a commission rate change takes effect must be defined. The most straightforward rule is that the commission is calculated using the rate that was active at the moment the client process was created and linked to the partner.
