---
date: 2026-05-12
wave: 1
producer: intel_radar
status: ready-to-implement
codex_review: applied
---

# Wave 1 — intel_radar → Intel Lake

## Corrections from Codex GPT-5.5 review (8 blockers integrated)

### 1. Migration number

- **NOT** 147 (collides with `147_federation_alert_proposals.sql`)
- Verify next available: `ls apps/backend-rag/backend/db/migrations_v2/` → pick first unused N
- Target: **157** (assuming 152-156 exist per test files)

### 2. Producer-side durable outbox (replaces "best-effort HTTP")

intel_radar writes to a local SQLite outbox in same transaction as `intel_radar_findings`:

```sql
-- ~/scripts/intel_lake_outbox.db
CREATE TABLE IF NOT EXISTS intel_lake_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    producer_name TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    enqueued_at TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at TEXT,
    attempts INTEGER DEFAULT 0,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON intel_lake_outbox(delivered_at) WHERE delivered_at IS NULL;
```

Drain worker (separate LaunchAgent every 60s):

- SELECT 100 rows WHERE delivered_at IS NULL ORDER BY id LIMIT 100
- POST batch to `/api/intel/lake/observations:batch`
- ON success: UPDATE delivered_at = NOW()
- ON fail: attempts++ + last_error. Stop retry after 10 attempts (manual review needed)

### 3. UPSERT policy (append-only items, mutate only last_seen_at)

```sql
INSERT INTO intel_items (canonical_url, content_hash, title, summary, source_domain, ...)
VALUES ($1, $2, $3, $4, $5, ...)
ON CONFLICT (canonical_url) DO UPDATE
  SET last_seen_at = NOW(),
      -- DO NOT mutate title, summary, content_hash, raw_payload
      -- They are immutable post-first-write
  WHERE intel_items.content_hash = $2  -- guard: only same-content updates
  RETURNING id, (xmax = 0) AS is_new;
```

If `content_hash` differs from existing → **content drift**: do NOT update, INSERT new row with same canonical_url + `_v2` suffix (or NULL → next sequence id). Decision deferred to Tier 2 LLM router.

**Observations always inserted** regardless of item conflict:

```sql
INSERT INTO intel_observations (item_id, producer_name, raw_payload, score)
VALUES ((SELECT id FROM intel_items WHERE canonical_url=$1), $2, $3, $4);
```

### 4. intel_radar bypass ON CONFLICT for lake-call

Current `intel_radar.py` does `INSERT INTO intel_radar_findings ... ON CONFLICT (canonical_url) DO NOTHING`.

Patch:

```python
# After PG INSERT (whether new or conflict):
# ALWAYS enqueue to lake outbox — observations table is append-only
outbox_payload = build_lake_payload(finding)
sqlite_outbox.enqueue(outbox_payload)
```

This way, even if `intel_radar_findings` skips (DO NOTHING), the lake gets the observation.

### 5. raw_payload size cap

- Adapter strips HTML server-side: `BeautifulSoup(html, 'html.parser').get_text()[:8000]`
- Server endpoint: `LENGTH(payload_str) < 50000` → reject 413 Payload Too Large
- raw_payload JSONB column: max 50KB explicit limit in adapter

### 6. Auth

New env `INTEL_LAKE_PRODUCER_TOKEN` in `~/.nuzantara-backend-secrets.env`:

- Generated: `openssl rand -hex 32`
- Fly secret: `fly secrets set INTEL_LAKE_PRODUCER_TOKEN=<value>`
- Producer adapter reads from `~/.nuzantara-secrets.env`
- Endpoint validates: `if request.headers.get('x-producer-token') != settings.INTEL_LAKE_PRODUCER_TOKEN: return 401`
- Audit log per request: `(producer_name, ip, timestamp, status)` → PG `intel_lake_audit_log`

### 7. Test matrix (replaces happy-path)

```python
# apps/backend-rag/backend/tests/unit/routers/test_intel_lake_router.py
def test_endpoint_idempotent_same_url():
    """Same canonical_url → 200 + new observation, items unchanged."""

def test_endpoint_content_drift():
    """Same URL different content_hash → new item not duplicate."""

def test_endpoint_oversize_payload_413():
    """raw_payload >50KB → 413 Payload Too Large."""

def test_endpoint_missing_token_401():
    """No x-producer-token → 401 Unauthorized."""

def test_endpoint_wrong_token_401():
    """Wrong token → 401 + audit log entry."""

def test_endpoint_outbox_notify_event():
    """New item → events_outbox row + NOTIFY intel_lake_event."""

def test_endpoint_concurrent_upsert_no_dup():
    """2 producers same URL race → 1 item + 2 observations."""

def test_migration_157_rollback():
    """Migration has -- === ROLLBACK === marker per Squawk."""

def test_pg_channel_map_intel_lake_event():
    """PG_CHANNEL_MAP must include intel_lake_event."""

def test_outbox_drain_retry_on_failure():
    """SQLite outbox row attempts increments on HTTP fail."""
```

