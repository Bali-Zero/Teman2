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

## Why they never ran (the istruttoria — root causes pinned to lines, all re-verified)

1. **The ENTIRE AutonomousScheduler never starts.** Its call-site is commented out:
   `app/setup/service_initializer.py` — `# 10. Background services (DISABLED for
   omnichannel stabilization)` / `# await _init_background_services(...)` (since commit
   `8dec12830`, 2026-02-11). Twin confirmation in `app/setup/app_factory.py` ("shutdown
   removed — re-add when re-enabled"). Only the Health Monitor was re-extracted (step
   10b); the scheduler — plus Compliance Monitor and the WS Redis listener on the same
   switch — has been dead ~5 months.
2. **Even if re-enabled, these three would still be at zero:**
   - `conversation_trainer`: registered but hardcoded `enabled=False`
     (`autonomous_scheduler.py` register_task block, "git subprocess on Fly.io ephemeral
     container");
   - `client_value_predictor`: **never registered** (12 register_task calls in the file,
     none with this name);
   - `knowledge_graph_builder`: **never registered** (only the different
     `kg_incremental_builder` exists, behind `ENABLE_KG_INCREMENTAL=false`).
   The scheduler docstring's "migrated to OpenClaw cron" claim **never materialized**: on
   Pro, `~/.openclaw/cron/jobs.json` is itself retired (`jobs.json.migrated`) and a
   recursive grep for trainer/predictor/builder in `~/.openclaw/` returns nothing.
3. **Execution stats are in-memory.** `app/routers/autonomous_agents.py:29`
   `agent_executions: dict = {}` — no table exists (no `agent_execution*` migration).
   Even a successful manual run shows `total_runs=0` after the next deploy/restart; the
   endpoint can never testify history (superscar-#2 lie-in-waiting).
4. **Collateral cron-theater found on the way** (family #2): the MCP chain
   `chain_daily_ops_autopilot` docstring promises "Check autonomous agent health →
   restart stale agents" (`workflows/chains.py:161`) but the code only READS `/status`
   and logs `stale_agents` (`chains.py:203-217`) — no `/run` is ever called. Meanwhile
   `run_client_predictor` / the client-health chain DO call
   `/client-value-predictor/run` (`tools/workflows.py:146`) — but only when invoked, and
   any run it ever made was erased from stats by (3).

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
