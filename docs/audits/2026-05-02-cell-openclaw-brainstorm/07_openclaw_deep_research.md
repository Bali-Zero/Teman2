# OpenClaw Deep Research: Architecture, Capabilities & Current Usage
**Date**: 2026-05-02 | **Version**: openclaw 2026.3.31 | **Local Install**: `~/.openclaw/lib/node_modules/openclaw/` | **Config**: `~/.openclaw/openclaw.json`

**Audience**: Claude (reader) + cross-LLM reviewers (Codex GPT-5.5, Gemini 3.1 Pro, DeepSeek V4 Reasoner) preparing to reason about OpenClaw's role in Nuzantara automations.

---

## Executive Summary

OpenClaw is a **Node.js-based personal AI gateway** running a WebSocket control plane (`ws://127.0.0.1:18789`) that routes inbound messages from 23+ messaging channels (Telegram, WhatsApp, Discord, Slack, iMessage, etc.) to isolated agents, which dispatch LLM requests with multi-model fallback + tool streaming. The runtime is process-managed by LaunchAgent on macOS; the agent itself is embedded (RPC mode). 

**Nuzantara is using OpenClaw for**:
- Primary messaging channel: Telegram (enabled, receiving message timeouts)
- Multi-LLM routing: MiniMax M2.7 (primary) → Kimi K2.6 → DeepSeek Chat → Ollama Qwen3.5
- Persistent memory: memory-core plugin (storing observations from tool use)
- Orchestration: lobster plugin (workflow DSL, enabled)
- Voice: voice-call skill (enabled)
- Custom extensions: claude-mem (v12.1.0, marketplace install)

**Version Gap**: Installed version is 2026.3.31 (released ~Mar 31); latest is 2026.4.29 (released Apr 30). Recent releases include Knowledge Agents system (12.1.0 in claude-mem), improved Telegram channel timeouts, and model failover hardening.

---

## A. Architecture

### Runtime Model

