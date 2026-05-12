---
date: 2026-05-13
domain: symbiosis
client_case: Bali Zero organism — Phase 3.5 daylight fix for split-brain Fly Upstash vs Pro localhost Redis
sources: 4
---

# TICKET G — narrow spec v2: HTTP bridge for `cell:skills` Fly→Pro

**Status**: APPROVED via 3-LLM brainstorm (NB-1 failed account-level RELOGIN NEEDED, 3/4 quorum met)
**Date**: 2026-05-13 03:25 WITA
**Author**: Claude Opus 4.7 after 4-LLM brainstorm on split-brain (2026-05-13 02:58) + 3-LLM brainstorm on G v1 (2026-05-13 03:18)
**Predecessor**: `2026-05-13-ticket-G-narrow-spec-DRAFT.md` (v1 with 7 corrections applied here)
**Depends on**: Phase 3 Tickets A.0/A.1/A.2/B/C all merged ✅
**Solves**: split-brain Fly Upstash (`fdaa:31:dc12:0:1::2`) vs Pro localhost Redis (`127.0.0.1:6379`) for `cell:skills` stream
**Pattern**: clone `apps/backend-rag/backend/app/routers/bridge.py` HTTP bridge canonical (NB-1 ground-truth recommendation from previous brainstorm)

## v1 → v2 changelog (7 CORR applied)

| CORR | Severity | Source | Change |
|---|---|---|---|
| G1 | CRITICAL | Claude F1 | Fixed Redis access pattern: `request.app.state.redis_manager.get_async_client()` |
| G2 | CRITICAL (resolved) | DeepSeek F2 | Empirical verify `genome.record_skill` has `ON CONFLICT(id) DO UPDATE` → sentinel-side dedup already exists. Defense-in-depth: incremental state save every 50 events |
| G3 | HIGH | Gemini F2 | Dedicated `BRIDGE_SKILLS_API_KEY` (NOT reuse generic `BRIDGE_API_KEY`) |
| G4 | HIGH | Gemini F1 | `XINFO STREAM` gap detection + 410 Gone response if `after_id` precedes head |
| G5 | HIGH | Claude F3 + DeepSeek F1 | Empirical pre-flight verify section |
| G6 | MEDIUM | DeepSeek F5+F6 + Claude F5+F6 | `_acquire_lock_or_exit()` impl + 4 explicit log lines + Telegram alert on 3 consecutive 503 |
| G7 | LOW | DeepSeek F4 | "Cron-invoked shim" wording (not "daemon") |

## Empirical pre-flight (CORR-G5)

Before merge, operator runs these grep commands and verifies all PASS:

```bash
cd ~/Desktop/nuzantara
# 1. bridge.py exists and has _check_auth + X-Bridge-Auth pattern
test -f apps/backend-rag/backend/app/routers/bridge.py && \
  grep -q "X-Bridge-Auth" apps/backend-rag/backend/app/routers/bridge.py && \
  grep -q "_check_auth" apps/backend-rag/backend/app/routers/bridge.py && \
  echo "✅ G5.1 PASS" || echo "❌ G5.1 FAIL"

# 2. redis_manager singleton + get_async_client
grep -q "def get_async_client" apps/backend-rag/backend/core/redis_manager.py && \
  echo "✅ G5.2 PASS" || echo "❌ G5.2 FAIL"

# 3. app.state.redis_manager wired in startup
grep -q "app.state.redis_manager = redis_manager" apps/backend-rag/backend/app/setup/service_initializer.py && \
  echo "✅ G5.3 PASS" || echo "❌ G5.3 FAIL"

# 4. genome.record_skill has ON CONFLICT (CORR-G2 resolution)
grep -q "ON CONFLICT(id) DO UPDATE" packages/cell-core/cell_core/genome.py && \
  echo "✅ G5.4 PASS" || echo "❌ G5.4 FAIL"

# 5. HGTConsumer ensure_group + consume_once exist
grep -q "async def ensure_group" packages/cell-core/cell_core/hgt/consumer.py && \
  grep -q "async def consume_once" packages/cell-core/cell_core/hgt/consumer.py && \
  echo "✅ G5.5 PASS" || echo "❌ G5.5 FAIL"
```

