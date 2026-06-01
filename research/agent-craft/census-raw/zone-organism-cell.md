# Agentic Census — Zone ORGANISM + INTELLIGENCE

> **Method**: read of REAL CODE on disk + empirical process/Redis/log state (read-only). NOT docs, NOT memory.
> **Machine**: Pro (`hostname=Nuzantara`, `whoami=nuzantara`) — the workhorse where these daemons actually run. M5 is thin-client; verification done here on Pro.
> **Date**: 2026-06-02 ~02:00 WITA
> **Auditor**: general-purpose subagent (organism-agentic-census worktree)
> **Scope**: `apps/cell`, `apps/organism`, `apps/mata-garuda`, `apps/war-room`, `apps/cell-observatory-collector`, `apps/crm-cell` + shared lib `packages/cell-core`

---

## Macro-architecture (as built, not as documented)

```
                          ┌──────────────────────────────────────────┐
                          │  packages/cell-core  (SHARED LIBRARY)      │
                          │  pulse · genome · homeostasis · memory_sqlite
                          │  hgt (Horizontal Gene Transfer) · observatory
                          │  lifecycle · safety · reasoner · sensors    │
                          └──────────────┬───────────────┬─────────────┘
                                         │ imports        │ imports
                  ┌──────────────────────┘                └────────────────────┐
                  ▼                                                             ▼
        apps/cell  (THE organism)                              apps/mata-garuda (OSINT/intel)
        cell.main → PulseEngine                                sentinel_cell (cell-core PulseLoop)
        sense→think→act→reflect→dream                          + 31 agents (harvesters)
        emits cell_pulse + cell_pulse_observed                 + task_consumer + runtime loop
                  │                                                   │
                  │ cell_pulse_observed (PG NOTIFY + Redis XADD)      │ garuda:raw/enriched/digest/alerts
                  ▼                                                   ▼
        organism.supervisor.daemon  ◄── organism:events Redis stream ◄── all organs emit here
        (consumes, decides, dispatches)                        intel-dedup-gateway (HOME) dedups
                  │
                  ▼ (W1: defer-only, shadow mode)
        organism actuators (13) — NOT firing (shadow)
```

**Three observation/intelligence planes, all real:**
1. **Cell** = single self-model organism that watches Bali Zero prod infra (Fly, Qdrant, Vercel, cron, backups) and reasons about its own health.
2. **Organism supervisor** = stateless event-driven incident responder (consumes `organism:events`, decides via YAML rules / LLM tiers, dispatches actuators). Currently observation-only.
3. **Mata Garuda** = OSINT/intel harvesting swarm (31 agents) feeding `garuda:*` Redis streams → KG + NotebookLM + Telegram.

---

## Component Census

