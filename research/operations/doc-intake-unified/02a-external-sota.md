---
date: 2026-06-04
domain: operations
client_case: Bali Zero unified document-intake agentic system (FASE 2 external SOTA)
sources:
  - https://www.docsumo.com/blog/what-is-agentic-document-processing
  - https://idp-software.com/guides/agentic-document-processing/
  - https://github.com/docling-project/docling
  - https://docling-project.github.io/docling/usage/vision_models/
  - https://procycons.com/en/blogs/pdf-data-extraction-benchmark/
  - https://llms.reducto.ai/document-parser-comparison
  - https://towardsdatascience.com/the-multi-agent-trap/
  - https://medium.com/@roshan-menon/multi-agent-architecture-for-document-processing-a-practical-implementation-5a0e10f0b45b
  - https://resources.edc.ae/insights/closing-the-loop-confidence-scoring-and-human-review-in-idp
  - https://iterationlayer.com/blog/ai-data-extraction-confidence-scores
  - https://docs.cloud.google.com/document-ai/docs/hitl
  - https://redis.io/tutorials/data-deduplication-with-redis/
  - https://www.architecture-weekly.com/p/deduplication-in-distributed-systems
  - https://dev.to/aloknecessary/idempotency-in-distributed-systems-design-patterns-beyond-retry-safely-k66
  - https://matchdatapro.com/complete-guide-to-fuzzy-probabilistic-data-matching-and-entity-resolution/
  - https://towardsdatascience.com/using-a-local-llm-as-a-zero-shot-classifier/
---

# FASE 2 — External SOTA for a Unified Agentic Document-Intake System (Bali Zero)

## Context recap
WhatsApp (disk + `ocr_status=pending` queue), Google Drive (Changes API poll) and Zoho email
attachments feed a pipeline that must OCR locally (qwen3-vl) → classify (akta/KTP/passport/NIB/
NPWP/KITAS/SK/OSS) → extract fields (SEA-LION local) → distribute (CRM Postgres + per-client Drive
+ audit). HARD constraint: PII never leaves the machine (UU PDP), everything local, $0.

## What the 2026 SOTA actually says

**1. The reference shape is "ingest → classify → extract → validate → route", and the industry has
moved the value up to *agentic orchestration*.** Forrester (Q4 2025, via Docsumo/IDP-Software) frames
the differentiator as multi-document reasoning + end-to-end routing, not raw OCR. LlamaIndex ADW and
UiPath IXP both productized the exact four-stage loop we already sketched in FASE 1. Confirmation, not
novelty: our stage decomposition is correct.

**2. Local-first is a first-class SOTA path now, not a downgrade.** Docling (IBM Granite-Docling) runs
VLMs **locally by default**, with an MLX backend for Apple Silicon — directly aligned with our M-series
+ qwen3-vl/SEA-LION constraint. Zero-shot VLM classification (Qwen2.5-VL + chain-of-thought) reaches
production-grade accuracy with no template training. This is the single most important external finding:
the privacy constraint does NOT force us off the SOTA path.

**3. Parser bench reality.** Docling ~94-98% on complex tables, linear speed scaling, fully local;
LlamaParse fast (~6s) but cloud + currency/footnote errors; Unstructured slow + weak on complex tables.
For Indonesian legal docs (akta tables, OSS NIB layouts) Docling is the right *structure* layer to wrap
around qwen3-vl OCR — and it is the only top-tier option that is local + $0.

**4. Multi-agent has a hard ceiling: the "15-20 tool" trap.** Tool-selection accuracy collapses below
80% once an agent holds >15 tools (Towards Data Science, "The Multi-Agent Trap"). The SOTA answer is
*small specialized agents with 3-5 tools each*, coordinated by ONE orchestrator — not a swarm of
chatty peers. Practical implication for us: split classify / extract / route as **stages with narrow
tools**, but keep a single deterministic orchestrator; avoid agent↔agent negotiation.

**5. Idempotency/dedup is a solved distributed-systems pattern: hash at ingestion.** SHA-256 of the
file bytes as the dedup key, written before any downstream work, with the key retained on a long window
(Redis SET NX / a unique column). This is exactly the cross-source case (same PDF from WhatsApp AND
email): one content-hash table, checked at intake, kills the duplicate before OCR. Fuzzy/near-dup (SK
original vs PERBAIKAN correction) is a *separate* layer — those are NOT byte-identical, so they must be
linked by (doc-type + client + nomor SK) and versioned, never silently deduped.

