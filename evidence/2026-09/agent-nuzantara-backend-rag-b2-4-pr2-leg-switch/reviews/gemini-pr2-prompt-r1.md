You are the second reader (adversarial) on B2.4 PR-2 of a WhatsApp answer pipeline. Read-only. Assume the change is defective until the code proves otherwise. Be concrete: every finding must cite a file and line you actually opened and a failure scenario you can trace in that code. Do not report findings you cannot trace (the previous round of this seat reported four claims that were refuted on disk).

Worktree: /Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-4-pr2-leg-switch (head 4611d1f42f, base origin/main b8162521b5).
Production diff (31 KB): /private/tmp/claude-501/-Users-nuzantara-nuzantara--worktrees-backend-rag-b2-4-judge-reach/5f34a6fa-f36b-48a6-ad4d-6b384d49b03a/scratchpad/pr2-production-v2.diff
Contract: /Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-4-judge-reach/evidence/2026-09/agent-nuzantara-backend-rag-b2-4-judge-reach-50b0c640/B2-4-design.md sections 1.1-1.5.

What PR-2 does: the Fly package build stops calling the support judge; the leg offers every job to the Pro broker daemon (which since PR-1 runs a majority-of-3 Codex support judge and returns an HMAC envelope bound to package_hash); after consume, the leg decodes the envelope: None -> fall-off `support_judge_absent:no_verdict` (never release; this covers an OLD daemon returning raw text); SUPPORTED -> release the envelope's answer through the existing finalizer; NOT_SUPPORTED/UNKNOWN -> terminal stub with the precomputed unsupported evidence pair; wait FAILED with error_class support_judge_unavailable -> `support_judge_absent:unavailable`. A package whose last user turn has no visible character is stubbed before the offer. Migration 315 widens the fall-off CHECK.

Rulings: the fail-closed gate stays (no text leaves without an authenticated SUPPORTED verdict for this package); an absent judge must be loud; no ungrounded answer may ship.

Hunt for: any release path without an authenticated SUPPORTED verdict; the envelope answer skipping restore_text/finalize/DLP/price/canary checks; wrong evidence carrier on stubs; builder still judging or scores changed; migration errors; logs carrying message text or keys; tests that pass for the wrong reason.

Output: first line `VERDICT: SHIP` / `VERDICT: FIX-FIRST` / `VERDICT: BLOCK`, then numbered findings (BLOCKER/MAJOR/MINOR), file:line, traced scenario, minimal fix. Under 700 words.
