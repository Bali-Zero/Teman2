# WhatsApp Full Corpus Gold Research

Generated UTC: `2026-05-26T18:32:30+00:00`

## Privacy Mode

- This tracked report contains no raw message text.
- This tracked report contains no message snippets.
- This tracked report contains no phone numbers or emails.
- This tracked report contains no raw source paths or contact names.
- Raw cleartext lives only in ignored `.local.*` artifacts on the Pro.
- No corpus text was sent to any cloud LLM or external API.

## What Changed

The corpus is now treated as a local cleartext asset, not only as a metadata
registry. The raw TXT exports were parsed into an ignored SQLite database with
FTS5 search. A narrow spicy-conversation quarantine then set aside only files
with explicit spicy keyword evidence. The remaining usable corpus was mined with
deterministic multilingual patterns for business and memory value.

## Verified Local Corpus State

| Layer                                  |    Count |
| -------------------------------------- | -------: |
| TXT files with parsed messages         |      699 |
| Zero-message files skipped             |      288 |
| Parsed raw messages                    |   162162 |
| Distinct sender hashes                 |      276 |
| Total body characters                  | 12052705 |
| Usable files after spicy quarantine    |      696 |
| Usable messages after spicy quarantine |   160530 |
| Quarantined spicy-candidate files      |        3 |
| Quarantined messages                   |     1632 |
| Gold signal hits                       |    62309 |
| Messages with at least one gold signal |    42735 |
| Files with at least one gold signal    |      605 |

## Local Artifacts

| Artifact                                  | Role                                           |
| ----------------------------------------- | ---------------------------------------------- |
| `full_messages.local.sqlite`              | Raw cleartext message store with FTS5.         |
| `spicy_quarantine.local.sqlite`           | Local spicy/intimate routing evidence.         |
| `spicy_quarantine.local.tsv`              | Private list of set-aside conversations.       |
| `usable_after_spicy_quarantine.local.tsv` | Private include list for mining.               |
| `full_gold_signals.local.sqlite`          | Hashed signal references over usable messages. |
| `full_corpus_parse_summary.md`            | Aggregate full parse report.                   |
| `spicy_quarantine_summary.md`             | Aggregate quarantine report.                   |
| `full_gold_signals_summary.md`            | Aggregate signal-mining report.                |

## External Research Basis

External sources were used only for general governance and risk framing, not for
corpus processing. The relevant takeaways:

- Indonesia PDP law: treat personal data processing as purpose-bound,
  controlled, and accountable. Local-only processing is still processing.
- GDPR Article 9 framing: intimate, health, biometric, religious, and other
  sensitive categories require special care if any EU persons are present.
- NIST AI RMF: keep a map-measure-manage-govern loop, with explicit data
  provenance, privacy risks, and human validation.
- OWASP LLM application guidance: the highest practical risks are sensitive
  information disclosure, overbroad retrieval, and tool/action execution from
  untrusted conversational content.

## Gold Signal Map

| Signal group            |  Hits | Meaning                                                          |
| ----------------------- | ----: | ---------------------------------------------------------------- |
| `immigration_lifecycle` | 24774 | Visa, permit, extension, appointment, biometric, stage movement. |
| `tax_payment`           | 13420 | Tax, invoice, transfer, payment proof, reconciliation.           |
| `followup_risk`         |  7539 | Pending, waiting, urgent, deadline, status pressure.             |
| `document_ops`          |  6509 | Passport, identity, company, property, notary, KBLI/OSS docs.    |
| `crm_lead_intake`       |  3958 | New leads, inquiries, pricing, quote, service-intake traces.     |
| `knowledge_mining`      |  3581 | Regulatory, permit, license, KBLI, ministry, local rules.        |
| `relationship_memory`   |  1443 | Non-quarantined life/memory events.                              |
| `operational_risk`      |  1085 | Problems, mistakes, rejection, complaints, cancellation.         |

## Highest-Value Products

### 1. Local WhatsApp Ops Search Console

Build a local dashboard over `full_messages.local.sqlite` and
`full_gold_signals.local.sqlite`. The first version should support:

- Search raw cleartext with FTS5.
- Filter by signal group, month, source, file ID, and sender hash.
- Open a case window around a message without exposing raw paths in reports.
- Mark reviewed rows as CRM action, KB extract, ignore, or private.