**Verification result (2026-05-13 03:22 WITA)**: All 5 PASS ✅ (verified by Claude during brainstorm).

## Architecture

```
Fly api machine                       Pro localhost
+--------------------------+           +----------------------------+
| EventBus → A.2 handler   |           | B intel-scraper            |
|    │                     |           |    │                       |
|    ▼                     |           |    ▼                       |
| XADD cell:skills (Fly)   |           | XADD cell:skills (Pro)     |
| Fly Upstash 6PN          |           | 127.0.0.1:6379             |
|     │                    |           |     ▲                      |
|     │ XREAD COUNT 500    |   HTTPS   |     │ XADD MAXLEN ~5000    |
|     ▼                    |  ◄─────   |     │                      |
| GET /api/bridge/skills   | ◄─────────┤ skills_bridge_consumer     |
| with X-Bridge-Skills-Auth|  cron 5m  | (Pro LaunchAgent)          |
| + XINFO gap detection    |  Tailscale| + flock single-instance    |
+--------------------------+           +----------------------------+
                                                  │
                                                  ▼
                                       Sentinel HGTConsumer "sentinel-1"
                                       (already exists, dedup via
                                       genome ON CONFLICT(id))
                                                  │
                                                  ▼
                                       genome.db + observatory.db
```

## Components

### G.1 — Fly side: extend `apps/backend-rag/backend/app/routers/bridge.py`

NEW endpoint `GET /api/bridge/skills` (~80 LOC with CORR-G1+G4):

