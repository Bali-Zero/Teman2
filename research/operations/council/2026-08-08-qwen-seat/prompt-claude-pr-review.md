---
adversarial_review: exempt-council-artifact
---

You are a Claude session convened by the qwen-cloud-code seat (external agent, author of the
work under review) to perform an adversarial PR review. generator≠grader: you are the
grader. You have full read access; MODIFY NOTHING (no edits, no comments posted, no merge).

# Subject
PR #3884, repo Bali-Zero/Teman2, branch agent/air-m5/ops/qwen-seat-review, checked out at:
/Users/balizero/nuzantara/.worktrees/ops-qwen-seat-review
Two commits: (1) research/operations/2026-08-08-qwen-code-seat-integration-and-system-review.md
(v4, already gate-reviewed by Fable 5 on 2026-08-08: SHIP-AFTER-FIXES, fixes applied) +
the council record under research/operations/council/2026-08-08-qwen-seat/; (2) scripts/
arsenal_probe.py registration of a new seat `qwen-cloud-code` + scripts/qwen-cloud-code.sh
wrapper. Read the diff: git -C /Users/balizero/nuzantara/.worktrees/ops-qwen-seat-review diff origin/main...HEAD

# OPERATOR RULING (Zero, 2026-08-09 — binding, verbatim)
1. "non ruoto, basta" — the Qwen runtime credential will NOT be rotated; the 0600
   mitigation stands as forward-fix. CONSEQUENCE: the keychain-based arming gate in the
   probe (service qwen-cloud-code-token) can never become true as designed. Adjudicate:
   should the gate be adapted (e.g. gate on the existing credential present with
   hardened perms), or should the seat stay dormant until further notice? Recommend ONE.
2. You (Claude) own this review.
3. After your review verdict, if and only if it is APPROVE or APPROVE-WITH-MINOR-FIXES,
   you will be asked in a SEPARATE follow-up dispatch to carry merge → fleet sync → test.
   Do NOT merge in this dispatch.

# Review checklist (be adversarial, not hostile)
1. Correctness of the probe registration: does it follow the file's conventions
   (status taxonomy, evidence hygiene/secret scrubbing, timeout mandate, machine-scoping)?
   Run: python3 scripts/arsenal_probe.py --selftest (from the worktree) and one live
   `--seats qwen-cloud-code --table` run; judge the actual output.
2. The wrapper scripts/qwen-cloud-code.sh: Legge-5 verb scan complete? Any bypass
   (arg splitting, flags that re-enable publishing)? Env hygiene?
3. Security: any secret, PII or credential material in the diff (Law 2 / Legge 5)?
   Does the diff touch off-limits files (zantara_core.py, fly.toml, .env*, alembic/env.py,
   curated datasets, WR2 queue JSONs)?
4. Doctrine: AGENTS.md external-agent contract respected? R1 gate markers present
   (adversarial_review frontmatter)? Commit messages conventional?
5. The v4 document: you do not re-gate it (Fable did), but flag anything in it that the
   operator ruling above now contradicts.

# Output format (markdown, this is your whole reply)
- VERDICT: APPROVE / APPROVE-WITH-MINOR-FIXES / REQUEST-CHANGES, one-line rationale
- EVIDENCE: what you ran and what it printed (selftest result, live probe output)
- FINDINGS: numbered, severity P0/P1/P2, each with file:line and the concrete fix
- RULING-1 RECOMMENDATION: your one recommended adaptation of the arming gate
- CHECKLIST RESULTS: one line per checklist item
