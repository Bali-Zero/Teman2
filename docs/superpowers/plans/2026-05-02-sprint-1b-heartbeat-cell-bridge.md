# Sprint 1.B — Heartbeat Cell-side Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `backend.api` and 4 channel webhook organs visible to `genome_aggregator_sensor` by writing sidecar liveness files (`~/.organism/last_seen/<id>.json`) from Cell sensors on Pro post-poll. Closes gap 2 of the Era Post-Agentica brief.

**Architecture:** Cell-side bridge. Backend exposes a minimal `/api/channels/{name}/health` endpoint (~30 LOC, GET-only, no auth). Cell `health_sensor.py` (already polls `/health`) and `channel_sensor.py` (already polls queue depth) call `emit_organ_last_seen` after each successful poll. Filesystem state lives on Pro (Pilastro 6 sovranità locale), survives daemon restart, no Fly ephemeral filesystem dependency.

**Tech Stack:** Python 3.11 (`apps/cell` + `apps/backend-rag`), FastAPI router, asyncpg, pytest.

**Reference spec:** `docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md` §3.3.5 (post-2026-05-02 refresh).

**Branch:** `feat/post-agentic-heartbeat-cell-bridge-2026-05-02` (parent: `main`)

**Coordination:**

- Sprint 1.A (skill registry extension) parallel allowed — touches `apps/backend-rag/backend/scripts/seed_initial_skills.py` only, zero overlap.
- Observatory PR-5 Task 5.3 — touches `cell_core.observatory` + `pulse.py` + plist env var. Sprint 1.B touches `apps/cell/cell/sensors/{health_sensor,channel_sensor}.py`. **Different files, zero conflict**.

**L2 Autonomous Operations:** commits/push/PR autonomous. Backend deploy via `fly-deploy.yml` autonomous on green CI. Cell-side changes deployed via Pro pull (`scripts/sync-pro.sh` or post-commit hook).

---

## File Structure (created/modified in this plan)

| File                                                                           | Responsibility                                                                                                          |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `apps/backend-rag/backend/app/routers/channel_health.py` (NEW)                 | Endpoint `GET /api/channels/{name}/health` returning `{status, ts, last_event_seen_at, queue_depth}`                    |
| `apps/backend-rag/backend/app/setup/router_manifest.py` (MODIFY)               | Register new `channel_health` router                                                                                    |
| `apps/cell/cell/sensors/health_sensor.py` (MODIFY)                             | Post-poll, call `emit_organ_last_seen('backend.api', ...)`                                                              |
| `apps/cell/cell/sensors/channel_sensor.py` (MODIFY)                            | Extend to also poll `/api/channels/{name}/health` for each channel + emit `emit_organ_last_seen('channel.{name}', ...)` |
| `apps/backend-rag/backend/tests/unit/app/routers/test_channel_health.py` (NEW) | Verify endpoint returns valid schema for each channel name                                                              |
| `apps/cell/tests/test_health_sensor_emits_sidecar.py` (NEW)                    | Verify health_sensor calls `emit_organ_last_seen` post-poll, mocks fs                                                   |
| `apps/cell/tests/test_channel_sensor_emits_sidecar.py` (NEW)                   | Verify channel_sensor emits one sidecar per channel post-poll                                                           |

**Out of scope:**

- Genoma auto-discovery (Sprint 1.C, deferred for Observatory coordination)
- New PG channels in events_outbox for heartbeat (using state file approach instead)
- Plist edits (Sprint 1.C)
- backend.api endpoints under different names (only `/api/channels/{name}/health` is new)

---

## Task 1: Branch creation

**Files:** N/A

- [ ] **Step 1: Sync main**

```bash
git checkout main
git fetch origin main
git pull origin main --ff-only
git status -s | grep -v 'research/\|notebooklm/' | head -5
```

Expected: empty output.

- [ ] **Step 2: Create feature branch**

```bash
git checkout -b feat/post-agentic-heartbeat-cell-bridge-2026-05-02
```

Expected: `Switched to a new branch 'feat/post-agentic-heartbeat-cell-bridge-2026-05-02'`

---

## Task 2: New backend router `channel_health.py`

**Files:**

- Create: `apps/backend-rag/backend/app/routers/channel_health.py`
- Test: `apps/backend-rag/backend/tests/unit/app/routers/test_channel_health.py`

### Schema

