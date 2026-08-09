# Visa Oracle V2 — Data Protection Impact Assessment V1

Status: **DRAFT / NO-GO FOR ENFORCE**

- Assessment date: 2026-08-06
- Privacy authority: `docs/policies/visa-oracle-privacy-policy-v1.json`
- Product owner: Zero
- Controller legal entity: **OPEN — Legal must record the exact entity**
- Privacy/DPO owner: **OPEN — must be named before approval**

This is the product-specific DPIA evidence packet required by Privacy Policy
V1. It is not yet an approval record. Any unresolved high risk below keeps
`VISA_ENGINE_EVALUATE_MODE=SHADOW`.

## 1. Processing and necessity

Visa Oracle asks one structured question at a time and evaluates the supplied
facts against a signed deterministic RulePack. The purpose is to return the
visa paths supported by current approved rules or to abstain with
`NEEDS_INPUT`, `HUMAN_REVIEW_REQUIRED`, `NO_SUPPORTED_PATH`, or
`TEMPORARILY_UNAVAILABLE`. It does not grant a visa and does not replace an
immigration officer or qualified human review.

The user-requested evaluation is processed as a pre-contractual step. Optional
WhatsApp and future CRM handoffs each require their own explicit, unticked
consent. Consent to one purpose is never consent to the other.

The public flow does not need an account, name, phone, email, passport number,
document upload, criminal narrative, medical narrative or free text. The
minimum structured facts are still personal data when they can be linked to an
assessment reference and must be protected accordingly.

## 2. Data flow and retention

| Stage              | Minimum data                                                                                                     | Recipient/store                                                                | Retention/control                                                                                                  |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| Interview          | Structured visa facts, including nationality, age/date band, purpose, stay and family/work context when relevant | Browser memory; optional local resume under the existing local-consent surface | No server account. User can restart/edit; descendant stale facts are pruned.                                       |
| Evaluation request | Structured facts, contract version and request metadata                                                          | Visa Oracle FastAPI endpoint                                                   | No LLM or vector search may choose, add, remove or order candidates. Payload/logging boundary is fail-closed.      |
| Durable audit      | Deterministic decision projection, source/rule/pack identity and optional encrypted payload                      | PostgreSQL                                                                     | 30 days from database-bound `evaluated_at`; legal hold only per identified record.                                 |
| Safe retry         | Request/response binding keyed by HMAC/idempotency material                                                      | PostgreSQL                                                                     | 24 hours; DSR deletion removes matching replay records atomically.                                                 |
| Product telemetry  | Event, terminal state, occurrence time, hash of a random opaque correlation value                                | Analytics endpoint only if configured                                          | PII-free allowlist; destination deletion at 90 days must be proven before use.                                     |
| WhatsApp           | Result state and optional opaque assessment reference                                                            | WhatsApp only after separate opt-in                                            | No raw answers and no implicit CRM creation. Provider retention remains to be recorded in the processor inventory. |
| CRM                | Not implemented/authorized by WhatsApp consent                                                                   | Future CRM processor only after separate opt-in                                | Must be assessed and noticed before activation.                                                                    |

Known infrastructure evidence: the backend Fly application declares Singapore
(`sin`) as its primary region. PostgreSQL, frontend hosting, analytics, Sentry,
WhatsApp/Meta and any backup/subprocessor storage region and transfer safeguard
must be recorded from the actual production contracts/configuration; this DPIA
does not infer them.

## 3. People affected and higher-risk data

- Prospective Bali Zero clients and people included in their visa scenario.
- Minors or cases involving minors. Child data receives the specific control
  below and is treated as high risk.
- Family/marriage context, nationality, immigration status and overstay facts,
  which may cause legal, financial or reputational harm if disclosed or used
  incorrectly.
- PEP/sanctions or other safety flags where supplied by an approved source.
  Visa Oracle must not collect a narrative or infer a flag from an LLM.

For a minor, the public result cannot become an automated supported handoff
without confirmed parent/guardian involvement. The safe path is human review;
WhatsApp/CRM still require independent purpose consent from the competent
adult.

## 4. Automated-triage safeguards

- Candidate selection and ordering are deterministic and RulePack-bound.
- LLM/Qdrant may explain only an already-approved decision.
- `UNKNOWN`, conflict, missing facts, stale sources, unavailable pricing or
  infrastructure failure cannot improve eligibility.
- Ed25519 verification, sequence/anti-rollback, bitemporal validity and HMAC
  evidence remain fail-closed. Unsigned production fallback is forbidden.
