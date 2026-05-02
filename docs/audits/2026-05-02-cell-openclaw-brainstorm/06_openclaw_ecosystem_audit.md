# OpenClaw Ecosystem Audit — 2026-05-02

**Source:** Explore agent deep-dive, post-brainstorm round 1
**Goal:** complete map of OpenClaw runtime + integration points + competing runtimes

## 1. Gateway core config

- **Port**: 18789 (loopback-only, local mode)
- **Agents**: **3** (not 2 as round 1 said) — `main`, `coder`, `claude-code` (latter undocumented)
- **Sandbox**: Disabled on main/coder
- **Auth token**: TCa9e8wV67ue_n1PX22... rate limited 10 attempts/60s
- **Reload mode**: Hybrid 500ms debounce

## 2. mcporter integration — IDLE (major gap)

- **Status**: Installed v0.7.3 (`/Users/nuzantara/.npm-global/bin/mcporter`)
- **Config**: Listed in `tools.alsoAllow` and `tools.exec.safeBins`
- **Reality**: ~129 MCP tools (Drive, GitHub, Notion, Linear, Slack, etc.) **loaded but idle**. No automation invokes mcporter today.
- **Opportunity**: major missed integration

## 3. Plugins enabled (5 active)

- **memory-core**: session/conversation state store
- **lobster**: orchestrates multi-step automation workflows
- **llm-task**: wraps LLM calls with task lifecycle
- **voice-call**: phone-based agent interactions (NOT in use)
- **telegram**: in allow list

**Disabled**: memory-lancedb (vector DB alternative not used)

## 4. Skills enabled (5 active)

- **goplaces**: Google Places API (GOOGLE_PLACES_API_KEY)
- **xurl**: URL normalization/detection
- **voice-call**: phone call execution
- **notion**: Notion integration (NOTION_API_KEY)
- **antigravity**: integration unknown (no docs)

**Disabled**: discord, slack, spotify-player, trello, bluebubbles, elite-longterm-memory, sherpa-onnx-tts

## 5. Telegram channel @Balizerobot

- **Memory**: 98 daily conversation files in `~/.openclaw/workspace/memory/` (Feb 2026 → May 2026)
- **Last activity**: 2026-05-02 13:59 today
- **Pattern**: dev test queries + occasional ops (compliance audits, tech summaries)
- **Streaming**: Disabled, timeout 60s, 2 retry attempts
- **Verdict**: UNDERUTILIZED — dev channel, not production traffic

## 6. OpenClaw internal scheduler — 24 FROZEN jobs

All jobs in `~/.openclaw/cron/jobs.json` UNFIRED since ~Apr 30 (status:null, lastRun:null, nextRun:null):
- `client-health-005`
- `seo-guardian-weekly-001`
- `conversation-cleanup-daily-001`
- `tech-orchestrator-l2-002`
- `system-doctor-001`
- 19 more UUID-based jobs

**Status**: DORMANT — scheduler not executing.

## 7. OpenClaw cron wrapper ecosystem — ACTIVE BUT SEPARATE

Bash wrappers in `~/scripts/openclaw-cron/` invoke external backends, **NOT OpenClaw gateway**:

| Script | Backend | Status |
|---|---|---|
| `_prewarm.sh` | Fly.dev | Active |
| `knowledge-graph-builder.sh` | Fly NUZANTARA_API | Active |
| `conversation-trainer.sh` | Local Python | Active |
| `garuda-indexer.sh` | Fly backend | Active |
| `garuda-gc.sh` | Fly backend | Active |
| `seo-cell-daily.sh` | Local Python cell | Active |
| `seo-cell-28d-check.sh` | Local Python cell | Active |
| `client-value-predictor.sh` | Unknown | Active |
| `renewal-alerts.sh` | Unknown | Active |
| `sentinel_ping.sh` | Unknown | Active |
| `drive-poll.sh` | Drive API | DISABLED |

**Finding**: 10 active jobs are NOT orchestrated by OpenClaw — completely bypass the gateway. Naming legacy from migration that never completed.

## 8. Lobster workflows — ONLY ACTIVE OPENCLAW USE

`~/.openclaw/workspace/workflows/*.lobster`:

1. **autofix-loop.lobster**: invokes `openclaw agent --agent coder` for automated test fixes
2. **nightly-code-quality.lobster**: code reviews + style enforcement
3. **weekly-dep-audit.lobster**: dependency updates, security scans
4. **nuzantara-dev-pipeline.lobster**: multi-stage CI/CD (test → build → deploy)

**45 discrete command steps total**. Use `--agent coder` = active OpenClaw integration. **This is the ONLY production OpenClaw usage today**.

## 9. Voice-call + browser

