# Phase 1 Synthesis — Unified Census of the Nuzantara Agentic System

> Date: 2026-06-02. Source: 7 zone maps as supplied. Method: facts-with-evidence only, no memory.
> **Data-provenance caveat (load-bearing):** the task announced "7 maps" but the delivered material resolves to **5 distinct zones**, split across two carriers:
> - **3 zones are on disk** in `phase1-zone-maps.json` — verified complete end-to-end (Zone A 34 ent, Zone B 90 ent, Zone C 8 ent = 132 entities).
> - **2 zones exist only inline in the task prompt** (Zone D channels/services, Zone G Symbiosis-organism). The inline JSON array was **truncated**: Zone G's last entity (`Mata Garuda task_consumer`) is cut mid-line and **any entities after it are not recoverable**. Zone G is therefore counted at its **19 fully-visible entities**; its true size is larger.
> - The two "missing" zones (to reach 7) were **never delivered in any form** — not on disk, not inline. They are recorded below as a known gap, NOT fabricated.
> All counts below are reproducible: file zones via `python3` JSON parse of `phase1-zone-maps.json`; inline zones via direct enumeration of the prompt text.

---

## 1. Total entity count by status

### Per-zone (evidence-backed)

| Zone | Source | Entities | OPERATIVO | INCERTO | ROTTO | DUPLICATO | MAI_USATO |
|---|---|---:|---:|---:|---:|---:|---:|
| A — Claude Code agents (`~/.claude/agents/*.md`) | disk JSON | 34 | 13 | 14 | 2 | 3 | 2 |
| B — LaunchAgents (launchd, Pro) | disk JSON | 90 | 67 | 12 | 7 | 2 | 2 |
| C — chain-mcp workflow chains (`chains.py`) | disk JSON | 8 | 8 | 0 | 0 | 0 | 0 |
| D — backend-rag channels + agentic services | inline prompt | 26 | 19 | 2 | 1 | 1 | 3 |
| G — Symbiosis-organism (cell/organism/mata-garuda) | inline prompt (TRUNCATED) | 19* | 9 | 3 | 5 | 1 | 1 |
| **TOTAL (delivered + visible)** | | **177** | **116** | **31** | **15** | **7** | **8** |

\* Zone G is truncated; ≥19 entities, true total unknown. All Zone-G numbers are a floor.

### Grand totals

| Status | Count | % of 177 |
|---|---:|---:|
| **OPERATIVO** | 116 | 65.5% |
| **INCERTO** | 31 | 17.5% |
| **ROTTO** | 15 | 8.5% |
| **MAI_USATO** | 8 | 4.5% |
| **DUPLICATO** | 7 | 4.0% |
| **TOTAL** | **177** | 100% |

**Read:** roughly two-thirds of the organism is verifiably alive. The remaining third splits into a large band of **unconfirmed (INCERTO, 31)** — dominated by the entire WR3 video pipeline never reaching steady-state — and a smaller hard-failure / dead-weight band (**ROTTO 15 + MAI_USATO 8 + DUPLICATO 7 = 30**) that is concrete, actionable cleanup.

---

## 2. Macro-groups (name · entity count · commander vs scattered)

A "commander" = a single orchestrator entity that other entities in the group are contractually subordinate to (e.g. `MUST BE USED by X`, or a Supervisor/Router daemon). "Scattered" = a flat collection of peers with no internal hierarchy.

### Pipelines with a clear commander

