---
date: 2026-05-18
domain: wr3-design
step: 6
title: Architettura + skeleton code WR3 (NOT LangGraph — Claude Agent SDK)
panel: Gemini 3.1 Pro + Codex GPT-5.5 + NB-AGENTS
deepseek: killed by user (Step 3 onwards)
panel_convergence: Plan B (LangGraph) REJECT 3/3 UNANIMOUS
critical_findings: 2 (skeleton path wrong, outbox auto-ack flaw)
---

# WR3 Step 6 — Architettura + skeleton code

## Decisione architetturale principale: REJECT LangGraph

**Plan B (LangGraph) REJECT 3/3 panel UNANIMOUS.**

Rationale convergente:

- LangGraph ~200MB sub-deps, new state paradigm, viola "reuse proven patterns" (Symbiosis Law 8 passato)
- WR2 shippato pattern (Claude Agent SDK + Python event-bus + PG NOTIFY) è proven, deterministic, low-dep
- Cascade fallback hot-path (Step 5 Law 1) richiede subprocess control fine, non in-process LLM calls (LangGraph default)
- Cost ceiling enforcement nativo via `ClaudeAgentOptions.max_budget_usd` (Codex+NB-AGENTS catch)

**Plan A (Claude Agent SDK + Python event-bus) confermato.** Ma rivisto con 2 critical corrections.

## Critical findings (panel)

### Finding 1 — Skeleton location SBAGLIATA (NB-AGENTS catch)

**Mio errore originale:** ho proposto `apps/wr3-room/` come nuovo monorepo dir.

**Realtà filesystem (verificata):**

```
~/.claude/agents/wr2-*.md          (8 agent definitions)
~/.claude/skills/bali-zero-brand/  (skill cortex)
scripts/wr2_*.py                   (20+ Python modules per WR2)
scripts/wr2_supervisor.py          (orchestrator equivalent)
scripts/wr2_flowkit_client.py      (Veo gateway)
apps/war-room/                     (output + venv, NOT primary code location)
apps/war-room/output/queue/        (human-review-queue.json)
apps/war-room/output/carousel/<slug>/  (per-episode artifacts)
```

**Corretto pattern WR3:**

```
~/.claude/agents/wr3-*.md          (13 agent definitions — git in ~/.claude/)
~/.claude/skills/bali-zero-brand/wr3/  (WR3 skill cortex sotto brand cortex shared)
scripts/wr3_*.py                   (Python modules)
scripts/wr3_supervisor.py          (orchestrator/event-bus consumer)
scripts/wr3_flowkit_client.py      (Veo Fast Tier_ONE gateway reuse pattern)
apps/war-room/output/episode/<slug>/   (per-episode artifacts — share parent dir with WR2 carousel/)
apps/war-room/output/queue/wr3-human-review-queue.json  (separate WR3 queue)
```

NO new app dir. WR3 vive sotto `scripts/` (executors) + `apps/war-room/output/episode/` (artifacts) + `~/.claude/agents/wr3-*` (definitions) + `~/.claude/skills/bali-zero-brand/wr3/` (cortex).

### Finding 2 — Outbox auto-ack flaw (NB-AGENTS catch da cicatrix)

