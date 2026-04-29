# 05 — DeepSeek v4: 3 minimum nervous contract proposals

**Data**: 2026-04-29 21:41 WITA
**Modello**: `deepseek-v4-flash` (DeepSeek API auto-routes from `deepseek-reasoner` request)
**Trasporto**: `complete_async()` via `apps/backend-rag/backend/llm/deepseek_client.py`
**Costo**: 5842 output tokens × ~$0.000003/token ≈ $0.018 (cache hit 896 input tokens)
**Note dispatch**: timeout 300s necessario; stderr "JSONL cost log /data not writable" → ignorabile (Pro non ha /data, è un Fly path).
**Output verbatim integrale (DeepSeek response raw)**:

---

# Innervation Architecture: 3 Minimum Nervous Contracts

## Context

- 149 organs across 7 runtimes (Pro LaunchAgent x52, Air x2, Fly x3, Vercel x8, GitHub Actions x10, MCP x3, backend-internal x12)
- Event stream `organism:events` (Redis + JSONL mirror) and 4 existing `emit_event()` callers
- No Genome yet; `redundancies.yaml` exists; Cell monitors only 1 organ
- Supervisor code-complete, not deployed
- SYMBIOSIS Laws: event-driven (no polling), graceful degradation, local sovereignty, measurable

---

## Proposal A: Minimal Heartbeat Bus (optimises for simplicity)

**Heartbeat protocol**
Every 60 s, each organ publishes an event with `kind="heartbeat"`, `severity=info`, `payload={}`.
Transport: Redis stream primary; if Redis is unreachable (timeout 2 s), fall back to appending JSONL directly (`open("~/logs/organism/events.jsonl","a")`).
If JSONL disk is full (>95%), skip heartbeat with a logged warning (no crash).
If both transports fail, the organ silently degrades (law-abiding).
Frequency N=60 chosen to balance traffic (149/60 ≈ 2.5 events/s) against detection latency.

**Event business protocol**
No change to existing `emit_event()` semantics.
Non-heartbeat events continue on: errors, state changes (start/stop), actionable signals (post-commit, scheduled tick, zombie detection).
Heartbeats are an *addition*, not a modification.
Schema: unchanged `Pydantic Event` (severity, source, kind, payload, correlation_id, is_actuation, host).

**Genome schema**
Single YAML file: `apps/organism/genome.yaml`, versioned in git.
Lists every expected organ by `source` (e.g. `launch_agent_pro_celery_worker:0123`), `runtime` label, and optional metadata (expected heartbeat interval, health check URI).
Read at startup by Cell and Supervisor; never re-read at runtime (immutable per deployment).
Does NOT replace `redundancies.yaml` – that file lists duplication relationships; Genome is the registry.
No concurrent schema conflict because Genome is a 1-to-1 mapping, not a duplicate list.

**Cell aggregation**
Cell subscribes to `organism:events` via Redis XREADGROUP.
Maintains an in-memory `dict[source → last_seen_timestamp]`.
Exposes `/health/innervation` returning number of alive organs (seen within 120 s), total expected, and the stale list.
Falls back to scanning JSONL on startup or if Redis is empty (replay last 200 entries).
If Cell dies, organs continue heartbeating – aggregation stops but Supervisor can read bus directly (no cascade).

**Organism observation**
Supervisor daemon (already code-complete) consumes stream via XREADGROUP.
On each event, looks up `source` in the Genome (loaded at init).
Maintains a Redis SET `organism:observed_sources` with TTL = 120 s (2x heartbeat interval).
Also stores an ordered diff: `organism:expected_sources` (from Genome) minus observed → `organism:stale_sources`.
Supervisor does **not** poll Genome periodically; only queries it when an event arrives (lazy validation).
If Supervisor dies, death detection stops but organs keep heartbeating.

**Explicit tradeoffs**

| Optimises for | Sacrifices | Cost per organ | Risk of regression |
|---|---|---|---|
| **Simplicity** – only 2–4 lines added per organ (a `while True: sleep(60); emit_event(heartbeat)` in the main loop). | **Offline robustness** – if both Redis and JSONL are down (extremely rare), heartbeats lost with no alternative. Also **granularity** – 60 s means ~2 min before death detection. | ~2 lines of code for the heartbeat loop; language-agnostic helper function (`innervate()`) can reduce to 1 import + 1 call. | Very low – existing `emit_event()` callers unchanged. Heartbeat is a new event kind, no schema conflict. |

**Potential Law violations**
Law 6 (local sovereignty) is satisfied as long as Redis or JSONL works offline. Law 3 (no polling) – everything is event-driven. Law 4 (graceful degradation) – if both transports fail, the organ continues functioning without heartbeat; no cascade.

---

## Proposal B: Tiered Resilience Bus (optimises for robustness)

