ROUND 2 — the round-1 run of this same review ran out of context before a verdict because it explored far beyond the change. This round is deliberately narrow. You are an adversarial reviewer: the change is defective until the code proves otherwise. Read-only; modify nothing.

BUDGET DISCIPLINE (mandatory): do NOT run stadio-zero, memory/ledger/scar searches, or any repo-wide grep; do NOT run pytest or linters (the Dux already ran them: 291 passed, ruff check clean); do NOT read PENDING-ARMS, CLAUDE.md, skills or other evidence directories. Read ONLY the files below, each once, and then answer.

Contract (short): `evidence/2026-09/agent-nuzantara-backend-rag-b2-4-judge-reach-50b0c640/B2-4-design.md` sections 1.1-1.5 only.

Candidate = commit a9811b2054 in worktree /Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-4-judge-reach, base 77af6c7ada. The production-code diff (30 KB) is at:
/private/tmp/claude-501/-Users-nuzantara-nuzantara/41da1564-0c18-4127-bd3f-965416164792/scratchpad/pr1-production.diff
Full current sources you may open for context (only if the diff hunk is not enough):

- apps/backend-rag/backend/services/integrations/wa_completion_envelope.py
- apps/backend-rag/backend/services/integrations/wa_codex_daemon.py (lines 440-730 only)
- apps/backend-rag/backend/services/rag/agentic/_support_signal.py (lines 160-230 and 430-495 only)
  Tests (skim only the names and the assertions of the new classes): apps/backend-rag/backend/tests/unit/services/test_wa_codex_daemon.py class TestSupportJudgeStage; apps/backend-rag/backend/tests/unit/services/integrations/test_wa_completion_envelope.py.

What PR-1 does: the Pro daemon, after claiming a broker job, derives (query, context) from the package wire, runs CodexSupportJudge (3 concurrent reps on the daemon's own CodexExecClient, model terra, timeout min(20 s, 0.45*budget)), takes the strict majority; UNAVAILABLE -> error_class support_judge_unavailable; NOT_SUPPORTED/UNKNOWN -> HMAC envelope answer=null; SUPPORTED -> generate with remaining budget, envelope carries the answer. Envelope: canonical JSON, HMAC-SHA256 under HMAC(WA_BROKER_KEY, "wa-completion-envelope/v1"), bound to package_hash, decode never raises. PR-2 (not here) makes the Fly leg require the envelope.

Hunt for, in order: (1) an answer enveloped without a SUPPORTED strict majority, or UNAVAILABLE enveloped; (2) MAC/canonicalization/key-derivation/compare weaknesses, fields trusted before MAC check, decode that can raise; (3) judge input differs from builder formula history[-1].content / "\n\n".join(chunk.text); (4) budget arithmetic: zero/negative timeout reaching CodexExecClient.generate, judge+generation exceeding budget, exec_ms wrong; (5) size caps on wrong bytes; (6) provisioning missing a transitively imported module; (7) any log carrying query/context/answer text or the key; (8) tests passing for the wrong reason.

Output format: first line `VERDICT: SHIP` or `VERDICT: FIX-FIRST` or `VERDICT: BLOCK`. Then numbered findings with severity (BLOCKER/MAJOR/MINOR), file:line, concrete failure scenario, minimal fix; mark UNSURE where unsure. No summary, no praise. Keep the whole answer under 900 words.