### 8. Shadow validation stop-loss (replaces "polling theater")

`~/scripts/intel-lake-shadow-validate.sh`:

- Runs every 6h via LaunchAgent (not daily — faster signal)
- Query: count rows in `intel_radar_findings` last 48h vs count in `intel_items WHERE producer=intel_radar` last 48h
- **Divergence threshold 5%**:
  - <5% divergence → SILENT (acceptable noise)
  - 5-15% → Telegram WARNING + investigate
  - > 15% → Telegram CRITICAL + **block Wave 2** (file `.intel-lake-wave2-blocked` touched, Wave 2 cron checks file before starting)

## Implementation steps (order matters)

1. ✅ **DONE**: design doc + Wave 1 plan committed
2. **Verify next migration number**: ls migrations_v2, pick first unused
3. **Generate INTEL_LAKE_PRODUCER_TOKEN**: openssl rand -hex 32, save to secrets env + Fly secret
4. **Write migration `157_intel_lake_schema.sql`**: items + observations + trigger + outbox channel registration in PG_CHANNEL_MAP (separate test for this)
5. **Write `IntelLakeService`**: backend service module with UPSERT logic + content drift handling
6. **Write router `intel_lake.py`**: `POST /api/intel/lake/observations` + `POST :batch` + audit log
7. **Write test matrix** (10 tests above)
8. **Run tests locally**: `pytest backend/tests/unit/routers/test_intel_lake_router.py -v`
9. **Deploy migration**: gh PR + CI + auto-merge + post-deploy migration runner (per cicatrix scar)
10. **Patch intel_radar.py**: dual-write to local SQLite outbox + ON CONFLICT bypass
11. **Bootstrap drain worker LaunchAgent**: `com.balizero.intel-lake.outbox-drain.minute`
12. **Bootstrap validation LaunchAgent**: `com.balizero.intel-lake.shadow-validate.6h`
13. **Smoke test**: kickstart intel_radar manually, verify finding appears in `intel_items` + `intel_observations` within 60s
14. **Shadow-write phase 7 days**: monitor divergence
15. **If green at day 7**: write closure doc, proceed to Wave 2

## Files to modify/create

| Action | Path                                                                                              |
| ------ | ------------------------------------------------------------------------------------------------- |
| CREATE | `apps/backend-rag/backend/db/migrations_v2/157_intel_lake_schema.sql`                             |
| CREATE | `apps/backend-rag/backend/services/intel/intel_lake_service.py`                                   |
| CREATE | `apps/backend-rag/backend/app/routers/intel_lake.py`                                              |
| MODIFY | `apps/backend-rag/backend/app/setup/router_registration.py` (register intel_lake router)          |
| MODIFY | `apps/backend-rag/backend/services/events/__init__.py` (add `intel_lake_event` to PG_CHANNEL_MAP) |
| CREATE | `apps/backend-rag/backend/tests/unit/routers/test_intel_lake_router.py` (10 tests)                |
| CREATE | `apps/backend-rag/backend/tests/db/test_migration_157_intel_lake.py`                              |
| MODIFY | `~/scripts/cron-agent-python/intel_radar.py` (dual-write outbox)                                  |
| CREATE | `~/scripts/intel-lake-outbox-drain.py`                                                            |
| CREATE | `~/scripts/intel-lake-shadow-validate.sh`                                                         |
| CREATE | `~/Library/LaunchAgents/com.balizero.intel-lake.outbox-drain.minute.plist`                        |
| CREATE | `~/Library/LaunchAgents/com.balizero.intel-lake.shadow-validate.6h.plist`                         |

Total: 4 create + 1 modify backend, 1 modify + 2 create scripts, 2 create plist = 10 files.

## Next: Wave 2 prerequisites

Wave 2 (fact_checker + t4_monitor + yt_monitor) starts ONLY if:

- `.intel-lake-wave2-blocked` file absent
- 7d shadow-write validation report shows divergence <5%
- Endpoint p99 latency <500ms
- No 5xx errors in /api/intel/lake/observations in last 24h