**Heartbeat protocol**
Every 30 s. Transport chain:
1. Redis stream (primary) – written via published `emit_event()`.
2. Local Unix domain socket → a per-machine relay daemon (`organ_relay`) that writes to `~/logs/organism/events.jsonl` and optionally forwards to Redis later (store-and-forward).
3. Direct JSONL append (if relay unavailable).
The organ uses a smart client library (`innervation.driver`) that tries each transport in order with exponential backoff (initial 1 s, max 10 s).
If all three fail, the organ writes a native heartbeat file `~/.organism/heartbeats/{source}.mtime` (touch the file) – zero infrastructure.
This guarantees local sovereignty even on an air-gapped Pro machine.

**Event business protocol**
Two categories: heartbeats (every 30s) + actionable events (post-commit, deploy, error, etc).
Heartbeat schema reduced to bare minimum (timestamp + source).
Actionable events use the existing Event schema unchanged.
Supervisor distinguishes by `kind` field; rule matchers do not fire on `kind=heartbeat`.

**Genome schema**
Per-runtime YAML files (`apps/organism/genome/pro.yaml`, `air.yaml`, `fly.yaml`, etc), merged at startup into a single in-memory map.
Each entry has: `source`, `runtime`, `expected_hb_seconds`, `recovery_action`, `severity_on_silence`.
Stored in git for versioning + ADR-7-style SHA256 signature in `genome.lock` (HALT on signature mismatch, alert Telegram).
Runtime mutation forbidden – modifications via PR review only.

**Cell aggregation**
Cell maintains a Redis HASH `cell:innervation:last_seen` with `source → timestamp` per organ.
Persisted every 60 s to JSONL (replay-safe).
On startup: load JSONL last 1h + scan local heartbeat files (touch mtime) to bootstrap.
If Cell dies, organs continue; Supervisor reads HASH directly (already there).
If Redis dies, organs write to JSONL + touch mtime; Cell on recovery rebuilds from JSONL.

**Organism observation**
Supervisor consumes stream + scans `~/.organism/heartbeats/` mtime every cycle (relay-mode catch-up for organs whose relay was offline).
Maintains `organism:observed_sources` HASH with TTL = 90 s (3x interval).
On stale detection: emit `organism:stale_organ` event + dispatch recovery action from Genome.

**Explicit tradeoffs**

| Optimises for | Sacrifices | Cost per organ | Risk of regression |
|---|---|---|---|
| **Robustness** – triple fallback (Redis → relay socket → JSONL → mtime touch). Zero data loss in air-gapped scenarios. | **Operational complexity** – a new daemon (`organ_relay`) to maintain on each machine. Bigger code surface. | ~5–10 lines per organ + shared `innervation.driver` library. | Low – relay is opt-in; organs falling back to direct JSONL still work. |

**Potential Law violations**
None. All four laws strongly satisfied. Trade-off is the relay daemon as a *new component* — but it's per-machine and stateless (just forwards). Not a SPOF.

---

## Proposal C: Zero-Config Mesh (optimises for decentralisation)

**Heartbeat protocol**
Variable cadence based on organ activity:
- Active organs (those emitting actionable events) skip heartbeat — their actionable events count as proof of life.
- Idle organs emit `kind=still_alive` after T seconds of silence (T configurable per organ, default 60 s).
Transport: Redis primary; fallback to `~/.organism/heartbeats/{source}` mtime touch.
Genome includes `T_seconds` per organ, so idle ones know when to emit.

**Event business protocol**
Existing actionable events count as proof of life automatically.
New `kind=still_alive` for idle organs.
Schema unchanged; `still_alive` is just a kind-discriminator.

**Genome schema**
Decentralised: each organ declares its identity via a build-time decorator/constant in code (`@organ("backend.api.health_probe", T=60)`).
A static genome file is generated at build time by scanning the codebase (`tools/build_genome.py`).
Embedded in the deploy artifact as `apps/organism/genome.json`.
Single source of truth at build time, distributed at runtime.

**Cell aggregation**
Cell maintains a sliding window of last event per source (in-memory map, persisted to Redis HASH every 60 s for crash recovery).
Exposes `/health/innervation` with "alive" (event seen within T seconds), "stale" (within 2T), "dead" (beyond 2T).
If Cell dies, it recovers by scanning JSONL and local heartbeat files on restart.
No fallback aggregation required because organs always push events.

**Organism observation**
Supervisor loads the embedded genome.
Consumes stream; on each event, checks if source is in genome.
Maintains `organism:last_event` in Redis (HASH with TTL = 2T).
A background task (every T/2 seconds) computes `expected - observed` from Redis, storing stale sources in `organism:stale_sources`.
No polling of genome; genome is static in memory.

**Explicit tradeoffs**

