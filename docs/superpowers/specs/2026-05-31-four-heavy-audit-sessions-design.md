---
date: 2026-05-31
domain: operations
client_case: none
sources:
  - shared/escalations_pro.jsonl (4519 entries, all dlq_autopilot_escalation, 44-day span)
  - .claude/rules/cicatrix-scars.md (9 STRUCTURAL + 1 PENDING P1 open)
  - ~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist (167 plist, 77 KeepAlive, 3 reboot-bombs)
  - apps/evaluator/nlm_nb{2..10}_claims.jsonl (~1204 NB ground-truth claims already extracted)
  - apps/backend-rag/data/evaluation/search_quality_golden.json + scripts/evaluate_search_quality.py
  - ~/.claude/agents/{client-case-quote-generator,yield-optimizer,devils-advocate}.md
author: Claude Opus 4.8 (1M context) + Antonello Siano
status: approved-design
---

# 4 Heavy Audit Sessions — Opus 4.8 max-effort, ~25% weekly quota

## Goal

Consume ~25% weekly Claude MAX quota in a few hours on **4 parallel heavy audit sessions**,
one per impact axis chosen by Antonello, each producing **empirical truth** about the real
state of the system (numbers measured, not estimated) **plus L2-shipped safe fixes**.

Form chosen: **audit + empirical truth**. Authority: **full L2 autonomy** (within AUTONOMOUS_OPS.md
guardrails). RAG ground-truth metric: **NotebookLM as oracle**. Business lever: **decision quality
on NEW clients**. Audit→action policy: **report + safe fixes shipped L2** (two-phase, see below).
Orchestration: **4 self-contained copy-paste prompts + 1 workflow orchestrator**.

## The 4 targets (one per axis)

| # | Axis | Target | Why Opus-grade (not grunt work) |
|---|------|--------|--------------------------------|
| S1 | Organism reliability | "The nervous system lies" — empirical audit of all 167 plist + DLQ + escalations + state-bridge: which alerts are real, which are structural noise, how many jobs are dead-but-think-they-live | 167 surfaces × cross-check launchctl↔disk↔log↔PG. Reasoning over self-contradicting distributed state. |
| S2 | RAG truth | "How accurate is Zantara really" — bipolar verifier at scale: ~1204 already-extracted NB claims → generate questions → ask Zantara prod → measure divergence vs NB-oracle per domain (visa/tax/KBLI/property) | Building the *judgment* over divergence: when Zantara and NB disagree, who is right? Opus arbitrates thousands of regulatory comparisons. |
| S3 | Business lever | "Does the quote hold up in court?" — red-team the `client-case-quote-generator` pipeline on N real client cases: wrong KBLI? tax miscalc? impossible timeline? price off PricingTool? | The only organ producing signed client deliverables. One error = money/reputation. Opus devil's-advocate on legal-fiscal output. |
| S4 | Structural debt | "The attack & incident surface" — unified audit of the 9 open STRUCTURAL scars + 170 branches + P1 `rolsuper=t` + worktree/deploy desync: what's still true, what already exploded, what will explode | Correlating 9 open scars with current state needs the whole system history in context. 1M Opus = right tool. |

## Common backbone (every prompt enforces this)

1. **ROLE + FOUNDING LAW** — "empirical auditor. Errare è umano, allucinare è diabolico. Never cite a tool's output without running it THIS turn." Anchors anti-hallucination + SYMBIOSIS Law 2 (OSINT stays local) + Law 7 (numbers first).
2. **MANDATORY WORKTREE** — `python scripts/agent_start.py --lane <X> --task-id <Y>` → cd → work there. Never the main checkout.
3. **PHASE A — MEASURE & FREEZE (read-only on prod, ABSOLUTE)** — count with double independent cross-check, write `research/operations/2026-05-31-<slug>-FROZEN.json` (the truth number). Zero Write/Edit/mutation on prod in Phase A.
4. **PHASE B — ACT ON SAFE FIXES (after the freeze)** — explicit "safe fix" vs "needs-Antonello" criterion; per safe fix: branch + test + PR + L2 merge if green; explicit never-touch list (off-limits files); re-measure ONLY the delta, append to report.
5. **CANONICAL OUTPUT** — `research/operations/2026-05-31-<slug>.md` with frontmatter + real green/yellow/red table + "shipped fixes" vs "fixes awaiting you" + 1-line to MEMORY.md.
6. **EXPLICIT ANTI-PATTERNS** — no estimated numbers passed as measured; no celebration without empirical derivation; no fix that mutates the count before freeze; iteration cap, no rabbit-hole.
7. **DEFINITION OF DONE** — verifiable checklist, not "I'm done".

### Cross-cutting gate (S2 + S3 only)
Before declaring an NB claim "wrong" or a quote "flawed", the finding **must** pass the
adversarial panel (`devils-advocate` subagent / DeepSeek V4 Pro). No single-LLM legal verdict —
that is failure #9 ("ethical collapse") in the Air-era failure taxonomy.

## Why two-phase (A freeze / B act) is non-negotiable

An audit that modifies what it measures falsifies its own result. If you fix a plist mid-count,
the final "red" number is no longer what you found. Phase A freezes the truth in a timestamped
file under absolute prod-read-only; Phase B acts on safe fixes *after* the freeze and re-measures
only the delta. The report always reads "how it was + what I changed", never a confused hybrid.

## Safe-fix vs needs-Antonello criterion (shared)

**SAFE (ship L2):** additive/idempotent, reversible in one command, no schema change, no secret
rotation, no off-limits file (`zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`),
covered by a test, blast radius ≤ 1 organ. Examples: add KeepAlive to a daemon plist; bonifica
a stale escalation file; fix a single wrong NB claim with citation; correct a quote template
typo.

**NEEDS-ANTONELLO (report only):** `rolsuper=t` demotion (W38 — already spec'd, awaiting sign-off);
anything touching auth/billing/pricing logic; deleting branches (except merged-deletable);
migrations; cross-organ changes; any legal-verdict-driven change that the panel did not
unanimously confirm.

## Deliverables of this brainstorming session

- 4 copy-paste self-contained prompts: `~/Desktop/nuzantara-audit-prompts-2026-05-31/S{1..4}-*.md`
- 1 orchestrator doc: `~/Desktop/nuzantara-audit-prompts-2026-05-31/orchestrator.md` (Modo A manual 4-window + Modo B Workflow fan-out + aggregated report)
- This design doc (committed)

## Out of scope

- Actually running the 4 sessions (Antonello launches them)
- Any fix that the audits surface (those happen inside the sessions, Phase B)
- W38 rolsuper demotion (explicitly needs-Antonello)