| name | kind | status | evidence (empirical, this audit) | macro_group |
|---|---|---|---|---|
| **cell.main / PulseEngine** | organism daemon (pulse loop) | **OPERATIVO (but perpetually RED)** | PID 9380 alive since Sat 09AM; `~/.organism/events/cell.jsonl` last pulse #2960 @ 2026-06-01T17:53Z; `organism.stderr.log` 38MB live. Health=red driven by `error_rate.errors_5min=4` + `cron.failed_jobs=[fly_pg_backup]`. RED is a **real benign signal**, not a crash. | cell |
| **cell.cortex (Cortex orchestrator)** | cognitive layer (6 components) | **OPERATIVO** | `cortex.py` wires critic/curiosity/goals/strategy_mutator/skill_library, lifecycle-gated. Log shows `Critic LLM returned ... Registered expectation 16868 (pulse 2960)`, `PatternIndex HIT similarity=0.9744`. Active every pulse. | cell |
| **cell.cortex.critic (CriticAgent)** | self-evaluation agent | **OPERATIVO** | Live log pulse 2960: registers + evaluates expectations via Ollama (`POST 127.0.0.1:11434/api/chat 200`). NOTE: emits `Critic LLM returned no JSON object` warnings — partial JSON-parse degradation, non-fatal. | cell |
| **cell.cortex.goal_generator / curiosity_engine / strategy_mutator** | autonomy agents | **INCERTO (phase-gated, likely dormant)** | Code present + wired. Activation gated on `LifecyclePhase` (GIOVANE+ for goals/curiosity, ADULTO+ for mutator). No direct log evidence of goal/mutation emission this audit — needs lifecycle-phase check. Files real, invocation conditional. | cell |
| **cell.slow.reasoner (SlowReasoner)** | Tier-0/1 local LLM reasoner | **OPERATIVO** | Reads `MODEL_TOPOLOGY.json` for Pro models; log shows tier -1 PatternIndex reuse (cheaper than LLM call). Ollama reachable (`/api/tags 200`, 3 models loaded). | cell |
| **cell.memory (episodic/LTM/STM/dreamer/pattern_index)** | memory subsystem | **OPERATIVO** | Log: `Episode stored: id=44204`, `PatternIndex HIT ... patterns=41`. Episodic DB growing (44k episodes). | cell |
| **cell sensors (17)** | health probes | **OPERATIVO** | db/qdrant/error_rate/ollama/backup/cron/vercel/health/outbox all returning live readings in pulse log. `qdrant` returns `None` collections (Qdrant sensor reading null — minor). | cell |
| **cell effectors (fly/local/logs/nlm/telegram + allowlist)** | actuators | **INCERTO (present, low-trigger)** | 5 effectors + allowlist.py present. Cell health=red→action=`check_health` (read-only) every pulse; no destructive effector observed firing. Allowlist-gated by design (`safety.py`). | cell |
| **OutboxSensor (cell_pulse_observed emit)** | bridge to observatory/supervisor | **OPERATIVO** | `CELL_OBSERVATORY_EMIT=true` in `apps/cell/.env`; `cell_pulse_observed` events ARE reaching `organism:events` (supervisor correlation_id 40630, stream XLEN 92419). **CONTRADICTS cicatrix/memory `discovery_cell_pulse_observed_gate_off_2026_05_22`** — gate is now ON. | cell |
| **organism.supervisor.daemon** | stateless incident responder | **OPERATIVO but OBSERVATION-ONLY** | PID 1016 alive; consumer group `organism-supervisor` lag=0, 92419 entries read, 0 pending. BUT: `~/.agent/supervisor/active.flag` MISSING → **shadow_mode=True** → every decision is `defer_to_human` / `deferred_defer_actuator` (verified in `~/logs/organism/decisions.jsonl` last 3 entries). Never actuates. | Symbiosis-organism |
| **organism.supervisor.decider (Decider)** | decision router | **OPERATIVO but W1-CRIPPLED** | `decider.py` line 42-49: only L0 YAML; if no rule → `defer_to_human`, comment `"W1: LLM tiers disabled"`. L1/L2/L3 NOT wired into decide(). | Symbiosis-organism |
| **organism.supervisor.claude_brain / ollama_classifier / consiglio_gate** | L1/L2/L3 LLM tiers | **MAI_USATO (code exists, unwired)** | Files present in `supervisor/` but `Decider.decide()` never calls them (W1 fallback short-circuits). Dead-but-present until W2 activation. | Symbiosis-organism |
| **organism actuators (13)** | repair effectors | **INCERTO (registered, never dispatched in shadow)** | 13 actuators (`fly_machines_restart/start`, `restart_agent`, `cleanup_log/cache/branches/zombie_plist`, `quarantine`, `adopt_module`, `consolidate_redundancy`, `notify_telegram`, `propose_yaml_rule`, `python_env_repair`). `build_actuator_registry` is called but dispatcher runs DRY in shadow → none invoked. Code real, runtime inert. | Symbiosis-organism |
| **organism.scheduled_tick** | hourly cron event emitter | **OPERATIVO (presumed)** | Emits `scheduled_tick` to organism bus hourly. `com.nuzantara.organism.scheduled-tick` loaded. Feeds time-based L0 rules. | Symbiosis-organism |
| **organism.control_panel** | TUI/status surface | **ROTTO** | `com.nuzantara.organism.control-panel` LastExitStatus=256 (crash). Not blocking organism (cosmetic/diagnostic surface). | Symbiosis-organism |
| **pg-organism-bridge** | PG→organism event bridge | **OPERATIVO** | `com.nuzantara.pg-organism-bridge` PID 1004, LastExitStatus=0. (HOME-script bridge, not in these app dirs but part of organism nervous system.) | Symbiosis-organism |
| **cell-observatory-collector (REPO)** | pulse-event collector + classifier API | **🔴 ROTTO — HARD CRASH-LOOP** | `com.nuzantara.cell-observatory` LastExitStatus=256, restarting every ~10s. `collector.err.log` = **97MB** of identical stack traces. Root cause (read in `config.py:27-35`): `RuntimeError: OPENROUTER_API_KEY or MINIMAXM2_API_KEY or MINIMAX_API_KEY required` — collector hard-requires a MiniMax/OpenRouter classifier key that isn't in `~/.nuzantara-secrets.env`. Has NEVER started successfully in current config. | cell |
| **observatory HOME-fork (`~/agents/.observatory/`)** | parallel observatory impl | **OPERATIVO (the one actually working)** | `com.balizero.observatory{,-server,-export}` (3 plists) → `~/agents/.observatory/observatory.py` (133 lines, **DIFFERENT file** from repo — md5 mismatch). PIDs 1046+1022 alive; writes `~/logs/cell-observatory/data.json` + `heartbeats.json` FRESH @ 2026-06-01T17:53. **DUPLICATO / split-brain with repo collector (W50/W51/W52 HOME-fork family).** | cell |
| **mata_garuda sentinel_cell (AI-Intel-Sentinel)** | living cell (cell-core PulseLoop) | **OPERATIVO (data fresh) — but dual-runner confusion** | `data/sentinel_cell.db` + `knowledge.db` updated 2026-06-02 00:55. BUT `com.matagaruda.sentinel.hourly` log (`ai-intel-sentinel.log`) STALE since 2026-05-22 (exit=0). The live runner is `com.balizero.research-sentinel` PID 1050. **Two sentinel launchd labels, ambiguous ownership.** | mata-garuda |
| **mata_garuda agents (31 .py)** | OSINT harvesters | **MIXED — infra live, many log_only/scaffold** | 31 agent modules (arxiv/bkpm/imigrasi/kemlu/kemkumham/lhkpn/reddit/youtube/github harvesters + regulation_watcher + wr2_bridge_publisher + ...). Live cron-fed: `garuda:raw`=3655, `garuda:enriched`=4539 entries. Latest `garuda:raw` entry is a YouTube paper-analysis (arxiv/youtube harvesters working). | mata-garuda / OSINT-intel |
| **mata_garuda task_consumer** | gap→agent dispatcher | **OPERATIVO but NO-OP (scaffold)** | `task_consumer.py` DISPATCH_TABLE is **100% `log_only`** (lines 51-61). Every gap_type/attribute maps to "future agent" that doesn't exist yet (NIP Finder, LHKPN scraper, profile refresher all marked `(future)`). Consumer runs (`matagaruda-gap-consumer.log` @ 2026-06-02 01:46) but only logs, never dispatches an agent. | mata-garuda / OSINT-intel |
| **mata_garuda classifier-worker** | intel classification | **OPERATIVO** | `matagaruda-classifier-worker.log` @ 2026-06-02 01:55 (minutes before audit). `com.matagaruda.classifier.adaptive` + `com.nuzantara.sentinel-aggregate`. | OSINT-intel |
| **mata_garuda NER worker / normalizer** | entity extraction | **OPERATIVO** | `matagaruda-ner-worker.log` @ 2026-06-02 01:55. `com.matagaruda.ner.adaptive` loaded. (Repairs from archived W-series scars held.) | OSINT-intel |
| **mata_garuda kg-linker** | KG edge builder | **INCERTO / DEGRADED** | `run_kg_linker.py` present; `com.matagaruda.kg-linker` loaded. BUT KG SQLite `~/.agent/mata-garuda/kg.db` STALE @ 2026-05-29 and near-empty (`kg_entities:2, kg_relations:0, kg_observations:3`). **Consistent with the NB-INTEL degradation claim direction** — KG enrichment effectively idle. | mata-garuda |
| **mata_garuda intel-dedup-gateway (HOME)** | active-active dedup | **OPERATIVO (the W57-era antibody)** | PID 1039; `intel-dedup-gateway.log` @ 2026-06-02 01:43 actively logging `DUPLICATE event=... (total dup=3/3)`. This is the live mitigation for the "12+1 active-active" scar. Has intermittent `xreadgroup Timeout reading from socket` errors. | OSINT-intel |
| **mata_garuda wr2_bridge_publisher / wr_topic_agent** | WR2 content pipeline feeders | **OPERATIVO** | `com.matagaruda.wr2-bridge`, `com.matagaruda.wr-topic` loaded + numerous `com.balizero.wr2.*` daemons running (queue-server PID 984, supervisor-watchdog PID 8749). WR2 lives HERE now, not in apps/war-room. | OSINT-intel |
| **mata_garuda regulation_watcher / regulation_alert_agent** | reg-alert pipeline | **OPERATIVO (scheduled)** | `com.matagaruda.watcher.daily` (`mata-garuda-watcher.log` @ 2026-06-01 06:00) + `com.matagaruda.reg-alert.30min` loaded. Tier-4 cascade per global CLAUDE.md. | OSINT-intel |
| **mata_garuda Council "Consiglio v1"** | multi-LLM deliberation (SYMBIOSIS Pillar 4) | **🔴 MAI_USATO — quarantined** | `.disabled-2026-05-06/council/` — own README: *"never produced a single deliberation; council.db never created; weekly LaunchAgent was for Air (decommissioned 2026-05-05 before cron installed); escalations.json stayed empty"*. Dead by self-admission. | mata-garuda |
| **apps/war-room** | WR1 carousel/intel pipeline | **🔴 DECOMMISSIONED RESIDUE** | NO launchd label (`war.room`/`warroom` → none). `logs/pipeline_*.log` STOP at 2026-04-22. `.env` is just Canva creds. Dir = output artifacts (64 carousel/episode subdirs) + dead pipeline logs. `intel_publisher.py` still references `../war-room/output/` paths and `source="war_room"` — WR was superseded by mata-garuda WR2 agents + `com.balizero.wr2.*` HOME cron. WR1 decommission acknowledged in code comments. | OSINT-intel |
| **apps/crm-cell** | CRM welcome-flow cell | **🔴 MAI_USATO — STUB (Sprint 3 W2)** | `event_bridge.py` is explicit `[STUB]`: `record_welcome_run` only logs the INSERT it *would* run, returns None, comment *"Sprint 4 requires pool"*. `scar_recorder.py` + `hgt_publisher.py` present but bridge never wired into `welcome_practice_service`. Never executed in prod. | cell |

