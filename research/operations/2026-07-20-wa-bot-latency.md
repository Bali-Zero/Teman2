---
date: 2026-07-20
domain: operations
client_case: none
adversarial_review: kimi-k3
sources:
  - prod Postgres `meta_inbox_messages`/`meta_inbox_threads` (thread_id=77, live query)
  - `apps/backend-rag/backend/services/rag/agentic/llm_gateway.py:336-338` (dated code comment, 2026-07-18)
  - `apps/backend-rag/backend/services/rag/agentic/reasoning.py:918-921,942-966`
  - `apps/backend-rag/backend/services/tools/definitions.py:104` (`AgentState.max_steps` default)
---

# WhatsApp bot reply latency — root cause + fix

## Finding

Zantara WA bot (Meta Business API channel) replies took **33-94 seconds**
end-to-end, measured empirically from `meta_inbox_messages.sent_at -
created_at` for a real thread (id 77) across five exchanges on 2026-07-19/20.
Zero flagged this as unexpectedly slow for `gemini-3.5-flash`, which alone
generates in a few seconds.

## Root cause

Not the model — the orchestration around it. Every WA message runs the full
non-streaming ReAct loop (`orchestrator_core.py:1006` →
`execute_react_loop`, `reasoning.py:209`), which can chain **up to 3
sequential LLM calls** (`AgentState.max_steps = 3`,
`backend/services/tools/definitions.py:104`), each independently profiled
in-code at **~15-17s** (`llm_gateway.py:336-338`, comment dated 2026-07-18 —
two days before this investigation, from a prior live-timeout repro). After
the loop, a separate `verification_service.verify_response()` call
(`verification_service.py:161`) scores the answer; if `score < 0.7`, a
self-correction rephrase + re-verify pass fires, profiled at **~23s**
(`reasoning.py:918-921,942-966`).

Arithmetic: 3×(15-17s) ReAct ≈ 45-51s + verification ≈ 5-10s + optional
self-correction ≈ 23s lands almost exactly in the observed 33-94s band.

Two live WhatsApp call paths hit this same loop:
`backend/services/integrations/wa_inbox_bot.py:266` (HTTP →
`/api/agentic-rag/query`, `agentic_rag.py:301`) and
`backend/app/routers/whatsapp_chat.py:530` (in-process
`orchestrator.process_query` call, a second/older WA surface). Telegram and
Instagram do **not** share this cost — they run the separate streaming path
(`orchestrator.stream_query` → `execute_react_loop_stream`,
`reasoning.py:996`) which has no self-correction rephrase branch at all.

## Fix shipped (this PR)

An additive, backward-compatible `max_steps` knob, forwarded end-to-end:
`AgenticQueryRequest.max_steps` (`agentic_rag.py`) →
`orchestrator.process_query(max_steps=...)` (`orchestrator.py`) →
`OrchestratorCore.process_query_core(max_steps=...)`
(`orchestrator_core.py`), applied as `state.max_steps = min(max_steps,
state.max_steps)` right after routing (never allowed to RAISE the cap, so
no caller can use this field to force deeper/costlier reasoning than the
route already assigned).

Both WhatsApp call sites now set `max_steps=2` (down from the default 3).
Self-correction is deliberately **left untouched** — the bot answers real
client questions on visa/legal topics, and trading away the one guardrail
that catches low-confidence answers for a few more seconds of speed is a
quality/trust call, not a pure infra one; that trade stays available as a
follow-up if Zero wants it (see PENDING-ARMS).

## Expected effect (not yet empirically re-measured post-deploy)

Removes the possibility of a 3rd ReAct step: caps the ReAct-loop-only tail
at ~2×15-17s ≈ 30-34s instead of ~45-51s. Typical-case exchanges that
already finished in 1-2 steps are unaffected (the cap only bites outlier
chains). Worst case (2 steps + self-correction) drops from ~94s toward
~55-65s.

## Adversarial review

Seat: **Kimi K3** (`kimi-code/k3`, Moonshot — cross-family vs. the
Claude-family author). Codex (`gpt-5.6-sol`) was the first-choice seat but
is dead on this account (`400 model not supported when using Codex with a
ChatGPT account` — another arsenal seat that lists as armed but isn't,
cf. the guardians audit). Kimi read the real code (not just the diff) and
found two real issues, both fixed in this PR:

1. **Missing floor on the clamp.** `min(max_steps, state.max_steps)` alone
   never raises the cap, but a 0/negative value on the in-process call path
   (`whatsapp_chat.py`, which bypasses the HTTP Pydantic `ge=1` schema
   entirely) would silently zero out the ReAct loop instead of just cutting
   latency. Fixed: `max(1, min(max_steps, state.max_steps))`
   (`orchestrator_core.py`).