`GET /api/channels/{name}/health` where `name ∈ {whatsapp, telegram, instagram, web}`. Returns:

```json
{
  "status": "ok" | "degraded" | "fail",
  "ts": <unix_epoch_float>,
  "channel": "whatsapp",
  "queue_depth": <int>,
  "last_event_seen_at": <unix_epoch_float | null>,
  "metadata": {}
}
```

`status` derived from queue_depth thresholds (mirror of ChannelSensor: ≤20 ok, 21-100 degraded, >100 fail). `last_event_seen_at` from latest `inbound_webhooks.received_at WHERE channel=$1`.

- [ ] **Step 1: Write failing test**

Create `apps/backend-rag/backend/tests/unit/app/routers/test_channel_health.py`:

```python
"""Verify /api/channels/{name}/health endpoint structure for Sprint 1.B Cell-side bridge.

Spec ref: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5
"""
from fastapi.testclient import TestClient
import pytest


def test_channel_health_returns_correct_schema_for_known_channels(monkeypatch):
    """Endpoint returns the heartbeat schema for each of the 4 known channels."""
    from backend.app.main import app

    client = TestClient(app)
    for name in ("whatsapp", "telegram", "instagram", "web"):
        r = client.get(f"/api/channels/{name}/health")
        assert r.status_code == 200, f"{name} returned {r.status_code}"
        body = r.json()
        assert body["channel"] == name
        assert body["status"] in {"ok", "degraded", "fail"}
        assert isinstance(body["ts"], (int, float))
        assert isinstance(body["queue_depth"], int)
        assert "last_event_seen_at" in body  # may be null
        assert isinstance(body["metadata"], dict)


def test_channel_health_unknown_channel_returns_404():
    """Unknown channel name → 404 (whitelist of 4 known names)."""
    from backend.app.main import app

    client = TestClient(app)
    r = client.get("/api/channels/unknown_channel/health")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test, verify fails (router not yet registered)**

```bash
cd apps/backend-rag
PYTHONPATH=. python -m pytest backend/tests/unit/app/routers/test_channel_health.py -v 2>&1 | tail -10
```

Expected: 2 FAILED with `404 not found` on `whatsapp` (router missing).

- [ ] **Step 3: Create router**

Create `apps/backend-rag/backend/app/routers/channel_health.py`:

```python
"""Channel health endpoint for Cell-side heartbeat bridge.

Sprint 1.B (2026-05-02) — exposes per-channel health for Cell's
channel_sensor to poll. Cell on Pro then writes sidecar files to
~/.organism/last_seen/channel.{name}.json which genome_aggregator_sensor
consumes.

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5

Status thresholds (mirror of ChannelSensor):
- ok:        queue_depth <= 20
- degraded:  21 <= queue_depth <= 100
- fail:      queue_depth > 100
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_db_pool

router = APIRouter(prefix="/api/channels", tags=["channels", "health"])

KNOWN_CHANNELS: frozenset[str] = frozenset(
    {"whatsapp", "telegram", "instagram", "web"}
)

_OK_CEILING = 20
_DEGRADED_CEILING = 100


def _classify(queue_depth: int) -> str:
    if queue_depth <= _OK_CEILING:
        return "ok"
    if queue_depth <= _DEGRADED_CEILING:
        return "degraded"
    return "fail"


@router.get("/{name}/health")
async def channel_health(name: str, db_pool: Any = Depends(get_db_pool)) -> dict[str, Any]:
    """Return current health for a known channel name.

    Args:
        name: one of whatsapp/telegram/instagram/web.

    Returns:
        {status, ts, channel, queue_depth, last_event_seen_at, metadata}.

    Raises:
        404: if name not in KNOWN_CHANNELS.
    """
    if name not in KNOWN_CHANNELS:
        raise HTTPException(status_code=404, detail=f"unknown channel: {name}")

    queue_depth = 0
    last_event_seen_at: float | None = None

    if db_pool is not None:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE processed_at IS NULL) AS pending,
                    EXTRACT(EPOCH FROM MAX(received_at)) AS last_ts
                FROM inbound_webhooks
                WHERE channel = $1 AND received_at >= NOW() - INTERVAL '60 minutes'
                """,
                name,
            )
            if row is not None:
                queue_depth = int(row["pending"] or 0)
                last_event_seen_at = (
                    float(row["last_ts"]) if row["last_ts"] is not None else None
                )

    return {
        "status": _classify(queue_depth),
        "ts": time.time(),
        "channel": name,
        "queue_depth": queue_depth,
        "last_event_seen_at": last_event_seen_at,
        "metadata": {
            "thresholds": {"ok": _OK_CEILING, "degraded": _DEGRADED_CEILING},
            "window_minutes": 60,
        },
    }