- **Voice-call dir**: `~/.openclaw/voice-calls/` (empty, no calls)
- **Plugin enabled** but no active call logs
- **Chrome extension**: `~/.openclaw/browser/chrome-extension/` exists but no activity logs

Both = capacity sprecata.

## 10. Alternative agent runtimes — COMPETITOR ECOSYSTEM (CRITICAL)

| Runtime | Type | Status | Role |
|---|---|---|---|
| **cron-agent-python** (`.cron-agent-python/`) | Python daemon | **ACTIVE — 19 strategies live** | Real production runner |
| **claude-squad** (`.claude-squad/`) | Git agent | Active | Branch/PR orchestration via Claude CLI |
| **.cron-agent** (`.cron-agent/`) | Older runner | Superseded | State files present, replaced |
| **kimi** (`.kimi/`) | MCP server | Session store only | Stores Kimi API sessions, not runner |
| **cagent** (`.cagent/`) | Agent framework | **ACTIVE — 19 registered strategies** | Competing with OpenClaw |
| **jules** (`.jules/`) | Unknown | Dormant | No recent activity |
| **kradle** (`.kradle/`) | Unknown | Dormant | No recent activity |

## 11. cron-agent-python — THE REAL PRODUCTION RUNNER

**Path**: `~/.cron-agent-python/`
**Status**: ACTIVE — executing 19 automation strategies (verified with state files)

Active strategies:
- `fact-checker` (running 14:15 today)
- `fly-watcher` (14:45 today)
- `tech-orchestrator` (12:30 today)
- `client-health-monitor` (14:00 today)
- `compliance-ops` (12:00 today)
- `daily-ops` (08:00 today)
- `log-anomaly-detector` (14:51 today)
- `intel-radar` + `intel-feed-processor` (14:00 today)
- `oss-monitor` (open-source dependency tracking)
- `pajak-monitor` (tax/compliance)
- `imigrasi-monitor` (immigration/regulatory)
- `bi-exchange-rate` (business metrics)
- `tdd-pipeline` (test-driven deploy)
- `vision-doc-extractor` (document OCR)
- `system-doctor` (infrastructure health)

**Architecture**: Manager-based dispatch with pluggable memory (unified_memory.py), encoding flows, recall strategies. Database-backed (sessions.db, 69KB).

⚠️ **CRITICAL FINDING**: cron-agent-python is a **PARALLEL execution engine to OpenClaw** running 19 automations that overlap with OpenClaw's 24 frozen jobs. **Architectural fragmentation**.

## 12. team-agent, cagent, claude-squad

- **team-agent**: subdir exists `~/Desktop/nuzantara/apps/team-agent/`, purpose undocumented
- **cagent**: config-driven agent framework, stored state (see #11)
- **claude-squad**: git-aware agent, routes Claude CLI commands to branch management

## 13. OpenClaw vs cell-core overlap

**cell-core** (reasoner, safety, observability):
- `apps/evaluator/seo_cell/` local Python cell
- Invoked by `seo-cell-daily.sh` and `seo-cell-28d-check.sh`
- Own SQLite memory, JSON state output

**OpenClaw**:
- Gateway safety (exec-approvals.sock manual approval)
- Agent sandbox (non-main mode)
- Loop detection + circuit breakers

**Verdict**: NOT competing. cell-core = domain-specific evaluator (SEO metrics), OpenClaw = general-purpose agentic gateway. They coexist but NOT integrated.

## 14. Workspace structure

- **workspace/**: main agent runtime (scripts, workflows, memory, shared_memory)
- **workspace-coder/**: isolated coder agent (code generation)
- **workspace/workflows/**: 4 lobster files, 45 commands
- **workspace/memory/**: 98 daily conversation logs

## Missed integrations & coverage gaps (round 1 brainstorm)

1. **mcporter (129 MCP tools) completely idle** → should integrate with OpenClaw agents
2. **cron-agent-python is REAL production runner** → 19 automations should consolidate
3. **24 OpenClaw scheduled jobs FROZEN** → frozen since Apr 30, overlap cron-agent-python
4. **Lobster workflows ARE using OpenClaw** (autofix-loop.lobster) → only active integration
5. **Telegram underutilized** → mostly dev testing
6. **cell-core SEO metrics parallel via bash** → not integrated with OpenClaw gateway
7. **Voice-call plugin enabled NOT used** → no logs
8. **Browser extension exists DORMANT** → no flows
9. **3 competing agent runtimes** (cron-agent-python, cagent, claude-squad) → architectural fragmentation

## Action items (post-audit)

- Consolidate cron-agent-python strategies into OpenClaw jobs
- Activate mcporter in lobster workflows
- Revive 24 frozen jobs OR migrate to cron-agent-python (decide one runtime)
- Route cell-core outputs through OpenClaw observation layer
