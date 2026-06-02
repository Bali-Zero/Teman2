---
date: 2026-05-27
domain: operations
client_case: wa-business-messages-research-console-wa-mirror-crm-enrichment
status: panel-synthesis
privacy: no-raw-whatsapp-content
tools:
  claude: completed
  gemini_agy: completed
  codex_gpt55: completed
  nlm_research: completed
  exa: unavailable_in_session
  tavily: unavailable_in_session
  manus: unavailable_401
sources:
  - Meta WhatsApp Cloud API overview
  - GDPR Art. 5 and Art. 6 references
  - Indonesia UU PDP No. 27/2022 references
  - Microsoft/AWS transactional outbox references
  - Martin Fowler event-driven/event-sourcing references
---

# WhatsApp Business Messages Architecture Brainstorm

## Executive Summary

The winning design is not just a "WhatsApp search console". It is a local-first
WhatsApp Intelligence Control Plane:

1. Raw WhatsApp stays local on the Pro.
2. `wa-mirror` remains the live capture feed and first identity signal.
3. Historical exports feed a local FTS/search and enrichment workbench.
4. Identity resolution is continuous and graph-like, not a one-time match.
5. CRM/workspace receives only derived internal facts and actions.
6. Client portal receives only explicit client-safe projections, never raw WA.

The panel converged on four architectural pillars:

| Pillar | Decision |
|---|---|
| Ingest firewall | Capture and index locally first; block raw egress by design |
| Identity graph | Score phone, LID, wa-mirror client_id, CRM context, names, documents |
| Temporal facts | Store derived facts with validity, confidence, supersession, provenance |
| Action routing | Use idempotent outbox/actions for CRM ops, compliance, docs, payments |

Immediate implementation should start with `build_workspace_enrichment.py`: it
turns the mined local corpus into candidate matches/facts/actions without
writing to CRM yet.

## Tool Run Log

| Tool/session | Result | Notes |
|---|---|---|
| Claude Opus via `claude --print --model opus` | Completed | Session 1, business/governance architecture |
| Gemini via `agy --print` | Completed | Session 2, critique and product/system design |
| Codex GPT-5.5 via `codex exec -m gpt-5.5` | Completed | Session 3, convergent implementation and red-team |
| NLM research | Completed | Created NotebookLM notebook with 42 sources |
| Exa | Not available | No CLI/MCP exposed in this session |
| Tavily | Not available | No CLI/MCP exposed in this session |
| Manus | Failed | Connector returned 401 invalid/revoked token |

NLM notebook:

```text
Notebook ID: 3ad29783-2dae-4a4c-9891-266e4a150a8b
Title: WA CRM Enrichment Architecture 2026
URL: https://notebooklm.google.com/notebook/3ad29783-2dae-4a4c-9891-266e4a150a8b
Imported sources: 42
```

## Public Research Digest

No private WhatsApp data was sent to external tools. Research prompts used only
abstract system context and aggregate counts.

| Source | Relevant point for architecture |
|---|---|
| Meta WhatsApp Cloud API overview | Cloud API relies on webhooks for inbound messages and outgoing delivery statuses; permissions include business and WhatsApp messaging scopes; transport uses HTTPS/TLS and business-destination security. |
| GDPR Art. 5 | Processing needs purpose limitation, minimization, accuracy, storage limitation, integrity/confidentiality, and accountability. |
| GDPR Art. 6 | Potential bases include contract necessity, legal obligation, consent, and legitimate interest; basis must be documented per use case. |
| Indonesia UU PDP No. 27/2022 | Personal data processing duties apply; full names and identifying combinations are personal data; controller/processor duties, rights, transfer, sanctions matter. |
| Microsoft Transactional Outbox | Save business object and event in the same transaction; a worker publishes later, avoiding dual-write loss. |
| AWS Transactional Outbox | At-least-once delivery can duplicate messages, so consumers must be idempotent; ordering can use timestamps/sequence numbers. |
| Martin Fowler on event-driven systems | "Event-driven" has multiple meanings; event notification can hide larger flows; event sourcing is powerful for audit/reconstruction but should be scoped. |
| NIST AI RMF / Privacy Framework | AI and privacy risk management should be designed into system lifecycle, not bolted on after feature work. |
| OWASP LLM Top 10 | Sensitive information disclosure and vector/embedding weaknesses are first-class risks in RAG/LLM systems. |

Source links:

- https://meta-preview.mintlify.io/docs/whatsapp/cloud-api/overview
- https://gdpr-info.eu/art-5-gdpr/
- https://gdpr-info.eu/art-6-gdpr/
- https://www.peraturan.go.id/id/uu-no-27-tahun-2022
- https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022
- https://learn.microsoft.com/en-us/azure/architecture/databases/guide/transactional-out-box-cosmos
- https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
- https://martinfowler.com/articles/201701-event-driven.html
- https://www.nist.gov/itl/ai-risk-management-framework
- https://www.nist.gov/privacy-framework
- https://owasp.org/www-project-top-10-for-large-language-model-applications/