2. **The "only trims the tail" claim was wrong for multi-hop/parallel-tool
   queries.** `reasoning.py:428-429` counts each parallel tool call as its
   own budget unit (verified on disk — deliberate design, §U6). With
   `max_steps=2`, a query needing 2+ tool calls exits the loop before an
   in-loop synthesis turn and falls to the post-loop context-synthesis path
   (`reasoning.py:656`) instead — same LLM-call count as before, but a
   different, less-tested answer-construction path. This hits hardest on
   exactly the intent class WA users trigger often
   (`COMPLEX_QUERY_INTENTS`, visa/company-setup — `reasoning.py:480-486`
   keeps these in the loop because they may need a KG hop). Comments fixed
   to state this accurately instead of overclaiming a clean latency-only
   change; tracked as a PROVE-LIVE watch item below, not a blocker — the
   single-hop majority still gets the full win, and multi-hop isn't made
   slower, only routed differently.

Both citations independently re-verified on disk by the orchestrating
session before accepting the review (W65: even the refuter's claims are
leads, not facts, until re-grepped).

## Verification checklist

- [x] `backend/tests/unit/services/rag/agentic/test_reasoning_comprehensive.py -k max_steps` (1 passed)
- [x] `backend/tests/unit/services/rag/agentic/test_reasoning_coverage.py -k max_steps` (1 passed)
- [x] `backend/tests/services/rag/test_verification_service.py -k validity_threshold` (1 passed)
- [x] `backend/tests/services/rag/agentic/test_orchestrator_core.py` (8/8 passed)
- [x] `tests/integration/app/routers/test_agentic_rag_integration.py` — skipped locally (no
      Docker/Redis in the verification sandbox); runs in CI, which is Docker-backed
- [x] Broader regression sweep (~1444 tests, agentic+router suites): 1409 passed / 30 skipped /
      5 failed — the 5 failures reproduce identically on unmodified `main` (test-order
      pollution in `test_prompt_builder.py`/`test_reasoning_utils.py`, pre-existing, unrelated
      to this diff)
- [x] Import chain + syntax clean on all 5 modified files
- [ ] PROVE-LIVE: re-query `meta_inbox_messages` for thread 77 post-deploy, confirm
      `sent_at - created_at` shifts down from the 33-94s band — **BLOCKED**, see below
- [ ] PROVE-LIVE watch item (from adversarial review): monitor the WA channel's
      abstain/low-context-quality rate after rollout, since multi-hop queries now resolve via
      the post-loop synthesis path rather than in-loop reasoning

## Deploy status (2026-07-20, post-merge)

PR #2891 merged to `main` (squash `c577cbbef24627e123484d5e1d9ff9596d6ab065`), triggering
`.github/workflows/fly-deploy.yml` run 29724366888. The `Run DB migrations on Fly.io` job
failed twice — first at the `flyctl` GraphQL control-plane query (`get app network... 503`),
then on rerun at the `setup-flyctl@master` action itself (`503 Service Unavailable`) — cascading
skips through rolling deploy, both migration re-run jobs, and post-deploy health check.

Root cause confirmed via three independent sources: (1) code-level reproduction — `fly status
-a nuzantara-rag` returns the same 503 live; (2) an unrelated deploy run 17 minutes prior to
#2891's merge shows the identical failure signature; (3) Fly's own status page
(status.flyio.net) shows an **active, acknowledged incident**: "High number of 5XX on the
Machines API and dashboard", status Investigating, opened 2026-07-20 07:10 UTC — explicitly
scoped to the Machines API + dashboard, with "existing machines... unaffected". This is an
ambient Fly.io platform outage, not caused by this PR's diff (no migration files touched) and
not fixable from this side. The currently-deployed (pre-fix) app remains healthy
(`/health` → 200 OK) — only new deploys are blocked.

**Action**: stopped retrying (2 attempts both hit the same outage; further reruns just burn
CI minutes against a control plane that isn't up). Deploy will be retried once Fly's status
page marks this incident resolved. PROVE-LIVE steps above stay blocked until then.

## Follow-up (not in this PR)

- Skip the self-correction re-verify pass specifically for WA — only worth
  doing with an explicit call on the quality/speed trade-off (Legge 5).
- `orchestrator_core.py:1601-1620` docstring claims context-load and
  entity/KG extraction run "in PARALLEL" but the code `await`s them
  sequentially — true parallelism is only the inner entity/KG/LangGraph
  trio (`asyncio.gather`, lines 665-670). Free latency left on the table,
  unrelated to the WA-specific fix above; not touched here to keep this
  diff scoped.
- `execute_react_loop_stream` (Telegram/Instagram's streaming path,
  `reasoning.py:996`) never receives this `max_steps` knob — a non-issue
  today (both WA call sites are sync), but if WA ever migrates to
  streaming, the cap silently stops applying. Worth a note if/when that
  migration happens, not work to do now.