---

## GAPS (the important part)

### G1 — 🔴 Supervisor is permanently observation-only; the whole "autonomous self-healing organism" is inert
The organism supervisor (PID 1016) consumes 92k events but **does nothing**: `active.flag` missing → shadow mode → every decision = `defer_to_human`. On top of that, `Decider` is W1 (L0 YAML only; L1/L2/L3 LLM tiers explicitly disabled in code). So even if `active.flag=1` were set, the brain is YAML-rules-only. The 13 actuators (`fly_machines_restart`, `restart_agent`, `python_env_repair`, etc.) have **never been dispatched** in this configuration. **The crisis-recovery the architecture promises is not armed.** The Cell faithfully detects RED (e.g. fly_pg_backup failing for 70+ hours) and emits it, the supervisor logs `defer_to_human`, and nothing repairs it.

### G2 — 🔴 cell-observatory split-brain: repo collector crash-loops on a missing paid API key while a HOME-fork silently does the job
`apps/cell-observatory-collector` (the canonical, version-controlled, tested copy) **cannot start** — `config.py` hard-requires `OPENROUTER_API_KEY`/`MINIMAXM2_API_KEY`/`MINIMAX_API_KEY` (a MiniMax classifier) that isn't provisioned → `RuntimeError` → LastExitStatus=256 → 97MB crash-log churning every 10s under launchd KeepAlive. Meanwhile `~/agents/.observatory/observatory.py` (a 133-line HOME-fork, different file) is the one actually producing the dashboard `data.json`. This is **(a) a crash-loop wasting CPU + 97MB disk, (b) a W50/W51/W52-class HOME-fork divergence** where the repo is NOT the source of truth. Either provision the key + retire the fork, or retire the repo collector. Also: the MiniMax key requirement may collide with the project's "no paid API" stance (OpenRouter free-tier is the intended path per the comment, but the env var is simply absent).

