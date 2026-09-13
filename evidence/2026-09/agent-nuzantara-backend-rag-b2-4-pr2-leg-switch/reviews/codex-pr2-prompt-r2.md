ROUND 2 — verification of your round-1 cures on B2.4 PR-2 only. Read-only; modify nothing. The cures are defective until the code proves otherwise.

BUDGET DISCIPLINE: no stadio-zero, no memory/ledger/scar searches, no repo-wide grep, no pytest/linters (the Dux ran them: 3086 passed in one process, ruff clean). Read only what is named, once, then answer.

Your round-1 findings: (1) MAJOR migration 315 rollback fails once rows carry `support_judge_absent`; (2) MAJOR `has_visible_character` accepted U+FE0F / U+0301 alone; (3) MINOR V4 test did not assert the offer was never made.

Cures = commits 55bf33e999 and 4611d1f42f in worktree /Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-4-pr2-leg-switch (head 4611d1f42f). Diff of the cures only (9.5 KB):
/private/tmp/claude-501/-Users-nuzantara-nuzantara--worktrees-backend-rag-b2-4-judge-reach/5f34a6fa-f36b-48a6-ad4d-6b384d49b03a/scratchpad/pr2-cure-r1.diff
Declared deviation on (1): the rollback re-adds the narrow CHECK `NOT VALID` instead of remapping rows, because the rows are the I96-5 durable counter on a retained table (and a local guardrail forbids UPDATE in migration files). Judge whether NOT VALID leaves the rollback complete and the table consistent for later migrations/forward re-apply.

Hunt for: (a) the NOT VALID rollback failing, or breaking a re-apply of 315's forward block, or a later `VALIDATE CONSTRAINT` elsewhere; (b) the new L/N/P/S rule rejecting a real question the builder produces (any script, emoji-only questions like "👍?" pass via P, digits-only pass via N) or still accepting an invisible one; (c) the daemon-side parser sharing the rule (note: the daemon picks it up only at its next provisioning — say whether that ordering creates any release path); (d) the offer assertion passing for the wrong reason.

Output: first line `VERDICT: SHIP` / `VERDICT: FIX-FIRST` / `VERDICT: BLOCK`, then numbered findings with severity, file:line, scenario, minimal fix; mark UNSURE. No summary. Under 500 words.
