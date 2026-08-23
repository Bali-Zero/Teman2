---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Research OS Surface Coverage Matrix

**Version:** `research-os/v1.0.0`
**Status:** frozen outcome-to-surface contract; current entries describe the target path, not proof of implementation

The carousel is one valuable surface, not the system objective. This matrix forces every one of the nine outcome families to possess a complete, privacy-correct route from daily signals to a decision, a specifically authorized action, a receipt, and measurable learning.

## 1. Coverage contract

A row is covered only when all of the following exist and reconcile:

1. named signal producers and protected source of record;
2. canonical `IntelEvent`, `Evidence`, and where consequential, `Claim` identities;
3. a traceable `DecisionPacket` and specialist `VerificationReceipt` where required;
4. one Action Inbox view, owner role, priority, and SLA;
5. a versioned `ActionIntent` with exact target and argument hash;
6. a specific, unexpired `ApprovalReceipt` before execution;
7. an immutable idempotent started `ExecutionAttempt` and a separate typed `OperationalReceipt` for the result;
8. a canonical `MetricResult` under a preregistered `MetricProfile`, followed by an `OutcomeEvent` bound to both exact hashes; and
9. retention, revocation, sensitivity, and sanitization propagation appropriate to the source.

No row may create its own general event, claim, action, approval, execution, or outcome ledger.

## 2. Nine-family matrix

| Outcome family | Signals and protected truth | Evidence-to-decision adapter | Action Inbox view and owner | Authority and execution boundary | Receipt and learning return | Protected store | Adoption packet |
|---|---|---|---|---|---|---|---|
| **Compliance protection** | Regulations, source health, NAGA expiry/contradiction, client obligation clocks | Grounded compliance `DecisionPacket`; NotebookLM specialist receipt for public domain facts | Compliance view; practice owner; statutory-risk SLA | No legal determination or client change by model; named human approves the exact intervention | Filing/renewal/escalation/correction result as `OutcomeEvent`, including no-result and lateness | NAGA for public claims; CRM for client obligations; no client rows in general ledger | [19](./work-packets/19-compliance-protection-slice.md) |
| **Client journey** | Portal friction, service milestones, consented CRM events, support classifications | Minimized journey packet linked to protected CRM references | Journey view; service owner; stage-specific SLA | Every message, record mutation, or service transition has exact approval and executor receipt | Response, completion, delay, satisfaction, renewal, and complaint outcomes; cohorts below 10 suppressed outside CRM | Protected CRM remains row-level source of truth | [20](./work-packets/20-client-journey-slice.md) |
| **Revenue and partnerships** | Renewal windows, consented engagement, public market/partner signals, service demand | Opportunity packet with PricingTool references and PII-minimized evidence | Revenue/partnership view; commercial owner; opportunity SLA | No outreach, quote, price, CRM mutation, or partner commitment without named approval | Qualified opportunity, accepted quote, conversion, loss reason, margin guardrail, partner outcome | CRM and PricingTool; general ledger receives IDs/aggregates only | [21](./work-packets/21-revenue-partnership-slice.md) |
| **Product and self-service** | Search gaps, failed journeys, support themes, portal and product telemetry | Product-friction packet with reproducible query cohort and evidence | Product view; product owner; severity/reach SLA | Experiment proposal is not a release; code change follows isolated worktree, tests, review, and deploy authority | Task success, deflection, latency, error, conversion and complaint guardrails | Product analytics plus issue tracker; sensitive queries minimized | [22](./work-packets/22-product-self-service-slice.md) |
| **Decision intelligence** | Intel Lake clusters, NAGA claims, NEXUS sanitized gaps, specialist sources | Ranked, citation-bearing `DecisionPacket` plus `VerificationReceipt` | Operator view; Conductor; decision freshness SLA | Conversation creates locks and action proposals only; no direct side effect | Operator edit, selection, rejection, snooze, assignment and downstream decision quality | Intel Lake/NAGA; NEXUS remains restricted and only receipt-approved projections leave it | [05](./work-packets/05-intel-lake-v2-mata-consolidation.md), [06](./work-packets/06-naga-claim-ledger.md), [07](./work-packets/07-nexus-temporal-entity-resolution.md), [08](./work-packets/08-hybrid-retrieval-evaluation.md), [17](./work-packets/17-notebooklm-verification-adapter.md), [18](./work-packets/18-conductor-session-bridge.md) |
| **Authority and demand** | Fresh public Bali signals, verified claims, search demand, prior content outcomes | Conductor topic/creative lock becomes one `ContentObject` and channel derivatives | Editorial view; operator/editor; freshness and risk SLA | v1.0.0 requires human approval before public publication; WR2/WR3 stop before final social publish | Deployment, verified indexing, reach, saves, watch quality, qualified demand, corrections and withdrawals | Publication ledger plus GSC/GA4/social aggregate projections | [09](./work-packets/09-blog-magazine-seo-loop.md), [10](./work-packets/10-wr2-creative-foundry.md), [11](./work-packets/11-wr3-video-foundry.md) |
| **Team enablement** | Unowned work, breached SLA, recurring questions, verified policy changes | Role-specific brief/checklist packet with citations and expiry | Team view; named team lead; acknowledgment/completion SLA | Internal assignment, notification, or workflow change still requires exact approval; no hidden send | Acknowledgment, completion, escalation, rework, question resolution and freshness outcomes | Action Inbox and approved operational systems; no parallel cockpit | [23](./work-packets/23-team-enablement-slice.md) |
| **Memory and learning** | Human edits, approvals, rejections, corrections, outcomes, source-quality changes | Versioned before/after examples and offline learning proposal | Learning review view; domain owner plus independent evaluator | Learner never mutates live prompts, code, ranking, or routes; adoption is a separately reviewed change | Offline lift with confidence/guardrails, accepted/rejected proposal and post-canary outcome | Canonical receipts and outcome repository; PII minimized and retention enforced | [13](./work-packets/13-outcome-telemetry.md), [15](./work-packets/15-active-learning.md) |
| **Platform governance** | Workflow runs, queue reconciliation, health, cost, security, privacy, stranded messages | Failure or simplification packet with exact affected objects and rollback | Reliability view; system owner; severity SLA | Deploy, flag flip, migration, secret rotation, scheduler activation, and retirement each need separate authority | Reliability, replay, cost, leakage, reconciliation, rollback and incident outcomes | Append-only audit receipts and protected secret system; never secret values | [14](./work-packets/14-cross-system-evaluations.md), [16](./work-packets/16-controlled-retirement.md) |

