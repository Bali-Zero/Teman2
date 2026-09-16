# Adversarial review — B2.5 PR-3 "one greeting authority"

You are an adversarial reviewer. Default to defective. Read-only. Do not print phone numbers or message ids.

Repository: the current directory (a git worktree). Candidate = `git diff origin/main...HEAD` (2 commits). Read the diff with git yourself; read surrounding code as needed.

## Mandate and measured defect

Production WhatsApp message `11.  Halo` looped through a 5-attempt retry ladder: `wa_greeting.match_greeting` returned None (the token `11` aborted the match) while `QueryPlanner` matched `\bhalo\b` → `QueryDomain.GREETING` → `wa_package_builder.build_context_package` raised `PackageUnbuildable("greeting_domain")`. Two detectors disagreed (guard over/under-match).
Ruling (d): ONE greeting authority for the WA leg (`wa_codex_leg.py`, calls `match_greeting` before the build) and the builder; a leading list ordinal does not change the classification.
Ruling C1: the builder's GENERAL fallback (planner says GREETING, `match_greeting` says no) must not reroute real questions; only greeting-classified texts may change domain.
Invariants: `query_planner.py` untouched (shared with web RAG); B2.4 support gate (`decode_completion`, `SupportVerdict`, `_support_signal.py`, `wa_completion_envelope.py`) untouched; no PII.

## What to attack

1. Over-match of `_LEADING_ORDINAL_RE` (`^\s*\d{1,3}\s*[.)]\s+`): any real message that loses meaning or becomes a scripted greeting because a leading number is stripped (prices, dates, article numbers, times like `10.30`, `1) KITAS`, `3. halo apa bisa bantu`)? Under-match: ordinal shapes clients actually send that still loop.
2. The builder: `match_greeting(query)` is now the gate; planner GREETING → mutate `plan.domain/collections` to GENERAL. Is `plan` really a non-shared, non-frozen local? Any downstream consumer (evidence inputs, abstain policy, curated-QA, pricing intent, hash) that now behaves differently or wrongly for these rows? Could a GREETING→GENERAL row now reach generation where it previously fell off, in a way that violates the fail-closed support gate? (It should still need an authenticated SUPPORTED envelope.)
3. Router `wa_package.py`: curated-QA prefetch gate switched from `plan.domain is not GREETING` to `match_greeting(query) is None`. Cost or behaviour regression? Disagreement with the builder?
4. Import cycle or import-time cost from `services/rag/agentic` importing `services/integrations/wa_greeting`; private import of `_DOMAIN_COLLECTIONS`.
5. Tests: do they prove guilt AND innocence? Is the C1 corpus test real (fixture loaded from disk, 62 texts, divergence only on GREETING)? Any assertion that cannot fail?
6. Anything that would make the scripted greeting fire for a message carrying a question.

## Output

Verdict line first: `SHIP` / `FIX-FIRST` / `BLOCK`. Then findings, each: severity (BLOCKER/MAJOR/MINOR), file:line, evidence (quote), concrete failing input, proposed fix. Mark UNSURE where you are. No praise, no summary of the diff.
