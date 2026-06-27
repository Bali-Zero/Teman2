---
date: 2026-06-28
domain: operations
client_case: none
sources:
  - launchctl print com.nuzantara.intake-worker (Pro, live)
  - ~/logs/intake-worker.launchd.err.log (Pro)
  - psql nuzantara_dev intake_queue (Pro, read-only nuzantara_dev_readonly)
  - ollama ps (Pro)
---

# Intake-blob orphan leak — root cause (2026-06-28)

## What happened
Pro disk hit 99% (Redis MISCONF outage). Largest single reclaim was the
intake-blob **orphan layer**: 40.639 files / **24.54 GB** of client documents on
disk under `~/.nuzantara/intake-blobs/drive` with **ZERO row** in
`intake_queue.blob_path`. Swept (re-downloadable 1:1 from Drive, stay on Drive,
Law 2 OK). 59.835 referenced blobs kept intact.

## Root cause (corrected — NOT SIGSEGV)
A first sweep reported "intake-worker SIGSEGV crash-loop". The live log
contradicts that: the worker is `state=running` (5 *historic* successive crashes
in launchctl, not an active loop). The real dynamic:

1. **OCR `qwen2.5vl:7b` times out repeatedly** (`TimeoutError`/`ReadTimeout`,
   ~12 per 200 log lines) on page after page → jobs fail at stage=extract/classify
   → `DEAD poison-pill after 5 attempts`.
2. **GPU contention**: `aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m` (24 GB) sits
   `100% GPU ... UNTIL: Stopping...` — stuck in "Stopping" for hours, never
   unloads. The 32B translator model starves the 7B OCR model of VRAM → OCR
   timeouts.
3. Jobs that never complete = blob downloaded to disk but `intake_queue` row never
   finalized → **orphan**. ALL orphans had mtime this month = active leak.
4. Backlog: `pending=92.673` (not draining), `done=54.667`, `dead=30`.

## The leak will RECUR until fixed
Cleanup is a firebreak. The orphan layer regrows every time an OCR job times out.

## Fix candidates (for the worker owner — not done here)
- **Unstick SEA-LION**: the 32B model wedged in "Stopping..." on GPU is the
  proximate VRAM thief. Investigate why it won't unload (keep_alive? a hung
  request?). Consider serializing translate.hourly vs intake OCR so a 32B and a
  7B model don't co-reside.
- **OCR timeout/back-pressure**: raise the qwen2.5vl timeout, or gate OCR
  submission on `ollama ps` having free VRAM, or move OCR to a dedicated Ollama
  instance (Mini) so the Pro translator can't starve it.
- **Orphan janitor**: add a disk→DB orphan-sweep to `intake_blob_retention.py`
  (currently DB→disk only, blind to orphans — superscar #2 / W81b corpse-sweep).
- **HOME-fork note**: worker runs from `~/Desktop/nuzantara-deploy/...` (the
  deploy clone) — confirm the cured puller keeps it fresh.

## Disk recovery this session
99% (7G) → 82% (77G). ~70G freed: dead deploy clones 10.6G, stale backups 4G,
caches 2 passes ~13G, archive→M5 4.8G, orphan-sweep 24.5G, app-regen (vm/OptGuide) 9.5G.