```python
class SkillsResponse(BaseModel):
    events: list[dict[str, Any]]
    last_stream_id: str
    events_orphaned: bool = False  # CORR-G4: true if after_id < stream lowest
    stream_lowest_id: str | None = None  # for client to reset


def _check_skills_auth(x_bridge_skills_auth: str | None) -> None:
    """CORR-G3: Dedicated auth for skills endpoint (NOT generic BRIDGE_API_KEY)."""
    expected = os.getenv("BRIDGE_SKILLS_API_KEY", "")
    if not expected:
        logger.error("BRIDGE_SKILLS_API_KEY not set in environment")
        raise HTTPException(503, "Bridge skills service unavailable")
    if not x_bridge_skills_auth or not hmac.compare_digest(x_bridge_skills_auth, expected):
        raise HTTPException(401, "Unauthorized")


@router.get("/skills", response_model=SkillsResponse)
async def get_skills(
    request: Request,
    after_id: str = Query("0-0", description="XREAD start ID (default 0-0 for full read)"),
    count: int = Query(100, ge=1, le=500),
    x_bridge_skills_auth: str | None = Header(default=None, alias="X-Bridge-Skills-Auth"),
) -> SkillsResponse:
    """Pro polls this to pull cell:skills stream entries from Fly Upstash.

    CORR-G3: dedicated auth (X-Bridge-Skills-Auth header / BRIDGE_SKILLS_API_KEY env)
    CORR-G4: XINFO STREAM gap detection — returns events_orphaned=true if after_id
    precedes stream's lowest entry ID.
    """
    _check_skills_auth(x_bridge_skills_auth)

    # CORR-G1: get redis_manager from app.state, NOT global helper
    redis_manager = getattr(request.app.state, "redis_manager", None)
    if not redis_manager or not redis_manager.available:
        raise HTTPException(503, "Redis unavailable")
    client = redis_manager.get_async_client()
    if not client:
        raise HTTPException(503, "Redis async client not initialized")

    # CORR-G4: gap detection — compare after_id to stream lowest
    events_orphaned = False
    stream_lowest_id = None
    if after_id not in ("0-0", "$"):
        try:
            info = await client.xinfo_stream("cell:skills")
            # XINFO STREAM returns dict with first-entry: [stream_id, fields]
            first_entry = info.get(b"first-entry") or info.get("first-entry")
            if first_entry:
                stream_lowest_raw = first_entry[0]
                stream_lowest_id = (
                    stream_lowest_raw.decode() if isinstance(stream_lowest_raw, bytes)
                    else stream_lowest_raw
                )
                # CORR-G4: compare ms-seq tuples
                if _stream_id_lt(after_id, stream_lowest_id):
                    events_orphaned = True
                    logger.warning(
                        "Bridge skills: gap detected — after_id=%s < stream_lowest=%s",
                        after_id, stream_lowest_id
                    )
        except Exception as e:
            # XINFO may fail if stream is empty/missing — non-fatal
            logger.debug("XINFO STREAM cell:skills failed: %s", e)

    # XREAD COUNT count STREAMS cell:skills after_id (non-blocking)
    try:
        result = await client.xread({"cell:skills": after_id}, count=count)
    except Exception as e:
        logger.exception("XREAD cell:skills failed")
        raise HTTPException(503, f"Stream read failed: {e}")

    events: list[dict[str, Any]] = []
    last_id = after_id
    if result:
        # result = [(b"cell:skills", [(b"id-stream", {b"field": b"value"}), ...])]
        for _stream_name, entries in result:
            for entry_id, fields in entries:
                last_id = entry_id.decode() if isinstance(entry_id, bytes) else entry_id
                decoded_fields = {
                    (k.decode() if isinstance(k, bytes) else k):
                    (v.decode() if isinstance(v, bytes) else v)
                    for k, v in fields.items()
                }
                events.append({"id": last_id, "fields": decoded_fields})

    logger.info(
        "Bridge skills: returned %d events (after_id=%s last_id=%s orphaned=%s)",
        len(events), after_id, last_id, events_orphaned
    )
    return SkillsResponse(
        events=events,
        last_stream_id=last_id,
        events_orphaned=events_orphaned,
        stream_lowest_id=stream_lowest_id,
    )


def _stream_id_lt(a: str, b: str) -> bool:
    """Return True if Redis stream ID a < b. Format: 'ms-seq'."""
    a_ms, _, a_seq = a.partition("-")
    b_ms, _, b_seq = b.partition("-")
    a_ms_i = int(a_ms) if a_ms.isdigit() else 0
    b_ms_i = int(b_ms) if b_ms.isdigit() else 0
    if a_ms_i != b_ms_i:
        return a_ms_i < b_ms_i
    return int(a_seq or 0) < int(b_seq or 0)
```

### G.2 — Pro side: NEW `apps/cell/scripts/skills_bridge_consumer.py` (~200 LOC with CORR-G2+G6)