**6. HITL = confidence-gated straight-through processing.** Google Document AI HITL, ABBYY and EDC all
converge: per-field confidence; above threshold → auto-commit to CRM; below → review queue with the
*reason and the specific uncertain fields* surfaced. Each human correction is a training signal.

**7. Entity resolution = blocking + scored fuzzy match.** Standard stack: normalize/parse name+phone+
passport, block into buckets, then Jaro-Winkler / Levenshtein scored match-merge. Passport number is a
near-unique key; phone (E.164 normalized) second; name fuzzy last.

## Pattern table

| Pattern | Pro | Contro | Adottare |
|---|---|---|---|
| Docling local VLM structure layer over qwen3-vl | Local, $0, 94-98% tables, MLX/Apple | Extra dependency, RAM | **SÌ** |
| Cloud parser (LlamaParse/Textract/Doc AI) | Fast, managed | PII to cloud → UU PDP breach | **NO** (constraint-fatal) |
| Zero-shot VLM classify (no template training) | No labeled data, new doc-types free | Needs CoT prompt tuning, edge ambiguity | **SÌ** |
| Specialized router model vs zero-shot | Cheaper/faster per call | Training + maintenance burden | NO (start zero-shot, add router only if drift) |
| Single orchestrator + narrow-tool stages | Avoids 15-tool collapse, debuggable | Less "autonomous" buzz | **SÌ** |
| Full agent swarm (peer negotiation) | Marketing-SOTA | Tool-accuracy <80%, non-deterministic, hard audit | **NO** |
| Content-hash dedup at ingestion (SHA-256) | Kills exact cross-source dupes cheaply | Misses near-dupes (PERBAIKAN) | **SÌ** |
| Fuzzy/version linking layer (doc+client+nomor) | Handles correction/revision docs | More logic | **SÌ** (separate from hash) |
| Event-driven queue + DLQ + idempotent consumer | Retry-safe, replayable, source-agnostic | Infra to run (already have PG queue) | **SÌ** |
| Confidence-gated HITL review queue | Auto-STP majority, human only on low-conf | Needs per-field conf from extractor | **SÌ** |
| Entity resolution (passport→phone→name fuzzy) | Auto-links doc to client | False-merge risk → needs review gate | **SÌ** (with HITL on low score) |

## Concrete recommendations
1. **Adopt Docling (MLX) as the structure/layout layer wrapping qwen3-vl OCR** — local, $0, top-tier
   tables; gives clean blocks to SEA-LION extraction.
2. **Keep zero-shot VLM classification** (Qwen + CoT) over the 8 doc-types; defer a trained router until
   measured misclassification justifies it.
3. **One deterministic orchestrator, narrow-tool stages** (classify / extract / validate / route, each
   ≤5 tools). Explicitly reject peer agent swarm — the 15-tool ceiling makes it less reliable AND less
   auditable, which matters for a regulated visa/tax agency.
4. **Two-tier dedup**: (a) SHA-256 content-hash table checked at ingestion across ALL three sources;
   (b) a *separate* version-link layer keyed on (doc_type, client_id, document_number) so SK ↔ SK-
   PERBAIKAN are linked + versioned, never collapsed.
5. **Reuse the existing PG `ocr_status` queue as the event bus** with explicit states
   (pending→ocr→classified→extracted→review→routed→done|dead) + a dead-letter state; consumers
   idempotent on content-hash so replays are safe.
6. **Confidence-gated HITL**: per-field confidence from SEA-LION; auto-commit to CRM above threshold,
   else a review queue row carrying the reason + the specific low-confidence fields. Feed corrections
   back as few-shot examples.
7. **Entity resolution doc→client**: normalize phone to E.164, exact-match passport/KITAS number first,
   then Jaro-Winkler on name; below a score floor → route to HITL rather than auto-merge.
8. **Audit agent = append-only event log**, never in the hot path; it observes the bus, satisfying the
   FASE 1 "audit agent" distribution target without adding orchestrator coupling.

## Net judgement
The privacy/local/$0 constraint is *not* a compromise versus 2026 SOTA — Docling-local + zero-shot VLM +
single-orchestrator narrow-tool stages IS the current best-practice shape. The only genuinely SOTA-vs-us
gap was framing (agentic orchestration language); the engineering primitives (hash dedup, DLQ,
confidence-gated HITL, fuzzy entity resolution) are mature and all implementable locally.
