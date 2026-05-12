# TICKET G — narrow spec DRAFT: HTTP bridge for `cell:skills` Fly→Pro

**Status**: DRAFT pre-4-panel review (daylight execution)
**Date**: 2026-05-13 03:08 WITA
**Author**: Claude Opus 4.7 after 4-LLM brainstorm on split-brain
**Depends on**: Phase 3 Tickets A.0/A.1/A.2/B/C all merged ✅
**Solves**: split-brain Fly Upstash (`fdaa:31:dc12:0:1::2`) vs Pro localhost Redis (`127.0.0.1:6379`) for `cell:skills` stream
**Pattern**: clone `apps/backend-rag/backend/app/routers/bridge.py` HTTP bridge canonical (NB-1 ground-truth recommendation)

## Objective

Bridge Fly Upstash `cell:skills` stream → Pro localhost Redis `cell:skills` stream via HTTP request/response (NOT polling-orchestrator-worker, which would violate SYMBIOSIS Law 3 "nessun orchestratore centrale").

After fix:
- A.2 CRM HGT handlers continue publishing to Fly Upstash (Phase 3 spec v2 unchanged)
- B intel-scraper continues publishing direct to Pro Redis (unchanged)
- Sentinel cell on Pro consumes unified Pro `cell:skills` stream (HGTConsumer "sentinel-1" group)
- Pro-side `skills_bridge_consumer` daemon polls Fly `/api/bridge/skills` endpoint every 5min, XADDs delta to Pro Redis

## Architecture

```
Fly api machine                       Pro localhost
+--------------------------+           +----------------------------+
| EventBus → A.2 handler   |           | B intel-scraper            |
|    │                     |           |    │                       |
|    ▼                     |           |    ▼                       |
| XADD cell:skills (Fly)   |           | XADD cell:skills (Pro)     |
| Fly Upstash 6PN          |           | 127.0.0.1:6379             |
|     │                    |   HTTP    |     ▲                      |
|     │ XREAD              |  ◄─────   |     │ XADD                 |
|     ▼                    |           |     │                      |
| GET /api/bridge/skills   | ◄─────────┤ skills_bridge_consumer     |
| router (extended)        |  cron 5m  | (NEW Pro-local LaunchAgent)|
+--------------------------+           +----------------------------+
                                                  │
                                                  ▼
                                       Sentinel HGTConsumer "sentinel-1"
                                       (already exists, reads Pro cell:skills)
                                                  │
                                                  ▼
                                       genome.db + observatory.db
```

## Why this respects principles

| Principle | Check |
|---|---|
| **OSINT-blindato** | Sentinel + cell-observatory-collector stay Pro-local. Only skill payloads (NOT raw OSINT) cross Fly→Pro. Skill payloads contain pattern_id+procedure+precondition+success_criterion+confidence+domain — NO PII, NO OSINT raw. ✓ |
| **Law 3 (no central orchestrator)** | `skills_bridge_consumer` is a cron-driven request/response client, NOT a polling daemon orchestrating between cells. Same pattern as existing `bridge_events_consumer.py` (Pro polls `/api/bridge/events` from Fly outbox). ✓ |
| **Law 6 (sovranità locale)** | If Fly is unreachable, Pro stream still receives B publisher. Degradation graceful. ✓ |
| **Phase 3 spec v2 CORR-2** | `cell:skills` "lives on Pro localhost" — TRUE after bridge: Pro stream is canonical, Fly is upstream feeder. ✓ |
| **Anti-orchestrator HTTP-only bridge** | Existing `bridge.py` already implements Pro pulls events outbox + pushes article. New endpoint `/api/bridge/skills` is one more route in same pattern. ✓ |

## Components

### G.1 — Fly side: extend `apps/backend-rag/backend/app/routers/bridge.py`

NEW endpoint `GET /api/bridge/skills` (~50 LOC):