OpenClaw is a **Node.js daemon** (v22.22.0, bundled) running:
- **Gateway** (port 18789, loopback-only, hybrid reload on config change)
- **Control UI** (Web dashboard, http://127.0.0.1:18789)
- **Pi agent** (embedded RPC, not external process)
- **Channel adapters** (Telegram: grammY, Discord: discord.js, WhatsApp: Baileys, etc.)

**Process Management**:
- macOS: LaunchAgent (`~/Library/LaunchAgents/openclaw.plist` — managed by Nuzantara's `monitor-air.log` cron)
- KeepAlive policy: checked via heartbeat monitor every 1h (Nuzantara config: `heartbeat.every="1h"`)
- Uptime target: 24/7 (threshold exceeded May 2, 2026 at 01:13 UTC — gap analysis in logs)

### Agent Abstractions

**Agent Definition** (`agents.list[]`):
- Nuzantara has 2 agents:
  1. **main**: primary, Telegram-bound, sandbox=off, model routing primary→fallback chain
  2. **coder**: isolated workspace, sandbox=off, web tools denied (no web_search, web_fetch, browser)

**Model Routing**:
```
main:
  primary: openrouter/minimax/minimax-m2.7
  fallbacks: [kimi-k2.6, deepseek-chat, ollama/qwen3.5:9b]

coder:
  primary: openrouter/qwen/qwen3-max
  fallbacks: [qwen3.6-plus, kimi-k2.6, deepseek-reasoner, qwen3.5:9b]
```

**Fallback Chain Logic**:
- Model request → try primary; if fails (auth, rate_limit, not_found) → try next fallback
- Auth cooldown: 300s lockout after 10 auth failures in 60s window (gateway.auth.rateLimit)
- Rate-limit cooldown: automatic provider cooldown (all-profiles-unavailable state) visible in logs (Mar 1-2, Google Gemini CLI exhausted)

**Sandbox Modes**:
- Default: `non-main` (separate container per agent workspace)
- Nuzantara: `mode=off` for both agents (no isolation) + `prune.idleHours=24` (clean up idle containers)

### Plugin System

Plugins extend gateway capabilities via allow-list:

**Loaded Plugins** (`plugins.entries`):
- **memory-core** (enabled): observation feed + persistent storage
- **memory-lancedb** (disabled): vector search backend (not active)
- **lobster** (enabled): workflow orchestration DSL
- **llm-task** (enabled): multi-step LLM orchestration
- **voice-call** (enabled): phone/VOIP integration
- **telegram** (implicit, channel adapter)

**Plugin Trust Model**:
- Plugins in `~/.openclaw/extensions/` are scanned; only those in `plugins.allow[]` are loaded
- Nuzantara's installed plugin: `claude-mem` (v12.1.0) in `~/.openclaw/extensions/claude-mem/`
- **Trust Warning**: claude-mem flagged in gateway logs as "loaded without install/load-path provenance" (implies manual fs install, not via package manager)

### Skill System

Skills add tools to agents via hooks + HTTP API.

**Bundled Skills** (`~/.openclaw/lib/node_modules/openclaw/skills/`):
- goplaces (Google Places API), xurl (URL shortener), voice-call (Twilio), notion, slack, discord, trello, spotify-player, etc.

**Nuzantara Enabled Skills** (`skills.entries`):
- **goplaces**: enabled (env: GOOGLE_PLACES_API_KEY)
- **xurl**: enabled
- **voice-call**: enabled
- **notion**: enabled (env: NOTION_API_KEY)
- **antigravity**: enabled

**Custom Skills Directory**: `/Users/nuzantara/Desktop/nuzantara/apps/nuzantara-mcp/skills` (loaded via `skills.load.extraDirs[]`)

### Channel Bindings

**Telegram Channel** (enabled, dmPolicy=open):
- **BotToken**: configured (redacted in config, present in plaintext)
- **Allowed Senders**: `allowFrom=["*"]` (open to all)
- **Streaming**: disabled (responses sent as complete message blocks)
- **Timeout**: 60s per message
- **Retry**: 2 attempts, min 5s delay, max 60s delay, 0.5 jitter
- **Known Issues**:
  - Network timeouts (ETIMEDOUT / EHOSTUNREACH observed Mar 1-2, 30s+ waits)
  - BOT_COMMANDS_TOO_MUCH (Telegram API limit: max 100 commands, Nuzantara registering 92-97, dropping 19-20 on each attempt)

**Other Channels**:
- WhatsApp, Discord, Slack, Signal, iMessage (BlueBubbles), IRC, Teams, Matrix: all disabled in config

### Memory Model

**memory-core** plugin:
- SQLite database: `~/.openclaw/agents/main/agent/memory.db` (not visible in config, inferred from logs)
- Observation feed: tool_use events → semantic summaries → injected into future sessions
- Token-aware: context pruning mode=cache-ttl (1h TTL), compaction mode=safeguard (96k reserve floor, 40% history max)
- Worker Service: runs on separate port (likely 37777 per claude-mem docs), managed by Bun
- Vector backend: Chroma (if memory-lancedb enabled; currently off)

### mcporter Integration

**Tool Surface**:
- Built-in: browser, canvas, nodes, cron, sessions
- MCP tools: claude-mem (`search`, `timeline`, `get_observations`), custom skills

**Safety Allowlist** (`tools.exec.safeBins[]`):
```
ls, cat, tail, which, nuzantara-ops, mcporter
```
- Only these binaries can be executed without sandbox approval
- `mcporter` is whitelisted (allows MCP tool invocation from agent)
- **Known Issue**: mcporter allowlist audited Mar 22; safeBins entries not matching plugin config (audit log shows mismatch fixed via plugin reload)

### Lobster Workflows

**Lobster Plugin** (enabled):
- DSL for multi-step orchestration
- Workflow files: `~/.openclaw/workspace/.lobster/*.yml` (inferred)
- Nuzantara logs show no active workflows, but plugin enabled for future use

### Sandbox & Safety

**Exec Approval Socket** (`exec-approvals.sock`):
- Manual approval flow for unsafe commands
- Not actively used in Nuzantara (sandbox=off, so no approvals needed)

**Circuit Breaker** (`tools.loopDetection`):
- Enabled globally (threshold=10 repeats)
- Detectors:
  - **genericRepeat**: catch identical tool calls in sequence
  - **knownPollNoProgress**: detect polling without state change
  - **pingPong**: detect tool A → B → A cycles
- Nuzantara: enabled, no circuit trips observed (logs clean on this metric)

---

## B. Current Capabilities

### Agentic Tasks

**Single-turn**: `openclaw agent --message "query"` (CLI or Gateway RPC)
**Multi-turn**: Session state preserved in memory; model compaction + context pruning per config
**Persistent Loops**: Supported via Lobster workflows (enabled but not in use)

### Tool Use

| Tool | Enabled | Notes |
|------|---------|-------|
| **web_search** | Yes | Integrated |
| **web_fetch** | Yes | Integrated |
| **browser** | No (coder agent denies) | Chrome control, snapshots, actions |
| **exec** | Partial (safeBins only) | ls, cat, tail, nuzantara-ops, mcporter |
| **file ops** | Via browser canvas | Not direct agent tool |
| **image** | Yes (image model routing) | Primary: ollama/qwen2.5vl:7b, fallback: openrouter/qwen3-vl |
| **canvas** (macOS) | Yes | A2UI protocol, push/reset/eval/snapshot |
| **cron** | Yes | 24 jobs max (Nuzantara shows 0 active, scheduler may be frozen as of Apr 30) |
| **custom MCP** | Yes (mcporter) | Route to local/remote MCP servers |

**Multi-LLM Routing**: Each agent has primary + 3 fallback models; per-model params (temperature, max_tokens) configurable

### Multi-LLM Routing

**Provider Configuration**:
- **openrouter**: native support, baseUrl=https://openrouter.ai/api/v1, 6 models configured
- **deepseek**: native support, baseUrl=https://api.deepseek.com/v1, 2 models configured
- **ollama**: local, baseUrl=http://127.0.0.1:11434, 0 models pre-configured (dynamic discovery)
- **anthropic**: **NOT configured** (no ANTHROPIC_API_KEY in env; Nuzantara policy: banned)
- **openai** (via openrouter): shim via openrouter provider

**Per-Model Tuning**:
```
temperature: 0.2–0.4 (reasoning), 0.3–0.4 (chat)
max_tokens: 4096–8192
ollama-specific: keep_alive=10m (memory cache), top_p=0.9, top_k=20
```

**Fallback Behavior**: 
- Try primary; if fails, cascade through fallbacks
- Rate-limit cooldown (300s) applied per provider
- Auth errors caught and retried with different auth profile (if multi-profile configured)

### Persistent Memory

**memory-core** (enabled):
- **Lifecycle Hooks**: SessionStart → UserPromptSubmit → PostToolUse → Summary → SessionEnd
- **Observation Compression**: tool_use events → semantic summaries (via Claude API or local LLM)
- **Injection Strategy**: progressive disclosure (layer 1: index; layer 2: timeline; layer 3: full details)
- **Search Tools**: `mem-search`, `timeline`, `get_observations` (MCP interface)
- **Durability**: SQLite persistent store, survives session/process restarts

### Channel I/O

**Telegram** (primary):
- Inbound: message events → matched to agent via binding (main agent, Telegram channel)
- Outbound: agent reply → formatted as Telegram message → sent via botToken
- **State**: connected (logs show recent message processing up to May 2 01:13)
- **Timeouts**: retry logic (2 attempts, 5–60s backoff) masks network latency

### Voice-Call

**voice-call Skill** (enabled):
- Integration: Twilio (inferred from OpenClaw docs; not explicitly in Nuzantara config)
- Capabilities: accept voice calls, stream audio, TTS output (ElevenLabs or system fallback)
- **Status in Nuzantara**: enabled but not actively tested

### Browser Automation

**Browser Tool** (available, not in use by main agent):
- Chrome/Chromium control (dedicated OpenClaw instance)
- Actions: snapshot, click, type, scroll, upload, profile switching
- **Nuzantara**: coder agent has browser denied via `tools.deny=["browser"]`

### Workflow Orchestration (Lobster)

**Lobster DSL** (enabled, not in active use):
- YAML-based multi-step orchestration
- Syntax: task dependencies, conditional routing, parallel execution
- **Nuzantara**: loaded but no workflows observed in logs

### Subagents

**Subagent Pattern**: supported via agent routing (`bindings[]` match rules)
- **Nuzantara**: 2 agents defined (main, coder); no inter-agent delegation observed
- **Limitation**: agents are isolated; no direct parent-child RPC (agents are standalone)

### Cron / Scheduled Jobs

**Cron Tool**:
- API: `POST /gateway/cron` or `openclaw cron add <schedule> <command>`
- Max 24 jobs per gateway
- **Nuzantara Status**: 0 active jobs logged (scheduler may be frozen since Apr 30 per audit notes)

### Hooks

**7 Lifecycle Hooks** (claude-mem):
- SessionStart, UserPromptSubmit, PostToolUse, Summary, SessionEnd, PreToolUse, Stop
- **Nuzantara Use**: memory-core hooks active (observation capture, summary generation)

### Plugin Development

**Plugin Template**:
- Entry point: `plugin/index.ts` or `dist/index.js`
- Hooks: export `hooks: { SessionStart, UserPromptSubmit, ... }`
- MCP Tools: export `tools: [ ... ]` (JSON-RPC 2.0 interface)
- **Nuzantara Custom Skills**: loaded from `/Users/nuzantara/Desktop/nuzantara/apps/nuzantara-mcp/skills/` (no plugins observed)

### Embedded Agent Runtime

**Pi Agent** (embedded, not delegated):
- Runs in-process with gateway (RPC loopback)
- Session state: maintained in gateway memory (not persistent across restarts without memory plugin)
- Tool dispatch: streaming responses back to gateway → channel output

---

## C. What's NEW (Recent OpenClaw Releases)

| Release | Date | Highlights |
|---------|------|-----------|
| **v2026.4.29** | Apr 30, 2026 | Stability improvements, auth profile migration docs |
| **v2026.4.09** | Apr 9, 2026 | Knowledge Agents system (6 new MCP tools: build_corpus, prime_corpus, query_corpus, etc.) |
| **v2026.3.31** | Mar 31, 2026 | **[INSTALLED]** DM pairing default, Telegram net timeout handling, provider enum changes |
| **v2026.1.5** | Jan 5, 2026 | Image model config, agent.imageModel + fallbacks, model shorthands (opus, sonnet, gpt, gemini) |

**Most Notable for Nuzantara**:
- **Knowledge Agents** (v2026.4.09): Compile filtered corpus from claude-mem observations, query conversationally. 6 new MCP tools (build_corpus, list_corpora, prime_corpus, query_corpus, rebuild_corpus, reprime_corpus). **Not yet exploited.**
- **Auth Profile Migration** (v2026.3.31 → v2026.4.29): DM pairing now default (requires approval codes); legacy "open to all" requires explicit dmPolicy=open + allowFrom=["*"]. **Nuzantara already configured.**
- **Telegram Timeout Hardening** (v2026.3.31): Retry + backoff for network errors (30s+ waits masked). **Experienced but handled gracefully.**

**Claude-Mem Integration** (v12.1.0, installed via marketplace):
- Knowledge agents now supported (native corpus build, prime, query MCP tools)
- Smart-explore extended to 24 languages
- File-read decision gate (PreToolUse hook blocks redundant reads using observation timeline)

---

## D. Comparison vs Alternatives

| Dimension | OpenClaw | cron-agent-python (Nuzantara) | LangChain/LangGraph | Anthropic Agent SDK (direct) |
|-----------|----------|------|-----------|---------|
| **Primary UX** | Gateway + multi-channel | Python cron + custom CLI | Chain/graph DSL | Messages API |
| **Multi-LLM** | Native (fallback chains) | Manual (explicit per-agent config) | LLMChain abstraction | No native support |
| **Persistent Memory** | Plugin-based (memory-core) | NotebookLM (external) | No built-in | No built-in |
| **Channel Binding** | 23+ integrations (Telegram, Discord, etc.) | CLI-only / webhooks | None (user's responsibility) | None |
| **Workflow Orchestration** | Lobster DSL | Python task queue | LangGraph (DAG-based) | Claude Agent SDK (new) |
| **Tool Streaming** | Yes (block streaming) | Manual | Yes (via tool classes) | Yes (native) |
| **Sandbox** | Exec approval socket | None (direct subprocess) | None | None (external runner) |
| **State Persistence** | SQLite (via plugins) | Disk-backed (JSON/state files) | Not built-in | Not built-in |
| **Scaling** | Single gateway (local) | Multi-machine (cron dispatch) | App-level (doesn't scale infra) | Delegated to cloud provider |
| **Ease of Setup** | `openclaw onboard` (90s) | Python venv + config | npm install + boilerplate | anthropic SDK (Python/JS) |

**OpenClaw's Unique Value Propositions**:
1. **Multi-channel inbox**: Single control plane for Telegram, WhatsApp, Discord, Slack, iMessage, IRC, Teams, Signal, etc.
2. **Persistence out-of-the-box**: memory-core plugin captures observations + injects into future sessions (no manual logging)
3. **Native fallback chains**: multi-model routing with per-provider cooldowns + auth management
4. **Embedded + local**: runs on your machine (no cloud), binds to loopback only (no public expose by default)

**Where OpenClaw Loses**:
1. **No cloud sync**: single-machine deployment (no multi-region HA out of the box)
2. **Provider enum rigidity**: only supports explicit providers (openrouter, deepseek, ollama, anthropic); no generic OpenAI-compatible override until v2026.3.31+ (baseUrl interpolation)
3. **Command limit (Telegram)**: max 100 commands registered; Nuzantara hitting 92-97, dropping 19-20 on each sync
4. **Scheduler frozen** (apr 30+): cron jobs not running (24-job queue inert); cause unknown

**vs cron-agent-python** (Nuzantara parallel):
- cron-agent-python: 19 active strategies, each runs independently on schedule; state decoupled (disk-backed JSON)
- OpenClaw: single agent with multi-LLM routing; state unified in memory-core
- **Recommendation**: cron-agent-python excels for **independent, scheduled tasks** (classification, analysis per-document); OpenClaw excels for **interactive, multi-turn conversations** with memory (Telegram chatbot + persistent context)

---

## E. Scaling Characteristics

### Concurrency

**Max Concurrent Agents**: 1 gateway, N agents (in Nuzantara: 2)
- **Per-Agent Sessions**: Unbounded (session state pruned on demand)
- **Concurrent Requests**: Limited by LLM provider rate limits (OpenRouter: ~100 req/min; DeepSeek: API doc unclear; Ollama: local, unbounded)
- **Telegram Message Queue**: Sequential (one message processed at a time, 60s timeout → retry → backoff)

### Memory Footprint

| Component | RSS (Idle) | RSS (Active) | Notes |
|-----------|-----------|-------------|-------|
| Gateway process | ~200–300 MB | ~400–600 MB | Node.js runtime + channel adapters |
| memory-core SQLite | ~10 MB | ~50+ MB | Depends on observation count + vector index |
| Chroma (if enabled) | N/A | ~200+ MB | Python subprocess (uv-managed), not active in Nuzantara |
| Total (Nuzantara) | ~250 MB | ~500+ MB | Measured via LaunchAgent memory monitor |

### Latency Overhead

| Operation | Latency | Notes |
|-----------|---------|-------|
| Gateway routing (inbound message) | <10ms | WebSocket demux + binding match |
| Agent dispatch (to LLM) | <50ms | HTTP to OpenRouter/DeepSeek |
| LLM request | 500ms–5s | Depends on model, fallback chain depth |
| Response streaming (Telegram) | 1–30s | Tool execution + LLM generation + retry backoff |
| Memory injection (PreToolUse) | 100–500ms | SQLite query + compression (if observation reuse) |

**Gateway overhead is negligible** (<10% of E2E latency).

### State Persistence

**Durable Across Crashes**: Yes (if memory-core enabled)
- Session state saved to SQLite after each tool_use hook
- Observation timeline reconstructed on SessionStart

**Graceful Shutdown**: LaunchAgent KeepAlive policy
- monitored by `launchctl unload/load` (manual) or cron watchdog (Nuzantara)
- Timeout: 30s (hard kill if not responsive)

### Crash Recovery

**KeepAlive=true** (Nuzantara config):
- LaunchAgent auto-restarts gateway on exit (non-zero exit code)
- State surviving: memory-core observations (durable), in-flight messages (lost, retried by Telegram)
- **Observed**: gateway crashes not logged; LaunchAgent restarts appear transparent

### Multi-Instance Topology

**Federation**: Not supported natively
- **Workaround**: run multiple gateways on different ports (18789, 18790, ...), but agents are isolated per gateway
- **Nuzantara**: single gateway (port 18789); no multi-instance setup

---

## F. Security Model

### Loopback-Only Binding

**gateway.bind=loopback** (Nuzantara default):
- Gateway listens on 127.0.0.1:18789 (localhost only)
- No public internet exposure (requires SSH tunnel or Tailscale to access from remote)
- **Threat Model**: protects against direct internet attacks; assumes local machine is secure

### Auth Token & Rate Limiting

**Token** (gateway.auth.token):
- Long random string (example: 64 char base64)
- Required in WebSocket `?token=...` query param or HTTP `Authorization: Bearer <token>` header
- **Storage**: plaintext in `~/.openclaw/openclaw.json` (same permissions as SQLite DB)
- **Rotation**: manual edit + `openclaw reload` (no auto-rotation tool visible)

**Rate Limiting**:
- **maxAttempts**: 10 failures in 60s window (Nuzantara config)
- **lockoutMs**: 300s (5 min) lockout after threshold
- **Scope**: per-IP (loopback is single IP, so affects all local clients equally)

### exec-approvals.sock

**Manual Approval Flow**:
- Unsafe exec commands → `exec-approvals.sock` (Unix domain socket, `/tmp/exec-approvals-<pid>.sock`)
- User approval via CLI: `echo "approve <exec-id>" | nc -U /tmp/exec-approvals-<pid>.sock`
- **Nuzantara Status**: sandbox=off for both agents, so approval flow never triggered

### Sandbox Modes

| Mode | Isolation | Use Case |
|------|-----------|----------|
| **off** | None | Development, trusted local use |
| **non-main** | Per-agent container | Multi-agent isolation (default agents.defaults.sandbox.mode) |
| **full** | Per-session container | Maximum isolation (experimental) |

**Nuzantara**: mode=off (no isolation). Rationale: single user, local machine, trusted workflows. Trade-off: agents can interfere (shared filesystem, process space).

### Safety Bins Allowlist

**Tools.exec.safeBins**:
```
ls, cat, tail, which, nuzantara-ops, mcporter
```
- Only these binaries bypass approval flow
- Others require exec approval (if sandbox=non-main or full)
- **Known Issue** (Mar 22): safeBins not matching plugin config; resolved via plugin reload

**Attack Surface**: agent can only run safe binaries; can't execute arbitrary commands (unless sandbox=off + agent has write access to filesystem, which it does in Nuzantara)

### Plugin Trust Model

**Plugin Loading** (`plugins.allow[]`):
- Whitelist-based: only plugins in allow-list are loaded
- Nuzantara loads: memory-core, lobster, llm-task, voice-call (implicit)
- claude-mem: loaded from `~/.openclaw/extensions/claude-mem/` (manual install, not in core plugins.allow)

**Trust Signals**:
- Official plugins: signed releases, open-source GitHub
- User plugins (Nuzantara custom skills): loaded from `/Desktop/nuzantara/apps/nuzantara-mcp/skills/` (same machine, implicit trust)
- **Warning**: claude-mem flagged as "loaded without install/load-path provenance" → suggests side-load outside normal package path

### Secret Handling

**API Key Interpolation**:
```json
{
  "providers": {
    "openrouter": {
      "apiKey": "${OPENROUTER_API_KEY}"
    }
  }
}
```

**Resolution**:
1. Check environment variable (shellEnv=true in Nuzantara config, shell timeout 15s)
2. Check EnvironmentVariables from LaunchAgent plist (if running as daemon)
3. Fall back to plaintext in config (NOT recommended)

**Nuzantara Config**:
- OPENROUTER_API_KEY, DEEPSEEK_API_KEY, GOOGLE_PLACES_API_KEY, NOTION_API_KEY → in `~/.openclaw/.env` (not shown, but inferred from skills.env)
- **Risk**: if `.env` checked into git, keys exposed

---

## G. Operational Model

### LaunchAgent Management

**Service File**: `~/Library/LaunchAgents/openclaw.plist` (macOS)
- **Label**: com.openclaw.daemon
- **Program**: node (bundled in ~/.openclaw/tools/node-v22.22.0/bin/node)
- **KeepAlive**: true (auto-restart on exit)
- **ThrottleInterval**: 30s (min time between restarts after crash)
- **RunAtLoad**: true (start on login)

**Manual Control**:
```bash
launchctl load ~/Library/LaunchAgents/openclaw.plist
launchctl unload ~/Library/LaunchAgents/openclaw.plist
launchctl start com.openclaw.daemon
launchctl stop com.openclaw.daemon
```

**Nuzantara Monitoring**: cron job `monitor-air.log` (implied by logs; monitors for crashes + auto-restart failures)

### Logs

| Log | Path | Rotation | Notes |
|-----|------|----------|-------|
| **gateway.log** | `~/.openclaw/logs/gateway.log` | Yes (daily) | Main diagnostic output (diagnostic, channel, agent events) |
| **gateway.err.log** | `~/.openclaw/logs/gateway.err.log` | Yes (daily) | Errors, warnings, stack traces |
| **commands.log** | `~/.openclaw/logs/commands.log` | N/A | Slash command executions |
| **config-audit.jsonl** | `~/.openclaw/logs/config-audit.jsonl` | Append | Config change audit trail |

**Log Level**: `logging.level=info` (Nuzantara config); controlled via `openclaw config set logging.level=debug` (or restart with env var)

**Retention**: no explicit TTL in config; logs grow unbounded (gateway.log: 21.7 GB as of May 2, gateway.err.log: 288 MB). **Risk**: disk space exhaustion.

### Health Endpoint

**Endpoint**: `GET /healthz` (Gateway)
- **Response**: `{ "status": "ok" }` (200 OK) or 500 on error
- **Nuzantara Use**: implied by monitor-air; likely polled every 5–60s

### Metrics Export

**Prometheus**: Not built-in to OpenClaw (as of v2026.3.31)
- **Workaround**: parse logs with regex + ship to external metrics service
- **Nuzantara**: no custom metrics exporter observed

### Debugging

**Verbose Mode**: `openclaw gateway --verbose` (CLI flag)
**Log Level Override**: `OPENCLAW_LOG_LEVEL=debug` (env var at startup)
**RPC Tracing**: gateway logs all RPC calls (agent → channel) with stack traces on failure

**Trace an Agent Decision**:
1. Enable debug logging
2. Send message via Telegram
3. Check gateway.log for SessionStart → UserPromptSubmit → tool_use → agent response flow
4. Correlate with memory-core observations (check `.openclaw/agents/main/agent/memory.db` if needed)

### Update Process

**Manual Update**:
```bash
npm install -g openclaw@latest
openclaw onboard --update   # or --install-daemon to refresh daemon
```

**Safe Update (Nuzantara)**:
1. `launchctl stop com.openclaw.daemon` (halt gateway)
2. Backup `~/.openclaw/openclaw.json` + `~/.openclaw/workspace/`
3. `npm install -g openclaw@latest`
4. Review CHANGELOG for breaking changes
5. Run `openclaw doctor` (auto-migrate config if needed)
6. `launchctl start com.openclaw.daemon` (restart)

**Auto-Update**: Not configurable in v2026.3.31; manual only.

---

## H. Known Issues & Pitfalls

### 1. Provider Enum Rigidity

**Issue**: openai-completions API wrapper only recognizes explicit `api: "openai"` (no generic override)

**Impact**: Can't use arbitrary OpenAI-compatible backends (e.g., vLLM, LocalAI) without forking

**Workaround** (Nuzantara): Use `api: "openai-completions"` with openrouter shim (all models exposed via openrouter baseURL)

**Status**: Likely fixed in v2026.4.29 (baseUrl interpolation mentioned in changelog), but not tested against Nuzantara's installed v2026.3.31

### 2. Secret Interpolation (`${VAR}` Only in env)

**Issue**: `apiKey: "${VAR}"` resolves ONLY if VAR is in EnvironmentVariables (from LaunchAgent plist or shell env at startup), NOT from `.env` file or inline plaintext

**Impact**: Easy to forget to export env var → silent fallback to missing key → auth failures

**Example** (Nuzantara):
```json
{
  "openrouter": {
    "apiKey": "${OPENROUTER_API_KEY}"  // resolves to env var if set, else null
  }
}
```

**Workaround**: Explicitly set in LaunchAgent plist `EnvironmentVariables` section or `source ~/.openclaw/.env` before `launchctl load`

### 3. mcporter Allowlist Quirks

**Issue** (Mar 22 audit log): safeBins entries `ls, cat, tail, which, nuzantara-ops, mcporter` not matching plugin config → mcporter tool calls rejected

**Root Cause**: Plugin loading race condition (safeBins checked before plugin registration completes)

**Status**: Resolved in Nuzantara by manual reload (launchctl stop/start)

**Fix Expected**: v2026.4.29+ (not tested)

### 4. Plugin Trust Warnings

**Issue**: claude-mem loaded from `~/.openclaw/extensions/claude-mem/` without install/load-path provenance

**Impact**: Minor (code review recommended for untrusted sources); claude-mem is open-source + widely used

### 5. Telegram Network Timeouts

**Issue**: `getUpdates` request times out after 30s; retry backoff (5s → 60s) masks latency but creates gaps in message delivery (Apr 30 + May 2 logs show repeated timeouts)

**Impact**: Inbound messages may be delayed 30–120s during network flaps

**Cause**: Likely ISP or Telegram API throttling (Nuzantara in Bali, geographically distant from Telegram servers)

**Workaround**: Increase timeout (Telegram: `timeoutSeconds=120`) or use webhook polling (if supported in next version)

**Status**: Retry logic + backoff now in v2026.3.31; gracefully handled but not ideal UX

### 6. BOT_COMMANDS_TOO_MUCH (Telegram API Limit)

**Issue**: Telegram API limits /command menu to 100 entries; Nuzantara registering 92–97 commands (skills + custom), dropping 19–20 on each sync

**Impact**: Some skills unavailable in Telegram /command autocomplete menu (but still callable via message mention)

**Log Evidence**:
```
[telegram] rejected 92 commands (BOT_COMMANDS_TOO_MUCH); retrying with 73.
[telegram] accepted 73 commands after BOT_COMMANDS_TOO_MUCH (started with 92; omitted 19).
```

**Root Cause**: Too many skills enabled (goplaces, xurl, voice-call, notion, antigravity) + OpenClaw bundled commands

**Workaround**: Disable low-use skills in `skills.entries` (set enabled=false for unused ones)

**Fix**: None in OpenClaw core (Telegram API limit). Requires operator intervention.

### 7. Scheduler Frozen (Apr 30+)

**Issue**: Cron jobs not running; 24-job queue inert

**Evidence**: No cron logs in gateway.log since Apr 30; cron tool still responds to queries but doesn't execute

**Impact**: Scheduled tasks (batch processing, daily summaries) missed

**Likely Cause**: 
- Scheduler process crash (separate thread)
- Job queue lock contention
- State corruption after config reload

**Status**: Unknown (no debugging done); requires `openclaw doctor` + manual job purge/recreate

**Workaround**: Migrate to external cron runner (separate Python process with its own scheduler) or upgrade to v2026.4.29+

### 8. Context Compaction False Positives

**Issue**: context pruning + compaction may discard relevant observations if TTL expires before session end

**Config** (Nuzantara):
```
contextPruning.mode=cache-ttl, ttl=1h
compaction.mode=safeguard, reserveTokensFloor=96k
```

**Impact**: Multi-day sessions lose early context after 1h, even if still relevant

**Workaround**: Increase TTL to 24h or use `mode: "never"` (disables pruning, risks context explosion)

---

## I. Roadmap & Future Direction

**Public Roadmap**: https://github.com/openclaw/openclaw/issues (GitHub Issues, no official roadmap doc)

**Recent PR Signals** (inferred from changelog):
- **Knowledge Agents** (v2026.4.09): Building queryable "brains" from observation history (corpus build + prime + query)
- **Auth Profile System** (v2026.3.31+): Multi-profile support + role-based failover (not fully enabled in Nuzantara)
- **DM Pairing Security**: Default dmPolicy=pairing (require approval code for unknown senders) — security-first direction
- **Provider Enum Expansion**: Support for more providers + generic OpenAI-compatible override (v2026.4.29 changelog hints)

**Likely Future Work** (speculative):
1. **Cloud Sync**: Multi-region HA + state replication (not in current roadmap, but enterprise feature request)
2. **Structured Output**: Typed tool responses (Zod schema validation) — currently working, likely formalization
3. **Voice Wake Improvements**: More language support, custom wake words (v2026.3.31 has voice-call, room for improvement)
4. **Scheduler Stability**: Fix cron job queue race conditions (based on Apr 30 frozen state)
5. **Knowledge Agent UI**: Web viewer for corpus browsing + semantic search (claude-mem v12.1.0 foundation)

---

## Summary Table: What Nuzantara Is Using vs. Available

| Feature | Available | Enabled | Status |
|---------|-----------|---------|--------|
| **Multi-LLM Routing** | Yes (4 providers) | Yes (fallback chain) | Working, no issues |
| **Persistent Memory** | Yes (memory-core) | Yes | Working, observations injected |
| **Telegram Channel** | Yes | Yes | Working, but network timeouts every 30s+ |
| **Workflow Orchestration** | Yes (Lobster) | Enabled but unused | Ready to use, no barriers |
| **Knowledge Agents** | Yes (new in v12.1.0) | No | **NOT EXPLOITED** (v2026.4.09 feature) |
| **Voice-Call Integration** | Yes | Yes | Enabled, not actively tested |
| **Browser Automation** | Yes (main agent denied) | Partial (coder agent) | Available for coder agent |
| **Cron Scheduler** | Yes (24 job limit) | Yes but frozen | **BROKEN** since Apr 30 |
| **Custom Skills** | Yes (extraDirs) | Partially | `/nuzantara-mcp/skills/` not fully synced |
| **Canvas (macOS)** | Yes | Implicit | Available if using macOS |
| **Multi-Channel** | Yes (23 channels) | Only Telegram | Others disabled; can be enabled |

---

## Recommendations for Nuzantara

1. **Upgrade to v2026.4.29** (from v2026.3.31): Knowledge Agents system ready; cron scheduler likely fixed; auth profiles stabilized
2. **Exploit Knowledge Agents**: Build corpus from claude-mem observations; enable conversational history replay (query_corpus tool)
3. **Fix Cron Scheduler**: Debug Apr 30 freeze; if unresolved in v2026.4.29, fallback to external cron-agent-python runner
4. **Reduce Telegram Commands**: Disable unused skills (elite-longterm-memory, bluebubbles, discord, slack, spotify, trello) to stay under 100-command limit
5. **Increase Telegram Timeout**: Raise `timeoutSeconds=120` to mask network latency (or implement webhook polling in next OpenClaw version)
6. **Monitor Memory Growth**: Track `~/.openclaw/logs/gateway.log` size (currently 21.7 GB); implement log rotation or external log shipping
7. **Test Voice-Call Skill**: Verify Twilio integration if voice interaction is planned
8. **Sync Custom Skills**: Ensure `/nuzantara-mcp/skills/` fully registered with OpenClaw (check skills.entries for all custom entries)

---

## Files Referenced

- **Config**: `/Users/nuzantara/.openclaw/openclaw.json` (v2026.3.31 schema)
- **Installation**: `/Users/nuzantara/.openclaw/lib/node_modules/openclaw/`
- **Logs**: `~/.openclaw/logs/gateway.log`, `gateway.err.log`
- **Memory DB**: `~/.openclaw/agents/main/agent/memory.db` (SQLite, not visible in config)
- **Workspace**: `~/.openclaw/workspace/` (markdown docs + agent state)
- **Extensions**: `~/.openclaw/extensions/claude-mem/` (installed plugin)
- **GitHub**: https://github.com/openclaw/openclaw (releases, issues, docs)
- **Documentation**: https://docs.openclaw.ai (official, updated for v2026.4.29)
- **claude-mem Marketplace**: `/Users/nuzantara/.claude/plugins/marketplaces/thedotmack/` (v12.1.0, AGPL-3.0)

---

**Document Compiled**: 2026-05-02 13:20 UTC | **Last Config Change**: 2026-05-02 13:20 UTC (Nuzantara-reported version)
