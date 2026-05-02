# Intel Scraper main path verification post drive-poll disable — Sprint 0 Track B4

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "Intel Scraper main path"
**Cicatrix:** drive-poll DISABLED 2026-04-29 (PG load incident, cf.
`cicatrix-scars.md` § "drive_poll_service called missing method")

## What's the question

The brainstorm round 2 raised: with `drive-poll.sh` disabled on Pro since
2026-04-29 (P0 incident, see cicatrix), **is the Intel Scraper main path
still alive?** Round 2 also asked whether the cell-leggera proposal
(`intel-scraper-cell` light: Genome scar registry + HGT publisher) maps
onto the actual production runner.

Three possible runners are entangled here:

1. **`apps/bali-intel-scraper/`** — full Python pipeline (scraper →
   enricher → publisher). Runs LOCALLY on Pro via OpenClaw cron at
   03:00 WITA (`apps/bali-intel-scraper/CLAUDE.md` confirms).
2. **`cron-agent-python intel-radar`** — a different runner (per round 1+2
   audit). 19-strategy Python framework on Pro. Runs hourly.
3. **`cron-agent-python intel-feed-processor`** — runs every 2h. Crawl +
   parse for raw signal ingest.

The drive-poll incident affected only `crm.drive_poll_service` (a separate
Drive-watch consumer for CRM client folders), NOT any of the 3 above. So
the disable did NOT cripple Intel Scraper. But it DID change the broader
"PG load budget" because the daily indexing sweep at 00:30 WITA still
runs and was previously sized assuming drive-poll consumed N reads/min.

## Evidence summary

### `apps/bali-intel-scraper/` — main daily path

- **Cadence:** 03:00 WITA daily, on Pro, via OpenClaw cron wrapper
  (`scripts/openclaw-cron/intel-scraper.sh` per repo grep — wrapper not
  versioned in this branch but referenced).
- **Pipeline stages:** scraper (`unified_scraper.py`) → enricher
  (`claude_cli_enricher.py` via Claude CLI subprocess, no paid API) →
  publisher (Qdrant `balizero_news` collection upsert).
- **Sentinel bridge:** `intel-scraper-sentinel-bridge.sh` polls Pro every
  5min — flagged in audit doc 04 as "Active; daemons + hourly Intel
  Radar".
- **State files:** `~/.agent/decisions/state/intel_scraper.last.json`
  (per audit doc 04, 63 state files registered).
- **Last successful run:** UNVERIFIED at audit time. Pro is SSH-unreachable
  during this Sprint 0 session (`Host is down`). Per audit transcript
  04_automation_inventory_complete.md: "Sentinel/Arch ... Active; daemons
  + hourly Intel Radar" → that means as of round 1 audit (a few hours
  before this Sprint 0 session) the path was alive.

### `cron-agent-python intel-radar` — hourly multi-source aggregator

- **Cadence:** hourly (per round 2 brainstorm DeepSeek table).
- **Runner:** `~/.cron-agent-python/` Python 3.11 daemon, manager-based
  dispatch.
- **State file:** `~/.agent/decisions/state/intel_radar.last.json`.
- **Last successful run:** UNVERIFIED at audit time (Pro SSH-unreachable).
  Round 1 audit captured "intel-radar (14:00 today)" — alive a few hours
  before this session.
- **Round-2 verdict:** **CANDIDATO migrare OpenClaw + Knowledge Agents
  v12.1.0 in Sprint 8** (post upgrade A4). Until Sprint 8: stays in
  cron-agent-python.

### `cron-agent-python intel-feed-processor` — every-2h crawl + parse

- **Cadence:** every 2h.
- **Runner:** cron-agent-python (Python framework).
- **Last run:** "intel-feed-processor (14:00 today)" per round 1 audit.
- **Round-2 verdict:** stays in cron-agent-python (split clean Opzione C).

## Drive-poll incident impact (2026-04-29)

Per cicatrix:

- `crm.drive_poll_service` was disabled because of `AttributeError` on a
  missing method on `ServiceAccountDriveService`.
- Hot-fix landed same day in commit `720d54f5c` (added `get_file_metadata`).
- Cron stayed disabled afterward as a precaution because the original
  test suite never exercised the call path against the real class.
- **No relation to Intel Scraper or intel-radar/intel-feed-processor.**

The brainstorm round-2 § "PG load substrate degrade (cicatrix lesson)"
was a forward-looking note: "if Intel Scraper grows beyond N reads/sec
without re-budgeting, expect a similar disable cascade". It's a
**cautionary observation, not an observed regression**.