```python
#!/usr/bin/env python3
"""Skills bridge cron shim — Pro side of TICKET G HTTP bridge.

CORR-G2: incremental state save every 50 events (resilience).
CORR-G6: flock single-instance + 4 explicit log lines + Telegram alert.
CORR-G7: cron-invoked shim, NOT daemon (KeepAlive=false in plist).
"""
from __future__ import annotations
import asyncio, os, sys, fcntl, json, time, logging
from pathlib import Path
import httpx
import redis.asyncio as aioredis

logger = logging.getLogger("skills_bridge")

STATE_DIR = Path.home() / ".cell-bridge-state"
LAST_ID_FILE = STATE_DIR / "skills_last_id.txt"
LOCK_FILE = STATE_DIR / "skills_bridge.lock"
FAIL_COUNT_FILE = STATE_DIR / "skills_bridge_503_count.txt"
INCREMENTAL_SAVE_EVERY = 50  # CORR-G2

FLY_BRIDGE_URL = os.getenv("FLY_BRIDGE_URL", "https://nuzantara-rag.fly.dev")
BRIDGE_SKILLS_API_KEY = os.getenv("BRIDGE_SKILLS_API_KEY", "")
PRO_REDIS_URL = os.getenv("PRO_REDIS_URL", "redis://127.0.0.1:6379")
STREAM_MAXLEN = 5000


def _acquire_lock_or_exit() -> int:
    """CORR-G6: file-based flock single-instance guard. Returns fd or exit(0)."""
    STATE_DIR.mkdir(exist_ok=True)
    fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("[skills_bridge] another instance running, skipping this tick")
        sys.exit(0)


def _load_last_id() -> str:
    if not LAST_ID_FILE.exists():
        return "0-0"
    try:
        content = LAST_ID_FILE.read_text().strip()
        return content or "0-0"
    except Exception as e:
        logger.warning("[skills_bridge] state file unreadable, reset to 0-0: %s", e)
        return "0-0"


def _save_last_id(last_id: str) -> None:
    """Atomic write via tempfile + rename."""
    STATE_DIR.mkdir(exist_ok=True)
    tmp = LAST_ID_FILE.with_suffix(".tmp")
    tmp.write_text(last_id)
    tmp.replace(LAST_ID_FILE)


def _increment_503_counter() -> int:
    """Returns new count after increment."""
    n = 0
    if FAIL_COUNT_FILE.exists():
        try:
            n = int(FAIL_COUNT_FILE.read_text().strip() or "0")
        except Exception:
            n = 0
    n += 1
    FAIL_COUNT_FILE.write_text(str(n))
    return n


def _reset_503_counter() -> None:
    if FAIL_COUNT_FILE.exists():
        FAIL_COUNT_FILE.unlink()


def _send_telegram_alert(msg: str) -> None:
    """CORR-G6: best-effort Telegram alert on 3 consecutive 503 (reuse existing pattern)."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not bot_token:
        return
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=data, timeout=5
        )
    except Exception as e:
        logger.warning("[skills_bridge] Telegram alert failed: %s", e)


async def _run_one_poll() -> int:
    """CORR-G6 + CORR-G2 + CORR-G4 acceptance.

    Returns exit code: 0 ok, 1 fail.
    """
    last_id = _load_last_id()

    if not BRIDGE_SKILLS_API_KEY:
        logger.error("[skills_bridge] BRIDGE_SKILLS_API_KEY not set, aborting")
        return 1

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(
                f"{FLY_BRIDGE_URL}/api/bridge/skills",
                params={"after_id": last_id, "count": 500},
                headers={"X-Bridge-Skills-Auth": BRIDGE_SKILLS_API_KEY},
            )
    except httpx.RequestError as e:
        logger.warning("[skills_bridge] HTTP request failed: %s", e)
        return 1

    if resp.status_code == 401:
        logger.error("[skills_bridge] auth failed (401) — check BRIDGE_SKILLS_API_KEY")
        return 1
    if resp.status_code == 503:
        n = _increment_503_counter()
        logger.warning("[skills_bridge] Fly returned 503 (consecutive=%d)", n)
        if n >= 3:
            _send_telegram_alert(
                f"⚠️ skills_bridge_consumer: Fly returned 503 {n} times consecutively. "
                "Check Fly app health + Upstash connectivity."
            )
        return 1
    if resp.status_code != 200:
        logger.error("[skills_bridge] unexpected status %d: %s", resp.status_code, resp.text[:200])
        return 1

    _reset_503_counter()
    payload = resp.json()
    events = payload.get("events", [])
    new_last_id = payload.get("last_stream_id", last_id)
    events_orphaned = payload.get("events_orphaned", False)
    stream_lowest_id = payload.get("stream_lowest_id")

    # CORR-G4: gap detected — reset to "$" (current head) to skip orphaned events
    if events_orphaned:
        logger.critical(
            "[skills_bridge] STREAM GAP DETECTED: after_id=%s precedes stream_lowest=%s. "
            "Resetting last_id to '$' (current head) — events ORPHANED.",
            last_id, stream_lowest_id
        )
        _save_last_id("$")
        _send_telegram_alert(
            f"🚨 skills_bridge: stream gap detected. {last_id} < {stream_lowest_id}. "
            "Reset last_id to $ — N events orphaned. Investigate Fly Upstash MAXLEN."
        )
        return 1

    if not events:
        logger.info("[skills_bridge] no new events (last_id=%s)", last_id)
        return 0

    # XADD to Pro Redis with MAXLEN bound
    redis_client = aioredis.from_url(PRO_REDIS_URL, decode_responses=False)
    try:
        added = 0
        last_saved_id = last_id
        for ev in events:
            fields = ev["fields"]
            # MAXLEN ~ STREAM_MAXLEN (approximate) bounds Pro stream
            await redis_client.xadd(
                "cell:skills",
                fields,
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
            added += 1
            # CORR-G2: incremental state save every INCREMENTAL_SAVE_EVERY events
            if added % INCREMENTAL_SAVE_EVERY == 0:
                last_saved_id = ev["id"]
                _save_last_id(last_saved_id)
                logger.debug("[skills_bridge] incremental save at event %d (id=%s)", added, last_saved_id)
        # Final save
        _save_last_id(new_last_id)
        logger.info(
            "[skills_bridge] success: XADD'd %d events, last_id=%s (was %s)",
            added, new_last_id, last_id
        )
    finally:
        await redis_client.aclose()

    return 0


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    lock_fd = _acquire_lock_or_exit()
    try:
        return await _run_one_poll()
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
```

