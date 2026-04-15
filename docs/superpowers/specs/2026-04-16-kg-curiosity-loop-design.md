# KG Curiosity Loop — Design Spec

**Date:** 2026-04-16
**Author:** Claude Opus 4.6 (Air)
**Status:** Implemented, pending first real cycle
**SYMBIOSIS Pilastro:** 6 (Curiosità)

## Problem

Gap detector v1 finds 56 gap topics across 7 domains (all 100% GAP as of T0).
No automated pipeline exists to research these gaps, validate evidence, and
propose KG enrichment. The gap-to-knowledge cycle is broken.

## Solution: Curiosity Loop v1

Autonomous pipeline: **scan → prioritize → dispatch → grade → propose**

### Architecture

```
coverage_matrix.json (7 domains × 8 topics)
    ↓
CuriosityOrchestrator.run_cycle(max_gaps=20)
    ↓
_load_gaps() → _prioritize() → classify_tier()
    ↓
┌────────────────┬──────────────────┬─────────────────┐
│ Tier 1 Simple  │ Tier 2 Medium    │ Tier 3 Complex  │
│ Ollama qwen3.5 │ HyDE expansion   │ Redis deep      │
│ + template     │ + synthesis      │ research queue   │
└────────────────┴──────────────────┴─────────────────┘
    ↓
CuriosityGrader.grade()
  >= 0.60 → PROPOSE
  0.15-0.60 → MORE_RESEARCH
  < 0.15 → ABSTAIN
    ↓
kg_proposals table (NEVER kg_nodes/kg_edges directly)
    ↓
Zero reviews via kg-propose CLI → apply/reject
    ↓
kg_nodes/kg_edges (only via apply_approved)
```

### Components

| Component | Path | Responsibility |
|-----------|------|----------------|
| Migration 108 | `backend/migrations/migration_108_kg_proposals.py` | kg_proposals table schema |
| Models | `curiosity/models.py` | GapTopic, ResearchEvidence, KGProposal, CycleResult |
| Orchestrator | `curiosity/orchestrator.py` | Pipeline orchestration, tier classification |
| CuriosityGrader | `curiosity/grader.py` | Evidence validation (substance+citations+confidence) |
| SimpleDispatcher | `curiosity/dispatchers/simple.py` | Ollama qwen3.5:9b research |
| MediumDispatcher | `curiosity/dispatchers/medium.py` | HyDE expansion + synthesis |
| ComplexDispatcher | `curiosity/dispatchers/complex.py` | Background Redis queue |
| ProposalStore | `curiosity/proposals.py` | PROPOSE-ONLY gateway + apply_approved |
| CLI | `curiosity/cli.py` | kg-propose list/show/apply/reject/stats |
| Cron | `scripts/gap_fill_autonomous.py` | Daily 04:30 WITA + Telegram report |

### Safety Invariants

1. **Propose-only**: Orchestrator NEVER writes to kg_nodes/kg_edges
2. **apply_approved()** is the ONLY path, requires status='approved'
3. **Dedup**: 7-day window, skip already-proposed gaps
4. **Blacklist**: 3+ rejections in 30 days → skip for 30 days
5. **Rate limit**: Max 20 gaps per cycle
6. **Expiry**: Pending proposals auto-expire after 14 days
7. **Audit**: Every apply/reject logged to audit.jsonl

### Grading Model

CuriosityGrader (not the RAG Self-RAG grader — adapted for curiosity):
- **Content substance** (50%): useful (>50 chars) + substantial (>100 chars) ratio
- **Citation quality** (30%): ratio of evidence with citations
- **Source confidence** (20%): average dispatcher confidence
- Thresholds: >= 0.60 propose, 0.15-0.60 more_research, < 0.15 abstain

### Tier Classification

| Criteria | Tier |
|----------|------|
| Critical domain + specific topic | Tier 1 (Simple) |
| Cross-domain keywords (vs, compared, conversion) | Tier 2 (Medium) |
| Broad topics (overview, complete guide) | Tier 2 (Medium) |
| Non-critical domains (editorial, lifestyle) | Tier 2 (Medium) |

### Tests (40 total)

- `test_grader.py`: 7 tests (scoring, thresholds, edge cases)
- `test_orchestrator.py`: 11 tests (cycle, prioritization, tier classification)
- `test_proposals_propose_only.py`: 8 tests (SACRED safety gate)
- `test_dispatchers.py`: 7 tests (all 3 tiers + graceful degradation)
- `test_safety_dedup_rate_limit.py`: 7 tests (rate limits, dedup, blacklist)

## T0 Baseline (2026-04-16)

- **Gap topics**: 56 (7 domains × 8 topics, all GAP)
- **KG density**: 2.247 (108,068 nodes, 242,827 edges)
- **Proposals**: 0 (first cycle pending)
- **Coverage health**: 0% (all domains at health_pct=0.0)