```

- [ ] **Step 4: Register router in manifest**

Read `apps/backend-rag/backend/app/setup/router_manifest.py` and find the existing `RouterEntry` list. Add (in alphabetical order):

```python
    RouterEntry(
        module_path="backend.app.routers.channel_health",
        process_groups=("api",),  # only api group serves HTTP, not rag
        prefix=None,  # router has its own prefix /api/channels
        tags=("channels", "health"),
    ),
```

- [ ] **Step 5: Re-run tests, verify pass**

```bash
cd apps/backend-rag
PYTHONPATH=. python -m pytest backend/tests/unit/app/routers/test_channel_health.py -v 2>&1 | tail -10
```

Expected: 2 PASSED.

- [ ] **Step 6: Run import chain validation (cicatrix safety)**

```bash
cd apps/backend-rag
PYTHONPATH=. python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/app/routers/channel_health.py \
        apps/backend-rag/backend/app/setup/router_manifest.py \
        apps/backend-rag/backend/tests/unit/app/routers/test_channel_health.py
git commit -m "feat(api): channel_health endpoint for Cell-side heartbeat bridge (Sprint 1.B)

GET /api/channels/{name}/health returns {status, ts, queue_depth,
last_event_seen_at, metadata} for whatsapp/telegram/instagram/web.
Status derived from inbound_webhooks queue depth thresholds.

Cell on Pro will poll this + write sidecar files to ~/.organism/last_seen/
for genome_aggregator_sensor consumption (closes gap 2 of Era Post-Agentica).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Cell `health_sensor.py` emits sidecar post-poll

**Files:**

- Modify: `apps/cell/cell/sensors/health_sensor.py`
- Test: `apps/cell/tests/test_health_sensor_emits_sidecar.py` (NEW)

### Logic

After each successful poll of `/health`, map `HealthReading` → `emit_organ_last_seen` status:

| HealthReading                | Emit status |
| ---------------------------- | ----------- |
| `reachable=True, status=200` | `ok`        |
| `reachable=True, status≠200` | `degraded`  |
| `reachable=False`            | `fail`      |

Metadata includes `http_status`, `latency_ms`. Failures of `emit_organ_last_seen` itself MUST NOT raise (already enforced by emitter contract — verify).

- [ ] **Step 1: Write failing test**

Create `apps/cell/tests/test_health_sensor_emits_sidecar.py`:

```python
"""Sprint 1.B 2026-05-02: HealthSensor must emit sidecar liveness file post-poll.

Spec ref: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest


def test_health_sensor_emits_ok_sidecar_on_200(tmp_path):
    """Reachable + status=200 → emit ok with metadata."""
    from cell.sensors import health_sensor as hs

    # Synthesize a successful reading via monkeypatch
    fake_reading = hs.HealthReading(
        timestamp=datetime.now(tz=timezone.utc),
        reachable=True,
        status_code=200,
        latency_ms=47.0,
    )

    sidecars: list[tuple[str, str, dict]] = []

    def fake_emit(organ_id, status, metadata=None, **kwargs):
        sidecars.append((organ_id, status, dict(metadata or {})))
        return True

    with patch.object(hs, "emit_organ_last_seen", side_effect=fake_emit):
        hs.bridge_reading_to_sidecar(fake_reading)

    assert sidecars == [
        (
            "backend.api",
            "ok",
            {"http_status": 200, "latency_ms": 47.0},
        ),
    ]


def test_health_sensor_emits_degraded_sidecar_on_5xx(tmp_path):
    """Reachable + non-200 → degraded."""
    from cell.sensors import health_sensor as hs

    fake_reading = hs.HealthReading(
        timestamp=datetime.now(tz=timezone.utc),
        reachable=True,
        status_code=503,
        latency_ms=12.0,
    )

    sidecars: list[tuple[str, str, dict]] = []
    with patch.object(hs, "emit_organ_last_seen", side_effect=lambda *a, **k: sidecars.append(a) or True):
        hs.bridge_reading_to_sidecar(fake_reading)

    assert len(sidecars) == 1
    assert sidecars[0][:2] == ("backend.api", "degraded")


def test_health_sensor_emits_fail_sidecar_on_unreachable(tmp_path):
    """Unreachable → fail."""
    from cell.sensors import health_sensor as hs

    fake_reading = hs.HealthReading(
        timestamp=datetime.now(tz=timezone.utc),
        reachable=False,
        status_code=0,
    )

    sidecars: list[tuple[str, str, dict]] = []
    with patch.object(hs, "emit_organ_last_seen", side_effect=lambda *a, **k: sidecars.append(a) or True):
        hs.bridge_reading_to_sidecar(fake_reading)

    assert len(sidecars) == 1
    assert sidecars[0][:2] == ("backend.api", "fail")
```

