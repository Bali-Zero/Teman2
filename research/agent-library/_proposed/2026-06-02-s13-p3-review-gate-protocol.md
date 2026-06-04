# S13-P3 — review-gate-protocol

> **Status**: PROPOSED (S13 evolution cycle, 2026-06-02). Draft only — Antonello approves graduation.
> **Kind**: shared-protocol · **Priority**: P2
> **Adversarial verdict**: ❌ KILLED by adversaries — documented, NOT graduated

## Problem

5 review-gate agents re-implement bounded-iteration cap (≤3) + binary-verdict + retry-feedback-JSON shape independently. Cap-3 lesson lives only in a memory file, not enforced in the gate agents.

## Proposal (as originally drafted)

One skill: standard verdict JSON schema {verdict:PASS|FAIL, findings:[{severity,one_line,evidence_ref}], retry_feedback}, the ≤3-iteration cap rule, and the anti-self-approval invariant (reviewer != author). Each gate keeps its OWN rubric; only the protocol/shape is shared.

## Agents served

- devils-advocate
- spalla-review
- wr2-critic
- wr3-critic
- wr3-pre-render-gatekeeper

## Evidence

02-patterns#7; 03-lessons#4 (devils-advocate cap 3)

## Cross-vendor adversarial review

- **DeepSeek V4 Pro** → `KILL`: Iteration cap is an orchestrator concern, not a gate-agent protocol. Embedding it in each reviewer would conflict with the existing critic loop and lock in an anti-pattern.
- **Codex GPT-5.5** → `KILL`: This abstracts too little and risks homogenizing intentionally distinct reviewers. JSON shape and cap-3 can live in agent templates or tests; a shared review skill adds coupling without fixing rubric quality.
- **Converged** → `KILL`

## Disposition (post-adversarial)

**KILLED (unanimous).** A shared review-gate skill homogenizes intentionally-distinct reviewers (adversarial vs constructive vs domain-rubric vs pre-spend) and adds coupling without improving rubric quality. The only shareable bit — ≤3-iteration cap + verdict-JSON shape — belongs in the **S13-P7 contract-test harness** (assert reviewer≠author, assert cap honored), NOT a loaded skill.