## Intel Scraper as cell-leggera (Sprint 1)

Round 2 final cell list (99b_synthesis_v2.md):

> 8. **intel-scraper-cell** ⭐ LEGGERA (Genome+HGT publisher only, no PulseLoop)

Mapping the real production runners to this cell:

| Production runner | Cell role |
|---|---|
| `apps/bali-intel-scraper/` (03:00 WITA daily) | Cell **body** — bulk scrape + enrich + publish |
| `cron-agent-python intel-radar` (hourly) | Cell **HGT publisher** — emits trend signals to `trend_signals` table → `intel_event` channel |
| `cron-agent-python intel-feed-processor` (2h) | Cell **light sensor** — feeds Intel Scraper's enricher with new feeds |

The cell-leggera Sprint 1 work is to formalize this:
- **Genome scar registry** entry for the cell (`apps/organism/organism/genome.yaml`)
- **HGT publisher** wrapper around the existing `trend_signals` insert path
  (no new code; just declare the cell + emit `cell_pulse_observed` events
  via the cell-observatory API)
- **Event bridge** to `intel_event` channel (already exists via mig 113 trigger)

NO PulseLoop, NO Homeostasis, NO new runtime. The light promotion is mostly
documentation + observability instrumentation.

## Verdict

| Question | Answer |
|---|---|
| Is Intel Scraper main path alive? | **Yes** — round-1 audit confirmed runs at 14:00 today (Pro), pre-Sprint 0 |
| Is drive-poll disable affecting Intel Scraper? | **No** — drive-poll was for CRM Drive folder watching, not Intel Scraper |
| Is the 03:00 WITA cron still authoritative? | **Yes** — `apps/bali-intel-scraper/CLAUDE.md` confirms; sentinel bridge polls every 5min |
| Is `intel-scraper-cell` light promotion a no-op or a refactor? | **Mostly no-op** — just declare the cell in `genome.yaml`, instrument observability emit, formalize HGT publisher contract |
| Re-livening required for Sprint 1? | **No** — already alive |

## Action items

### Sprint 0 follow-up (now Pro reaches a healthy state)

1. **Antonello: verify state file timestamps** to confirm last successful runs:

   ```bash
   ssh pro 'for f in ~/.agent/decisions/state/intel_*.last.json; do
     echo "=== $(basename "$f") ==="
     stat -f "%Sm  size=%z bytes" "$f"
     python3 -m json.tool "$f" 2>/dev/null | head -10 || echo "(invalid JSON)"
   done'
   ```

   Expected: timestamps within last 4 hours. If older than 24h, escalate.

2. **Antonello: Qdrant `balizero_news` recent uploads** (count last 7 days):

   ```bash
   ssh pro 'cd ~/Desktop/nuzantara/apps/bali-intel-scraper && \
     source venv/bin/activate && \
     python3 -c "
   from qdrant_client import QdrantClient
   import os
   client = QdrantClient(url=os.environ[\"QDRANT_URL\"],
                         api_key=os.environ[\"QDRANT_API_KEY\"])
   info = client.get_collection(\"balizero_news\")
   print(\"vectors:\", info.points_count)
   "'
   ```

   Expected: count growing day-over-day. If flat for 48h+, escalate.

### Sprint 1 — light promotion work

3. Add `intel-scraper-cell` entry to `apps/organism/organism/genome.yaml`
   (per brainstorm Genome scar registry pattern).
4. Add observability emit in the publisher step (one-liner: `await
   ObservedShellBus.emit("intel-scraper.publish", "ok", {count, slug})`
   — uses Track C2 framework).
5. Document cell contract in `docs/cell-core/intel-scraper-cell.md`
   (Sprint 1, NOT Sprint 0).

## References

- `apps/bali-intel-scraper/CLAUDE.md` (deployment notes, Pro 03:00 WITA cron)
- `apps/bali-intel-scraper/scripts/unified_scraper.py` (scraper entry)
- `apps/bali-intel-scraper/scripts/claude_cli_enricher.py` (enricher via Claude CLI)
- `apps/bali-intel-scraper/scripts/init_news_collection.py` (Qdrant `balizero_news` schema)
- `~/.agent/decisions/state/intel_*.last.json` (Pro state files)
- `cicatrix-scars.md` § "Backend prod down — drive_poll_service called missing method" (drive-poll cicatrix)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/04_automation_inventory_complete.md` § "Intelligence Pipelines"
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md` § "8. intel-scraper-cell"
