---
date: 2026-06-28
domain: operations
client_case: false
sources:
  - opus-mythos workflow wm7mwjzpx (38 agents, 9 anatomy + 1 currency + 3 SOTA + 23 refute + synthesis)
  - live Pro verification (KG/KB row counts, split-brain detector exec, ollama daemon)
  - docs/mata-garuda/01-VISION.md (2026-04-08), 02-ARCHITECTURE.md
  - cicatrix-superscar.md (#1 HOME-fork, #2 esiste≠armato, #10 split-brain)
---

# Mata Garuda — opus-mythos TAC (Anatomy + Currency + SOTA + re-architecture)

> Method: full opus-mythos loop via Workflow `wm7mwjzpx` — 9 anatomy agents (1/organ),
> 1 currency analysis (Opus), 3 SOTA research angles (WebSearch), 23 adversarial refuters,
> 1 Opus synthesis. Final gate: Opus on-disk verification on the Pro (runtime truth), which
> CORRECTED both the anatomy agents (worktree-empty artifact) AND the refuter (overstated KG size).

## ⚠️ Load-bearing facts VERIFIED LIVE ON PRO (2026-06-28, not from agent reports)

These three numbers were re-checked by hand on the Pro because the agents disagreed
(worktree-isolated agents saw "empty", refuter saw inflated counts):

- **KB `apps/mata-garuda/data/knowledge.db`**: EXISTS, 5.0M, **7,370 rows** → KB is ALIVE.
- **KG `~/.agent/mata-garuda/kg.db`**: EXISTS, 192K, **132 entities / 45 relations / 239 observations**
  → KG is alive but SMALL (not the "409/1549/622" the refuter claimed, not the "zero/empty" anatomy claimed).
- **Split-brain detector `check_redis_split_brain.py`**: cannot even run — `redis-cli` not in PATH
  → the guardian of the split-brain is itself UNARMED (cicatrix #2 applied to the watchdog). The
  exec failure is fresh proof of the synthesis's central claim.

The exact figures differ from the synthesis but the DIRECTION holds: store alive, watchdog disarmed.

---

## §0 Executive verdict

**Mata Garuda is ATROPHIED, not dead — and it should NOT be rebuilt as designed, nor killed.**
The 2026-04 VISION (Palantir ontology + Neo4j 108K graph + NSA pattern-of-life + self-rewriting
meta-agent) is ~70% never-shipped vapor and is off every current roadmap. What actually runs is a
smaller, real system: ~7 working harvesters, an 11-worker Redis pipeline, a populated SQLite KG+KB
(7,370 KB rows + small KG), and ~12 cron-wired Layer-4 product agents shipping to Telegram/email/kita.
The organ's true problem is not ambition-vs-reality alone; its load-bearing function — **intel →
NotebookLM** — is now REDUNDANT with the newer Intel Lake router, and its pipeline is riddled with
green-but-dead surfaces (gap_consumer ~95% unacked, ~32-day-dead consumer groups W5/W6/W9,
split-brain across two Redis hosts with the detector itself unrunnable).

**Recommendation: keep the live harvesters + product agents, finish the Intel-Lake dedup migration,
fix the split-brain with one Postgres advisory lock, and retire the organism-vision scaffolding. Do
not revive the meta-agent.**

## §1 What it IS today (per-organ, honest)

| Layer / Organ | Status | Honest reality |
|---|---|---|
| **L1 Harvesters** | PARTIAL ALIVE | ~7 with real reachable sources (arxiv, RSS, github, youtube, imigrasi, kemlu, kemkumham, LHKPN/elhkpn, intel-scraper-bridge). `run_sentinel_py.py` contains the harvest() for arxiv/rss/github/youtube but is NOT cron-wired (armament-sospeso). Gov-harvesters unscheduled. BKPM source unverifiable/likely-dead. AI-twitter = placeholder (confirmed). intel-bridge is **Mini-canonical** and live on Mini. |
| **L2 Workers (11)** | DEGRADED | Workers ARE idempotent (XREADGROUP+ACK consumer groups — refuter confirmed). But ≥3 consumer groups were dead ~32d (NER/classifier, cicatrix W5/W6/W9). Embedding is **local Ollama** (nomic 768 / mxbai 1024), NOT the frozen prod text-embedding-3-small (1536) — by design (Law 2 OSINT-blindato), dimensionally incompatible with prod RAG. |
| **L3 Storage** | ALIVE (small) | KB 7,370 rows (live-verified). KG 132 ent/45 rel/239 obs (live-verified, small). SQLite by deliberate design; Neo4j explicitly designed out (exists only in separate OSINT-Nexus app, ~1406 nodes, never integrated). Qdrant/Postgres = dormant placeholders. |
| **L4 Product agents** | ALIVE | ~12 cron-wired: daily-briefing, weekly-digest, reg-alert/30min, kita-feed, public-channel, wr2-bridge, wr-topic, nlm-expander, intel-bridge, kg-linker + invalidation/unmapped sweeps. ai_digest ready but NOT cron-wired. Outputs live in agent modules, not run_* wrappers. |
| **Lamarckian / meta-agent** | DORMANT | Code complete (lamarckian/genome/fitness/reflection). `mutation_version` frozen at 0 = zero mutations ever applied. Council v1 quarantined 2026-05-06 (zero executions ever). gap_consumer (the dispatcher) IS cron every 10min but STALE: depth ~1149, ~95% unacked — exit-0, acks nothing. (NOTE: the "stalled since 2026-05-17" date rested on a fitness file that does not exist on disk — treat as not-running, date-unverified.) |
| **Cell/Bridge framework** | DORMANT (decorative) | cell.runner, bridge.nerve: full implementations, zero runtime callers (tests only). The working system is the deterministic cron scripts, not the PulseLoop "organism". |
| **Infra / host topology** | SPLIT-BRAIN | ~12-13 crons hardcode /Users/nuzantara (cicatrix #1). Producers write Pro Redis, sentinel writes Mini Redis, nlm-feeder defaults 127.0.0.1, GARUDA_REDIS_HOST unset in every plist. No master-election, no singleton lock. Split-brain detector exists, wired to NO cron, and is itself unrunnable (redis-cli not in PATH). |

## §2 What it was MEANT to be vs what shipped

| Promised (01-VISION / 02-ARCH) | Shipped |
|---|---|
| Palantir dynamic self-evolving ontology | Flat SQLite KG, fixed schema |
| Neo4j 108K-node OSINT graph | SQLite (designed out); Neo4j only in separate app |
| CIA CATALYST analyst-in-the-loop retraining | None |
| NSA pattern-of-life detectors | None |
| Bloomberg /POL /COMPANY MCP shortcuts | None |
| Recorded-Future novelty+velocity+SILENCE scoring | Only base quality gate |
| Babel-Street Bahasa-nuance engine | None |
| Self-rewriting PROTEUS/DGM meta-agent | Code exists, never runs in prod (mutation_version=0) |
| 5-channel one-packet fan-out | ~6 product agents, no unified fan-out |
| text-embedding-3-small → Qdrant (L2) | Local Ollama embeddings, no Qdrant write |

**The gap is ~70% of the design.** What survived is the unglamorous core: harvest → enrich → store
→ ship-to-TG/email. The moonshots never left the document.

## §3 §Meta-pattern — the malattia-delle-malattie

**The single belief that generated this organ's entire decay: "build the organism, and it will come
alive."** Three concrete consequences, each a named cicatrix family:

1. **Esiste ≠ Armato (cicatrix #2) at industrial scale.** Almost everything is built-but-not-armed:
   run_sentinel_py.py (coded, unscheduled), gov-harvesters (coded, unscheduled), cell.runner/bridge.nerve
   (coded, zero callers), Lamarckian loop (coded, mutation_version=0), Council (coded, zero executions).
   Cruelest variant: gap_consumer is armed AND green (cron every 10min, exit 0) while acking ~5% of ~1149
   messages. The organism metaphor rewards building organs over wiring them; "alive" was conflated with
   "exists in the codebase". The split-brain detector itself can't run (redis-cli absent) — the watchdog
   is unarmed.

2. **Split-brain by no-singleton (cicatrix #10).** An "organism" across Pro+Mini with no master-election,
   no declarative `assigned_node`, GARUDA_REDIS_HOST unset everywhere → state smeared across two Redis
   instances + filesystem + launchd exit-codes. No single authoritative writer because the design never
   named one.

3. **Redundancy by parallel-world (cicatrix #10 NLM variant).** The newer Intel Lake router (2026-05-12)
   was explicitly built to subsume mata_garuda's nlm_feeder onto `intel_lake:routed`. That migration
   stalled. Now two pipelines race into the SAME capped NB-INTEL notebooks. The organism grew a second
   nervous system instead of finishing the cutover.

**One sentence:** *Mata Garuda is what happens when you design an autonomous organism instead of a
wired pipeline — a beautiful anatomy where "exists" is mistaken for "alive", nobody is the single
writer, and a newer simpler system has already made half of it redundant.*

## §4 SOTA — is there a better 2026 approach

The SOTA research converged on one answer for a solo local-sovereign operator: **collapse the control
plane onto Postgres.**

**Option A — Durable execution as a library (DBOS-on-Postgres) [RECOMMENDED].**
Replace (Redis Streams consumer-groups + cron LaunchAgents + *.last.json state) with one library backed
by the Postgres you already run (PG17 on M5/Pro, Fly nuzantara_rag). Workflows checkpointed per-step,
idempotent, auto-resume on reboot, ONE log per run. **Fit: strong.** Directly kills the dominant scar
families: #2 (a workflow either committed-in-DB or didn't — no green-exit lie), #1 (no hand-armed
daemons), #9 (one journaled history vs N drifting JSON readers). Zero new always-on daemons. It is the
"Heartbeat Semantico" doctrine made structural.

**Option B — Keep SQLite, add bitemporal + provenance + rerank [the STORE answer].**
Do NOT rebuild toward Neo4j/GraphRAG — unanimous that at solo scale Neo4j-108K is over-engineering and
would become a #2 dead-organ. The existing SQLite-KG + FTS5 + Qdrant + NotebookLM stack accidentally
landed near pragmatic SOTA. Genuine upgrades: (1) bitemporal fact validity (event-time + ingestion-time
+ valid-from/to) — critical for superseding Indonesian regs (KBLI/visa/tax); (2) fuse the three
retrievers (vector + FTS5 + KG) into one rerank path; (3) LightRAG/LazyGraphRAG query-time graph, never
Microsoft-GraphRAG upfront indexing (cost cliff on a daily-changing corpus). **Fit: strong, additive,
no server.**

**Option C — Temporal / Raft / etcd / Redis-Sentinel [REFUSE].**
Over-engineering for 2-3 Macs: add a second home of truth and more daemons that can lie green, recreating
#2 and #10. A 2-node fleet can't even form a safe quorum.

**Split-brain + dead-cron cure (how modern systems solve it):** single-writer via `pg_try_advisory_lock`
(one DB → exactly one lock-holder → exactly one live instance; auto-released on crash, no TTL guessing)
+ end-to-end heartbeat row written at the END of real work (judge by rows-processed, not exit-code/TCC).
Both use the Postgres you already keep armed. (Note: this is the SAME receptor pattern we just shipped
for the core-organ heartbeats, PR #1805/#1808 — generalize it, don't reinvent.)

## §5 Re-architecture PROPOSAL (staged, YAGNI, NOT a Palantir rebuild)

Each stage: **go/no-go gate + 1 falsifiable metric.** No code here — this is the plan.

**Stage 0 — Triage & honest inventory (1 session).** Run check_redis_split_brain.py (after fixing
redis-cli PATH) and check_consumer_lag.py manually; confirm which of the ~12 crons actually produced
output in the last 7 days (heartbeat-by-output, not launchctl green).
- *Metric:* a table {cron, last-real-output-ts} with ≥1 verified-dead entry surfaced.
- *Go/no-go:* if >50% crons have no real output in 7d → organ is more dead than assumed; escalate to Zero.

**Stage 1 — Split-brain cure (single-writer) [GO].** Add `pg_try_advisory_lock(<organ_key>)` at startup
of each singleton (nlm-feeder, gap_consumer, intel-bridge); no-lock → graceful exit. Declarative
`assigned_node` read on every host. Set GARUDA_REDIS_HOST explicitly in every plist OR demote Redis to
single-host cache.
- *Metric:* check_redis_split_brain.py exits 0 (drift <1h) for 7 consecutive days.

**Stage 2 — DB heartbeat (cure green-but-dead) [GO].** Every cron writes {organ, ts, rows_processed,
run_id} to a Postgres `organ_heartbeat` table at END of work. One watcher alerts on staleness. Generalizes
launchd_liveness_detector (PR #1518) + the receptor (PR #1805/#1808).
- *Metric:* gap_consumer's ~95%-unacked condition fires an alert within 1 run instead of being invisible.

**Stage 3 — Finish the Intel-Lake dedup (kill the #1 NLM split-brain) [NEEDS ZERO].** Point ONE feeder at
`intel_lake:routed`; retire the other. Decision required: which survives (mata_garuda nlm_feeder vs frozen
nb-pusher).
- *Metric:* zero duplicate sources pushed to any NB-INTEL UUID over 7 days.

**Stage 4 — Prune the vapor [GO, pure deletion].** Delete/quarantine: Council stream constants,
task_consumer.py, cell.runner/bridge.nerve (test-only), dormant gov-harvesters overlapping the production
regulatory-watcher, ai_twitter placeholder. Update the 27-day-stale README.
- *Metric:* LOC + import-graph edges down ≥30%; `cli.py run <agent>` lists only armed agents.

**Stage 5 (OPTIONAL, defer) — DBOS control-plane migration.** Only if Stages 1-2 reveal the cron-theater
is unfixable piecemeal. Port DLQ/intake gates to DBOS resumable workflows.
- *Metric:* a forced mid-run reboot resumes from last step (not silent loss). *Go/no-go:* NO-GO by default.

**Stage 6 — NEVER.** Do not revive: Lamarckian always-on meta-agent (#2/#5/RSI-overreach, scarred W74),
Neo4j-108K, Palantir ontology, pattern-of-life, Bahasa-nuance. If self-evolution ever returns it must be
offline/sandboxed/benchmark-gated (DGM pattern) in a dedicated worktree, 4-LLM-graded, and labeled
self-healing, not RSI.

## §6 §Solo-operator boundary (Zero's hand, not autonomous)

1. **KILL vs KEEP the organism vision** — strategic product-identity call. Autonomous Ops can wire/fix/prune
   but cannot officially demote mata_garuda from "autonomous OSINT organism" to "harvesters + product agents
   feeding Intel Lake". **Needs Zero.**
2. **Stage 3 — which NLM feeder survives** (nlm_feeder vs Intel Lake nb-pusher). Retiring a pipeline touching
   client-facing NB-INTEL = shared-state + business-judgment. **Needs Zero.**
3. **NB source-cap policy** — ~500-600/NB cap (W15) + the 2026-06-28 nlm-CLI blast-radius break mean the NLM
   strategy needs a human call on capping/rotation/account. **Needs Zero.**
4. **Public-channel publishing** — public_channel_publisher posts client-facing; arming past DRY-RUN is a
   Legge-5 publish-gate decision. **Needs Zero.**
5. **PII boundary on any KG/entity-resolution work** — OSINT entities (officials, companies, cases) are
   PII/Law-2 territory; processing stays Pro-local, no third-party paid endpoint. Entity-resolution must be
   on-box (e.g. Splink local). **Boundary, non-negotiable.**

## Method caveat (honesty)

- 1 refuter (refute[8]) died on schema after retry — that claim ("clean DAG, no cycle") went unverified;
  not load-bearing for the recommendation.
- The anatomy agents ran on Haiku inside the ISOLATED worktree (knowledge.db absent there) → several
  "empty/dead" claims were worktree artifacts, corrected by the refuter and by live Pro verification.
  This is exactly the worktree-vs-main trap (cicatrix #1 family); the live Pro numbers above are authoritative.

**Bottom line:** Mata Garuda earned its keep as a *pipeline*, not an *organism*. Keep the live harvesters +
product agents, cure the split-brain with one advisory lock, make green mean work-landed via a DB heartbeat,
finish the Intel-Lake dedup, delete the vapor. Refuse Temporal/Neo4j/the meta-agent. The organ doesn't need
more anatomy — it needs to be *wired and singular*.