- [ ] **Step 2: Run test, verify fail (function not yet defined)**

```bash
cd apps/cell
PYTHONPATH=. python -m pytest tests/test_health_sensor_emits_sidecar.py -v 2>&1 | tail -10
```

Expected: 3 FAILED with `AttributeError: bridge_reading_to_sidecar`.

- [ ] **Step 3: Add bridge function to health_sensor.py**

Read `apps/cell/cell/sensors/health_sensor.py` and identify the existing class/structure. Add at module level (after imports + dataclass HealthReading):

```python
from cell.utils.organ_emitter import emit_organ_last_seen


_BACKEND_API_ORGAN_ID = "backend.api"


def bridge_reading_to_sidecar(reading: HealthReading) -> bool:
    """Translate a HealthReading into a Genoma sidecar file.

    Sprint 1.B 2026-05-02: backend.api lives on Fly.io with ephemeral
    filesystem; it cannot write the sidecar itself. Cell on Pro polls
    /health and bridges the result into ~/.organism/last_seen/backend.api.json
    via emit_organ_last_seen.

    Best-effort: never raises. Returns True on success, False on swallowed I/O failure.

    Mapping:
        reachable=True, status=200      → "ok"
        reachable=True, status!=200     → "degraded"
        reachable=False                 → "fail"
    """
    if not reading.reachable:
        status = "fail"
    elif reading.status_code == 200:
        status = "ok"
    else:
        status = "degraded"

    metadata: dict[str, Any] = {"http_status": reading.status_code}
    latency = getattr(reading, "latency_ms", None)
    if latency is not None:
        metadata["latency_ms"] = latency

    return emit_organ_last_seen(_BACKEND_API_ORGAN_ID, status, metadata=metadata)
```

If `HealthReading` does not currently have `latency_ms` field, add it as optional (default `None`).

- [ ] **Step 4: Wire bridge into the existing sensor's read/poll method**

Find the existing `HealthSensor.read()` (or equivalent) method that returns `HealthReading`. After the return value is computed, insert (before `return reading`):

```python
        # Sprint 1.B Cell-side bridge: translate to Genoma sidecar
        try:
            bridge_reading_to_sidecar(reading)
        except Exception as exc:  # pragma: no cover — best-effort, never raise
            logger.debug(f"sidecar bridge failed: {exc}")
```

- [ ] **Step 5: Re-run tests, verify pass**

```bash
cd apps/cell
PYTHONPATH=. python -m pytest tests/test_health_sensor_emits_sidecar.py -v 2>&1 | tail -10
```

Expected: 3 PASSED.

- [ ] **Step 6: Run full Cell test suite (no regression)**

```bash
cd apps/cell
PYTHONPATH=. python -m pytest tests/ -q 2>&1 | tail -10
```

Expected: existing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/cell/cell/sensors/health_sensor.py \
        apps/cell/tests/test_health_sensor_emits_sidecar.py
git commit -m "feat(cell): health_sensor bridges /health poll to Genoma sidecar (Sprint 1.B)

Adds bridge_reading_to_sidecar() that translates HealthReading into
emit_organ_last_seen('backend.api', status) on Pro filesystem.

Mapping:
- reachable=True, status=200    → ok
- reachable=True, status!=200   → degraded
- reachable=False               → fail

Best-effort: emit failures swallowed via debug log, never raise.
Closes gap 2 (backend.api visibility) for genome_aggregator_sensor.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Cell `channel_sensor.py` polls + emits per-channel sidecar

**Files:**

- Modify: `apps/cell/cell/sensors/channel_sensor.py`
- Test: `apps/cell/tests/test_channel_sensor_emits_sidecar.py` (NEW)