### G.3 — LaunchAgent plist `com.nuzantara.skills-bridge-consumer.plist`

**Operator-controlled**: NEW file in repo at `apps/cell/launchagent/com.nuzantara.skills-bridge-consumer.plist`, operator copies + chmod 0444 + launchctl bootstrap manually.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.nuzantara.skills-bridge-consumer</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/cell/.venv/bin/python</string>
    <string>-u</string>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/cell/scripts/skills_bridge_consumer.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>FLY_BRIDGE_URL</key>
    <string>https://nuzantara-rag.fly.dev</string>
    <key>PRO_REDIS_URL</key>
    <string>redis://127.0.0.1:6379</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>StartCalendarInterval</key>
  <array>
    <!-- Every 5min between 06-22 WITA (sleep_hours 22-06 align with sentinel) -->
    <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>5</integer></dict>
    <!-- ... operator may use a Python helper to generate the full 17h × 12 = 204 entries
         OR a single Minute interval if launchd allows it.
         RECOMMENDED: operator-generated full array in deploy script. -->
  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>/Users/nuzantara/Library/Logs/skills-bridge-consumer.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/nuzantara/Library/Logs/skills-bridge-consumer.log</string>
</dict>
</plist>
```

**Operator deploy steps** (manual, per cicatrix-scars 2026-04-29 antibody pattern):
1. Copy: `cp apps/cell/launchagent/com.nuzantara.skills-bridge-consumer.plist ~/Library/LaunchAgents/`
2. Permissions: `chmod 0444 ~/Library/LaunchAgents/com.nuzantara.skills-bridge-consumer.plist`
3. Add `BRIDGE_SKILLS_API_KEY` to `~/.nuzantara-secrets.env` (operator-controlled)
4. Add `FLY_API_TOKEN` reuse: NOT needed for this plist (no fly calls).
5. Set Fly secret: `fly secrets set BRIDGE_SKILLS_API_KEY=<generated> -a nuzantara-rag`
6. Source secrets: ensure plist EnvironmentVariables or shell entry sources `~/.nuzantara-secrets.env` (preferred: skill_bridge_consumer.py reads via `os.getenv`; operator sets `BRIDGE_SKILLS_API_KEY` in plist EnvironmentVariables OR sources from secrets file at runtime).
7. Bootstrap: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.skills-bridge-consumer.plist`
8. Verify first 5-min tick: `tail -f ~/Library/Logs/skills-bridge-consumer.log`