- Legal eligibility, operational availability and Bali Zero service
  availability remain separate dimensions.
- Every terminal state is exposed in the UI and a user can edit prior answers.
- Human review takes precedence for minors and the policy-defined safety cases.

## 5. Rights, deletion and exceptional preservation

Requests go to `privacy@balizero.com` and receive an opaque case reference.
The operational target for a valid request is 3 x 24 hours. Identity is
verified proportionately outside engineering logs. Access, correction,
restriction, withdrawal and erasure are distinct operations.

The bounded DSR function deletes one decision, its encrypted payload and
matching replay rows atomically. An active legal hold blocks erasure. A hold
requires a case token, opaque reason code, separate approver and a
timezone-aware review deadline within 30 days. Set and release are append-only
audited transitions; indefinite or bulk holds are forbidden.

## 6. Risk assessment

| Risk                                                        | Inherent | Current control                                                                                   | Residual / owner                                                                                    |
| ----------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Unsupported visa recommendation causes legal/financial harm | High     | Signed deterministic engine; tri-state rules; abstention; source freshness; five terminal states  | Medium after production smoke and independent adversarial gate — Product/Legal                      |
| Child case receives automated recommendation or handoff     | High     | Human-review default plus guardian confirmation before separate handoff consent                   | Medium; validate guardian wording and operating procedure — Privacy/Product                         |
| Raw facts leak through logs/analytics                       | High     | PII-free frontend allowlist, no generic session/user ID, payload/log tests                        | **High until destination schema, access and 90-day deletion evidence are proven** — Analytics/Infra |
| Durable records outlive approved purpose                    | High     | Policy-bound 30-day/24-hour database deadlines; bounded external purge and aggregate lag evidence | **High until migrations, policy registration, scheduler and alerts are armed** — Infra/Privacy      |
| Unauthorized pack activation or data mutation               | High     | Proposed owner/capability separation and read-only preflight                                      | **High: production privilege inspection currently fails** — DBA/Infra                               |
| DSR erases the wrong record or exposes identity evidence    | High     | Exact engine decision ID, dry-run operator command, legal-hold check, no ID in audit log          | Medium after operator rehearsal and two-person SOP — Privacy/Engineering                            |
| Cross-border processor/storage obligations are incomplete   | High     | Backend region known; public data minimization                                                    | **High until controller, processors, regions, contracts and safeguards are signed** — Legal/Privacy |
| Network/DB outage fabricates a result                       | High     | Timeout/failure maps to `TEMPORARILY_UNAVAILABLE`; no frontend fabricated fallback                | Low after production controlled-outage smoke — Engineering                                          |
| Replay/rollback or stale authority re-enables unsafe rules  | High     | Idempotency HMAC, Ed25519, anti-rollback and freshness fail-closed gates                          | Medium after production key/alert/preflight evidence — Security/Infra                               |

## 7. Mandatory closure evidence

The following attachments are required before this assessment can be approved:

1. exact controller legal entity, privacy owner and incident contacts;
2. production processor/subprocessor register, regions, transfer basis and
   retention for Fly, PostgreSQL/backups, frontend hosting, analytics/Sentry,
   WhatsApp/Meta and any CRM;
3. successful migration 264–266 and exact Privacy Policy V1 registration;
4. successful privilege preflight with no combined pack-write/activation login;
5. scheduler, missed-run, purge-lag and 90-day telemetry-deletion evidence;
6. DSR/legal-hold tabletop including wrong-ID, active-hold and absent-record
   cases;
7. SHADOW production smoke for all five terminal states, network/DB failure,
   PII-free logs and desktop/mobile accessibility;
8. independent review with no BLOCKER or MEDIUM finding.

## 8. Decision and signatures

Current decision: **DO NOT ENFORCE — open high residual risks remain.**

When all evidence above is attached, record the residual-risk decision here:

- Privacy/DPO owner: ____________________ Date: __________ Decision: ________
- Security/Infra owner: __________________ Date: __________ Decision: ________
- Product owner (Zero): _________________ Date: __________ Decision: ________

Approval of this DPIA would close only the privacy-impact gate. The ENFORCE
change window remains a separate explicit authorization after production
smoke and the independent release gate.

## Official legal sources

- <https://www.peraturan.go.id/id/uu-no-27-tahun-2022>
- <https://jdih.komdigi.go.id/produk_hukum/view/id/832/t/undangundang%2Bnomor%2B27%2Btahun%2B2022>