### Logic

Existing `ChannelSensor` queries DB for queue depth. Sprint 1.B extends it with HTTP poll to `/api/channels/{name}/health` for each of 4 channels and emits one sidecar per channel.

Two modes (controlled by constructor flag):

- `db_only=True` (default for backward compat): existing behavior, no HTTP poll.
- `db_only=False`: HTTP poll + emit sidecar for each channel.

Cell `main.py` will switch to `db_only=False` in a follow-up task.

- [ ] **Step 1: Write failing test**

Create `apps/cell/tests/test_channel_sensor_emits_sidecar.py`:

```python
"""Sprint 1.B 2026-05-02: ChannelSensor emits one sidecar per channel after HTTP poll.

Spec ref: §3.3.5 (post-2026-05-02 refresh).
"""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_channel_sensor_emits_sidecar_per_channel():
    """4 channels polled → 4 sidecars emitted with mapped status."""
    from cell.sensors.channel_sensor import ChannelSensor

    sensor = ChannelSensor(db_only=False)

    # Mock HTTP responses: 3 ok, 1 degraded
    fake_responses = {
        "whatsapp": {"status": "ok", "queue_depth": 5, "last_event_seen_at": 12345.0},
        "telegram": {"status": "ok", "queue_depth": 0, "last_event_seen_at": None},
        "instagram": {"status": "ok", "queue_depth": 1, "last_event_seen_at": 67890.0},
        "web": {"status": "degraded", "queue_depth": 50, "last_event_seen_at": 11111.0},
    }

    async def fake_http_get(url):
        for name, body in fake_responses.items():
            if f"/{name}/health" in url:
                return body
        raise AssertionError(f"unexpected url {url}")

    sidecars: list[tuple[str, str, dict]] = []

    with (
        patch.object(sensor, "_http_get_channel_health", side_effect=fake_http_get),
        patch(
            "cell.sensors.channel_sensor.emit_organ_last_seen",
            side_effect=lambda organ_id, status, metadata=None, **kw: sidecars.append((organ_id, status, dict(metadata or {}))) or True,
        ),
    ):
        await sensor.bridge_channels_to_sidecar()

    # 4 sidecars, one per channel
    assert len(sidecars) == 4
    organ_ids = {s[0] for s in sidecars}
    assert organ_ids == {"channel.whatsapp", "channel.telegram", "channel.instagram", "channel.web"}

    # web should be degraded
    web_sidecar = next(s for s in sidecars if s[0] == "channel.web")
    assert web_sidecar[1] == "degraded"
    assert web_sidecar[2]["queue_depth"] == 50


@pytest.mark.asyncio
async def test_channel_sensor_emits_fail_sidecar_on_http_error():
    """HTTP error on a channel → fail sidecar for that channel only."""
    from cell.sensors.channel_sensor import ChannelSensor

    sensor = ChannelSensor(db_only=False)

    async def fake_http_get(url):
        if "/whatsapp/" in url:
            raise ConnectionError("simulated network failure")
        return {"status": "ok", "queue_depth": 0, "last_event_seen_at": None}

    sidecars: list[tuple[str, str, dict]] = []

    with (
        patch.object(sensor, "_http_get_channel_health", side_effect=fake_http_get),
        patch(
            "cell.sensors.channel_sensor.emit_organ_last_seen",
            side_effect=lambda organ_id, status, metadata=None, **kw: sidecars.append((organ_id, status, dict(metadata or {}))) or True,
        ),
    ):
        await sensor.bridge_channels_to_sidecar()

    # 4 sidecars total; whatsapp = fail, others = ok
    statuses = {s[0]: s[1] for s in sidecars}
    assert statuses["channel.whatsapp"] == "fail"
    assert statuses["channel.telegram"] == "ok"
    assert statuses["channel.instagram"] == "ok"
    assert statuses["channel.web"] == "ok"
```

- [ ] **Step 2: Run test, verify fail**

```bash
cd apps/cell
PYTHONPATH=. python -m pytest tests/test_channel_sensor_emits_sidecar.py -v 2>&1 | tail -10
```

Expected: 2 FAILED — `ChannelSensor.__init__` got unexpected keyword `db_only`, OR no `bridge_channels_to_sidecar` method.

- [ ] **Step 3: Add `db_only` flag, `_http_get_channel_health` and `bridge_channels_to_sidecar`**