## Session 1: Claude

Claude's framing: the corpus is gold for structured facts, poison for direct
exposure.

Key proposals:

| Area | Proposal |
|---|---|
| Use messages for | Identity resolution, practice lifecycle signals, compliance deadlines, document tracking, payment/quote audit, lead capture, risk flags |
| Do not use for | Client portal raw display, cloud LLM raw processing, marketing profiling, team performance scoring, automated client replies |
| Console | Local FTS5 search, result windows not full threads, audit every query, no bulk export by default |
| wa-mirror | Keep live feed in `whatsapp_message_context`; use outbox to route derived events |
| Identity | Phone/LID first, name only as weak signal, never auto-link first-name only |
| Facts | deadline, payment, document, complaint/risk, regulatory rumor, lead, quote |
| Governance | Purpose limitation, minimization, retention classes, search audit, subject rights |
| Build order | Governance and identity before extraction breadth |

Important critique: one unverified detail appeared in Claude's output. The
synthesis excludes it. The durable conclusion is the architecture, not that
specific assumption.

## Session 2: Gemini

Gemini's framing: search is not enough; build proactive operational surfaces.

Main disagreements with Session 1:

| Disagreement | Synthesis decision |
|---|---|
| "Identity first" can block ingest | Ingest first locally; identity gates only CRM writes |
| Search console is reactive | Add triage queues, entity dossiers, signal dashboards |
| `internal_facts` too flat | Use temporal facts with valid_from/valid_until/supersession |
| Full event sourcing with PII is dangerous | Use audit/outbox for derived events only; do not event-source raw WA |
| Redaction can break RAG | Prefer entity-linked placeholders and strict routing schemas |

Gemini emphasized:

| Area | Recommendation |
|---|---|
| Product surfaces | Triage queue, entity dossiers, DSR/erasure console, aggregate signal dashboard |
| Data model | Separate toxic raw ingest from derived facts and egress payloads |
| Identity | Continuous graph with edges, clusters, evidence weights |
| Routing | CRM receives strict typed facts; local triage sees raw context; KB receives only de-identified process knowledge |
| Build order | Pipes and firewall first, local LLM extraction later |

## Session 3: Codex

Codex converged the panel into an implementation blueprint.

Resolution of conflicts:

| Conflict | Final decision |
|---|---|
| Raw TTL vs legal audit | Raw has configurable TTL/legal hold; durable audit stores hashes/metadata/decisions, not raw body |
| Identity-first vs ingestion-first | Ingest locally first; identity gates downstream writes |
| `internal_facts` vs temporal facts | One canonical temporal fact model with validity, status, confidence, provenance |
| Event sourcing vs audit logs | No raw event sourcing; use transactional outbox and append-only audit for derived events |
| Search console vs automation | Build both: local operator console plus action routing |

Codex's final shape:

```text
WhatsApp exports + wa-mirror
  -> local raw/quarantine/index
  -> message firewall
  -> continuous identity resolver
  -> local enrichment pipeline
  -> temporal internal facts
  -> action_queue + operator console
  -> transactional outbox
  -> internal CRM/workspace derived records only
  -> client-safe projection only after explicit allowlist
```

## Final Architecture

### System Map

```text
PRO LOCAL ONLY

Historical corpus:
  full_messages.local.sqlite
  full_gold_signals.local.sqlite
  spicy_quarantine.local.sqlite

Live capture:
  apps/wa-mirror
  whatsapp_message_context
  whatsapp_conversations
  wa_lid_phone_map
  whatsapp_identity_audit

Local intelligence:
  wa_search_console local API/UI
  workspace_enrichment.local.sqlite
  candidate_matches
  candidate_facts
  candidate_actions
  blocked_records

Derived write zone:
  whatsapp_extractions
  crm_whatsapp_enrichment_facts
  action_queue
  transactional_outbox
  wa_processing_audit

Internal workspace:
  kita.balizero.com internal CRM views
  internal dossiers
  ops queue
  compliance queue

Client portal:
  my.balizero.com
  only client_safe_projection
  no raw WA, no hashes, no source traces, no internal evidence
```

### Product Surfaces

| Surface | User | Purpose | Raw access |
|---|---|---|---|
| WA Research Console | Owner/operator | Local search, triage, identity review, context windows | Local only |
| Signal Queue | Operator | Proactive extracted signals needing attention | No raw unless local drilldown |
| Entity Dossier | Internal CRM user | Client/practice facts, risk, deadlines, docs, payments | Derived only |
| Identity Review | Admin/operator | Resolve ambiguous phone/LID/name/company matches | Local evidence |
| Action Queue | Team/ops | Follow-up, payment, document, compliance tasks | Derived only |
| KB Draft Queue | Owner/research | De-identified process/regulatory knowledge | No client identity |
| Client-safe Projection | Client portal | Approved status only | Never raw |