**Cicatrix scar existing** (EventBus Phase 1 PR #342): `replay_unconsumed` auto-ack BEFORE handler completes. Handler crash = event marked consumed = silent drop.

**Implicazione WR3:** se `wr3-post-assembler` ffmpeg crash mid-render, event `wr3_episode_assembly_ready` viene auto-acked, retry impossibile.

**Fix obbligatorio:** WR3 deve implementare **explicit per-handler ack** in `scripts/wr3_supervisor.py` consumer:

```python
async def route_event(conn, pid, channel, payload):
    event = json.loads(payload)
    outbox_id = event["_outbox_id"]
    try:
        await dispatch_agent(channel, event)
        await outbox.acknowledge(conn, outbox_id)  # ACK only on success
    except Exception as e:
        await emit_telemetry(channel, "FAIL", str(e))
        if is_hot_path(channel):
            await telegram_p0(f"WR3 {channel} handler crashed: {e}")
        raise  # do NOT ack — event replays on reconnect
```

Cicatrix scar entry pre-existing — Phase 3 (per-handler ack + pruning cron) era già marked "pending". WR3 deve essere il driver per chiudere Phase 3.

## Convergenze 3/3 (panel UNANIMOUS verdicts)

| #   | Q                        | Verdict                                                                                         | Source                 |
| --- | ------------------------ | ----------------------------------------------------------------------------------------------- | ---------------------- |
| Q1  | Plan A vs Plan B         | **REJECT Plan B**, KEEP Plan A                                                                  | Gemini+Codex+NB-AGENTS |
| Q2  | Orchestrator split-brain | **KEEP** (semantic router pattern)                                                              | Gemini+Codex+NB-AGENTS |
| Q6  | Cost ceiling violation   | **MODIFY**: cascade lower-tier FIRST, hard halt last resort                                     | Gemini+Codex+NB-AGENTS |
| Q7  | Telemetry namespacing    | **MODIFY**: inject `room: wr3` field in JSONL (cell_pulse_observed shared with WR2/mata-garuda) | Gemini+Codex+NB-AGENTS |
| Q10 | Pilot v0→v1 transition   | **MODIFY**: **3 consecutive successes** (rule of 3, not 1 fluke)                                | Gemini+Codex+NB-AGENTS |

## Convergenze 2-vs-1 con clarification

| #   | Q                               | Decision                                                                                                                                                                                                                                                          |
| --- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q3  | Cost estimation pre-call        | **MODIFY** — Gemini propose char_count/4 heuristic; Codex+NB-AGENTS propose **Claude Agent SDK `ClaudeAgentOptions.max_budget_usd`** native field. **Winner: SDK native** (2/3) — cleaner, no heuristic guesswork.                                                |
| Q4  | Subagent invocation from Python | **MODIFY** — Gemini propose wrapping `claude --print` + Agent tool prompt; Codex+NB-AGENTS propose **`query(prompt, options=ClaudeAgentOptions(agent="<name>"))`** native Python SDK. **Winner: SDK native** — already a subprocess wrapper compliant with Law 1. |
| Q5  | Migration numbering             | **MODIFY** — Gemini propose 178 integer; **NB-AGENTS catches**: hallucinated 177 — must query `schema_migrations` empirically (NOT `_schema_versions` per existing cicatrix scar). **Verified empirically 2026-05-18: last applied = 181, WR3 migration = 182.**  |
| Q8  | Skeleton location               | **MODIFY** — Gemini approve `apps/wr3-room/`; NB-AGENTS catches real WR2 path `apps/war-room/` + `scripts/wr2_*.py` + `~/.claude/agents/wr2-*.md`. **Winner: NB-AGENTS** (ground truth from filesystem).                                                          |
| Q9  | Test strategy gaps              | **MODIFY** — both Gemini and Codex flag missing tests: **concurrent episodes** (Gemini) + **cascade fallback** + **300s watchdog timeout** (Codex). Add all 3 to test plan.                                                                                       |

## Critical Claude Agent SDK clarification (3 panel convergent)

**Mio draft errore:** ho assunto necessario raw subprocess `claude --print --agent <name>` wrapped manually.

**Realtà (NB-AGENTS authoritative + Codex confirm):** Claude Agent SDK Python è **già un wrapper subprocess** compliant Law 1.

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async def dispatch_brief_interpreter(brief_topic: str):
    async for message in query(
        prompt=f"Analyze topic: {brief_topic}",
        options=ClaudeAgentOptions(
            agent="wr3-brief-interpreter",
            max_budget_usd=0.15,  # text_planning ceiling
            timeout_ms=300000,    # 300s hard timeout (Codex Q9 missing test)
            allowed_tools=["Read", "Glob", "Grep", "Bash", "WebFetch"],
        ),
    ):
        if hasattr(message, "result"):
            return message.result
```

**Note 2026-06-15 (NB-AGENTS citation 20):** Agent SDK on subscription plans starts drawing from **separate monthly Agent SDK credit** (distinct from interactive limits). To monitor before WR3 hits production scale.

## Final architecture (post-panel)

### File structure (corretta)

```
~/.claude/agents/                       # 13 WR3 agent definitions
├── wr3-design-architect.md
├── wr3-brief-interpreter.md
├── wr3-script-editor.md
├── wr3-shot-director.md
├── wr3-pre-render-gatekeeper.md
├── wr3-clip-renderer.md
├── wr3-audio-asset-producer.md
├── wr3-post-assembler.md
├── wr3-critic.md
├── wr3-reflexion-synth.md
├── wr3-yt-metrics-analyst.md
├── wr3-editorial-bench.md
└── wr3-b-roll-curator.md

~/.claude/skills/bali-zero-brand/wr3/   # WR3 skill cortex (under shared brand cortex)
├── design-architect/
├── brief-interpreter/
│   ├── SKILL.md
│   ├── nb-routing-domain-map.md
│   └── legal-claim-extraction-templates.md
├── script-editor/
├── ... (1 dir per agent)
├── _proposed/                          # New skills awaiting graduation
├── _archived/
├── _quarantine/
├── _voyager-curriculum.md
└── _reflexion-synthesis.py             # Mirror existing WR2 cron pattern

~/Desktop/nuzantara/scripts/            # Python executors (mirror WR2 pattern)
├── wr3_supervisor.py                   # Event-bus consumer (orchestrator/Python coord layer)
├── wr3_flowkit_client.py               # Veo Fast Tier_ONE via Flow UI Pro gateway
├── wr3_chatterbox_runner.py            # Local Chatterbox TTS (Emma seed=42 locked)
├── wr3_ffmpeg_wrapper.py               # /tmp/ffmpeg-full/ffmpeg evermeet static
├── wr3_arcface_verify.py               # Identity gate (insightface lib)
├── wr3_nlm_subprocess.py               # NB queries via CLI (Law 1)
├── wr3_dispatch_agent.py               # Claude Agent SDK wrapper (cost ceiling + cascade)
├── wr3_telemetry.py                    # JSONL emit helper (Law 7)
├── wr3_episode_manifest.py             # 18-field manifest builder
├── wr3_smoke_test.py                   # Pilot Manifesto end-to-end test
├── tests/
│   ├── test_wr3_supervisor.py
│   ├── test_wr3_contracts.py
│   ├── test_wr3_cost_ceiling.py
│   ├── test_wr3_idempotence.py
│   ├── test_wr3_outbox_explicit_ack.py
│   ├── test_wr3_outbox_replay.py
│   ├── test_wr3_full_episode_e2e.py
│   ├── test_wr3_critic_gate_retry.py
│   ├── test_wr3_concurrent_episodes.py
│   ├── test_wr3_cascade_fallback.py
│   └── test_wr3_watchdog_timeout.py
└── lint/
    ├── wr3_lint_cli_only.py
    ├── wr3_lint_osint_boundary.py
    ├── wr3_lint_cloud_dependency.py
    ├── wr3_lint_autonomous_publish.py
    ├── wr3_lint_telemetry_completeness.py
    └── wr3_lint_skill_versioning.py

~/Desktop/nuzantara/apps/war-room/output/  # Artifacts
├── episode/<slug>/                     # Per-episode dir
│   ├── brief.json
│   ├── script.json
│   ├── shot-pack.json
│   ├── clips/<n>.mp4
│   ├── audio/vo.wav + music.wav
│   ├── master.mp4
│   ├── variants/{tiktok,ig-reels,yt-shorts,fb}.mp4
│   ├── episode_manifest.json           # 18 fields
│   ├── critic-report.json
│   └── lessons.md
└── queue/
    └── wr3-human-review-queue.json

~/Desktop/nuzantara/apps/backend-rag/backend/db/migrations_v2/
└── 182_wr3_eventbus_channels.sql

~/Desktop/nuzantara/docs/wr3/
├── contracts/                          # YAML I/O contracts per agent
│   ├── _schema.yaml                    # Meta-schema
│   ├── brief-interpreter.yaml
│   └── ... (1 per agent)
├── symbiosis-precedence.md             # Law 2 > Law 5 > Law 7 > Law 4 doctrine
└── runbook-supervisor.md
```

### Episode lifecycle (6 channels post-Step 5 consolidation)

```
Antonello/Damar request → PG NOTIFY wr3_episode_brief_requested
                              ↓
                          wr3_supervisor.py consumer
                              ↓
                  dispatch_agent("wr3-brief-interpreter", ...)
                  via Claude Agent SDK query() + max_budget_usd=0.15
                              ↓
                  (sanitize NB source_ids — Law 2)
                              ↓
                          legal_claim_gate
                              ↓ PASS
                  PG NOTIFY wr3_episode_pre_render_ready
                              ↓
                          consumer fanout
                  ┌──────────┴──────────┐
                  ↓ parallel             ↓ parallel
        wr3-script-editor      wr3-audio-asset-producer
        (Sonnet, $0.15)        (Sonnet, $0.05)
                  ↓
        wr3-shot-director      [Chatterbox local]
        (Opus, $0.50)              ↓
                  ↓                  ↓
        wr3-pre-render-gate         (VO ready)
        (Sonnet, $0.10)             ↓
                  ↓ PASS              │
        PG NOTIFY gate_passed        │
                  ↓                  │
        wr3-clip-renderer            │
        (Sonnet, 200cr Flow Pro)     │
                  ↓                  │
        (12 MP4 clips ready)         │
                  └──────────┬───────┘
                  ↓ both ready
        PG NOTIFY assembly_ready
                  ↓
        wr3-post-assembler (Python-first + Sonnet diagnostic, $0.10)
                  ↓
        master.mp4 + variants/{4} + episode_manifest.json
                  ↓
        wr3-critic (Opus + Haiku VLM pre-pass, $0.50)
                  ↓
        PG NOTIFY critic_verdict (PASS|FAIL payload)
                  ↓
            ┌─────┴─────┐
            ↓ PASS      ↓ FAIL (per lane)
   PG NOTIFY staged    orchestrator routes retry:
            ↓           lane 1 → wr3-shot-director
   Drive staging        lane 2 → wr3-post-assembler
   Telegram P0          lane 3 → wr3-script-editor
            ↓           lane 4 → wr3-brief-interpreter
   Antonello/Damar
   manual publish
```

### Cost ceiling enforcement (Q3 + Q6 + Symbiosis precedence)

```python
async def dispatch_agent(agent_name: str, prompt: str):
    contract = load_contract(agent_name)
    is_hot_path = contract["lifecycle_tier"] == "core"
    is_gate = agent_name in ("wr3-design-architect", "wr3-pre-render-gatekeeper")

    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                agent=agent_name,
                max_budget_usd=contract["cost"]["ceiling_usd"],
                timeout_ms=300000,
                allowed_tools=contract["allowed_tools"],
            ),
        ):
            if hasattr(message, "result"):
                return message.result
    except BudgetExceededError:
        if is_gate:
            await telegram_p0(f"{agent_name}: cost ceiling hit. Episode HALTED.")
            raise HardHaltException(agent_name)
        if is_hot_path:
            return await cascade_to_gemini(agent_name, prompt)
        return await mark_failed_for_next_cycle(agent_name)
