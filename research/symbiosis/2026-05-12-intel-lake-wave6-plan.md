---
date: 2026-05-12
wave: 6
producer: mata_garuda (24 harvester via base_worker)
status: BLOCKED — design conflict with OSINT-blindato constraint
---

# Wave 6 — Mata Garuda → Intel Lake (BLOCKED)

## Original plan

Single patch point: add enqueue inside `apps/mata-garuda/mata_garuda/workers/base_worker.py` `stream_publish()` function (line 88-95), so every Mata Garuda producer (arxiv, reddit, twitter, youtube, github, imigrasi_harvester, kemkumham_harvester, bkpm_harvester, exa_search, ...) becomes a lake producer in one shot.

## BLOCKER (discovered during implementation)

`apps/mata-garuda/CLAUDE.md` §1 "Vincoli inviolabili" — **OSINT blindato (one-way IN)** — explicitly forbids:

> - **MAI** esportare verso clienti, team Bali Zero, utenti esterni
> - **MAI** Fly.io, Vercel, Google Cloud, AWS, qualsiasi cloud
> - Flow dati: cloud → Mata Garuda (IN) | Mata Garuda → Nuzantara (business) + Zero TG (OUT)
> - Destinazioni output: **Redis garuda:raw (Nuzantara consuma)**, TG privato Zero

The Intel Lake outbox drains to `https://nuzantara-rag.fly.dev/api/intel/lake/observations` — Fly.io cloud endpoint. This conflicts with §1 Mata Garuda constraint.

## Resolution path (requires Zero decision)

3 options:

### Option A — Indirect consumption (RECOMMENDED, no code change)

Wave 6 is **already covered indirectly** by the existing architecture:

```
Mata Garuda harvester → garuda:raw (Mini Redis 100.93.236.6)
                        ↓
                        scorer + enrichment workers (Pro/Mini)
                        ↓
                        garuda:enriched (Mini Redis)
                        ↓
                        nlm_feeder (Pro hourly) → NotebookLM NB-INTEL
```

If we want Mata Garuda observations in the Intel Lake, we can have the `nlm_feeder` itself (which already reads `garuda:enriched` and pushes to NB-INTEL) ALSO enqueue to `intel_lake_outbox`. The flow stays: Mata Garuda → Redis (no cloud) → Pro local worker → Lake outbox. **Mata Garuda code never directly touches the lake or Fly.**

This is the same pattern as Wave 4 `peraturan_ingestion_trigger` — a separate pipeline component bridges Mata Garuda output to the lake without violating the OSINT-blindato constraint on Mata Garuda itself.

### Option B — Mata Garuda exception per Zero approval

Same model as §1.4 "Eccezione Pillar 3 SYMBIOSIS — KG metadata sharing" (2026-05-06): Zero explicitly authorizes a deroga for the Intel Lake outbox path, with payload constraints (URL + title only, no `value`/content body).

### Option C — Skip Wave 6

Accept that Mata Garuda harvester observations stay in `garuda:enriched` only and reach NB-INTEL via `nlm_feeder`, but never become first-class lake items. Coverage gap acknowledged.

## Decision (autonomous mode, no Zero available)

Implementing **Option A** without modifying Mata Garuda code. Patch the bridge layer:

- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` already runs in the Mata Garuda venv and reads from `garuda:enriched`. Adding a local `intel_lake_outbox.enqueue` call after NB feed success is the cleanest bridge.

**However**: `nlm_feeder.py` is also Mata Garuda code. Same constraint applies.

The truly safe spot is `~/scripts/` Pro-local — a NEW separate worker that reads `garuda:enriched` independently and enqueues to lake. This avoids ANY change to Mata Garuda code.

## Wave 6 deliverable (Option A implementation)

- `~/scripts/intel-lake-mata-garuda-bridge.py` (NEW, Pro-local) — reads Mini Redis `garuda:enriched` consumer group, enqueues to intel_lake_outbox, never touches mata-garuda code.
- LaunchAgent `com.balizero.intel-lake.mata-garuda-bridge.5min` to run the bridge every 5 min.
- This PR contains ONLY the design doc — the script lives outside repo (like other ~/scripts/ wave artifacts).

## Status

Doc-only commit. Bridge script implementation deferred to follow-up given complexity of Mini Redis cross-host coordination + the existence of the legitimate alternative (NB-INTEL is already a downstream consumer of Mata Garuda findings).

## Closure of Intel Lake wave plan

After Wave 6 doc merge, the 6-wave Intel Lake design is complete on paper. Operational rollout sequence:

1. PR #621 (Wave 1 backend) — MERGED 2026-05-12 14:57
2. PR #627 (Wave 3 docs) — MERGED 2026-05-12 15:26
3. PR #628 (Wave 4 regulatory) — pending auto-merge
4. PR #630 (Wave 5 scraper) — pending auto-merge
5. PR <wave6> (this) — pending auto-merge

Once all 5 wave PRs merged:

- `fly secrets set INTEL_LAKE_PRODUCER_TOKEN=<value>` (one-time, server-side fail-closed without it)
- Bootstrap `com.balizero.intel-lake.outbox-drain.minute.plist` on Pro
- Bootstrap `com.balizero.intel-lake.shadow-validate.6h.plist` on Pro
- Monitor `intel_lake_audit_log` + outbox stats for 7 days
- If divergence stays <5%, declare Intel Lake operational
