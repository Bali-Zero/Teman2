# Visa Oracle Privacy Policy V1 — approval record

Status: **APPROVED FOR IMPLEMENTATION; NOT AN ENFORCE AUTHORIZATION**

- Approved by: **Zero**
- Approval date: **2026-08-06**
- Machine-readable authority: `docs/policies/visa-oracle-privacy-policy-v1.json`

## Approved policy

| Control                              | Approved value                                                             |
| ------------------------------------ | -------------------------------------------------------------------------- |
| Durable Visa Oracle decision         | 30 days from `evaluated_at`                                                |
| Idempotency/replay record            | 24 hours from reservation                                                  |
| Visa Oracle telemetry                | PII-free allowlist, 90 days                                                |
| Data-subject request operational SLA | 3 x 24 hours after a valid request                                         |
| WhatsApp handoff                     | Separate, explicit, unticked consent                                       |
| CRM creation/contact                 | Separate, explicit, unticked consent; never inferred from WhatsApp consent |
| Minor                                | Confirmed parent/guardian consent; otherwise `HUMAN_REVIEW_REQUIRED`       |
| DPIA                                 | Must be approved before `VISA_ENGINE_EVALUATE_MODE=ENFORCE`                |

The evaluation lawful basis is the step requested by the person before a
possible service contract. Consent is not used to disguise processing that is
necessary to calculate and return the requested result. Consent remains the
authority for optional WhatsApp and CRM handoffs, independently for each
purpose.

## Data boundary

The public interview does not require an account, phone, email, passport
number, document upload, criminal narrative or medical narrative. Structured
answers remain in memory/browser storage only as long as needed to operate the
flow. A durable decision stores the minimum deterministic audit projection and,
where configured, an encrypted payload separated from the audit row.

Visa Oracle telemetry is closed to the following fields only:

- event name;
- terminal state;
- hash of a random, opaque correlation value;
- occurrence time.

Raw answers, nationality, passport data, family data, free text, request and
response payloads are forbidden in telemetry and logs. The analytics sink must
delete the allowlisted events after 90 days; a client-side field allowlist does
not by itself satisfy that retention requirement.

## Data-subject requests

Requests are received through `privacy@balizero.com` and assigned an opaque
case reference. The operator verifies identity proportionately, searches by the
minimum supplied reference, and records the response or completion within 72
hours. Identity evidence is not copied into engineering tickets or logs.

Access, correction, restriction, withdrawal and deletion are distinct actions.
Deletion is executed unless a documented legal obligation or active legal hold
applies. Any exception states its legal basis, scope, owner, review date and the
data withheld from deletion. The response must not expose another person's
data.

## Legal hold

A hold is exceptional and decision-specific. It requires an opaque case
reference, reason, approver, timestamp and 30-day review date. The database
records set/release transitions append-only and synchronizes the encrypted
payload hold with its parent decision. A generic, indefinite or bulk hold is
not permitted.

## Minor protection

Visa Oracle may ask the age band needed for triage but does not collect a
minor's identity in the public interview. A case identified as involving a
minor cannot become an automated supported recommendation without confirmed
parent/guardian involvement. The safe terminal state is
`HUMAN_REVIEW_REQUIRED`; WhatsApp and CRM purposes still require their own
consents from the competent parent/guardian.

## Activation boundary

This approval authorizes engineering implementation of the policy. It does not
authorize production database mutation or ENFORCE. Before ENFORCE, the release
owner must attach:

1. an approved DPIA covering automated triage, minors, specific personal data,
   cross-border processors, security controls and residual risk;
2. evidence that the 30-day/24-hour database policy and 90-day telemetry
   deletion are actually scheduled and alerted;
3. a privilege preflight showing runtime, activation, policy, retention and
   legal-hold capabilities are separated;
4. a production smoke executed while public traffic remains fail-closed;
5. an independent gate with no open BLOCKER or MEDIUM finding.

## Legal reference

The operational controls are aligned to Indonesia's UU No. 27 Tahun 2022 on
Personal Data Protection, including the lawful-basis, notice, child-data,
high-risk assessment, data-subject-rights, deletion and breach-notification
provisions. Canonical official copies:

- <https://www.peraturan.go.id/id/uu-no-27-tahun-2022>
- <https://jdih.komdigi.go.id/produk_hukum/view/id/832/t/undangundang%2Bnomor%2B27%2Btahun%2B2022>