## Identity Scoring

Existing wa-mirror recognition is the strongest signal. The matcher must not
discard it and rematch from scratch.

| Signal | Strength | Decision |
|---|---:|---|
| Existing `whatsapp_message_context.client_id` from wa-mirror | 0.98 | Auto-link unless conflict |
| Existing `practice_id` from wa-mirror | 0.95 | Preferred practice; can be refined |
| Existing `conversation_id` | 0.95 | Canonical conversation window |
| Exact normalized phone to CRM | 0.95 | Auto-link |
| LID -> phone/client via `wa_lid_phone_map` | 0.90 | Auto-link if no conflict |
| Team email to active staff | 1.00 team identity | Marks sender role, not client identity |
| Unique document/invoice/reference match | 0.80-0.90 | Strong supporting signal |
| Company/practice name unique match | 0.75-0.85 | Candidate or auto only with another signal |
| Sender/chat/export display name to client | 0.35-0.75 | Useful, but capped if alone |
| Name-only match | max 0.54 | Never CRM auto-write |
| First name/nickname/common local names | 0.20-0.40 | Context only |

Decision bands:

| Band | Behavior |
|---|---|
| `>= 0.90` | Auto-link and allow derived fact routing |
| `0.75-0.89` | Extract locally; route to triage or low-risk internal action only |
| `0.55-0.74` | Candidate only, no CRM write |
| `< 0.55` | Unresolved |
| quarantine hit | Block all CRM enrichment |

## Enrichment Taxonomy

Start narrow. Do not begin with broad summarization.

| Fact family | Examples | Route |
|---|---|---|
| Deadline | filing date, appointment, response due, expiry mention | compliance, ops |
| Payment | promised, paid, proof sent, overdue, invoice request | finance/action_queue |
| Document | requested, missing, received, expired, signature needed | docs/compliance |
| Complaint/risk | dissatisfaction, refund, delay, escalation, threat, fraud | owner_review |
| Lead/interest | first inquiry, service interest, quote request, referral | sales/lead capture |
| Quote/scope | price quoted, package, discount, scope boundary | sales/finance audit |
| Identity | new phone, alias, LID bridge, related person/company | identity_review |
| Legal/compliance | visa/tax/company/license obligation | compliance |
| Relationship context | preferred language, urgency, VIP, communication preference | internal dossier only |
| Knowledge mining | procedural/regulatory insight without identity | KB draft queue |

## Routing Firewall

No route gets raw message body by default.

| Destination | Allowed payload | Blocked |
|---|---|---|
| Local console | Raw local evidence, context windows, match explanations | Cloud export |
| CRM workspace | typed facts, confidence, source hash, local reference | raw body, source path, phone snippets |
| Action queue | task, entity id, due date, reason enum, confidence | raw thread text |
| KB draft | de-identified process/regulatory insight | client/team identity |
| Client portal | approved client-safe status | WA provenance, internal evidence, hashes |

Strict egress payload shape:

```json
{
  "fact_type": "deadline",
  "entity_type": "practice",
  "entity_id": "internal-id",
  "value": {"date": "YYYY-MM-DD", "kind": "submission_deadline"},
  "confidence": 0.84,
  "source": {
    "system": "whatsapp_local",
    "body_hash": "sha256",
    "raw_available_local": true
  },
  "visibility": "internal_only"
}
```

## Timing

| Cadence | Job |
|---|---|
| Per message | `wa-mirror` writes, hash, DLP/spicy check, identity candidate update |
| 1 minute | deterministic high-confidence facts, urgent action enqueue |
| 5 minutes | identity resolver catch-up, conversation grouping, triage refresh |
| 15 minutes | transactional outbox dispatch, retry failed idempotent deliveries |
| Hourly | local Ollama extraction batches, conflict detection, dossier refresh |
| Daily | retention sweep, privacy audit, unresolved identity report |
| Weekly | sample quality review, threshold tuning, false positive review |

Historical backfill:

| Step | Output |
|---|---|
| Parse | `full_messages.local.sqlite` |
| Quarantine | spicy/private exclude list |
| Mine signals | `full_gold_signals.local.sqlite` |
| Build enrichment | `workspace_enrichment.local.sqlite` |
| Apply high-confidence facts | CRM/workspace derived tables only |

## Data Model Delta

Reuse existing tables where possible:

