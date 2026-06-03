# S13-P5 — orchestrator-contract-protocol

> **Status**: PROPOSED (S13 evolution cycle, 2026-06-02). Draft only — Antonello approves graduation.
> **Kind**: shared-protocol · **Priority**: P3
> **Adversarial verdict**: ⚖️ SPLIT verdict — downgraded per Codex (contract-test, not skill)

## Problem

wr2-design-architect and wr3-design-architect copy-paste the 3-contracts enforcement (fan-out, NB-ground-truth, no-silent-asset-reuse) + Voyager-graduation prose. Drift risk: a fix to one orchestrator's contract logic doesn't reach the other.

## Proposal (as originally drafted)

One skill encoding the 3 universal orchestrator contracts + critic-gate invariant + Voyager graduation criteria. Both orchestrators load it; pipeline-specific steps stay in each agent.

## Agents served

- wr2-design-architect
- wr3-design-architect

## Evidence

OVL-4; both agent descriptions verbatim-share contract language

## Cross-vendor adversarial review

- **DeepSeek V4 Pro** → `KEEP`: Orchestrator contract prose is copy-pasted; a single protocol skill prevents drift and centralizes the three universal contracts + Voyager graduation criteria.
- **Codex GPT-5.5** → `KILL`: Orchestrator contracts are load-bearing pipeline prose. A shared skill could blur WR2/WR3 differences and create false universality; enforce drift with contract tests or inventory checks instead.
- **Converged** → `SPLIT`

## Disposition (post-adversarial)

**DOWNGRADE (Codex KILL over DeepSeek KEEP).** Orchestrator contracts are load-bearing pipeline prose; a shared skill blurs WR2/WR3 differences and creates false universality. Enforce drift with **contract tests** (S13-P7 lane), not a shared skill.
