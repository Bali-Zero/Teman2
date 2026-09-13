You are an adversarial reviewer (default: the change is defective until the code proves otherwise). Read-only. Do not modify files.

Repository worktree: /Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-4-judge-reach
Frozen candidate: the diff of the working tree against commit 77af6c7ada8e1fc3de2f50ba3e64a78e330f9adf (run `git -C <worktree> diff 77af6c7ada -- apps scripts infra` and `git -C <worktree> status --short` yourself; read the new untracked files too).

Contract you judge against (read both first):

- evidence/2026-09/agent-nuzantara-backend-rag-b2-4-judge-reach-50b0c640/B2-4-design.md
- evidence/2026-09/agent-nuzantara-backend-rag-b2-4-judge-reach-50b0c640/PR-1-build-spec.md

Context: WhatsApp answers must never release unless an I26 support judge (Codex seat, RUBRIC, 3 repetitions, strict majority, split = NOT_SUPPORTED) ruled SUPPORTED. The judge was unreachable in production (it ran inside a Fly container with no codex/ollama). PR-1 moves the judge into the Pro daemon (`wa_codex_daemon.py`) which claims broker jobs, and returns an HMAC envelope (`wa_completion_envelope.py`) bound to package_hash; an absent judge is error_class `support_judge_unavailable`. PR-1 is inert on Fly; PR-2 (not in this diff) will make the leg require the envelope.

Hunt specifically for:

1. Any path where the daemon generates or envelopes an answer without a SUPPORTED strict majority, or envelopes UNAVAILABLE.
2. Envelope forgery or confusion: MAC computed over a non-canonical or attacker-influenced form, fields trusted before MAC verification, missing constant-time compare, key derivation mistakes, a way for model output (the `answer` string) to alter the outer structure, replay across package_hash, decode that raises instead of returning None.
3. The judge input derived from the wire differs from what `wa_package_builder.build_context_package` used (history[-1].content, "\n\n".join(chunk.text)) — any divergence in empty-history/zero-chunk cases.
4. Budget/timeout: judge + generation exceeding the claim budget, negative/zero timeouts passed to `CodexExecClient.generate`, orphaned subprocesses, exec_ms/last_exec_ms wrong.
5. Size caps measured on the raw text instead of the envelope actually sent; NUL handling.
6. Broker vocabulary: `support_judge_unavailable` accepted by router AND service, fold semantics unchanged, any vocabulary mirror (scripts, sentinels, tests, docs) left stale.
7. Pro runtime tree: provisioning installs every module the daemon now imports (transitively: `_support_signal` -> `codex_exec_client`), empty `__init__.py` markers for new packages, no heavy import reachable; declared-pairs entries correct.
8. PII / secret: any log line that could carry query/context/answer text or the key; the key reaching the codex child env.
9. Tests that pass for the wrong reason (fakes that never exercise the real code path, assertions on mocks only).

Output format: first line `VERDICT: SHIP` or `VERDICT: FIX-FIRST` or `VERDICT: BLOCK`. Then numbered findings, each with severity (BLOCKER/MAJOR/MINOR), file:line, the concrete failure scenario, and the minimal fix. Mark anything you are unsure about as UNSURE. No praise, no summary of the change.