## 3. Shared public surfaces

- **Blog** is an existing public outcome surface. Its deployment and indexing truth are separated.
- **Magazine** is frozen as a future public surface, but `research-os/v1.0.0` does not authorize a public launch or unattended job. It must pass Packet 09 shadow/canary and receive separate owner authorization.
- **WR2** and **WR3** are foundries after Conductor locks; they do not discover or approve their own topic.
- **Instagram and other social platforms** retain a manual final-publish stop in this freeze.
- **CRM, portals, alerts, and team views** consume canonical packets and receipts; they do not recreate evidence or action truth.

## 4. Coverage evidence and release rule

Each adoption packet produces a machine-readable row fixture containing object IDs and hashes, owner role, SLA, sensitivity, feature flag, operating window, an exact `{metric_profile_id, object_hash}` reference, an exact `{metric_result_id, object_hash}` reference, an exact metric-bearing `{outcome_event_id, object_hash}` reference that binds both preceding hashes, rollback proof, and an exact independent-verdict receipt. Packet 14 treats any blank cell, bare metric ID, missing member of that causal triplet, unconfirmed revocation target, hidden parallel queue, missing denominator, or unreceipted effect as a blocking gap.

The Matrix is complete only when all nine rows pass in shadow for two predeclared operating windows and each separately authorized canary remains inside its privacy, cost, quality, and reliability guardrails. Paper coverage is not implementation coverage.