This is the immediate killer app because it turns four years of chat history
into a private operational search engine.

### 2. CRM Case Timeline Builder

Group messages by file, month, and signal sequence to reconstruct client/practice
timelines:

- Lead intake.
- Quoted service or price.
- Documents requested.
- Payment proof or invoice.
- Visa/company/tax stage.
- Follow-up or issue.
- Completion or stalled state.

The output should be local drafts only. No automatic CRM write until owner
approval.

### 3. Follow-Up and Deadline Recovery Queue

Use the 7539 follow-up/risk hits plus case windows to surface:

- Stale pending threads.
- Deadline pressure.
- Repeated unanswered asks.
- High-value clients with payment or document blockers.
- Risky complaint or rejection sequences.

This should become an internal queue with `approve/hold/no_action`, mirroring
the current case-window review workflow.

### 4. Knowledge Extraction for Bali Zero Internal KB

Use `knowledge_mining`, `document_ops`, and `immigration_lifecycle` hits to
extract reusable internal knowledge:

- Repeated visa document explanations.
- Repeated tax-payment explanations.
- Repeated KBLI/company setup explanations.
- Common client misunderstandings.
- Local procedural edge cases not yet in the KB.

All extraction should be local first. Only sanitized, owner-approved knowledge
should enter tracked KB files.

### 5. Client Similarity and First-30-Day Playbooks

Cluster early-stage lead/client conversations locally to answer:

- What do similar leads ask first?
- Which documents are usually missing?
- Which questions predict later payment or deadline pressure?
- Which service explanations reduce repeated follow-ups?

This is the best bridge from raw history into proactive CRM and sales operations.

## Recommended Local Architecture

| Layer            | Choice                                                     | Reason                                               |
| ---------------- | ---------------------------------------------------------- | ---------------------------------------------------- |
| Raw text store   | SQLite FTS5                                                | Already built, local, fast enough for 160k messages. |
| Signal store     | SQLite                                                     | Deterministic, auditable, easy to join.              |
| Local embeddings | `bge-m3` or equivalent local model                         | Avoid cloud embedding of raw chat text.              |
| Vector DB        | Local Qdrant or pgvector sandbox                           | Keep separate from production KB vectors.            |
| LLM reasoning    | Ollama local first                                         | Satisfies corpus sovereignty.                        |
| Cloud LLM        | Only after E2E encryption or sanitized extracts            | Never raw team/personal chat.                        |
| UI               | Local dashboard under `research` or internal `/home` route | Owner-only review and action approval.               |

Do not mix this corpus with production Qdrant collections that use the frozen
production embedding model. If embeddings are added, create a separate local
collection with explicit naming and dimensions.

## Implementation Roadmap

### Phase 1: Search and Review

- Build local dashboard over FTS5 and signal DB.
- Add message-window viewer with previous/next context.
- Add owner decision table for gold hits.
- Keep all decisions in `.local.tsv` until approved.

### Phase 2: CRM Draft Actions

- Convert approved hits into local CRM draft rows:
  `client_candidate`, `practice_stage`, `document_needed`, `payment_event`,
  `followup_due`, `risk_note`.
- Require owner approval before writing to canonical CRM.
- Store source as file/message IDs only, not raw chat text.

### Phase 3: Internal KB Drafts

- Extract recurring explanations and procedural facts.
- Generate local drafts with citations to file/message IDs.
- Owner sanitizes before tracked KB commit.

### Phase 4: Local Semantic Layer

- Embed non-quarantined messages locally.
- Build per-domain collections: immigration, tax/payment, document ops,
  follow-up/risk, lead intake.
- Add similarity search for new leads and first-30-day playbooks.

### Phase 5: Automation

- Add scheduled local re-indexing when new WA exports arrive.
- Add privacy audit before any tracked report changes.
- Add action queues with explicit owner approval gates.

## Do Not Do

- Do not upload raw messages to OpenAI, Anthropic, Google, or Gemini.
- Do not train a commercial model on the corpus.
- Do not expose raw chat text or source IDs in a client portal.
- Do not auto-create CRM records without owner approval.
- Do not use quarantined spicy-candidate conversations for mining.

## Next Execution Prompt

Build the local WhatsApp Ops Search Console over
`full_messages.local.sqlite` and `full_gold_signals.local.sqlite`, with FTS5
query, signal filters, message-window context, and owner decision export.