```

### Telemetry (Q7 — room namespace)

```python
def emit(agent: str, episode_id: str, **fields):
    line = {
        "ts": utcnow_isoformat(),
        "room": "wr3",                     # Mandatory namespace
        "agent": agent,
        "episode_id": episode_id,
        "duration_ms": fields.get("duration_ms"),
        "cost_usd": fields.get("cost_usd"),
        "outcome": fields["outcome"],
        "retry_count": fields.get("retry_count", 0),
        "critic_lane": fields.get("critic_lane"),
        "contract_version": fields.get("contract_version"),
    }
    path = Path.home() / ".cell-observatory/wr3" / f"{agent}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(line) + "\n")
```

### Migration N=182 (Q5 verified empirically)

Last applied migration on disk = 181 (`crm_guardian_file_content_cache.sql`). WR3 N=182. **NEVER query `_schema_versions`** (legacy, cicatrix scar) — query `schema_migrations` for authoritative apply state on Fly PG.

### Explicit per-handler ack (Finding 2 — closes EventBus Phase 3)

```python
async def route_event(conn, pid, channel, payload):
    event = json.loads(payload)
    outbox_id = event.get("_outbox_id")
    episode_id = event["episode_id"]

    start_ts = time.time()
    try:
        if channel == "wr3_episode_brief_requested":
            result = await dispatch_brief_interpreter(episode_id, event)
        elif channel == "wr3_episode_pre_render_ready":
            result = await asyncio.gather(
                dispatch_shot_director(episode_id),
                dispatch_audio_producer(episode_id),
            )
        # ... etc

        await outbox.acknowledge(conn, outbox_id)  # ACK ONLY on success

        wr3_telemetry.emit(
            agent=AGENT_FOR_CHANNEL[channel],
            episode_id=episode_id,
            duration_ms=int((time.time() - start_ts) * 1000),
            outcome="PASS",
        )
    except Exception as e:
        wr3_telemetry.emit(
            agent=AGENT_FOR_CHANNEL[channel],
            episode_id=episode_id,
            duration_ms=int((time.time() - start_ts) * 1000),
            outcome="FAIL",
            error=str(e),
        )
        if channel in HOT_PATH_CHANNELS:
            await telegram_p0(f"WR3 {channel} handler crashed: {e}")
        raise  # do NOT ack — event replays on reconnect
