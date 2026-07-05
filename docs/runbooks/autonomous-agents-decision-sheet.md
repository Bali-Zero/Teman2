# Tier-1 "Autonomous" Agents — arm-or-retire decision sheet (TAC-2 A13)

date: 2026-07-05 · lane: TAC-2 burn-down A13 · status: **awaiting operator decision** (Legge 5)
Evidence gathered read-only; production runtime untouched.

## The finding

`GET /api/autonomous-agents/status` (probed live 2026-07-05T09:12Z) reports all three
Tier-1 agents with `status=idle, last_run=null, next_run=null, total_runs=0`:

| Agent | Manual trigger | Scheduler |
|---|---|---|
| Conversation Quality Trainer | `POST /api/autonomous-agents/conversation-trainer/run` (`app/routers/autonomous_agents.py:107`) | none |
| Client LTV Predictor & Nurturer | `POST /api/autonomous-agents/client-value-predictor/run` (`:192`) | none |
| Knowledge Graph Builder | `POST /api/autonomous-agents/knowledge-graph-builder/run` (`:285`) | none |

They have **never run since being scaffolded** (TAC-1 2026-07-02 found the same; re-proven
live today). MCP mirrors exist (`run_conversation_trainer`, `run_client_predictor`) — equally
never invoked.

## Why they never ran (the istruttoria)

1. **No scheduler arms them.** `services/misc/autonomous_scheduler.py` explicitly lists all
   three among "Disabled Tasks (migrated to OpenClaw cron)" — an AUDIT 2026-03-16 decision
   taken when the Fly app had `auto_stop=true`. Two facts have since rotted:
   - the app is **always-on** today (CLAUDE.md §11: `nuzantara-rag` shared-2x, always-on),
     so the auto_stop rationale no longer holds;
   - the "migration to OpenClaw cron" **never materialized**: on Pro,
     `~/.openclaw/cron/jobs.json` is itself retired (`jobs.json.migrated` — the OpenClaw cron
     subsystem was decommissioned) and a recursive grep for
     `conversation.trainer|value.predictor|graph.builder` in `~/.openclaw/` returns nothing.
     The docstring's migration list is archaeology, not configuration.
2. **Execution stats are in-memory.** The `/status` endpoint aggregates from the module-level
   `agent_executions` dict (`app/routers/autonomous_agents.py:584` ff.) — even a successful
   manual run would show `total_runs=0` after the next deploy/restart. The endpoint can never
   testify to history; it is a lie-in-waiting of the superscar-#2 family.

## Options (operator picks per agent)

**ARM** — one launchd cron per agent on Pro or Mini hitting the manual endpoint, e.g.:

```
curl -sS -m 600 -X POST -H "X-API-Key: $NUZANTARA_API_KEY" \
  "https://nuzantara-rag.fly.dev/api/autonomous-agents/conversation-trainer/run?days_back=7"
```

(weekly for trainer/predictor; KG builder daily `days_back=1`). Pre-req: verify each agent's
happy path once by hand — they have never executed, so their first run is a test run
(watch Fly logs; the trainer's 2026-03 "git subprocess won't work on Fly" concern needs
re-verification before trusting output).

**RETIRE** — remove the three `/run` endpoints + `/status` card + the 2 MCP mirror tools,
and delete the scheduler's dead "Disabled Tasks" entries. Zero functional loss versus today
(they do nothing now); removes a permanently-lying status surface.

**Recommendation (non-binding):** retire Conversation Trainer (its design predates the
current prompt-management reality and needs a git worktree it cannot have on Fly); trial-ARM
the KG Builder (the KG is live and growing — `108,068` nodes per DOCSYNC — and this agent is
the only automated feeder); decide LTV Predictor after one supervised manual run.

If ARM is chosen for anything, also make `/status` honest: either persist executions
(`agent_executions` → Postgres table) or label the stats "since last deploy" in the payload.

## Status

- [ ] Operator decision per agent (ARM / RETIRE / defer)
- [ ] If ARM: first supervised manual run + cron PR
- [ ] If RETIRE: removal PR (endpoints + MCP tools + scheduler stanzas)