### G3 — 🟡 Mata Garuda harvests but its knowledge graph is dead
`garuda:raw`/`garuda:enriched` flow fine (harvesters + classifier + NER all ran minutes ago), but the **KG (`~/.agent/mata-garuda/kg.db`) is stale (2026-05-29) and near-empty (2 entities, 0 relations)**. The kg-linker label is loaded but producing nothing. The intel ingestion half works; the intel *synthesis* half (entity graph, the thing that powers cross-referencing / the SYMBIOSIS Pillar-3 MCP bridge) is effectively off. Matches the documented "NB-INTEL degraded post-UUID-switch" direction.

### G4 — 🟡 task_consumer is a dispatch skeleton with no muscles
The gap→agent dispatcher's entire DISPATCH_TABLE is `log_only`. Every intelligence gap (missing NIP, missing LHKPN, stale profile, missing WORKS_AT relation) routes to a "future" agent that was never built. The consumer runs on schedule and dutifully logs gaps that nothing acts on. The autonomous-enrichment loop is a stub.

### G5 — 🟡 Dual-runner ambiguity for AI-Intel-Sentinel (and 25+ matagaruda labels = active-active risk persists)
Sentinel data is fresh (`sentinel_cell.db` @ 2026-06-02) but the obvious launchd label `com.matagaruda.sentinel.hourly` has a STALE log (last 2026-05-22); the live process is `com.balizero.research-sentinel` (PID 1050). Two labels, unclear which is canonical. More broadly, ~25 `com.matagaruda.*` labels are loaded on Pro — the **"12+1 active-active Pro+Mini" scar (2026-05-07) is structurally unresolved**; the only thing keeping it sane is the `intel-dedup-gateway` (G-positive) catching duplicates after the fact rather than preventing double-emit. (Mini state not verifiable from Pro this audit.)