Read `apps/cell/cell/sensors/channel_sensor.py` and find `class ChannelSensor`. Modify `__init__` to add `db_only: bool = True` parameter. Add:

```python
import os
import httpx
from cell.utils.organ_emitter import emit_organ_last_seen


_KNOWN_CHANNELS: tuple[str, ...] = ("whatsapp", "telegram", "instagram", "web")
_BACKEND_BASE_URL = os.environ.get(
    "NUZANTARA_BACKEND_BASE_URL",
    "https://nuzantara-rag.fly.dev",
)


class ChannelSensor:
    # ... existing code ...

    def __init__(
        self,
        *,
        yellow_threshold: int = _YELLOW_THRESHOLD,
        red_threshold: int = _RED_THRESHOLD,
        window_minutes: int = _RECENT_WINDOW_MINUTES,
        db_only: bool = True,
        http_timeout_s: float = 5.0,
    ) -> None:
        self._yellow = int(yellow_threshold)
        self._red = int(red_threshold)
        self._window = int(window_minutes)
        self._db_only = bool(db_only)
        self._http_timeout = float(http_timeout_s)

    async def _http_get_channel_health(self, url: str) -> dict[str, Any]:
        """HTTP GET wrapper, returns parsed JSON. Raises on network error."""
        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()

    async def bridge_channels_to_sidecar(self) -> dict[str, str]:
        """Poll /api/channels/{name}/health for each known channel + emit sidecar.

        Returns dict {channel_name: emitted_status}. Always 4 entries (one per channel).
        Best-effort: a single channel HTTP failure produces fail status for that
        channel only, others continue. emit_organ_last_seen failures are logged but never raised.
        """
        results: dict[str, str] = {}
        for name in _KNOWN_CHANNELS:
            url = f"{_BACKEND_BASE_URL}/api/channels/{name}/health"
            organ_id = f"channel.{name}"
            try:
                body = await self._http_get_channel_health(url)
                status = body.get("status", "fail")
                metadata = {
                    "queue_depth": body.get("queue_depth", -1),
                    "last_event_seen_at": body.get("last_event_seen_at"),
                }
            except Exception as exc:
                status = "fail"
                metadata = {"error": str(exc)[:200]}
            results[name] = status
            try:
                emit_organ_last_seen(organ_id, status, metadata=metadata)
            except Exception as exc:  # pragma: no cover
                logger.debug(f"sidecar emit failed for {organ_id}: {exc}")
        return results
```

- [ ] **Step 4: Re-run tests, verify pass**

```bash
cd apps/cell
PYTHONPATH=. python -m pytest tests/test_channel_sensor_emits_sidecar.py -v 2>&1 | tail -10
```

Expected: 2 PASSED.

- [ ] **Step 5: Run full Cell test suite (no regression)**

```bash
cd apps/cell
PYTHONPATH=. python -m pytest tests/ -q 2>&1 | tail -10
```

Expected: all existing tests still PASS (the new `db_only` flag defaults to `True` so legacy callers behave unchanged).

- [ ] **Step 6: Commit**

```bash
git add apps/cell/cell/sensors/channel_sensor.py \
        apps/cell/tests/test_channel_sensor_emits_sidecar.py
git commit -m "feat(cell): channel_sensor bridges /api/channels/.../health to per-channel sidecars (Sprint 1.B)

Extends ChannelSensor with db_only=False mode and bridge_channels_to_sidecar()
that polls /api/channels/{name}/health for each of 4 known channels (whatsapp/
telegram/instagram/web) and writes ~/.organism/last_seen/channel.{name}.json
via emit_organ_last_seen.

Backward compatible: db_only defaults to True, existing callers unchanged.

Best-effort: per-channel HTTP failures produce fail status for that channel
only, others continue. emit failures logged via debug.

Closes gap 2 (channel.* visibility) for genome_aggregator_sensor.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Wire Cell PulseEngine to call bridges every cycle

**Files:**

- Modify: `apps/cell/cell/main.py`

The PulseEngine already calls `health_sensor.read()` each tick (Task 3 hooks into that). For `channel_sensor`, the bridge is async + currently isolated; needs explicit invocation.

- [ ] **Step 1: Identify PulseEngine pulse loop**

Read `apps/cell/cell/main.py` and find the main pulse loop where sensors are evaluated. Look for the section that calls `ChannelSensor().read(conn)` or instantiates ChannelSensor.

- [ ] **Step 2: Switch ChannelSensor instantiation to db_only=False mode**

Change:

```python
ChannelSensor()  # OR ChannelSensor(yellow_threshold=...)
```

to:

```python
ChannelSensor(db_only=False)
```

And after the existing `read()` call, add:

```python
            # Sprint 1.B: bridge HTTP poll → Genoma sidecar (one per channel)
            try:
                await channel_sensor.bridge_channels_to_sidecar()
            except Exception as exc:  # pragma: no cover — best-effort
                logger.debug(f"channel sidecar bridge failed: {exc}")
