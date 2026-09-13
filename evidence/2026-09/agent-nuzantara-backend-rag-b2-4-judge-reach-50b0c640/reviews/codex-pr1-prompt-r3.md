ROUND 3 — verification of the round-2 cure only (fix-of-a-fix depth 1). You are an adversarial reviewer: the cure is defective until the code proves otherwise. Read-only; modify nothing.

BUDGET DISCIPLINE (mandatory): no stadio-zero, no memory/ledger/scar searches, no repo-wide grep, no pytest or linters (the Dux ran them: 2723 passed across rag/agentic + integrations + daemon + broker router in ONE process, ruff check clean). Read ONLY the files below, each once, then answer.

Your round-2 finding (MAJOR): `support_inputs_from_wire` accepted `history=[]` as `query=""`, so a question-less claimed package could be judged on context alone.

Cure = commit 025fc275e1 on top of a9811b2054 in worktree /Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-4-judge-reach. Its full diff (8.6 KB) is at:
/private/tmp/claude-501/-Users-nuzantara-nuzantara--worktrees-backend-rag-b2-4-judge-reach/5f34a6fa-f36b-48a6-ad4d-6b384d49b03a/scratchpad/pr1-cure-r2.diff
Context you may open only if the diff is not enough:

- apps/backend-rag/backend/services/rag/agentic/_support_signal.py lines 440-510
- apps/backend-rag/backend/services/integrations/wa_package_builder.py function `_sanitize_history` only
- apps/backend-rag/backend/services/integrations/wa_codex_daemon.py: only the call site of `support_inputs_from_wire` and its except branch

The cure also contains a test-isolation change: `TestImportIsFree` no longer `importlib.reload`s the shared module (the reload rebound `SupportVerdict`, turning 21 daemon tests red by run order); it executes a fresh copy under a private module name registered via monkeypatch for the test's lifetime.

Hunt for: (1) the cure still lets a package with no real question reach the judge or generation (e.g. last turn not role=user, whitespace-only variants, non-str content) — mark UNSURE unless the real builder can produce it; (2) the cure rejects a package the REAL builder produces (false UNAVAILABLE on legitimate traffic — this is the worse failure, read `_sanitize_history`); (3) the ValueError path in the daemon releasing anything but error_class support_judge_unavailable; (4) the import-probe test passing for the wrong reason (e.g. no longer executing module top-level code under the blocked connect) or leaking the probe module into later tests.

Output format: first line `VERDICT: SHIP` or `VERDICT: FIX-FIRST` or `VERDICT: BLOCK`. Then numbered findings with severity (BLOCKER/MAJOR/MINOR), file:line, concrete failure scenario, minimal fix; mark UNSURE where unsure. No summary, no praise. Under 600 words.