### G6 — 🟢/⚪ Dead code carrying architectural intent: war-room, crm-cell, council, supervisor LLM tiers
Four substantial subsystems are present-but-unused: `apps/war-room` (decommissioned residue, still path-referenced by `intel_publisher`), `apps/crm-cell` (explicit Sprint-3 STUB), mata-garuda Council (self-quarantined), and the supervisor L1/L2/L3 brain (W1-disabled). None are harmful, but they inflate the apparent capability of the organism vs. what actually executes. `intel_publisher.py` hard-coding `~/Desktop/nuzantara/apps/war-room/output/` paths is a latent breakage if war-room dir is ever cleaned.

---

## Cross-check vs cicatrix-scars.md (verified on disk THIS audit)

| Scar claim (cicatrix / memory) | Verdict on disk 2026-06-02 |
|---|---|
| "Cell daemon was dead" (W57-era / memory) | **FALSE NOW** — Cell PID 9380 alive, pulse #2960, fresh. Daemon healthy (org_status reporting RED is the *content*, not a crash). |
| `cell_pulse_observed` gate-off since 2026-05-16 (`discovery_cell_pulse_observed_gate_off`) | **RESOLVED** — `CELL_OBSERVATORY_EMIT=true`, events reaching `organism:events` (XLEN 92419, supervisor consuming live). |
| mata-garuda consumer-group repaired (archived W-series) | **HOLDS** — `organism-supervisor` group lag=0; matagaruda classifier/ner/gap consumers ran 2026-06-02 01:46-01:55. |
| "12+1 mata_garuda LaunchAgents active-active Pro+Mini" (2026-05-07, P1, no fix) | **STILL STRUCTURAL** — ~25 `com.matagaruda.*` labels loaded on Pro; dedup-gateway is the de-facto (reactive) mitigation, not a fix. |
| NB-INTEL severely degraded post-UUID-switch (memory) | **CONSISTENT** — KG.db stale + near-empty (2 entities, 0 relations); kg-linker idle. |
| W50/W51/W52 HOME-fork family (deploy/script forks) | **NEW INSTANCE FOUND** — cell-observatory: repo copy crash-loops, HOME-fork `~/agents/.observatory/` is the live one. |
| 53 LaunchAgents, 13% KeepAlive (2026-04-29) | **WORSENED** — 161 `com.{cell,balizero,nuzantara}.*` labels loaded now (matches S1 audit "167 plist" memory). cell-observatory KeepAlive is actively harmful here (restarts a guaranteed-to-crash process). |

---

## One-line status roll-up

- **cell**: OPERATIVO (alive, RED-but-honest, cortex thinking) — observatory collector half is ROTTO (crash-loop) / DUPLICATO (HOME-fork).
- **organism**: OPERATIVO-but-INERT (observes 92k events, actuates 0; W1 + shadow). control_panel ROTTO.
- **mata-garuda**: ingestion OPERATIVO (streams + classifier + NER live), synthesis DEGRADED (KG dead, task_consumer no-op), Council MAI_USATO.
- **war-room**: DECOMMISSIONED RESIDUE.
- **crm-cell**: MAI_USATO (STUB).
- **shared `packages/cell-core`**: the real load-bearing library under cell + sentinel.