```

## Pilot Manifesto Zantara success criteria (Q10 — rule of 3)

| Metric                     | Target                          | Hard fail if                                |
| -------------------------- | ------------------------------- | ------------------------------------------- |
| End-to-end latency         | ≤45 min                         | >75 min                                     |
| Total cost cash equivalent | ≤$0.50 (~120 cr Flow Pro + LLM) | >$2                                         |
| Critic 4 lanes verdict     | PASS all 4                      | Any FAIL after 2 retry rounds               |
| ArcFace cosine identity    | ≥0.6 avg over 12 clips          | <0.55 in any single clip                    |
| Manifest fields complete   | 18/18                           | Any missing                                 |
| Silent placeholder count   | 0                               | ≥1 (would violate Law 4 degrade-loud)       |
| Designer override diff     | Empty/null                      | Any field modified by Antonello pre-publish |

**v0 → v1 transition: 3 consecutive successes** (rule of 3).

## Open questions per Antonello (decision gate)

1. **REJECT LangGraph confermo**: 3/3 panel converge no Plan B. Plan A definitivo? → CONFIRMED user 2026-05-18 "seguo il panel"
2. **Skeleton path corretto**: scripts/ + ~/.claude/agents/ + apps/war-room/output/episode/. NO new `apps/wr3-room/`. Confermi? → CONFIRMED
3. **Claude Agent SDK adoption**: usiamo `claude_agent_sdk.query()` con `ClaudeAgentOptions(max_budget_usd=...)` native — NOT raw subprocess. SDK è wrapper Law 1 compliant. → CONFIRMED
4. **Outbox explicit ack**: WR3 chiude EventBus Phase 3 (per-handler ack). → CONFIRMED
5. **Migration N empirico**: 182 verified via ls migrations_v2/ → CONFIRMED
6. **Test concurrent_episodes + cascade_fallback + watchdog_timeout** add a Step 7 → CONFIRMED
7. **Pilot manifest "Manifesto Zantara"** confermo come primo pilot → CONFIRMED
8. **Rule of 3 → v1**: 3 consecutive pilot pass → CONFIRMED
9. **Cost class allocation final**:
   - text_planning $0.15: brief/script/gatekeeper/b-roll/post-assembler-diag
   - reasoning $0.50: shot-director/critic/design-architect
   - render plan-aware: clip-renderer (200 cr/episode Flow Pro)
   - audio_gen $0.05 local: audio-asset-producer → CONFIRMED
10. **Step 7 pilot execution sequence**: migration → 13 agents → scripts → tests → pilot → CONFIRMED

## Next step (Step 7 — Pilot Manifesto Zantara via WR3 v0)

Sequenza esecuzione:

1. PR migration `182_wr3_eventbus_channels.sql` + outbox explicit-ack test
2. 13 commits (1 PR `wr3-room-genesis`): agent `.md` + skill cortex stub + I/O contract YAML + smoke test fixture + memory seed per agent
3. `scripts/wr3_*.py` Python modules (supervisor, dispatch, telemetry, lint)
4. Smoke pilot "Manifesto Zantara": topic + brief request → end-to-end episode
5. Critic gate → staged → Antonello review
6. Telegram P0 + manifest
7. v0 declared production-ready after 3 consecutive pilots PASS (rule of 3)

## Sources

| Panel          | LLM                             | Bytes                      | Quality                                                                                                                                    |
| -------------- | ------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Gemini 3.1 Pro | gemini-3.1-pro-preview          | 3877                       | terse, KEEP/MODIFY/REJECT per Q, 2 critical flaw noted (Law 1 env var, ffmpeg injection)                                                   |
| Codex GPT-5.5  | gpt-5.5 xhigh                   | 4938 (30KB inc. exec logs) | thorough, ran filesystem checks (WR2 path, schema_migrations cicatrix)                                                                     |
| NB-AGENTS      | NotebookLM RAG                  | 4500                       | **best architectural verdict** — cites Claude Agent SDK native pattern, ground truth WR2 paths, catches outbox auto-ack flaw from cicatrix |
| DeepSeek       | KILLED by user (Step 3 onwards) | —                          | —                                                                                                                                          |

**Strongest panel disagreement neutralized:** my draft Plan A skeleton location was wrong (would create orphan dir). NB-AGENTS catch via direct filesystem grep prevents architectural drift before any code written. Codex + NB-AGENTS converge on Claude Agent SDK native usage — avoids reinventing subprocess wrapper that already exists Law 1 compliant.

**Critical contribution NB-AGENTS:** outbox auto-ack flaw catch from existing cicatrix scar (EventBus Phase 1 PR #342). Without this catch, WR3 ffmpeg crashes would silently drop episode state. Phase 3 implementation in WR3 closes the cicatrix at the same time.