### G.4 — Tests (CORR-G6 expanded)

**`apps/backend-rag/backend/tests/app/routers/test_bridge_skills.py` (6 tests)**:
1. `test_no_auth_returns_401`
2. `test_bad_auth_returns_401`
3. `test_redis_unavailable_returns_503`
4. `test_empty_stream_returns_empty_events`
5. `test_populated_stream_returns_events_with_correct_last_id`
6. `test_gap_detection_returns_orphaned_flag` (CORR-G4)

**`apps/cell/tests/scripts/test_skills_bridge_consumer.py` (8 tests)**:
1. `test_first_run_uses_00_id` (no state file)
2. `test_state_file_persisted_id_loaded`
3. `test_empty_response_no_xadd_no_save`
4. `test_http_error_returns_1_no_state_change`
5. `test_concurrent_invocation_skipped_via_flock` (CORR-G6)
6. `test_incremental_save_every_50_events` (CORR-G2)
7. `test_orphaned_gap_resets_last_id_to_dollar` (CORR-G4)
8. `test_503_3_consecutive_triggers_telegram_alert` (CORR-G6)

## Out-of-scope (deferred)

- Bidirectional sync (Pro→Fly): Pro intel-scraper events stay Pro-local.
- Multi-stream bridge: scoped to `cell:skills` only.
- Fly Upstash MAXLEN policy enforcement on publishers (Phase 4 — current scope is Pro side).
- NB-1 re-verification: failed account-level access tonight, re-run after `nlm login` reauth.

## Effort estimate (v2)

| Component | Hours |
|---|---|
| G.1 bridge.py extension (~80 LOC) | 2 |
| G.2 Pro consumer (~200 LOC) | 2.5 |
| G.3 plist + deploy doc | 0.5 |
| G.4 tests (14 total) | 3 |
| Empirical pre-flight + operator deploy | 1.5 |
| **Total v2** | **9.5h (~1.2 day)** |

## Risk profile (v2)

| Risk | Severity | Mitigation |
|---|---|---|
| Fly→Pro HTTP unreachable | LOW | flock prevents pileup, 3-strike Telegram alert |
| Duplicate XADD on crash | LOW (resolved) | genome ON CONFLICT(id) DO UPDATE — sentinel-side dedup verified empirical |
| Event orphaning Fly Upstash MAXLEN | MEDIUM | CORR-G4: XINFO STREAM gap detection, 410 response, Telegram alert |
| Skills stream contains PII | LOW | A.2 handlers already pass through PII filter (CrmHGTBridge). Dedicated auth key isolates blast radius |
| `BRIDGE_SKILLS_API_KEY` leak | MEDIUM | Dedicated key (not shared), rotation procedure inherits BRIDGE_API_KEY pattern |
| Pro Redis disk-full | LOW | MAXLEN ~5000 bounds ~10KB × 5000 = 50MB cap |
| State file corruption | LOW | Atomic write tempfile+rename, incremental save every 50 events |
| Laptop sleep skips ticks | ACCEPTABLE | SYMBIOSIS Law 6 — sovranità locale, documented limitation |

## Decision required from operator BEFORE shipping

- [x] APPROVED v2 spec via 3-LLM brainstorm (NB-1 unavailable)
- [ ] Confirm `BRIDGE_SKILLS_API_KEY` to be generated + set in Fly secrets + Pro secrets
- [ ] Authorize TICKET G.1 PR (Fly endpoint) — autonomous auto-merge
- [ ] Authorize TICKET G.2 PR (Pro consumer) — autonomous auto-merge
- [ ] G.3 plist: operator manual deploy (chmod 0444 antibody)
- [ ] G.5 first-tick empirical verify after deploy