```python
class SkillsResponse(BaseModel):
    events: list[dict[str, Any]]
    last_stream_id: str

@router.get("/skills", response_model=SkillsResponse)
async def get_skills(
    after_id: str = Query("0-0", description="XREAD start ID (default 0-0 for full read)"),
    count: int = Query(100, ge=1, le=500),
    block_ms: int = Query(0, ge=0, le=5000, description="XREAD BLOCK timeout"),
    x_bridge_auth: str | None = Header(default=None, alias="X-Bridge-Auth"),
) -> SkillsResponse:
    """Pro polls this to pull cell:skills stream entries from Fly Upstash."""
    _check_auth(x_bridge_auth)
    # async redis client from app.state.redis_pool (existing redis_manager)
    redis_client = await get_redis_client()
    # XREAD COUNT count STREAMS cell:skills after_id [BLOCK block_ms]
    result = await redis_client.xread({"cell:skills": after_id}, count=count, block=block_ms or None)
    events = []
    last_id = after_id
    if result:
        # result = [(b"cell:skills", [(b"id-stream", {b"field": b"value"}), ...])]
        for stream_name, entries in result:
            for entry_id, fields in entries:
                last_id = entry_id.decode() if isinstance(entry_id, bytes) else entry_id
                decoded = {k.decode() if isinstance(k, bytes) else k:
                           v.decode() if isinstance(v, bytes) else v
                           for k, v in fields.items()}
                events.append({"id": last_id, "fields": decoded})
    return SkillsResponse(events=events, last_stream_id=last_id)
```

Reuses existing `_check_auth` (X-Bridge-Auth header). Reuses existing `get_redis_client` from redis_manager. Adds ~50 LOC.

### G.2 — Pro side: NEW `apps/cell/scripts/skills_bridge_consumer.py` (~150 LOC)

Cron-invoked (NOT daemon — Law 3). Single-shot polls Fly endpoint, XADDs delta to Pro Redis, persists `last_stream_id` to `~/.cell-bridge-state/skills_last_id.txt`.

```python
async def _run_one_poll() -> int:
    last_id = _load_last_id()  # default "0-0" on first run
    async with httpx.AsyncClient() as http:
        resp = await http.get(
            f"{FLY_BRIDGE_URL}/api/bridge/skills",
            params={"after_id": last_id, "count": 500, "block_ms": 0},
            headers={"X-Bridge-Auth": BRIDGE_API_KEY},
            timeout=30.0,
        )
        resp.raise_for_status()
        payload = resp.json()
    events = payload.get("events", [])
    new_last_id = payload.get("last_stream_id", last_id)
    if not events:
        logger.info("[skills_bridge] no new events (last_id=%s)", last_id)
        return 0
    redis_client = await aioredis.from_url("redis://127.0.0.1:6379", decode_responses=False)
    try:
        added = 0
        for ev in events:
            fields = ev["fields"]
            # MAXLEN ~ 5000 to bound stream
            await redis_client.xadd(
                "cell:skills",
                fields,
                maxlen=5000,
                approximate=True,
            )
            added += 1
        logger.info("[skills_bridge] XADD'd %d events, new last_id=%s", added, new_last_id)
    finally:
        await redis_client.aclose()
    _save_last_id(new_last_id)
    return 0
```

### G.3 — LaunchAgent plist `com.nuzantara.skills-bridge-consumer.plist`

Hourly (or 5-min) invocation:
- `ProgramArguments`: `["/Users/nuzantara/Desktop/nuzantara/apps/cell/.venv/bin/python", "-u", "apps/cell/scripts/skills_bridge_consumer.py"]`
- `StartCalendarInterval`: every 5min between 06-22 WITA (sleep_hours align with sentinel)
- `RunAtLoad`: false
- `KeepAlive`: false (cron-style, NOT daemon)
- `StandardOutPath` + `StandardErrorPath`: `~/Library/Logs/skills-bridge-consumer.log`
- Operator chmod 0444 after first deploy (antibody pattern per cicatrix-scars 2026-04-29).

### G.4 — Tests

- `apps/cell/tests/scripts/test_skills_bridge_consumer.py` (5 tests):
  1. First-run reads from "0-0" with no last_id state file
  2. State file populated → reads from saved last_id
  3. Empty response (events=[]) → no XADD, last_id unchanged
  4. HTTP error → exit 1, no XADD, last_id unchanged
  5. Concurrent invocation safety via flock (single-instance guard)

- `apps/backend-rag/backend/tests/app/routers/test_bridge_skills.py` (4 tests):
  1. No auth → 401
  2. Bad auth → 401
  3. Empty stream → events=[], last_stream_id="0-0"
  4. Populated stream → events=[...], last_stream_id=correct

### G.5 — Bridge auth secret rotation

Existing `BRIDGE_API_KEY` Fly secret reused. Pro-side reads from `~/.nuzantara-secrets.env` (already in inventory, no new secret). 

## Out-of-scope (deferred)

