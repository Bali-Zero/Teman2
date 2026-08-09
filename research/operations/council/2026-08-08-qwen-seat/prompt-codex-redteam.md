---
adversarial_review: exempt-council-artifact
---

Independent correctness review (red-team chair). A Qwen Code session produced a document
at:

/Users/balizero/nuzantara/.worktrees/ops-qwen-seat-review/research/operations/2026-08-08-qwen-code-seat-integration-and-system-review.md

Read that file. It contains (1) a strengths/weaknesses analysis of the Nuzantara system
and (2) a proposed seat configuration for the Qwen Code agent itself, with open questions
Q1-Q4 in section 2.5 and a meta-pattern thesis in section 1.4.

Your job: find the flaw; default to defective. Specifically:

1. VERIFY THE EVIDENCE. The document cites repo facts (file paths, counts, CI gates,
   memory entries, a .claude-vs-.agents skill drift in section W2, probe results in 3.0).
   You have read-only access to this repository checkout. Re-check at least 5 load-bearing
   claims against disk (e.g. the two SKILL.md copies, the ledger files, the scripts it
   names). Report each checked claim as CONFIRMED or REFUTED with what you ran.
2. Attack the seat design: where could a `qwen` seat harm the organism (security,
   cost, quota, doctrine conflicts, probe-traps, PII path)?
3. Rule on Q1-Q4 (section 2.5): your recommendation per question.
4. Identify any claim in sections 1.2/1.3 that is exaggerated, unsupported, or stale.

Do not modify any file. Output format (markdown):
- VERDICT: PASS / PASS-WITH-FINDINGS / FAIL, one-line rationale
- EVIDENCE CHECKS: the >=5 claims you re-verified, CONFIRMED/REFUTED + command used
- FINDINGS: numbered, severity P0/P1/P2, each falsifiable
- Q1-Q4 RULINGS
