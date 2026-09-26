# S13-P2 — nb-ground-truth-protocol

> **Status**: PROPOSED (S13 evolution cycle, 2026-06-02). Draft only — Antonello approves graduation.
> **Kind**: shared-protocol · **Priority**: P1
> **Adversarial verdict**: 🔧 REVISE — right gap, wrong artifact (see revised proposal)

## Problem

5 NB-consumer agents duplicate the domain->NB routing table and NONE implements the freshness-check (02-patterns#6 PARTIAL). Stale NB source (e.g. superseded Permenkumham) returns confidently-wrong ground truth.

## Proposal (as originally drafted)

One skill: domain->NB routing map (single source of truth, currently copy-pasted), citation-verbatim extraction shape, AND the missing freshness-check (compare NB source last-ingest date vs regulation decree date; flag stale). Respects WR3 Contract 2 (only brief-interpreter CALLS NB; skill is shared reference, not a caller).

## Agents served

- wr2-brief-interpreter
- wr3-brief-interpreter
- nb-curator
- deep-researcher
- regulatory-watcher

## Evidence

02-patterns#6 PARTIAL; audit_subagent_nb_mcp_isolation_2026_05_20 (Contract 2)

## Cross-vendor adversarial review

- **DeepSeek V4 Pro** → `KILL`: Freshness check belongs at retrieval, not in a consumer-side skill. Routing table should be a config file, not a skill loaded by five agents.
- **Codex GPT-5.5** → `REVISE`: Freshness check is real, but sharing an NB protocol across callers risks eroding WR3 Contract 2. Split routing/freshness metadata from call authority; only approved interpreters should load callable NB procedures.
- **Converged** → `REVISE`

## Disposition (post-adversarial)

**REVISE / SPLIT.** Preserve WR3 Contract 2. Split into (a) routing+freshness _metadata_ — a config file + retrieval-side freshness check, loadable by anyone as reference; (b) NB _call-authority_ — only `wr3-brief-interpreter` (WR3) / `wr2-brief-interpreter` (WR2) hold callable NB procedures. A single shared 'NB protocol' skill that any agent loads would erode Contract 2.