| Existing | Keep/extend |
|---|---|
| `whatsapp_message_context` | live/source message store with identity columns |
| `whatsapp_conversations` | canonical conversation windows |
| `whatsapp_extractions` | extracted facts before promotion |
| `whatsapp_identity_audit` | decision audit |
| `wa_lid_phone_map` | LID bridge |
| `action_queue` | operator tasks |

Add:

| New table/file | Purpose |
|---|---|
| `workspace_enrichment.local.sqlite` | local candidate matches/facts/actions before CRM write |
| `crm_whatsapp_enrichment_facts` | temporal internal facts derived from WA |
| `fact_provenance` | source hashes, extractor version, identity confidence, no raw |
| `wa_processing_audit` | processing decisions without raw body |
| `transactional_outbox` | reliable idempotent routing to workspace/actions |
| `client_safe_fact_projection` | explicit client portal allowlist |

## Implementation Roadmap

### Phase 0: Panel Output To Repo

This report plus the previous architecture note become the decision record.

Existing note:

```text
research/operations/2026-05-27-whatsapp-local-search-console-wa-mirror-enrichment-routing.md
```

This report:

```text
research/operations/2026-05-27-wa-business-messages-architecture-brainstorm.md
```

### Phase 1: Local Enrichment Builder

Create:

```text
scripts/whatsapp_corpus/build_workspace_enrichment.py
scripts/tests/test_whatsapp_corpus_workspace_enrichment.py
```

Outputs:

```text
research/personal/wa-corpus/full/workspace_enrichment.local.sqlite
research/personal/wa-corpus/full/workspace_enrichment_summary.md
```

Tables inside local SQLite:

| Table | Purpose |
|---|---|
| `candidate_matches` | file/message/conversation to CRM candidate |
| `candidate_facts` | typed local facts before CRM write |
| `candidate_actions` | local action suggestions |
| `blocked_records` | quarantine, low-confidence, conflict, no target |
| `run_metrics` | thresholds, counts, versions |

### Phase 2: Privacy Firewall

Create:

```text
apps/backend-rag/backend/services/wa_copilot/privacy_firewall.py
apps/backend-rag/backend/tests/services/wa_copilot/test_privacy_firewall.py
```

Rules:

| Rule | Behavior |
|---|---|
| raw_body field in egress | fail closed |
| phone/email/passport/NIK in free text payload | fail closed unless field is explicitly typed and internal-only |
| quarantine source | block CRM write |
| name-only identity | block CRM write |
| unknown visibility | block |

### Phase 3: Temporal Facts Migration

Create:

```text
apps/backend-rag/backend/db/migrations_v2/202_wa_whatsapp_enrichment_facts.sql
```

Tables:

```text
crm_whatsapp_enrichment_facts
crm_whatsapp_fact_provenance
wa_processing_audit
transactional_outbox
client_safe_fact_projection
```

### Phase 4: Apply Writer

Create:

```text
scripts/whatsapp_corpus/apply_workspace_enrichment.py
scripts/tests/test_whatsapp_corpus_apply_workspace_enrichment.py
```

Behavior:

| Input | Output |
|---|---|
| high-confidence `candidate_facts` | `crm_whatsapp_enrichment_facts` |
| high-confidence action candidates | `action_queue` |
| conflicts | `identity_review` action |
| blocked | audit only |

### Phase 5: Console

Create:

```text
apps/backend-rag/backend/app/routers/wa_search_console.py
apps/backend-rag/backend/services/wa_copilot/search_console.py
apps/backend-rag/backend/tests/unit/routers/test_wa_search_console.py
```

Frontend later:

```text
apps/mouth/src/app/(workspace)/whatsapp-console/page.tsx
```

## Top 10 Risks

| Risk | Mitigation |
|---|---|
| Wrong client linkage | identity score bands, name-only cap, conflict queue, audit |
| Raw data egress | privacy firewall, tests, no raw fields in outbox |
| Portal leak | separate client-safe projection table |
| Over-automation | start with 3 fact families; review gates |
| Retention/legal conflict | raw TTL plus legal hold; audit hashes long-term |
| PII event sourcing burden | no raw event sourcing |
| Quarantine contamination | quarantine gate before all enrichment |
| Duplicate actions | transactional outbox + idempotency keys |
| Identity drift | hourly reconciliation and score decay |
| SQLite/local bottleneck | batch checkpoints, FTS5/WAL, derived-only promotion |

## Final Recommendation

Build in this order:

1. `build_workspace_enrichment.py`
2. `privacy_firewall.py`
3. `202_wa_whatsapp_enrichment_facts.sql`
4. `apply_workspace_enrichment.py`
5. `wa_search_console.py`

Do not start with a big RAG bot. Do not start with broad summarization. Do not
write raw WhatsApp into CRM.

Start by making the local mined corpus produce a safe candidate enrichment
database. Once that is stable, add the write path to internal CRM tables and
then the local operator console.
