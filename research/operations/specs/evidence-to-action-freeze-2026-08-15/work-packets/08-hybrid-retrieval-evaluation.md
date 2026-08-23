---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 08 — Hybrid Retrieval and Evaluation

**Wave:** 1
**Depends on:** Packets 05 and 06
**Unlocks:** Packet 14 and higher-quality Conductor/RAG consumers
**Risk:** medium; read-path change only after benchmark

## Session prompt

You own a measured retrieval upgrade, not a vector-stack rewrite. Preserve the canonical dense embedding `text-embedding-3-small` at 1536 dimensions. Add lexical/sparse, temporal, and selective graph signals only where a frozen evaluation proves value.

You are not alone in the codebase. Work in a dedicated worktree, declare the exact collections/services/tests you own, preserve concurrent changes, and do not alter collection dimensions or rebuild canonical vectors. Do not deploy or cut over a reader without explicit approval.

## Mission

Improve supported retrieval for lexical, semantic, temporal, no-answer, and genuinely multi-hop questions while controlling latency, cost, privacy, and failure modes.

## Baseline to establish

Audit the live collection registry, Qdrant collection/vector configuration, current search fusion, metadata filters, reranking, fallback paths, latency, and consumers. Confirm the actual embedding model/dimension from code and live collection metadata. Sample current failures instead of assuming hybrid retrieval is absent everywhere.

Primary ownership should remain within:

- `apps/backend-rag/backend/core/collection_registry.py` only if additive registry metadata is necessary;
- focused retrieval services under `apps/backend-rag/backend/services/rag/`;
- new research-OS retrieval adapters/evaluators;
- isolated evaluation datasets and focused tests;
- Qdrant configuration changes that do not invalidate the existing dense vector.

Do not own claim truth, graph entity merging, content generation, or source ingestion.

## Inputs and frozen contracts

- Canonical Intel event/story identity from Packet 05.
- Reviewed claims/evidence/validity from Packet 06.
- Query context must include allowed sensitivity, jurisdiction, valid-at time, and purpose.
- The dense embedding and dimension are immutable in this packet.

## Deliverables

1. A versioned 200+ query evaluation set with lexical, semantic, multilingual, temporal, local, global, multi-hop, contradictory, and no-answer cases.
2. Current-system baseline: Recall@20, nDCG@10, MRR, supported-answer rate, temporal precision, no-answer precision, p50/p95 latency, and cost.
3. Additive sparse/BM25 representation or index, with language-aware normalization.
4. Dense+sparse fusion using Reciprocal Rank Fusion or a benchmarked alternative.
5. Metadata filters for jurisdiction, valid time, sensitivity, document/claim status, and source tier.
6. Optional reranker over a bounded top-K only when its measured value exceeds cost/latency.
7. A query router that invokes graph/global retrieval only for classified multi-hop/global questions.
8. Explicit abstention/no-answer behavior when support is insufficient.
9. Per-query trace showing candidates, filters, fusion scores, rerank decisions, evidence IDs, and timing.

## Non-goals

- Do not switch embeddings or dimensions.
- Do not replace Qdrant or add a new vector database.
- Do not apply GraphRAG to the full corpus by default.
- Do not use retrieved popularity as evidence truth.
- Do not expose restricted NEXUS material through a broader query context.
- Do not ship a change that only improves an LLM judge while degrading deterministic retrieval metrics.

## Implementation sequence

1. Freeze real query samples and label relevance/support with domain reviewers.
2. Reproduce the baseline using the production-like index and fixed seeds/config.
3. Add sparse retrieval behind a flag.
4. Benchmark fusion variants and temporal/sensitivity filters.
5. Add bounded reranking only if the fusion baseline leaves a material gap.
6. Pilot selective graph retrieval on the global/multi-hop subset only.
7. Test abstention and permission boundaries adversarially.
8. Shadow production queries with redacted IDs and compare offline; never log raw PII queries.

## Golden set requirements

At least 200 queries, including:

- exact regulation number and Indonesian phrase;
- English paraphrase of Indonesian source text;
- “what was valid on date X?”;
- superseded and contradictory claims;
- same name/different entity;
- global pattern across multiple sources;
- question whose answer is absent;
- query requiring red data while caller has only public scope;
- typo, acronym, and transliteration cases;
- fresh event not yet broadly linked.

Labels must distinguish document relevance, evidence support, temporal correctness, and answerability.

## Tests and exit criteria

- Unit tests for sparse normalization, RRF, filters, permission checks, and deterministic trace.
- Integration tests against an isolated Qdrant collection or fixture.
- Regression test proving dense-vector model and dimension unchanged.
- Adversarial tests for sensitive filter bypass and prompt/query injection.
- Load test for p95 and bounded rerank cost.

Before inspecting candidate results, materialize canonical `MetricProfile` objects with the frozen dataset hash, exact numerator/denominator, minimum sample, subgroups, paired estimator, 95% paired-bootstrap confidence method, exclusions, missing-data rule, cost/latency guardrails, and these exact decision thresholds:

- overall nDCG@10 relative improvement is at least 0.12 and its 95% confidence interval lower bound is greater than 0;
- supported-answer rate relative improvement is at least 0.12 and its 95% confidence interval lower bound is greater than 0;
- no-answer precision and temporal correctness each regress by no more than 0.01 absolute;
- p95 latency and per-query cost are each no more than 2.00 times baseline;
- if graph retrieval is included, global/multi-hop nDCG@10 relative improvement is at least 0.17, its confidence-interval lower bound is greater than 0, and ordinary-query nDCG@10 regresses by no more than 0.01 absolute.

The overall held-out floor is 200 independently labeled queries, with at least 30 eligible queries in every subgroup used to pass a gate. Candidate measurements are written as immutable `MetricResult` objects bound to the exact profile hash. An unmet floor, unavailable denominator, expired profile, incomplete window, or failed mandatory guardrail yields `insufficient_evidence` or failure and leaves the current dense retriever canonical. Thresholds are never selected from a range after results are visible.

## Shadow, canary, and rollback

Shadow the new retriever beside the existing one and store only sanitized traces. Canary a small internal reader cohort behind a flag. Rollback switches readers to the current dense path; additive sparse vectors/indexes may remain inert for audit and later evaluation.

## Reviewer handoff

Provide the frozen dataset, labeling instructions, baseline and candidate traces, metric confidence intervals, latency/cost distributions, permission-boundary tests, and exact proof that the canonical dense embedding did not change.