- Bidirectional sync (Pro→Fly): Pro events stay Pro-local (intel-scraper publisher).
- Deduplication: if A.2 publishes practice_id X event at time T1, Pro consumes at T1+5min, sentinel ACKs at T1+5min+poll. If `skills_bridge_consumer` re-runs and gets same event (last_id state file corrupted), duplicate XADD. Mitigation: state file is single-line, atomic write via tempfile + rename. Acceptable rare-edge case.
- Multi-stream bridge (other cell:* streams): scoped to `cell:skills` only. Future cells get same pattern by addition.

## Effort estimate

| Component | Hours |
|---|---|
| G.1 bridge.py extension (1 endpoint) | 1 |
| G.2 skills_bridge_consumer.py (Pro shim) | 1.5 |
| G.3 plist + cron config | 0.5 |
| G.4 tests (9 total) | 2 |
| Empirical verification + operator deploy | 1 |
| 4-panel brainstorm gate | 1 |
| **Total** | **~7h (~1 day)** |

## Sequencing

1. Spec G v1 (this DRAFT) → 4-panel review (Claude self + Gemini + DeepSeek + NB-1)
2. Spec G v2 with corrections applied
3. PR G.1 (Fly bridge endpoint) → auto-merge SQUASH
4. PR G.2 (Pro consumer + tests) → auto-merge SQUASH
5. Operator deploys plist via chmod 0444 antibody workflow
6. First 5-min tick → verify Pro `XLEN cell:skills` increments from Fly side
7. Verify sentinel consumes both streams via observatory.db green rows from `cell_id='sentinel'`
8. Update Phase 3 spec v2 CORR-2 invariant: "cell:skills is canonical on Pro, Fly→Pro via /api/bridge/skills"

## Open questions for 4-panel

- **Q1**: Should `skills_bridge_consumer` use `XREAD BLOCK ms` (long-poll, requires daemon-style or longer cron) or `XREAD COUNT n` (point-in-time, current spec)? Current = point-in-time, simpler.
- **Q2**: What's the appropriate cron cadence? 5min = ~12 polls/hour × 17 active hours = 204 polls/day = ~50ms each = trivial. 1min = 1020 polls/day. Recommend 5min as soak-test default, can tighten if backlog issue observed.
- **Q3**: Should Fly endpoint use XREAD `BLOCK ms` for efficiency or stay simple? Recommendation: simple non-blocking XREAD COUNT N, since Pro polls every 5min and won't wait. BLOCK only helps if Pro wants to long-poll.
- **Q4**: Authentication — reuse existing `BRIDGE_API_KEY` or new `BRIDGE_SKILLS_API_KEY`? Recommendation: reuse, same auth surface, scope creep minimal.
- **Q5**: After daylight fix lands, should we revisit `DISABLE_BACKGROUND_WORKERS=1` removal Fly-side? Currently UNSET. Phase 2 outbox pattern shipped (PR #618/#620). If 48h post-fix-G shows no asyncpg pool corruption, declare kill-switch deprecated.

## Risk profile

| Risk | Severity | Mitigation |
|---|---|---|
| Fly→Pro HTTP unreachable (Pro offline, NordVPN, DNS) | LOW | Graceful: poll fails, retries next tick, no data loss because Fly stream retains entries (maxlen ~1000 default) |
| Duplicate XADD if state file corruption | LOW | Atomic write. Sentinel HGTConsumer is idempotent (dedup via skill_id hash) |
| Skills stream contains PII | LOW | A.2 handlers already pass through PII filter (existing CrmHGTBridge). Audit before deploy: log first 10 events bridged, manual review. |
| Fly Upstash unreachable from Fly api (rare) | LOW | XREAD fails with 503, Pro retries next tick. No production impact (A.2 handlers are async fire-and-forget). |
| BRIDGE_API_KEY leak | MEDIUM | Reuse existing key. Rotation procedure already in runbook. |
| Pro Redis disk-full (cell:skills grows unbounded) | LOW | MAXLEN ~5000 ensures bounded. ~10KB/entry → 50MB cap. |

## Decision required from operator BEFORE 4-panel

- Approve spec G DRAFT direction (HTTP bridge, NOT redis-to-redis sync, NOT sentinel migration)?
- Approve cron cadence 5min default?
- Approve secret reuse `BRIDGE_API_KEY`?
- Authorize 4-panel brainstorm tomorrow daylight (~1h)?