| Macro-group | Entities | Commander | Notes |
|---|---:|---|---|
| **WR2 carousel pipeline** | **8 agents** (Zone A) + **21 launchagents** (Zone B, `wr2-pipeline`) + backend WR2 services (Zone D: critic_rubric, outbox_consumer, WarRoomRepository) + `canva_renderer_v2` | **`wr2-design-architect`** (Zone A orchestrator) at agent layer; **`com.balizero.wr2.supervisor`** (pid 17298, KeepAlive) at daemon layer | The single largest, fully-commanded subsystem. Genuinely in production (33 carousel output dirs, 15-row episodic log). Two-tier command: agent orchestrator drives the creative fan-out, supervisor daemon drives the cron production loop. |
| **WR3 video pipeline** | **13 agents** (Zone A) + **4 launchagents** (Zone B, `wr3-pipeline`) | **`wr3-design-architect`** (Zone A orchestrator, INCERTO); daemon commander **`com.balizero.wr3.supervisor` is ROTTO (NOT LOADED, binary missing)** | Has a commander on paper but it is broken. Entire group is INCERTO/ROTTO: pilot-stage only, no episodic-log, `.openclaw/bin/wr3/` dir deleted. The most structurally distressed macro-group. |
| **Organism core** | **9 launchagents** (Zone B) + Zone G Supervisor daemon + actuators + scheduled-tick + control-panel + bridges | **`com.nuzantara.organism.supervisor`** (pid 1016) — Redis-event brain, 92k events consumed | Commanded, but the commander runs **SHADOW-mode only** (never actuates — see §4). Control-panel ROTTO, federation-alert-dispatcher ROTTO. |
| **Channels (omnichannel ingress)** | **10 entities** (Zone D: 4 live channels + 2 quarantine + 2 taxonomy-only + Router + Engine) | **`ChannelRouter`** → **`ConversationEngine`** → **`AgenticRAGOrchestrator`** | Clean 3-layer command chain; the shared "brain" (`AgenticRAGOrchestrator`, ReAct + Gemini function-calling) sits behind all 4 live channels. |
| **Mata Garuda OSINT hub** | **1 launchagent** (Zone B) + ≥9 Zone-G entities (40+ harvesters, sentinel-cell, KG/NER/classifier workers, nlm-feeder, bridge.nerve) | No single live orchestrator; harvesters fan out to `garuda:*` Redis. `sentinel_dna.json` (8 priority rules) is the nearest thing to a policy-commander | Effectively **scattered/event-bus-driven**, not commanded. Genuinely pulsing today, but the business-handoff nerve (`bridge.nerve`) is ROTTO. |
| **Cell organism** | **2 launchagents** (Zone B `cell-organism`) + Zone G PulseEngine + cell-core | **`com.cell.organism`** (pid 9380) Voyager pulse loop | Commanded and alive (Pulse #2947). Observatory web surface ROTTO. |

### Scattered groups (no internal commander — flat peer collections)

| Macro-group | Entities | Character |
|---|---:|---|
| **nuzantara-mcp deterministic chains** | 8 (Zone C) | 8 sibling MCP tools in one registry, no orchestrator. All code-complete, but **none autonomously invoked** (see §4). |
| **research agents** | 4 (Zone A: deep-researcher, devils-advocate, nb-curator, regulatory-watcher) | Independent lanes; devils-advocate is a *gate* invoked BY deep-researcher but not a commander. |
| **infra-verify lane-aggregators** | 4 (Zone A: spalla-review, backend-verifier, frontend-browser, mcp-health) | Flat set of read-only verifier lanes. |
| **sentinel** | 4 (Zone B) | Peer daemons (sentinel, sentinel-aggregate, cron-log-sentinel, research-sentinel). |
| **intel (lake)** | 5 (Zone B) | Peer cron/daemons (nightly, router.5min, dedup-gateway, outbox-drain, radar-digest). |
| **wa-mirror** | 6 (Zone B) | Peer daemons; 1 superseded duplicate. |
| **monitors** | 4 (Zone B: disk, cpu, profile, audit-launchd) | Independent watchdogs. |
| **codex-autonomy** | 3 (Zone B) | 2 of 3 NOT LOADED (MAI_USATO). |
| Smaller singletons/pairs | crm-analytics(2), mos-plus(2), post-publish(2), notebooklm-curation(2), observatory(3), tunnels(2), vector-store(2), repomap(2), regulatory(2), automap(2), maintenance(2), brand-email(1), hr(1), competitor-intel(1-2), seo(1), translation(1), domain-mesh(1), agent-evolution(1), security-hr(1) | Mostly scattered utility cron. |

---

## 3. Suspected DUPLICATES (pairs doing the same thing)

7 entities are flagged DUPLICATO across the maps. They resolve into **5 duplicate relationships**:

| # | Pair / superseded | Where | Evidence (verbatim from maps) |
|---|---|---|---|
| D1 | **`wr2-brief-interpreter`** ≈ **`wr3-brief-interpreter`** | Zone A | "both are the sole NB-grounding layer of their pipeline, same nlm-CLI mechanism, same claim/citation-verbatim contract — only NB routing (NB-1/4/5 vs NB-2..7) and downstream consumer differ." Same role, two pipelines. |
| D2 | **`wr2-external-bench`** ≈ **`wr3-editorial-bench`** | Zone A | "identical 'monthly SOTA external bench, 12 editorial brands + 3 competitors + trend reports, agy+Claude+DeepSeek cascade' design — one for carousel, one for video." (wr3 side is also ROTTO — see §4.) |
| D3 | **`canva_renderer` (legacy claude_invoker v1)** superseded by **`canva_renderer_v2`** | Zone D | "Superseded by canva_renderer_v2 (which routers/asset_upload.py imports). Legacy v1 alongside v2 — duplicate Canva-apply surface… own 2400s subprocess timeout." Only v2 is imported in prod; v1 is dead-but-present. |
| D4 | **`com.balizero.wa-mirror`** superseded by **`com.balizero.wa-mirror-launcher`** | Zone B | "[NOT LOADED] though plist exists… the live WhatsApp mirror is driven by com.balizero.wa-mirror-launcher (pid 10543). This standalone wa-mirror label is superseded/not-bootstrapped." |
| D5 | **`com.balizero.prime-tunnel`** vs **`com.nuzantara.prime-tunnel`** | Zone B | "[NOT LOADED]; … 'plist MISSING ON DISK'. The functional tunnel is com.nuzantara.prime-tunnel (pid 968). This balizero-namespaced label is a stale census artifact / superseded duplicate." Namespace-orphan dup (`com.balizero.*` vs `com.nuzantara.*`). |
| D6 | **`com.matagaruda.sentinel.hourly`** superseded by **`sentinel-aggregate` + `sentinel-meta-watchdog`** | Zone G | "legacy hourly is superseded/redundant, exit-1 noise, work not lost" — `sentinel_cell.db` is fresh today via the aggregate workers, not the hourly. (Classified DUPLICATO in Zone G; emits permanent exit-1 noise.) |

> Note: D2 and D6 are *both* duplicate AND broken/noisy — they appear again in §4.
> **Cross-zone duplication pattern worth flagging:** the `com.balizero.*` vs `com.nuzantara.*` namespace split (D4, D5) is a recurring source of orphan-duplicate launchagents — no reconciliation job exists between the two namespaces (Zone B gap).

---

## 4. ROTTO / MAI_USATO — full list with evidence

### ROTTO (15) — defined as confirmed hard-failure / structurally broken

| Entity | Zone | Evidence |
|---|---|---|
| `wr3-editorial-bench` | A | Cron entry-point `~/.openclaw/bin/wr3/wr3-editorial-bench-run.sh` MISSING while `com.balizero.wr3.editorial-bench.monthly.plist` is loaded — binary_missing class. |
| `client-case-quote-generator` | A | (1) hardcodes deprecated `deepseek-reasoner` → silent flash-downgrade TRAP; (2) toolset has NO PricingTool (violates Golden Rule #11). FROZEN S3 red-team verdict: 0/3 quotes send-ready. |
| `com.nuzantara.organism.control-panel` | B & G | `last exit 1`, repeating `No module named uvicorn`; stdout frozen at 2026-04-30. 22,972 flapping restarts under KeepAlive. |
| `com.nuzantara.federation-alert-dispatcher` | B | `last exit 1`, 21MB err log mtime today, `ModuleNotFoundError: No module named orjson` via `backend.services.events` import chain. Crashes every spawn. |
| `com.balizero.wr2.canva-renderer` | B | `last exit 78 EX_CONFIG`. ProgramArguments → `.openclaw/bin/wr2/wr2-canva-renderer-wrapper.sh` confirmed MISSING; render log frozen 2026-05-24. |
| `com.balizero.wr3.supervisor` | B | NOT LOADED; the entire `.openclaw/bin/wr3/` dir does not exist. Binary_missing. |
| `com.balizero.wr3.yt-metrics.weekly` | B | `last exit 127` (command not found); `wr3-yt-metrics-run.sh` MISSING (wr3/ dir absent). |
| `com.balizero.wr3.editorial-bench.monthly` | B | `last exit 127`; `wr3-editorial-bench-run.sh` MISSING (wr3/ dir absent). (Daemon side of Zone-A `wr3-editorial-bench`.) |
| `com.balizero.translate.hourly` | B | `last exit 1`; log tail `[ERROR] Model gemma4:26b not found. Available: qwen3.5:9b, qwen2.5vl:7b, bge-m3`. Fails every hour — required Ollama model absent on Pro. |
| Twitter/X channel adapter | D | Physically in `channels/.disabled-2026-04-30/twitter/`; README "CRC broken (X webhook handshake fails)"; NOT `register_adapter()`'d. |
| Cell `.env` world-readable secrets | G | `-rw-r--r-- (0644)` — leaks `CELL_TELEGRAM_BOT_TOKEN`/`FLY_API_TOKEN`/`GOOGLE_API_KEY`/`CELL_DATABASE_URL`. W21 scar family; S4 flagged chmod 0400 SAFE-pending, still 0644. |
| `cell-observatory` HTTP server | G | `last exit 1`, 22,324 flapping; `TypeError: argument of type HTTPStatus is not iterable` at `~/agents/.observatory/serve.py:62`. Crashes on every 404. |
| Mata Garuda `bridge.nerve` | G | Err log repeats EVERY minute `BRIDGE_API_KEY not set — aborting bridge cycle`; key absent from `~/.nuzantara-secrets.env`. **FALSE-GREEN:** parent `bridge.adaptive` reports `last exit 0` while nerve aborts internally. New unreported break. |
| Redis split-brain Pro/Mini | G | `garuda:raw` drift 240h (Pro stale vs Mini fresh), `enriched` 182h, `alerts` 450h. 2026-05-07 active-active scar, still live. Detection works (check exit 1); reconciliation does not exist. |
| (D2 dup also = ROTTO) `wr3-editorial-bench` daemon | — | counted once above. |

### MAI_USATO (8) — defined as loaded/defined but never produced an artifact / never bootstrapped

| Entity | Zone | Evidence |
|---|---|---|
| `yield-optimizer` | A | Cron `com.balizero.yield-optimizer.weekly.plist` EXISTS, but `research/commercial/` dir does NOT exist → zero opportunity files ever written. |
| `competitor-monitor` | A | Cron `com.balizero.competitor-monitor.monthly.plist` EXISTS, but `research/competitive/` dir does NOT exist → zero digests. Description self-admits "plist deferred to Phase B… never triggered." |
| `com.nuzantara.codex-spark-loop` | B | NOT LOADED — plist on disk but not bootstrapped into launchd → never runs. |
| `com.nuzantara.codex-overnight-runner` | B | NOT LOADED — plist on disk, not in launchd → never runs. |
| Slack channel | D | `find channels -iname '*slack*'` returns EMPTY — no dir ever existed; entry exists only in the channel taxonomy table. |
| Google Chat (gchat) channel | D | `find` returns EMPTY — "no scaffold files were ever committed under backend/channels/gchat/." |
| WR3 (backend service footprint) | D | `grep -rln 'wr3\|WR3\|content.creator' backend/services` = EMPTY; `ls scripts/ \| grep wr3` = EMPTY. WR3 has zero backend presence. |
| Organism Supervisor SHADOW-mode gate | G | Kill switch `~/.agent/supervisor/active.flag` DOES NOT EXIST → daemon defaults to shadow_mode. `decisions.jsonl`: every record `shadow_mode:true, actuator:'defer_to_human'`. 92k events observed, **ZERO actuators ever dispatched in prod.** |

> **Adjacent but NOT counted as ROTTO/MAI_USATO** (kept as INCERTO per the maps, flagged here because they are 1 step from broken):
> - `Organism Actuators` (13 modules) — INCERTO only because the Supervisor never dispatches them (shadow-mode), so runtime correctness is unverifiable.
> - `TrendHunterOrchestrator` (Zone D) — INCERTO: ships `_score_relevance`/`_link_entities` that **permanently return None** ("deferred wiring") — agentic layer not wired.
> - `Twitter/X webhook router` (Zone D) — INCERTO split-brain: router re-enabled + accepting CRC handshakes while its channel adapter is quarantined → orphan endpoint.
> - `frontend-browser` (Zone A) — INCERTO: `tools` list has no browser MCP, references CLAUDE.md-banned `mcp__playwright__` → cannot do its visual-QA mission autonomously.

---

## 5. ZONE CARENTI (aggregated capability gaps)

Synthesized and de-duplicated across all delivered zones. Ordered by business impact.

### G1 — Client quoting has no trustworthy automation
`client-case-quote-generator` (ROTTO) has **no PricingTool** in its toolset and runs math on deprecated `deepseek-reasoner` (silent flash-downgrade). FROZEN S3 verdict: 0/3 send-ready. Bali Zero still hand-builds A4 quotes. **Need:** a PricingTool-grounded, `deepseek-v4-pro`-math quote agent. (Zone A.)

### G2 — DeepSeek model-id rot silently degrades 4 agents
`client-case-quote-generator`, `deep-researcher`, `devils-advocate`, `wr2-external-bench` all call `deepseek-reasoner`/`DeepSeek Reasoner`, documented as a TRAP returning `deepseek-v4-flash` (lower quality) instead of `deepseek-v4-pro`. None migrated. Red-team / math / synthesis quality silently lowered fleet-wide. (Zone A.)

### G3 — Competitor & revenue intelligence is fully manual
`competitor-monitor` (Lets Move / Emerhub / Flado) and `yield-optimizer` (KITAS-expiring / KITAP-eligible / dormant-high-value scan) are both MAI_USATO — crons loaded, output dirs never created. Competitor pricing tracking and renewal/upsell opportunity detection are done by humans. (Zone A.)

### G4 — The entire WR3 video pipeline is unmaintained / never went live
WR3 reached pilot only: no episodic-log; `wr3-design-architect` INCERTO; `wr3-editorial-bench`/`wr3.supervisor`/`wr3.yt-metrics` ROTTO (whole `.openclaw/bin/wr3/` dir deleted); zero backend service footprint (Zone D); `wr3-yt-metrics`/`wr3-reflexion` have no substrate (0 published episodes). Every WR3 episode is hand-run. (Zones A, B, D.)

### G5 — No autonomous scheduler invokes the 8 deterministic chains
All 8 `chain_*` MCP tools are code-complete, py_compile OK, 12/12 tests pass — but the backend caller is `enabled=False` ("BUG calls localhost:8000=itself") and live OpenClaw `cron/jobs.json` has **0 chain jobs**. The WhatsApp onboarding consumer (`_trigger_onboarding_chain`) is a hardcoded STUB returning a mock `{'status':'queued'}`. The deterministic automation layer was de-wired in favor of free-form agent prompts (chain refs survive only in `backup/`); docs still advertise them as H24 autopilots. (Zone C + Zone D.)

### G6 — The self-healing actuation layer has never fired
Organism Supervisor has consumed 92k events in **SHADOW-mode only**; `~/.agent/supervisor/active.flag` doesn't exist; every incident resolves as `defer_to_human`. fly-restart / agent-restart / quarantine / python_env_repair actuators are coded but never dispatched. Flipping the flag is a manual decision nobody has made. (Zone G.)

### G7 — No daemon-level dependency / model / plist-health enforcement
- Python import drift undetected: `federation-alert-dispatcher` (orjson) + `organism.control-panel` (uvicorn) crash-loop every spawn, only visible in 20MB+ err logs.
- Ollama model presence unchecked: `translate.hourly` fails hourly because `gemma4:26b` was never re-pulled.
- Broken/NOT-LOADED/missing-wrapper plists linger (all `wr3.*`, `wr2.canva-renderer`) with no auto-cleanup.
- `com.balizero.*` vs `com.nuzantara.*` namespace orphans never reconciled.
- Loaded-but-never-ran crons (`wr2.canva-apply`, `wr2.fact-checker`, `regulatory-watcher.fix-b-verify`) un-flagged. (Zone B.)

### G8 — World-readable plaintext secrets persist (security debt)
`apps/cell/.env` (0644) and `apps/war-room/.env` (0644) leak EXA/CANVA/FIREWORKS/DEEPSEEK/OPENROUTER/GROK/TELEGRAM/FLY/GOOGLE/DB credentials. W21 scar family; S4 flagged `chmod 0400` as SAFE-pending; no agent enforces plist/.env permission hardening. (Zone G + cicatrix family.)

### G9 — OSINT knowledge-graph + business handoff broken, only monitored
- `bridge.nerve` (garuda→Nuzantara-business) dead every minute on missing `BRIDGE_API_KEY`, masked by a false-green parent (exit 0).
- `garuda.consumer.daily` (Redis→Neo4j) dead since 2026-05-13 (Neo4j down on :17687) — KG ingestion stopped.
- Redis Pro/Mini split-brain detected hourly but nothing reconciles or picks a canonical writer. (Zone G.)

### G10 — Genome / source-of-truth is stale vs reality
`organs_registry.yaml` snapshot 2026-05-18 declares 120 organi; live launchd shows ~167–169 labels. SHA256-validated but content-stale; no reconciliation job rewrites it. The "single source of truth" no longer maps the organism. (Zone B + Zone G.)

### G11 — No agent owns CRM mutation / Guardian hygiene at the agent layer
`client-case-quote-generator`'s own footer: "Update the client's CRM (out of scope; CRM-Guardian agent — TBD)". The backend `crm_guardian/*` deterministic engine exists, but there is no *agent* that links/cleans CRM records after a quote or onboarding. (Zones A, D.)

### G12 — HR / regulatory knowledge substrate unverified
`hr-companion`'s scripture (`employee-handbook-v1-ID.html`, `pkwtt-template-master.html`) was not verified present — if absent, every "cite Bab/Pasal" HR answer has no source. (Zone A.)

### G13 — Test infra cannot catch backend↔script and manifest↔registration drift
Cicatrix-confirmed structural class: WR2 agentic orchestration lives in `scripts/` (cron-driven), backend `wr2_outbox_consumer`/`critic_rubric`/`WarRoomRepository` have ZERO in-repo callers — boundary undocumented/unverifiable from inside the package. Twitter split-brain (router live, adapter quarantined) has no reconciliation test. (Zone D.)

---

## 6. Reconciliation note (for Phase 2)

- **Delivered & verified:** 5 zones, 177 entities (132 on disk + 45 inline-visible).
- **Truncated:** Zone G (Symbiosis-organism) cut at `task_consumer`; its full entity set and gap list are partially lost — Phase 2 should re-emit Zone G complete.
- **Never delivered:** 2 of the announced 7 zones produced no entities in either carrier. Phase 2 must identify which two zones were dropped (candidates by absence: a dedicated **MCP-servers inventory** zone, and a **skills / scripts (`~/scripts`, `scripts/`)** zone — neither appears as a standalone map, though both are referenced obliquely).
- **Double-counting check:** WR2 and WR3 appear in BOTH Zone A (agent defs) and Zone B (launchagents) and Zone D (backend services) — these are **distinct entities at distinct layers** (an agent `.md` def ≠ a `.plist` ≠ a backend `.py` service), so they are correctly counted separately, not deduped. The duplication that IS real (same job, two entities) is captured in §3.