```

(`channel_sensor` is the existing variable holding the ChannelSensor instance — adapt name to match actual code.)

- [ ] **Step 3: Run import chain validation (cicatrix)**

```bash
cd apps/cell
PYTHONPATH=. python -c "from cell.main import main; print('import OK')"
```

Expected: `import OK` (no syntax/import errors).

- [ ] **Step 4: Run full Cell test suite**

```bash
cd apps/cell
PYTHONPATH=. python -m pytest tests/ -q 2>&1 | tail -10
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/cell/cell/main.py
git commit -m "feat(cell): PulseEngine wires channel_sensor bridge per cycle (Sprint 1.B)

Switches ChannelSensor to db_only=False and invokes bridge_channels_to_sidecar()
each pulse cycle. Sidecar files for channel.{whatsapp,telegram,instagram,web}
land in ~/.organism/last_seen/ and feed genome_aggregator_sensor.

Bridge wrapped in try/except: PulseEngine never crashes on bridge failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Open PR + auto-merge

**Files:** N/A

- [ ] **Step 1: Push**

```bash
git push -u origin feat/post-agentic-heartbeat-cell-bridge-2026-05-02
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --base main --title "feat: Sprint 1.B — Cell-side heartbeat bridge for backend.api + 4 channels" --body "$(cat <<'EOF'
## Summary

Sprint 1.B of Era Post-Agentica injection. Closes gap 2 (backend.api + 4 channel webhooks not visible to genome_aggregator_sensor).

## Approach (post-2026-05-02 design refresh §3.3.5)

Original plan was a FastAPI middleware in backend.api calling emit_organ_last_seen — broken-by-design because Fly.io filesystem is ephemeral.

Cell-side bridge instead:
- Backend exposes new GET /api/channels/{name}/health (~30 LOC, queue_depth-based status)
- Cell health_sensor (already polls /health) bridges reading → ~/.organism/last_seen/backend.api.json
- Cell channel_sensor (already polls inbound_webhooks) extended to also poll new endpoint + emit ~/.organism/last_seen/channel.{name}.json (4 files)
- All filesystem state lives on Pro (Pilastro 6 sovranità locale)

## Tests

- 2 endpoint tests (channel_health.py — 4 channels schema + 404)
- 3 health_sensor bridge tests (ok / degraded / fail mapping)
- 2 channel_sensor bridge tests (4 channels emission + per-channel HTTP failure isolation)
- All existing Cell + backend tests still pass (no regression)

## Out of scope

- Genoma auto-discovery (Sprint 1.C, deferred for Observatory PR-5)
- New events_outbox channels for heartbeat (state file approach instead, simpler + Pilastro 4)

## Coordination

- Sprint 1.A skill registry parallel allowed — disjoint files (seed_initial_skills.py)
- Observatory PR-5 Task 5.3 — disjoint files (cell_core.observatory + pulse.py + plist env var)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Auto-merge**

```bash
PR=$(gh pr list --head feat/post-agentic-heartbeat-cell-bridge-2026-05-02 --json number -q '.[0].number')
gh pr merge $PR --squash --auto
```

Required checks (Sprint 0 discovery): E2E + MCP + Frontend + Detect Secrets. Wait until merged.

---

## Task 7: Verify on prod (post-deploy)

**Files:** N/A

- [ ] **Step 1: Wait for fly-deploy.yml run**

```bash
gh run list --workflow="Deploy Backend to Fly.io" --branch=main --limit=1 --json databaseId,status -q '.[0]'
```

Wait until `status: completed, conclusion: success`.

- [ ] **Step 2: Verify endpoint live on prod**

```bash
for name in whatsapp telegram instagram web; do
    curl -fsS "https://nuzantara-rag.fly.dev/api/channels/$name/health" | python3 -m json.tool || echo "FAIL: $name"
