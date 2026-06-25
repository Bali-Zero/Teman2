---
date: 2026-06-24
domain: compliance
client_case: WR2 pipeline — fact-check grounding (REV 2, post-panel + DB audit)
sources:
  - wr2_fact_checker.py:247 _extract_source_text (Pro) — reads research_json + brief_json + council_debate_json; brief_json is "the ACTUAL research the draft generator consumed"; research_json "the production pipeline never populates (only probes/smoke)"
  - wr2_fact_checker.py:_has_external_truth (Pro) — returns True if _find_law_citations() finds ANY law in research|brief|council; else needs non-trivial leaf text
  - wr2_topic_selector.py:393/604 — enrichment comes from Fly staging, which returns {}
  - wr2_draft_generator.py:366 _build_enriched_brief reads enrichment.the_facts/... — CONSUMER exists end-to-end
  - scripts/warroom_step2_briefer.py (PR #1155, d6ac67f78) — PRODUCER exists, injects law citations into enrichment.the_facts. NOT wired.
  - DB audit 2026-06-24 (12 live drafts): enrichment={} on 12/12, LAW_in_brief=no on 12/12, fact_check=degraded on the 5 with law-claims.
  - LIVE RAG probe 2026-06-24 (3 domains): /api/v1/visa-oracle/chat returns prose + title-only sources, NO extractable PP/PMK/UU N/YYYY. The cron-safe HTTP path cannot currently supply citations.
---

# SPEC — WR2 fact-check grounding (REV 2): ARM the existing engine, don't build a research step

## What REV 1 got wrong (corrected by reading the parser + the DB)
REV 1 proposed a new research_json column. Two facts kill that:
1. The fact-checker keys off brief_json.enrichment, NOT research_json ("the production pipeline never populates" it).
2. The grounding producer already exists and was merged: warroom_step2_briefer.py (#1155) injects verbatim law citations into enrichment.the_facts via _inject_rails_into_facts (deterministic, zero-LLM).

This is NOT a missing phase. It is an UNARMED phase — superscar #2.

## Root cause (measured 2026-06-24, 12 live drafts)
brief_json.enrichment == {} on 12/12 → no rails → no law text → _has_external_truth=False → degraded (correct given empty input).

## STATUS (verified live, blocking)
The implementation (scripts/wr2_grounding.py + topic-selector hook) is BUILT, unit-tested 5/5, and shipped FLAG-OFF (WR2_RESEARCH_STEP_ENABLED). But the only cron-safe citation source — the Fly RAG HTTP endpoint — returns prose + title-only sources, NOT extractable citations (verified 3 domains). So the hook is INERT: it degrades to enrichment={} on real queries. It activates the day a real citation source is wired.

## Three viable citation sources (decision pending)
- (a) Materialize an nb_brief file (arm wr2-brief-interpreter to write regulatory_citations_verbatim before the cron). The designed ground-truth path.
- (b) Enrich the KB vector payload with reg-numbers + expose a raw-chunk endpoint. Touches backend-rag (L3).
- (c) Accept 'degraded' (content is accurate; only the 'verified' badge is missing). Zero cost.

## Panel 4-LLM (3/3 GO-WITH-CONDITIONS) — all integrated in the module
C1 strict timeout (8s) · C2 read-parser-first (done) · C3 enrich-prompt (satisfied by _build_enriched_brief) · C4 flag default-off + try/except · C5 PII-free query · C6 silent-degradation monitor (TODO when armed) · C7 no dep bloat (in-process, no backend-rag import).

## Out of scope
Fact-checker severity (correctly strict); dead research_json column; NB-MCP live (cron-incompatible); any client/PII.