| Optimises for | Sacrifices | Cost per organ | Risk of regression |
|---|---|---|---|
| **Decentralization** – no runtime config files, no periodic unnecessary events. **Bus load** – traffic proportional to active events, not idle clock. | **Deterministic detection latency** – death detection depends on organ's last event; an organ that goes idle (no events) but is alive will be falsely detected as dead after T. Must enforce the "still_alive" rule, which adds complexity. Also **build-time overhead** – scanning code to extract genome. | ~1–3 lines per organ: a decorator `@organ("source_id")` or a constant + startup registration. For passive organs, a timer to emit `still_alive` adds 2–3 lines. | Moderate – existing `emit_event()` callers untouched, but all organs must now guarantee they emit within T. Active organs (e.g., post_commit_hook) emit naturally; passive ones need the timer. Risk of missing `still_alive` in some organs → false positive death. |

**Potential Law violations**
Law 3 – no polling, still event-driven.
Law 4 – if an organ fails to emit `still_alive` due to bug, it's considered dead but is actually alive (false positive). Countermeasure: tolerance interval > 2T.
Law 6 – local file writes work offline, but genome scan requires internet? No, build-time; runtime genome is local binary.

---

## Comparison Matrix

| Feature | A: Minimal | B: Tiered | C: Zero-Config |
|---|---|---|---|
| Heartbeat interval | 60 s fixed | 30 s fixed | Variable (based on idle T) |
| Transport fallback | Redis → JSONL | Redis → Unix relay → JSONL → file touch | Redis → file touch |
| Genome format | Single YAML (git) | Per-runtime YAML + merged JSONL | Embedded JSON (build-time) |
| Cell aggregation | In-memory map | Redis HASH + relay | In-memory + Redis persist |
| Organism death detection | 120 s stale | 90 s stale | 2T stale (default 240 s) |
| Lines per organ | ~2 | ~5–10 | ~1–3 (+ decorator) |
| Risk of regression | Very low | Low | Moderate |
| Offline resilience | Good (JSONL) | Excellent (file touch) | Good (file touch) |
| Deployment complexity | Low | Medium (relay daemon) | Medium (build scan) |
| Bus traffic (events/s) | ~2.5 (heartbeats) + existing | ~5 (heartbeats) + actionable | ~0.5–2 (idle only) |
| Law 4 compliance (graceful degradation) | Partial (if both transports fail, no heartbeat) | Full (triple fallback + file touch) | Full (file touch) |

---

## Recommended: Proposal B — Tiered Resilience Bus

**Why.**
It satisfies all four SYMBIOSIS Laws with the strongest guarantees:
- Law 3 (event-driven) – no polling; relay is a push sidecar, not a poller.
- Law 4 (graceful degradation) – three transport layers ensure heartbeat delivery even when Redis, JSONL, and relay all fail (file touch survives).
- Law 6 (local sovereignty) – works offline on Pro+Air via relay and local files.
- Law 7 (measurable) – every heartbeat is an event; latency, loss rate, and stale detection delta are all countable in Redis metrics.

The cost per organ (5–10 lines) is acceptable for 149 organs, especially with a shared `innervation.driver` library. The relay daemon is a minor operational overhead but eliminates single-point-of-failure for a system that already has a Supervisor and Cell. Implementation risk is low because existing `emit_event()` callers are untouched and the new heartbeat call is an additive, idempotent operation. We recommend starting with Proposal B and optionally simplifying to Proposal A for quick deployment once the relay is proven stable.

---

## Orchestrator note

DeepSeek raccomanda **Proposal B (Tiered Resilience Bus)** ma con un caveat operazionale: introduce un nuovo daemon (`organ_relay`) per macchina. Questo aggiunge un actuator-like component non strettamente necessario.

**Proposal A** è la più conservativa: 2 LOC per organo, riusa `emit_event()` esistente, no nuovi componenti. Trade-off: granularity 60s (vs 30s di B) e fallback JSONL-only se Redis cade (vs file-touch di B). Per 149 organi su 2 macchine + 3 cloud provider, A è "enough" — Law 4 satisfaction è "Partial" solo nel caso _entrambi_ Redis E JSONL siano down, scenario praticamente impossibile sul Pro 48GB.

**Proposal C** è elegante ma porta build-time complexity nuova (scanning genome from code) — viola implicitly NB-1 ADR-7 (signature on registry: i 149 organi devono dichiarare se stessi, ADR-7 vuole un file canonico SHA-checked). C richiede scanner code + autogeneration → fragility cross-platform.

**Decisione FASE 2** (sezione 7 in `07_innervation_protocol.md`): **A con 1 element of B** — heartbeat 60s frequency, transport Redis → JSONL fallback (A), MA Genoma per-runtime YAML files merged at load (B's modular Genoma vs A's monolitica), MA NESSUN relay daemon (no nuovo component). Questo è il punto di Pareto: simplicity di A + modularity di B's Genoma.

**Cost per organ ratificato**: ~3-5 LOC (heartbeat task + emit_event call). Per 149 organi: ~600 LOC totali distribuite. Vs Proposal B's 5-10 LOC × 149 = ~1500 LOC + relay daemon. 60% riduzione effort.