done
```

Expected: 4 JSON bodies with `{status, ts, channel, queue_depth, last_event_seen_at, metadata}`.

- [ ] **Step 3: Pull Cell changes on Pro + restart organism**

```bash
ssh pro 'cd ~/Desktop/nuzantara && git pull origin main --ff-only && launchctl kickstart -k gui/$(id -u)/com.cell.organism' 2>&1 | tail -5
```

Expected: pull succeeds, organism restart confirmed.

- [ ] **Step 4: Verify sidecar files on Pro after one Cell pulse cycle (~60s)**

```bash
sleep 90
ssh pro 'ls -la ~/.organism/last_seen/backend.api.json ~/.organism/last_seen/channel.{whatsapp,telegram,instagram,web}.json 2>&1' | tail -8
```

Expected: 5 JSON files, each ≤ 300 bytes, mtime within last 90s.

- [ ] **Step 5: Verify status content**

```bash
ssh pro 'for f in ~/.organism/last_seen/backend.api.json ~/.organism/last_seen/channel.*.json; do echo "=== $f ==="; cat $f; echo; done' 2>&1 | tail -30
```

Expected: each contains `{"ts": ..., "status": "ok|degraded|fail", "organ_id": "...", "metadata": {...}}`.

---

## Task 8: MOS save + Telegram notification

- [ ] **Step 1: MOS save**

```bash
~/.claude/scripts/mem save decision "Sprint 1.B complete 2026-05-02: Cell-side heartbeat bridge for backend.api + 4 channels. health_sensor.py + channel_sensor.py now write sidecar files to ~/.organism/last_seen/ on Pro. backend exposes new /api/channels/{name}/health endpoint. Closes gap 2 of Era Post-Agentica brief. genome_aggregator_sensor can now classify these 5 organs correctly. Sprint 1.A skill registry parallel; Sprint 1.C deferred for Observatory." 8
```

- [ ] **Step 2: Telegram notification**

```bash
TOKEN=$(grep "TELEGRAM_BOT_TOKEN" ~/.nuzantara-secrets.env 2>/dev/null | cut -d= -f2 | tr -d "\"'")
[ -z "$TOKEN" ] || curl -s "https://api.telegram.org/bot$TOKEN/sendMessage" \
  -d "chat_id=1125336968" \
  --data-urlencode "text=✅ Sprint 1.B complete — heartbeat Cell-side bridge live. backend.api + 4 channels now visible to genome_aggregator_sensor via ~/.organism/last_seen/ sidecars on Pro. Gap 2 closed."
```

- [ ] **Step 3: Branch cleanup**

```bash
git checkout main
git pull origin main --ff-only
git branch -d feat/post-agentic-heartbeat-cell-bridge-2026-05-02
```

---

## Verification: Sprint 1.B success criteria

After Task 8, all must be true:

- [ ] PR merged to main + fly-deploy success
- [ ] `/api/channels/{whatsapp,telegram,instagram,web}/health` all return 200 with valid schema
- [ ] 5 sidecar files in `~/.organism/last_seen/` on Pro, mtime fresh within Cell pulse cadence
- [ ] `genome_aggregator_sensor` classifies backend.api + 4 channels as `green` (assuming all healthy)
- [ ] No regression: existing Cell tests + existing backend tests still pass

If any criterion fails, do NOT consider Sprint 1.B done.

---

## Cicatrix safety checklist

- [x] No SQL migrations (Sprint 1.B is HTTP + filesystem only)
- [x] No fly ssh write on Fly DB (read-only via endpoint)
- [x] No plist edits (deferred to Sprint 1.C)
- [x] No conflict with Observatory PR-5 (different files: cell_core.observatory + pulse.py vs sensors/{health,channel}.py)
- [x] Import chain validation runs after backend changes (cicatrix 2026-04-21 anti-rogue-AI)
- [x] WIP commit checkpoint at end of each Task (cicatrix 2026-04-29)
- [x] Best-effort error handling: emit failures swallowed via debug log, never raise (matches organ_emitter contract)

---

**End of Sprint 1.B plan.** Sprint 1.C (Genoma auto-discovery + organism plist edits) deferred until Observatory PR-5 Task 5.3 done + 48h obs window passed + PR-6/PR-7 merged.
