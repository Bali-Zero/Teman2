# S13-P4 — metrics-analyst-protocol

> **Status**: PROPOSED (S13 evolution cycle, 2026-06-02). Draft only — Antonello approves graduation.
> **Kind**: shared-protocol · **Priority**: P2
> **Adversarial verdict**: 🔧 REVISE — right gap, wrong artifact (see revised proposal)

## Problem

wr2-ig-metrics-analyst and wr3-yt-metrics-analyst are twins with identical insufficient-data starvation; the pre-flight-gate + amendment-proposal shape is duplicated. Both loops have produced ZERO real amendments.

## Proposal (as originally drafted)

One skill: insufficient-data pre-flight gate (threshold check before LLM spend — already correct), amendment-proposal markdown schema, attribute-correlation method. Surface-specific thresholds (IG=10, YT=3) as parameters. ALSO documents the upstream unblock dependency (publish volume) so the starvation is visible, not silent.

## Agents served

- wr2-ig-metrics-analyst
- wr3-yt-metrics-analyst

## Evidence

5 insufficient-data stubs; OVL-3

## Cross-vendor adversarial review

- **DeepSeek V4 Pro** → `KEEP`: Identical twin metrics analysts with same starvation pattern; a shared protocol with parameterized thresholds consolidates duplication and makes data-gap visible.
- **Codex GPT-5.5** → `REVISE`: Starvation is upstream, not analyst logic. Keep a visible no-data gate and shared output schema, but do not build a correlation protocol until enough IG/YT observations exist to validate it.
- **Converged** → `REVISE`

## Disposition (post-adversarial)

**REVISE.** Starvation is upstream (publish volume: 1/10 IG, 0/3 YT), not analyst logic. KEEP the visible no-data pre-flight gate + shared amendment-output schema. DEFER the correlation protocol until enough IG/YT observations exist to validate it. Document the upstream unblock dependency so the starvation stays visible, not silent.
