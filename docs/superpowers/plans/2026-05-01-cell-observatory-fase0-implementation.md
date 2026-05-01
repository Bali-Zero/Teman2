# Cell Observatory Fase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Pro-local observatory that listens to cell pulse events from `events_outbox`, classifies them async with MiniMax M2, and exposes a dashboard tab in `admin-dashboard-local`. Phase 0 is read-only observability — no proposals, no HGT, no SafetyGate writes.

**Architecture:** New Python service `apps/cell-observatory-collector/` runs as a Pro LaunchAgent (KeepAlive=true, log to `~/logs/cell-observatory/`). It LISTENs on PG channel `cell_pulse_observed`, idempotent-inserts to local SQLite WAL DB, dispatches MiniMax classification off-path (raw rows survive classifier outage). Cells emit pulses via a new `cell_core.observatory` module that writes directly to `events_outbox` with asyncpg (NO lazy import of `backend.services.events` — that was BLOCKER B1 from cross-LLM review). Dashboard reads via loopback HTTP `127.0.0.1:17891`.

**Tech Stack:** Python 3.11+ (asyncio, asyncpg, FastAPI, Pydantic v2, structlog, aiosqlite), SQLite WAL+FTS5, MiniMax M2 (OpenAI-compat API), Next.js 16/React 19/TypeScript/Tailwind/SWR, LaunchAgent (launchd).

**Spec reference:** `docs/superpowers/specs/2026-05-01-cell-observatory-fase0-design.md`. Read §10 (Issues) before starting — this plan resolves all 4 BLOCKERS as prerequisite tasks.

---

## Plan structure

- **PR-0** — Resolve cross-LLM-review blockers (5 tasks). Must merge before any other PR.
- **PR-1** — `cell_core.observatory` module + `pulse.py` hook + `PulseResult.pulse_id` field.
- **PR-2** — Register PG channel `cell_pulse_observed` in event_bus.
- **PR-3** — `cell-observatory-collector` Python service + LaunchAgents.
- **PR-4** — Dashboard tab `/observatory` in admin-dashboard-local.
- **PR-5** — Activate organism cell pilot (gated 48h observation).
- **PR-6** — Activate seo_cell + evaluator (gated 48h).
- **PR-7** — Prune cron + retention validation.

---

## PR-0: Resolve blockers

**Branch:** `feat/cell-observatory-blockers-pr0`

**Files:**
- Modify: `scripts/patch_launchagents.sh` (B3 chmod handling)
- Modify: `packages/cell-core/cell_core/types.py` (A3 pulse_id field)
- Verify (read-only): `apps/backend-rag/backend/services/events/outbox.py` (B4 regex match)

### Task 0.1: Verify B4 — `outbox.validate_channel` accepts `cell_pulse_observed`

**Files:**
- Read: `apps/backend-rag/backend/services/events/outbox.py:57`

- [ ] **Step 1: Run regex check via Python REPL**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "import re; ok = re.match(r'^[A-Za-z_][A-Za-z0-9_]{0,62}\$', 'cell_pulse_observed'); print('OK' if ok else 'FAIL')"
```

Expected: `OK`

- [ ] **Step 2: Confirm by reading `validate_channel` body**

Run: `grep -A20 "def validate_channel" apps/backend-rag/backend/services/events/outbox.py`

Expected: regex matches our channel name; no allowlist beyond regex.

- [ ] **Step 3: Document verification in commit message (no code change)**

This task produces no commit (read-only). Record outcome in PR-0 description.

### Task 0.2: B3 fix — `patch_launchagents.sh` handles chmod 0444 plists

**Files:**
- Modify: `scripts/patch_launchagents.sh:1-200` (add `--add-observatory-emit` flag + chmod handling)

- [ ] **Step 1: Add CLI flag parsing for `--add-observatory-emit`**

In the existing argument loop near line 22:

```bash
case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --apply)   DRY_RUN=false; shift ;;
    --add-observatory-emit) ADD_OBS_EMIT=true; shift ;;   # NEW
    --no-reload) RELOAD=false; shift ;;
    --only)    ONLY_FILTER="$2"; shift 2 ;;
    --yes|-y)  ASSUME_YES=true; shift ;;
    ...
```

Initialize `ADD_OBS_EMIT=false` near the other flag defaults (line 13-17 area).

- [ ] **Step 2: Add chmod-aware patch helper function**

Add after `mkdir -p "$LOGS_DIR"` (around line 41):

```bash
add_observatory_emit_to_plist() {
    local plist="$1"
    local backup="${plist}.pre-observatory-emit"

    [ -f "$backup" ] || cp "$plist" "$backup"

    local original_mode
    original_mode=$(stat -f "%Lp" "$plist")
    chmod u+w "$plist"

    if /usr/bin/plutil -extract EnvironmentVariables xml1 -o - "$plist" 2>/dev/null | grep -q CELL_OBSERVATORY_EMIT; then
        /usr/bin/plutil -replace EnvironmentVariables.CELL_OBSERVATORY_EMIT -string "true" "$plist"
    else
        /usr/bin/plutil -extract EnvironmentVariables xml1 -o - "$plist" 2>/dev/null >/dev/null \
            || /usr/bin/plutil -insert EnvironmentVariables -dictionary "$plist"
        /usr/bin/plutil -insert EnvironmentVariables.CELL_OBSERVATORY_EMIT -string "true" "$plist"
    fi

    /usr/bin/plutil -lint "$plist" >/dev/null

    chmod "0$original_mode" "$plist"
    echo "[ok] $(basename "$plist")"
}
```

- [ ] **Step 3: Wire into main flow**

After existing patch logic, before the launchctl reload section, add:

```bash
if [ "$ADD_OBS_EMIT" = "true" ]; then
    for plist in "$PLIST_DIR"/com.cell.organism.plist \
                 "$PLIST_DIR"/com.balizero.seo-cell*.plist \
                 "$PLIST_DIR"/com.balizero.evaluator*.plist; do
        [ -f "$plist" ] || continue
        if [ "$DRY_RUN" = "true" ]; then
            echo "[dry-run] would add CELL_OBSERVATORY_EMIT=true to $(basename "$plist")"
        else
            add_observatory_emit_to_plist "$plist"
        fi
    done
fi
```

- [ ] **Step 4: Test on a sandbox plist (do NOT modify prod)**

```bash
mkdir -p /tmp/launchagents-test
cat > /tmp/launchagents-test/com.test.fake.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict><key>Label</key><string>com.test.fake</string></dict>
</plist>
EOF
chmod 0444 /tmp/launchagents-test/com.test.fake.plist
PLIST_DIR_OVERRIDE=/tmp/launchagents-test ./scripts/patch_launchagents.sh --apply --add-observatory-emit --no-reload
```

(For Step 4 to be self-contained, add `PLIST_DIR="${PLIST_DIR_OVERRIDE:-$HOME/Library/LaunchAgents}"` in the script.)

Expected: `[ok] com.test.fake.plist`. Verify mode preserved:

```bash
stat -f "%Lp" /tmp/launchagents-test/com.test.fake.plist
```

Expected: `444`. Verify env var present:

```bash
plutil -extract EnvironmentVariables.CELL_OBSERVATORY_EMIT raw /tmp/launchagents-test/com.test.fake.plist
```

Expected: `true`.

- [ ] **Step 5: Commit**

```bash
git add scripts/patch_launchagents.sh
git commit -m "$(cat <<'EOF'
feat(launchagents): add --add-observatory-emit flag with chmod 0444 handling

Resolves BLOCKER B3 from cell-observatory cross-LLM review:
plist hardening (scar P0-3) made plist files chmod 0444, blocking
existing patch flow. New helper unlocks via chmod u+w, applies
plutil edit, restores original mode. Backs up to .pre-observatory-emit
before any change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 0.3: A3 fix — Add `pulse_id` field to `PulseResult`

**Files:**
- Modify: `packages/cell-core/cell_core/types.py:110` (`PulseResult` dataclass)
- Test: `packages/cell-core/tests/test_types.py` (create or extend)

- [ ] **Step 1: Write failing test for `pulse_id` default**

In `packages/cell-core/tests/test_types.py` (create if missing):

```python
import pytest
from cell_core.types import PulseResult


def test_pulse_result_has_pulse_id_default():
    """PulseResult must have a pulse_id field auto-populated with a ULID-like string."""
    from datetime import datetime, timezone
    result = PulseResult(
        timestamp=datetime.now(timezone.utc),
        sensor_readings=[],
        classifier_label="green",
        trend_label="stable",
        scar_signals=[],
    )
    assert hasattr(result, "pulse_id")
    assert isinstance(result.pulse_id, str)
    assert len(result.pulse_id) >= 16


def test_pulse_result_pulse_id_unique_per_instance():
    """Two PulseResult created back-to-back must have different pulse_ids."""
    from datetime import datetime, timezone
    a = PulseResult(timestamp=datetime.now(timezone.utc), sensor_readings=[],
                    classifier_label="green", trend_label="stable", scar_signals=[])
    b = PulseResult(timestamp=datetime.now(timezone.utc), sensor_readings=[],
                    classifier_label="green", trend_label="stable", scar_signals=[])
    assert a.pulse_id != b.pulse_id
```

- [ ] **Step 2: Run tests; expected FAIL**

```bash
cd packages/cell-core && pip install -e . && python -m pytest tests/test_types.py -v
```

Expected: 2 FAIL with `AttributeError` or `TypeError` (no `pulse_id` field).

- [ ] **Step 3: Add `pulse_id` to `PulseResult`**

In `packages/cell-core/cell_core/types.py`, near the existing `PulseResult` dataclass (line 110):

```python
import secrets
from dataclasses import dataclass, field


def _default_pulse_id() -> str:
    """Generate a 26-char Crockford-base32 ULID-style pulse id (sortable).

    Format: 10-char timestamp ms + 16-char random. Good enough for log correlation
    without adding a `ulid-py` dependency.
    """
    import time
    ts_ms = int(time.time() * 1000)
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    enc = ""
    n = ts_ms
    for _ in range(10):
        enc = alphabet[n & 0x1F] + enc
        n >>= 5
    rnd = "".join(secrets.choice(alphabet) for _ in range(16))
    return enc + rnd


@dataclass
class PulseResult:
    timestamp: datetime
    sensor_readings: list[SensorReading]
    classifier_label: str
    trend_label: str
    scar_signals: list[dict]
    pulse_id: str = field(default_factory=_default_pulse_id)  # NEW
```

(Adapt to actual existing `PulseResult` field order; just add `pulse_id` last with default factory so existing constructors don't break.)

- [ ] **Step 4: Re-run tests; expected PASS**

```bash
python -m pytest tests/test_types.py::test_pulse_result_has_pulse_id_default tests/test_types.py::test_pulse_result_pulse_id_unique_per_instance -v
```

Expected: 2 PASS.

- [ ] **Step 5: Run full cell-core test suite to verify no regression**

```bash
python -m pytest tests/ -v
```

Expected: all PASS. If any test breaks because of constructor signature, those tests need to use kwargs (the field default avoids positional drift, but verify).

- [ ] **Step 6: Commit**

```bash
git add packages/cell-core/cell_core/types.py packages/cell-core/tests/test_types.py
git commit -m "$(cat <<'EOF'
feat(cell-core): add PulseResult.pulse_id with ULID-style default factory

Resolves AMBIGUITY A3 from cell-observatory cross-LLM review.
PulseResult now carries a sortable, unique pulse_id used by the
observatory pipeline to correlate raw events to classifications and
to inject _outbox_id idempotent ack downstream.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 0.4: Open PR-0 + verify CI green

- [ ] **Step 1: Push branch, open PR**

```bash
git push -u origin feat/cell-observatory-blockers-pr0
gh pr create --title "feat(observatory): PR-0 resolve cross-LLM blockers (B3+A3+B4 verify)" \
  --body "$(cat <<'EOF'
## Summary
- B4 verified: \`outbox.validate_channel\` accepts \`cell_pulse_observed\` via existing regex (no allowlist code change needed)
- B3 fixed: \`patch_launchagents.sh\` adds \`--add-observatory-emit\` with chmod 0444 round-trip
- A3 fixed: \`PulseResult.pulse_id\` field with ULID-style default factory + 2 tests

Spec ref: \`docs/superpowers/specs/2026-05-01-cell-observatory-fase0-design.md\` §10.

## Test plan
- [ ] Unit tests: \`pytest packages/cell-core/tests/test_types.py -v\` — 2 PASS
- [ ] Sandbox plist test: \`patch_launchagents.sh --apply --add-observatory-emit\` against \`/tmp/launchagents-test/\` — chmod preserved, env var present

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Wait for CI**

```bash
gh pr checks --watch
```

Expected: All required checks (E2E Tests Playwright, MCP Server Tests) pass.

- [ ] **Step 3: Merge after green**

```bash
gh pr merge --squash --auto
```

---

## PR-1: cell-core observatory module

**Branch:** `feat/cell-observatory-pr1-cell-core`
**Depends on:** PR-0 merged.

**Files:**
- Create: `packages/cell-core/cell_core/observatory.py`
- Modify: `packages/cell-core/cell_core/__init__.py` (export observatory)
- Modify: `packages/cell-core/cell_core/pulse.py` (add fire-and-forget hook)
- Create: `packages/cell-core/tests/test_observatory.py`

### Task 1.1: B1 fix — Direct asyncpg emitter (NO lazy EventBus import)

- [ ] **Step 1: Write failing test for `is_enabled()`**

In `packages/cell-core/tests/test_observatory.py`:

```python
import os
import pytest
from cell_core import observatory


def test_is_enabled_default_false(monkeypatch):
    monkeypatch.delenv("CELL_OBSERVATORY_EMIT", raising=False)
    assert observatory.is_enabled() is False


def test_is_enabled_when_true(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")
    assert observatory.is_enabled() is True


def test_is_enabled_case_insensitive(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "TRUE")
    assert observatory.is_enabled() is True


def test_is_enabled_other_values_are_false(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "yes")
    assert observatory.is_enabled() is False
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "1")
    assert observatory.is_enabled() is False
```

- [ ] **Step 2: Run; expected FAIL (module not yet exists)**

```bash
cd packages/cell-core && python -m pytest tests/test_observatory.py::test_is_enabled_default_false -v
```

Expected: `ModuleNotFoundError: No module named 'cell_core.observatory'`

- [ ] **Step 3: Create observatory.py with `is_enabled()` only**

Create `packages/cell-core/cell_core/observatory.py`:

```python
"""Cell pulse observatory emitter.

Writes pulse events directly to the EventBus events_outbox via asyncpg,
then triggers pg_notify on the 'cell_pulse_observed' channel. Designed
to run inside any cell process (standalone LaunchAgent or in-app), with
NO dependency on backend-rag's Python package — that was BLOCKER B1
from the 2026-05-01 cross-LLM review.

Failures are swallowed (WARN log) — pulse loop must NEVER block on
observability.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_pool_lock_pid: Optional[int] = None  # detect fork without inherit


def is_enabled() -> bool:
    """Return True iff CELL_OBSERVATORY_EMIT env var is the literal 'true' (case-insensitive)."""
    return os.environ.get("CELL_OBSERVATORY_EMIT", "").lower() == "true"
```

- [ ] **Step 4: Run; expected 4 PASS**

```bash
python -m pytest tests/test_observatory.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/observatory.py packages/cell-core/tests/test_observatory.py
git commit -m "feat(cell-core): observatory.is_enabled() env-controlled flag

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.2: Add `_get_or_create_pool()` for direct asyncpg

- [ ] **Step 1: Write failing test**

Append to `packages/cell-core/tests/test_observatory.py`:

```python
@pytest.mark.asyncio
async def test_get_or_create_pool_returns_pool(monkeypatch):
    """Lazy-init pool from EVENTBUS_DATABASE_URL env var."""
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://invalid-host/test")

    # Pool creation is lazy; we just verify the function returns a callable that
    # produces an asyncpg.Pool object (we don't actually connect — the URL is fake).
    from cell_core import observatory
    observatory._reset_pool_for_tests()  # test hook

    # We mock asyncpg.create_pool to avoid real network call
    import asyncpg
    called = {}

    async def fake_create_pool(dsn, **kwargs):
        called["dsn"] = dsn
        called["kwargs"] = kwargs
        # Return a minimal mock pool
        class _MockPool:
            async def close(self): pass
        return _MockPool()

    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    pool = await observatory._get_or_create_pool()
    assert pool is not None
    assert called["dsn"] == "postgresql://invalid-host/test"
    assert called["kwargs"]["min_size"] == 1
    assert called["kwargs"]["max_size"] == 3


@pytest.mark.asyncio
async def test_get_or_create_pool_returns_none_if_url_unset(monkeypatch):
    monkeypatch.delenv("EVENTBUS_DATABASE_URL", raising=False)
    from cell_core import observatory
    observatory._reset_pool_for_tests()
    pool = await observatory._get_or_create_pool()
    assert pool is None
```

- [ ] **Step 2: Run; expected FAIL**

```bash
python -m pytest tests/test_observatory.py::test_get_or_create_pool_returns_pool -v
```

Expected: `AttributeError: module has no attribute '_get_or_create_pool'`.

- [ ] **Step 3: Implement pool helper**

Append to `packages/cell-core/cell_core/observatory.py`:

```python
async def _get_or_create_pool() -> Optional[asyncpg.Pool]:
    """Return the lazy-initialized asyncpg pool, or None if EVENTBUS_DATABASE_URL is unset."""
    global _pool, _pool_lock_pid

    current_pid = os.getpid()
    if _pool_lock_pid is not None and _pool_lock_pid != current_pid:
        # Process forked since pool creation; pool is invalid in child.
        _pool = None
        _pool_lock_pid = None

    if _pool is not None:
        return _pool

    dsn = os.environ.get("EVENTBUS_DATABASE_URL")
    if not dsn:
        return None

    _pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=3,
        command_timeout=5.0,
    )
    _pool_lock_pid = current_pid
    return _pool


def _reset_pool_for_tests() -> None:
    """Internal test hook — DO NOT use in production."""
    global _pool, _pool_lock_pid
    _pool = None
    _pool_lock_pid = None
```

- [ ] **Step 4: Run; expected 2 PASS**

```bash
python -m pytest tests/test_observatory.py::test_get_or_create_pool_returns_pool tests/test_observatory.py::test_get_or_create_pool_returns_none_if_url_unset -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/observatory.py packages/cell-core/tests/test_observatory.py
git commit -m "feat(cell-core): observatory pool helper with fork-safety

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.3: B1 + B4 fix — `emit_pulse_observed()` direct INSERT + pg_notify

- [ ] **Step 1: Write failing test**

Append to `packages/cell-core/tests/test_observatory.py`:

```python
@pytest.mark.asyncio
async def test_emit_pulse_observed_disabled_no_op(monkeypatch):
    monkeypatch.delenv("CELL_OBSERVATORY_EMIT", raising=False)
    from cell_core import observatory
    observatory._reset_pool_for_tests()

    # Should NOT call create_pool when disabled
    import asyncpg
    monkeypatch.setattr(asyncpg, "create_pool",
                        lambda *a, **kw: pytest.fail("must not call create_pool when disabled"))

    await observatory.emit_pulse_observed(
        cell_id="test", cell_kind="test", pulse_id="01ABC",
        pulse_timestamp_ms=0, phase="homeostatic",
        sensors=[], pulse_result={}, homeostatic_state={},
    )


@pytest.mark.asyncio
async def test_emit_pulse_observed_writes_outbox_and_notifies(monkeypatch):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://fake/db")

    from cell_core import observatory
    observatory._reset_pool_for_tests()

    captured = {"insert_sql": None, "notify_sql": None, "insert_args": None, "notify_args": None}

    class FakeConn:
        async def fetchrow(self, sql, *args):
            captured["insert_sql"] = sql
            captured["insert_args"] = args
            return {"outbox_id": 42}

        async def execute(self, sql, *args):
            captured["notify_sql"] = sql
            captured["notify_args"] = args

        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeTx:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeConnContext:
        def __init__(self, conn): self.conn = conn
        async def __aenter__(self): return self.conn
        async def __aexit__(self, *a): pass

    fake_conn = FakeConn()
    fake_conn.transaction = lambda: FakeTx()

    class FakePool:
        def acquire(self): return FakeConnContext(fake_conn)

    async def fake_create_pool(*a, **kw):
        return FakePool()

    import asyncpg
    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    await observatory.emit_pulse_observed(
        cell_id="organism", cell_kind="innervation",
        pulse_id="01TEST", pulse_timestamp_ms=1000,
        phase="homeostatic", sensors=[],
        pulse_result={"classifier_self": "green"}, homeostatic_state={"energy_pct": 80},
    )

    assert "INSERT INTO events_outbox" in captured["insert_sql"]
    assert captured["insert_args"][0] == "cell_pulse_observed"
    payload = json.loads(captured["insert_args"][1])
    assert payload["cell_id"] == "organism"
    assert payload["pulse_id"] == "01TEST"

    assert "pg_notify" in captured["notify_sql"]
    assert captured["notify_args"][0] == "cell_pulse_observed"
    notify_payload = json.loads(captured["notify_args"][1])
    assert notify_payload["_outbox_id"] == 42  # injected after insert


@pytest.mark.asyncio
async def test_emit_pulse_observed_swallows_db_errors(monkeypatch, caplog):
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://fake/db")

    from cell_core import observatory
    observatory._reset_pool_for_tests()

    async def fake_create_pool(*a, **kw):
        raise asyncpg.PostgresError("connection refused")

    import asyncpg
    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    # Must NOT raise
    await observatory.emit_pulse_observed(
        cell_id="test", cell_kind="test", pulse_id="01X",
        pulse_timestamp_ms=0, phase="homeostatic",
        sensors=[], pulse_result={}, homeostatic_state={},
    )
    assert any("emit failed" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run; expected FAIL**

```bash
python -m pytest tests/test_observatory.py -v
```

Expected: 3 FAIL with `AttributeError: module 'cell_core.observatory' has no attribute 'emit_pulse_observed'`.

- [ ] **Step 3: Implement `emit_pulse_observed()`**

Append to `packages/cell-core/cell_core/observatory.py`:

```python
_INSERT_SQL = (
    "INSERT INTO events_outbox (channel, payload) "
    "VALUES ($1, $2) RETURNING outbox_id"
)
_NOTIFY_SQL = "SELECT pg_notify($1, $2)"


async def emit_pulse_observed(
    cell_id: str,
    cell_kind: str,
    pulse_id: str,
    pulse_timestamp_ms: int,
    phase: str,
    sensors: list[dict[str, Any]],
    pulse_result: dict[str, Any],
    homeostatic_state: dict[str, Any],
    scar_signals: Optional[list[dict[str, Any]]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Emit a pulse-observed event to events_outbox + pg_notify.

    No-op when CELL_OBSERVATORY_EMIT != 'true' or EVENTBUS_DATABASE_URL is unset.
    Errors are swallowed (WARN log) — caller MUST NOT block on this.
    """
    if not is_enabled():
        return

    try:
        pool = await _get_or_create_pool()
        if pool is None:
            return

        payload: dict[str, Any] = {
            "event_version": "v1",
            "cell_id": cell_id,
            "cell_kind": cell_kind,
            "pulse_id": pulse_id,
            "pulse_timestamp": pulse_timestamp_ms,
            "phase": phase,
            "sensors": sensors,
            "pulse_result": pulse_result,
            "homeostatic_state": homeostatic_state,
            "scar_signals": scar_signals or [],
            "metadata": metadata or {},
        }

        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(_INSERT_SQL, "cell_pulse_observed", json.dumps(payload))
                outbox_id = row["outbox_id"]
                payload["_outbox_id"] = outbox_id
                await conn.execute(_NOTIFY_SQL, "cell_pulse_observed", json.dumps(payload))
    except Exception as exc:
        logger.warning(
            "cell_observatory emit failed (non-blocking): cell=%s pulse=%s err=%s",
            cell_id, pulse_id, exc,
        )
```

- [ ] **Step 4: Run; expected 3 PASS**

```bash
python -m pytest tests/test_observatory.py -v
```

Expected: 7 PASS total (4 prior + 3 new).

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/observatory.py packages/cell-core/tests/test_observatory.py
git commit -m "$(cat <<'EOF'
feat(cell-core): observatory.emit_pulse_observed direct asyncpg

Resolves BLOCKER B1 + B4 from cross-LLM review:
- Direct asyncpg INSERT to events_outbox (NO lazy backend.services.events
  import — that path silently no-op'd for all standalone cells)
- Manual _outbox_id injection after RETURNING clause
- Channel name 'cell_pulse_observed' matches outbox.validate_channel regex
- pool fork-safe via PID check
- Failures swallowed with WARN log (pulse loop never blocks)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 1.4: B2 fix — Add fire-and-forget hook to `pulse.py`

**Files:**
- Modify: `packages/cell-core/cell_core/pulse.py` (locate `PulseLoop.run_cycle()` method, add hook at end before return)

- [ ] **Step 1: Write failing integration test**

Create `packages/cell-core/tests/test_pulse_observatory_hook.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_pulse_cycle_emits_to_observatory_when_enabled(monkeypatch):
    """When CELL_OBSERVATORY_EMIT=true, run_cycle schedules a fire-and-forget emit."""
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")

    from cell_core import observatory
    fake_emit = AsyncMock()
    monkeypatch.setattr(observatory, "emit_pulse_observed", fake_emit)
    monkeypatch.setattr(observatory, "is_enabled", lambda: True)

    # Construct a minimal PulseLoop and run one cycle.
    # (Adapt to actual constructor signature; pseudo-code below — real test
    #  must follow apps/cell or apps/organism's existing PulseLoop init pattern.)
    from cell_core.pulse import PulseLoop
    loop = PulseLoop(...)  # actual fixture from existing pulse tests
    result = await loop.run_cycle()

    # Allow the create_task to run
    await asyncio.sleep(0)

    fake_emit.assert_called_once()
    assert fake_emit.call_args.kwargs["cell_id"] == loop.cell_id


@pytest.mark.asyncio
async def test_pulse_cycle_does_not_block_on_emit(monkeypatch):
    """Slow observatory emit MUST NOT delay pulse cycle return."""
    monkeypatch.setenv("CELL_OBSERVATORY_EMIT", "true")

    from cell_core import observatory

    async def slow_emit(**kw):
        await asyncio.sleep(5.0)

    monkeypatch.setattr(observatory, "emit_pulse_observed", slow_emit)
    monkeypatch.setattr(observatory, "is_enabled", lambda: True)

    from cell_core.pulse import PulseLoop
    loop = PulseLoop(...)

    import time
    start = time.monotonic()
    await loop.run_cycle()
    elapsed = time.monotonic() - start

    # Pulse cycle must return in <1s even though observatory takes 5s
    assert elapsed < 1.0, f"pulse blocked on observatory: {elapsed}s"
```

- [ ] **Step 2: Run; expected FAIL (hook not yet present)**

```bash
python -m pytest tests/test_pulse_observatory_hook.py -v
```

Expected: 2 FAIL (`fake_emit.assert_called_once()` fails — never called).

- [ ] **Step 3: Locate `PulseLoop.run_cycle()` body and add hook**

Find the `run_cycle` method in `pulse.py`. At the end of the method, immediately before `return pulse_result`:

```python
async def run_cycle(self) -> PulseResult:
    # ... existing logic ...
    pulse_result = ...

    # NEW (B2 fix): fire-and-forget observatory emit
    try:
        from cell_core import observatory
        if observatory.is_enabled():
            import socket
            asyncio.create_task(observatory.emit_pulse_observed(
                cell_id=self.cell_id,
                cell_kind=getattr(self, "cell_kind", "unknown"),
                pulse_id=pulse_result.pulse_id,
                pulse_timestamp_ms=int(pulse_result.timestamp.timestamp() * 1000),
                phase=str(self.maturation.current_phase) if hasattr(self, "maturation") else "unknown",
                sensors=[r.to_dict() if hasattr(r, "to_dict") else r.__dict__
                         for r in pulse_result.sensor_readings],
                pulse_result={
                    "classifier_self": pulse_result.classifier_label,
                    "trend_window_min": getattr(self.config, "trend_window_min", None)
                                          if hasattr(self, "config") else None,
                    "trend_label": pulse_result.trend_label,
                },
                homeostatic_state={
                    "energy_pct": getattr(self.homeostatic_controller, "energy_pct", None)
                                    if hasattr(self, "homeostatic_controller") else None,
                    "load_factor": getattr(self.homeostatic_controller, "load_factor", None)
                                    if hasattr(self, "homeostatic_controller") else None,
                },
                scar_signals=getattr(pulse_result, "scar_signals", []),
                metadata={
                    "host": socket.gethostname(),
                    "machine_role": os.environ.get("MACHINE_ROLE", "unknown"),
                },
            ))
    except Exception as exc:
        logger.warning("observatory hook scheduling error (non-blocking): %s", exc)

    return pulse_result
```

Add `import os` and `import asyncio` and `import logging; logger = logging.getLogger(__name__)` at top of file if not present.

- [ ] **Step 4: Run; expected 2 PASS**

```bash
python -m pytest tests/test_pulse_observatory_hook.py -v
```

Expected: 2 PASS. (Slow emit test verifies fire-and-forget — 5s emit completes in <1s pulse cycle.)

- [ ] **Step 5: Run full cell-core suite to verify no regression**

```bash
python -m pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/cell-core/cell_core/pulse.py packages/cell-core/tests/test_pulse_observatory_hook.py
git commit -m "$(cat <<'EOF'
feat(cell-core): pulse.run_cycle fire-and-forget observatory hook

Resolves BLOCKER B2 from cross-LLM review:
asyncio.create_task() so a slow events_outbox INSERT can never block
the cell's homeostatic loop. Hook is opt-in via CELL_OBSERVATORY_EMIT;
all errors swallowed at scheduling level + at coroutine level.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 1.5: Export observatory from cell_core package

- [ ] **Step 1: Modify `__init__.py`**

In `packages/cell-core/cell_core/__init__.py`, add:

```python
from cell_core import observatory  # noqa: F401 — opt-in emit module
```

And in `__all__`:

```python
__all__ = [
    # ... existing entries ...
    "observatory",
]
```

- [ ] **Step 2: Test export works**

```bash
cd packages/cell-core && python -c "from cell_core import observatory; print(observatory.is_enabled())"
```

Expected: `False` (no env set), no ImportError.

- [ ] **Step 3: Commit + push + open PR**

```bash
git add packages/cell-core/cell_core/__init__.py
git commit -m "chore(cell-core): export observatory submodule

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin feat/cell-observatory-pr1-cell-core

gh pr create --title "feat(cell-core): observatory emitter + pulse hook (PR-1)" \
  --body "Implements §6 of cell-observatory spec. Resolves B1+B2 from §10 review."
```

- [ ] **Step 4: Wait CI green + merge**

```bash
gh pr checks --watch
gh pr merge --squash --auto
```

---

## PR-2: Register PG channel `cell_pulse_observed` in event_bus

**Branch:** `feat/cell-observatory-pr2-channel`
**Depends on:** PR-1 merged.

**Files:**
- Modify: `apps/backend-rag/backend/services/events/event_bus.py:46` (add to `PG_CHANNEL_MAP`)
- Test: `apps/backend-rag/backend/tests/services/events/test_channels.py`

### Task 2.1: Add channel to map + test

- [ ] **Step 1: Read existing PG_CHANNEL_MAP**

```bash
sed -n '46,80p' apps/backend-rag/backend/services/events/event_bus.py
```

Note the existing format (channel: event_type pairs).

- [ ] **Step 2: Write failing test**

In `apps/backend-rag/backend/tests/services/events/test_channels.py` (create or extend):

```python
def test_cell_pulse_observed_channel_registered():
    from backend.services.events.event_bus import PG_CHANNEL_MAP
    assert "cell_pulse_observed" in PG_CHANNEL_MAP


def test_cell_pulse_observed_channel_name_matches_outbox_validation():
    """The channel name must satisfy outbox.validate_channel regex."""
    from backend.services.events.outbox import validate_channel
    validate_channel("cell_pulse_observed")  # raises if invalid
```

- [ ] **Step 3: Run; expected FAIL on first test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -m pytest backend/tests/services/events/test_channels.py::test_cell_pulse_observed_channel_registered -v
```

Expected: FAIL with `assert "cell_pulse_observed" in PG_CHANNEL_MAP`.

- [ ] **Step 4: Add channel to PG_CHANNEL_MAP**

In `apps/backend-rag/backend/services/events/event_bus.py:46`, add entry:

```python
PG_CHANNEL_MAP: dict[str, str] = {
    # ... existing entries ...
    "cell_pulse_observed": "cell.pulse.observed",  # NEW: cell observatory phase 0
}
```

(Use the dotted event_type that follows existing conventions — adapt to actual existing pattern after reading line 46.)

- [ ] **Step 5: Run; expected 2 PASS**

```bash
PYTHONPATH=. python -m pytest backend/tests/services/events/test_channels.py -v
```

- [ ] **Step 6: Commit + PR**

```bash
git add apps/backend-rag/backend/services/events/event_bus.py apps/backend-rag/backend/tests/services/events/test_channels.py
git commit -m "$(cat <<'EOF'
feat(events): register cell_pulse_observed PG channel

Phase 0 of cell observatory — see spec §6 + §10 B4. Channel name
matches outbox.validate_channel regex, no allowlist code change needed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"

git push -u origin feat/cell-observatory-pr2-channel
gh pr create --title "feat(events): register cell_pulse_observed channel (PR-2)" --body "Spec §6"
gh pr checks --watch
gh pr merge --squash --auto
```

---

## PR-3: cell-observatory-collector Python service

**Branch:** `feat/cell-observatory-pr3-collector`
**Depends on:** PR-2 merged.

This PR is large (~12 sub-tasks). Group into logical commits within the same branch but commit-as-you-go (frequent commits per spec §11 WIP-commit-every-10min).

### Task 3.1: Bootstrap package skeleton

- [ ] **Step 1: Create directory + pyproject.toml**

```bash
mkdir -p apps/cell-observatory-collector/cell_observatory \
         apps/cell-observatory-collector/tests \
         apps/cell-observatory-collector/scripts
```

Create `apps/cell-observatory-collector/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "cell-observatory-collector"
version = "0.1.0"
description = "Listen to cell pulse events, classify with MiniMax M2, persist to local SQLite"
requires-python = ">=3.11"
dependencies = [
    "asyncpg>=0.29",
    "aiosqlite>=0.20",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "httpx>=0.27",
    "pydantic>=2.6",
    "structlog>=24.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.12",
]

[tool.setuptools.packages.find]
include = ["cell_observatory*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `__init__.py` and `__main__.py`**

`apps/cell-observatory-collector/cell_observatory/__init__.py`:

```python
"""Cell Pulse Observatory — listener + classifier + storage on Pro local."""
__version__ = "0.1.0"
```

`apps/cell-observatory-collector/cell_observatory/__main__.py`:

```python
"""python -m cell_observatory — entrypoint for LaunchAgent."""
import asyncio
import structlog

from cell_observatory.collector import run_collector
from cell_observatory.api import run_api

structlog.configure(processors=[
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.JSONRenderer(),
])

log = structlog.get_logger()


async def main():
    log.info("cell-observatory-collector starting", version="0.1.0")
    await asyncio.gather(run_collector(), run_api())


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Smoke test imports**

```bash
cd apps/cell-observatory-collector && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -c "from cell_observatory import __version__; print(__version__)"
```

Expected: `0.1.0`.

- [ ] **Step 4: Commit**

```bash
git add apps/cell-observatory-collector/pyproject.toml \
        apps/cell-observatory-collector/cell_observatory/__init__.py \
        apps/cell-observatory-collector/cell_observatory/__main__.py
git commit -m "feat(observatory): bootstrap cell-observatory-collector package

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.2: Pydantic models

- [ ] **Step 1: Write failing test**

`apps/cell-observatory-collector/tests/test_models.py`:

```python
import pytest
from cell_observatory.models import PulseEventV1, ClassificationLabel


def test_pulse_event_v1_minimal():
    event = PulseEventV1(
        _outbox_id=1,
        event_version="v1",
        cell_id="organism",
        cell_kind="innervation",
        pulse_id="01ABC",
        pulse_timestamp="2026-05-01T00:00:00.000Z",
        phase="homeostatic",
        sensors=[],
        pulse_result={"classifier_self": "green", "trend_window_min": 15, "trend_label": "stable"},
        homeostatic_state={"energy_pct": 80, "load_factor": 0.3},
        scar_signals=[],
        metadata={"host": "Nuzantara", "machine_role": "Pro", "cell_core_version": "0.1.4"},
    )
    assert event.cell_id == "organism"
    assert event.outbox_id == 1  # underscore-prefixed alias


def test_classification_label_enum():
    assert ClassificationLabel.NORMAL.value == "normal"
    assert ClassificationLabel.ANOMALY.value == "anomaly"
    assert ClassificationLabel.CRITICAL.value == "critical"
    assert ClassificationLabel.UNCERTAIN.value == "uncertain"


def test_pulse_event_v1_rejects_event_version_mismatch():
    with pytest.raises(ValueError):
        PulseEventV1(
            _outbox_id=1,
            event_version="v2",  # wrong
            cell_id="x", cell_kind="x", pulse_id="x",
            pulse_timestamp="2026-05-01T00:00:00.000Z",
            phase="x", sensors=[], pulse_result={}, homeostatic_state={},
            scar_signals=[], metadata={},
        )
```

- [ ] **Step 2: Run; expected FAIL**

```bash
python -m pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement models.py**

`apps/cell-observatory-collector/cell_observatory/models.py`:

```python
from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class ClassificationLabel(str, Enum):
    NORMAL = "normal"
    ANOMALY = "anomaly"
    CRITICAL = "critical"
    UNCERTAIN = "uncertain"


class PulseEventV1(BaseModel):
    """Schema for cell_pulse_observed events. Frozen v1 — bump to v2 if shape changes."""
    outbox_id: int = Field(alias="_outbox_id")
    event_version: Literal["v1"]
    cell_id: str
    cell_kind: str
    pulse_id: str
    pulse_timestamp: str  # ISO 8601 string; collector converts to int ms
    phase: str
    sensors: list[dict[str, Any]]
    pulse_result: dict[str, Any]
    homeostatic_state: dict[str, Any]
    scar_signals: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class ClassificationOutput(BaseModel):
    """Strict schema for MiniMax classifier output (Pydantic v2 generate_structured pattern)."""
    reasoning: str = Field(min_length=1, max_length=500)
    label: ClassificationLabel
    confidence: float = Field(ge=0.0, le=1.0)


class ClassificationResult(BaseModel):
    """Persisted classification (output + metadata)."""
    outbox_id: int
    label: ClassificationLabel
    confidence: float
    reasoning: str
    label_diff: Literal["agree", "disagree"]
    model: str
    model_version: str | None = None
    cost_usd: float
    latency_ms: int
    error: str | None = None
```

- [ ] **Step 4: Run; expected 3 PASS**

```bash
python -m pytest tests/test_models.py -v
```

- [ ] **Step 5: Commit**

```bash
git add apps/cell-observatory-collector/cell_observatory/models.py \
        apps/cell-observatory-collector/tests/test_models.py
git commit -m "feat(observatory): pydantic v2 models for pulse events + classification

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.3: Config module

- [ ] **Step 1: Test**

`apps/cell-observatory-collector/tests/test_config.py`:

```python
import pytest
from cell_observatory.config import Config


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-fake")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://x/y")
    cfg = Config.from_env()
    assert cfg.minimax_api_key == "sk-fake"
    assert cfg.api_port == 17891
    assert cfg.cost_alert_threshold_usd == 1.0  # M6 default
    assert cfg.retention_days == 90
    assert cfg.classifier_max_inflight == 50
    assert cfg.classifier_queue_maxsize == 10000  # G1 fix


def test_config_overrides(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-fake")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("OBSERVATORY_COST_ALERT_THRESHOLD_USD", "5.0")
    monkeypatch.setenv("OBSERVATORY_API_PORT", "17892")
    cfg = Config.from_env()
    assert cfg.cost_alert_threshold_usd == 5.0
    assert cfg.api_port == 17892


def test_config_required_keys_missing(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("EVENTBUS_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="MINIMAX_API_KEY"):
        Config.from_env()
```

- [ ] **Step 2: Implement**

`apps/cell-observatory-collector/cell_observatory/config.py`:

```python
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    minimax_api_key: str
    eventbus_database_url: str
    db_path: Path
    api_port: int
    api_key: str
    cost_alert_threshold_usd: float
    retention_days: int
    classifier_max_inflight: int
    classifier_queue_maxsize: int

    @classmethod
    def from_env(cls) -> "Config":
        try:
            minimax_api_key = os.environ["MINIMAX_API_KEY"]
        except KeyError as e:
            raise RuntimeError("MINIMAX_API_KEY required") from e

        try:
            eventbus_database_url = os.environ["EVENTBUS_DATABASE_URL"]
        except KeyError as e:
            raise RuntimeError("EVENTBUS_DATABASE_URL required") from e

        db_path = Path(os.environ.get(
            "OBSERVATORY_DB_PATH",
            str(Path.home() / ".cell-observatory" / "observatory.db"),
        ))

        return cls(
            minimax_api_key=minimax_api_key,
            eventbus_database_url=eventbus_database_url,
            db_path=db_path,
            api_port=int(os.environ.get("OBSERVATORY_API_PORT", "17891")),
            api_key=os.environ.get("OBSERVATORY_API_KEY", ""),
            cost_alert_threshold_usd=float(os.environ.get("OBSERVATORY_COST_ALERT_THRESHOLD_USD", "1.0")),
            retention_days=int(os.environ.get("OBSERVATORY_RETENTION_DAYS", "90")),
            classifier_max_inflight=int(os.environ.get("OBSERVATORY_CLASSIFIER_MAX_INFLIGHT", "50")),
            classifier_queue_maxsize=int(os.environ.get("OBSERVATORY_CLASSIFIER_QUEUE_MAXSIZE", "10000")),
        )
```

- [ ] **Step 3: Run + commit**

```bash
python -m pytest tests/test_config.py -v
git add apps/cell-observatory-collector/cell_observatory/config.py tests/test_config.py
git commit -m "feat(observatory): env-based Config with G1+M6 defaults

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.4: SQLite storage with WAL + idempotent inserts

- [ ] **Step 1: Test**

`apps/cell-observatory-collector/tests/test_storage.py`:

```python
import pytest
from pathlib import Path
from cell_observatory.storage import Storage


@pytest.fixture
async def storage(tmp_path):
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    await s.init()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_init_creates_schema(storage):
    rows = await storage._fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {r["name"] for r in rows}
    assert "pulse_events" in table_names
    assert "pulse_classifications" in table_names
    assert "pulse_daily_rollup" in table_names
    assert "pulse_classifications_fts" in table_names
    assert "schema_version" in table_names


@pytest.mark.asyncio
async def test_wal_mode_enabled(storage):
    rows = await storage._fetchall("PRAGMA journal_mode")
    assert rows[0]["journal_mode"].lower() == "wal"


@pytest.mark.asyncio
async def test_insert_pulse_event_idempotent(storage):
    payload = {
        "outbox_id": 1, "event_version": "v1", "cell_id": "organism",
        "cell_kind": "test", "pulse_id": "01ABC",
        "pulse_timestamp": "2026-05-01T00:00:00.000Z",
        "phase": "homeostatic",
        "sensors": [], "pulse_result": {"classifier_self": "green"},
        "homeostatic_state": {}, "scar_signals": [], "metadata": {},
    }
    inserted_first = await storage.insert_pulse_event(payload)
    inserted_second = await storage.insert_pulse_event(payload)
    assert inserted_first is True
    assert inserted_second is False  # already exists, skipped


@pytest.mark.asyncio
async def test_classification_upsert(storage):
    """Backfill must overwrite existing classification — A1 fix."""
    # First, insert a parent pulse event
    pulse = {"outbox_id": 1, "event_version": "v1", "cell_id": "x", "cell_kind": "x",
             "pulse_id": "x", "pulse_timestamp": "2026-05-01T00:00:00.000Z",
             "phase": "x", "sensors": [], "pulse_result": {"classifier_self": "green"},
             "homeostatic_state": {}, "scar_signals": [], "metadata": {}}
    await storage.insert_pulse_event(pulse)

    cls1 = {"outbox_id": 1, "label": "normal", "confidence": 0.9, "reasoning": "calm",
            "label_diff": "agree", "model": "minimax-m2", "model_version": None,
            "cost_usd": 0.0001, "latency_ms": 100, "error": None}
    cls2 = {**cls1, "label": "anomaly", "confidence": 0.6, "reasoning": "rethink"}

    await storage.upsert_classification(cls1)
    await storage.upsert_classification(cls2)

    rows = await storage._fetchall("SELECT label, confidence FROM pulse_classifications WHERE outbox_id=1")
    assert len(rows) == 1
    assert rows[0]["label"] == "anomaly"  # second won
    assert rows[0]["confidence"] == 0.6
```

- [ ] **Step 2: Implement**

`apps/cell-observatory-collector/cell_observatory/storage.py`:

```python
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pulse_events (
    outbox_id INTEGER PRIMARY KEY,
    cell_id TEXT NOT NULL, cell_kind TEXT NOT NULL,
    pulse_id TEXT NOT NULL, pulse_timestamp INTEGER NOT NULL,
    phase TEXT NOT NULL, classifier_self TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    received_at INTEGER NOT NULL, received_lag_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pulse_events_cell_ts ON pulse_events(cell_id, pulse_timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_pulse_events_classifier ON pulse_events(classifier_self, pulse_timestamp DESC);

CREATE TABLE IF NOT EXISTS pulse_classifications (
    outbox_id INTEGER PRIMARY KEY REFERENCES pulse_events(outbox_id),
    classified_at INTEGER NOT NULL,
    label TEXT NOT NULL, confidence REAL NOT NULL,
    reasoning TEXT, label_diff TEXT,
    model TEXT NOT NULL, model_version TEXT,
    cost_usd REAL NOT NULL, latency_ms INTEGER NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS ix_classifications_label ON pulse_classifications(label, classified_at DESC);
CREATE INDEX IF NOT EXISTS ix_classifications_disagree ON pulse_classifications(label, outbox_id) WHERE label_diff='disagree';

CREATE TABLE IF NOT EXISTS pulse_daily_rollup (
    day TEXT NOT NULL, cell_id TEXT NOT NULL,
    n_pulse INTEGER NOT NULL, n_self_green INTEGER NOT NULL,
    n_self_yellow INTEGER NOT NULL, n_self_red INTEGER NOT NULL,
    n_classified INTEGER NOT NULL, n_anomaly INTEGER NOT NULL,
    n_critical INTEGER NOT NULL, n_disagree INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    PRIMARY KEY (day, cell_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS pulse_classifications_fts USING fts5(
    outbox_id UNINDEXED, label, reasoning,
    content='pulse_classifications', content_rowid='outbox_id'
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL
);
INSERT OR IGNORE INTO schema_version VALUES (1, strftime('%s','now')*1000);
"""


def _to_epoch_ms(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        assert self._conn is not None
        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def insert_pulse_event(self, payload: dict[str, Any]) -> bool:
        """Idempotent insert. Returns True if inserted, False if outbox_id already present."""
        assert self._conn is not None
        ts_ms = _to_epoch_ms(payload["pulse_timestamp"])
        now = _now_ms()
        cursor = await self._conn.execute(
            "INSERT OR IGNORE INTO pulse_events "
            "(outbox_id, cell_id, cell_kind, pulse_id, pulse_timestamp, phase, "
            " classifier_self, payload_json, received_at, received_lag_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                payload["outbox_id"], payload["cell_id"], payload["cell_kind"],
                payload["pulse_id"], ts_ms, payload["phase"],
                payload["pulse_result"].get("classifier_self", "unknown"),
                json.dumps(payload),
                now, max(0, now - ts_ms),
            ),
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def upsert_classification(self, c: dict[str, Any]) -> None:
        """A1 fix: ON CONFLICT DO UPDATE so backfill can re-classify."""
        assert self._conn is not None
        await self._conn.execute(
            "INSERT INTO pulse_classifications "
            "(outbox_id, classified_at, label, confidence, reasoning, label_diff, "
            " model, model_version, cost_usd, latency_ms, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(outbox_id) DO UPDATE SET "
            "classified_at=excluded.classified_at, label=excluded.label, "
            "confidence=excluded.confidence, reasoning=excluded.reasoning, "
            "label_diff=excluded.label_diff, model=excluded.model, "
            "model_version=excluded.model_version, cost_usd=excluded.cost_usd, "
            "latency_ms=excluded.latency_ms, error=excluded.error",
            (
                c["outbox_id"], _now_ms(), c["label"], c["confidence"],
                c["reasoning"], c["label_diff"], c["model"], c["model_version"],
                c["cost_usd"], c["latency_ms"], c["error"],
            ),
        )
        await self._conn.commit()
```

- [ ] **Step 3: Run + commit**

```bash
python -m pytest tests/test_storage.py -v
git add apps/cell-observatory-collector/cell_observatory/storage.py tests/test_storage.py
git commit -m "feat(observatory): SQLite storage WAL + idempotent inserts + A1 upsert

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.5: MiniMax classifier with circuit breaker (M3) + bounded queue (G1)

- [ ] **Step 1: Test**

`apps/cell-observatory-collector/tests/test_classifier.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from cell_observatory.classifier import MinimaxClassifier, CircuitOpenError
from cell_observatory.models import PulseEventV1


@pytest.fixture
def event():
    return PulseEventV1(
        _outbox_id=1, event_version="v1", cell_id="organism", cell_kind="x",
        pulse_id="01A", pulse_timestamp="2026-05-01T00:00:00.000Z",
        phase="homeostatic", sensors=[],
        pulse_result={"classifier_self": "green", "trend_window_min": 15, "trend_label": "stable"},
        homeostatic_state={"energy_pct": 80, "load_factor": 0.3},
        scar_signals=[], metadata={},
    )


@pytest.mark.asyncio
async def test_classify_returns_structured(event):
    clf = MinimaxClassifier(api_key="sk-fake")
    fake_response = {
        "choices": [{"message": {"content": '{"reasoning": "all good", "label": "normal", "confidence": 0.9}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
    }
    with patch.object(clf, "_call_api", AsyncMock(return_value=fake_response)):
        result = await clf.classify(event)
    assert result.label.value == "normal"
    assert result.confidence == 0.9
    assert result.cost_usd > 0


@pytest.mark.asyncio
async def test_classify_label_diff_disagree(event):
    """Cell self=green, LLM=anomaly → label_diff='disagree'."""
    clf = MinimaxClassifier(api_key="sk-fake")
    fake_response = {
        "choices": [{"message": {"content": '{"reasoning": "subtle issue", "label": "anomaly", "confidence": 0.7}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
    }
    with patch.object(clf, "_call_api", AsyncMock(return_value=fake_response)):
        result = await clf.classify(event)
    assert result.label_diff == "disagree"


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_n_failures():
    """M3 fix: 5 consecutive 5xx → circuit opens, raises CircuitOpenError on 6th call."""
    clf = MinimaxClassifier(api_key="sk-fake", circuit_threshold=5)
    failing = AsyncMock(side_effect=Exception("500"))
    with patch.object(clf, "_call_api", failing):
        for _ in range(5):
            with pytest.raises(Exception):
                await clf.classify(event_factory())  # any event
    # 6th: circuit open
    with pytest.raises(CircuitOpenError):
        await clf.classify(event_factory())


def event_factory():
    return PulseEventV1(
        _outbox_id=1, event_version="v1", cell_id="x", cell_kind="x",
        pulse_id="x", pulse_timestamp="2026-05-01T00:00:00.000Z",
        phase="x", sensors=[], pulse_result={"classifier_self": "green"},
        homeostatic_state={}, scar_signals=[], metadata={},
    )
```

- [ ] **Step 2: Implement classifier.py**

`apps/cell-observatory-collector/cell_observatory/classifier.py`:

```python
from __future__ import annotations
import json
import time
from typing import Any
import httpx
from pydantic import ValidationError

from cell_observatory.models import (
    ClassificationLabel, ClassificationOutput, ClassificationResult, PulseEventV1
)


class CircuitOpenError(Exception):
    """Raised when MiniMax circuit breaker is open."""


_PROMPT_VERSION = "v1"
_SYSTEM_PROMPT = """You are an SRE classifier for biological-cell-style health pulses.
Given sensor readings + self-classification by the cell, output a JSON with:
- reasoning: 1-2 sentences, what catches your attention or confirms normality
- label: 'normal' | 'anomaly' | 'critical' | 'uncertain'
- confidence: 0.0 to 1.0

Rules:
- 'normal' = sensors within expected band, no trend break
- 'anomaly' = ONE sensor unusual but not failing, OR self-yellow with stable trend
- 'critical' = multi-sensor failure, OR self-red, OR trend break crossing threshold
- 'uncertain' = ambiguous, missing data, never seen pattern

Confidence calibration: 0.9+ only when symptom matches known scar OR signals are unambiguous.

Respond ONLY with valid JSON, no markdown."""


def _render_user_prompt(event: PulseEventV1) -> str:
    sensors_fmt = "\n".join(
        f"- {s.get('name', '?')}: " + ", ".join(f"{k}={v}" for k, v in s.items() if k != "name")
        for s in event.sensors
    ) or "  (no sensors)"
    return (
        f"Cell: {event.cell_id} ({event.cell_kind}, phase={event.phase})\n"
        f"Self-classification: {event.pulse_result.get('classifier_self', '?')}\n"
        f"Sensors:\n{sensors_fmt}\n"
        f"Trend: {event.pulse_result.get('trend_label', '?')} "
        f"over {event.pulse_result.get('trend_window_min', '?')}min\n"
        f"Homeostatic state: energy={event.homeostatic_state.get('energy_pct', '?')}%, "
        f"load={event.homeostatic_state.get('load_factor', '?')}\n\n"
        f"Classify."
    )


class MinimaxClassifier:
    BASE_URL = "https://api.minimax.io/v1/chat/completions"
    MODEL = "MiniMax-M2"
    PRICE_INPUT_USD_PER_M = 0.30
    PRICE_OUTPUT_USD_PER_M = 1.20

    def __init__(self, api_key: str, circuit_threshold: int = 5,
                 circuit_recovery_s: float = 60.0):
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=10.0)
        self._consecutive_failures = 0
        self._circuit_threshold = circuit_threshold
        self._circuit_open_until: float = 0.0
        self._circuit_recovery_s = circuit_recovery_s

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _call_api(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        resp = await self._client.post(
            self.BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self.MODEL, "messages": messages, "temperature": 0.1, "max_tokens": 200},
        )
        resp.raise_for_status()
        return resp.json()

    def _check_circuit(self) -> None:
        if time.monotonic() < self._circuit_open_until:
            raise CircuitOpenError("MiniMax circuit open")

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_threshold:
            self._circuit_open_until = time.monotonic() + self._circuit_recovery_s

    async def classify(self, event: PulseEventV1) -> ClassificationResult:
        self._check_circuit()
        start = time.monotonic()

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _render_user_prompt(event)},
        ]

        try:
            resp = await self._call_api(messages)
        except Exception:
            self._record_failure()
            raise
        self._record_success()

        latency_ms = int((time.monotonic() - start) * 1000)
        content = resp["choices"][0]["message"]["content"]

        try:
            parsed = ClassificationOutput.model_validate_json(content)
        except ValidationError:
            # Retry once (PR #311 pattern); if second fail propagate
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "Output was not valid JSON. Re-emit ONLY the JSON object."})
            resp2 = await self._call_api(messages)
            content2 = resp2["choices"][0]["message"]["content"]
            parsed = ClassificationOutput.model_validate_json(content2)

        usage = resp.get("usage", {})
        cost = (
            usage.get("prompt_tokens", 0) / 1_000_000 * self.PRICE_INPUT_USD_PER_M
            + usage.get("completion_tokens", 0) / 1_000_000 * self.PRICE_OUTPUT_USD_PER_M
        )

        cell_self = event.pulse_result.get("classifier_self", "unknown")
        label_diff = "agree" if (
            (cell_self == "green" and parsed.label == ClassificationLabel.NORMAL)
            or (cell_self in ("yellow", "red") and parsed.label != ClassificationLabel.NORMAL)
        ) else "disagree"

        return ClassificationResult(
            outbox_id=event.outbox_id,
            label=parsed.label,
            confidence=parsed.confidence,
            reasoning=parsed.reasoning[:500],
            label_diff=label_diff,
            model=f"minimax-m2-{_PROMPT_VERSION}",
            model_version=resp.get("model"),
            cost_usd=round(cost, 6),
            latency_ms=latency_ms,
            error=None,
        )
```

- [ ] **Step 3: Run + commit**

```bash
python -m pytest tests/test_classifier.py -v
git add apps/cell-observatory-collector/cell_observatory/classifier.py tests/test_classifier.py
git commit -m "feat(observatory): MiniMax classifier with circuit breaker + structured output

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.6: Collector with bounded queue (G1) + outbox replay

- [ ] **Step 1: Test**

`apps/cell-observatory-collector/tests/test_collector.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from cell_observatory.collector import Collector


@pytest.mark.asyncio
async def test_bounded_queue_drops_oldest_on_overflow():
    """G1 fix: queue maxsize=10000, drop-oldest on overflow."""
    storage = AsyncMock()
    storage.insert_pulse_event = AsyncMock(return_value=True)
    classifier = AsyncMock()

    collector = Collector(storage=storage, classifier=classifier,
                          classifier_max_inflight=2, classifier_queue_maxsize=3)

    for i in range(10):
        collector._enqueue_for_classification({"outbox_id": i})

    # Queue should be capped at maxsize, oldest dropped
    assert collector._classification_queue.qsize() == 3


@pytest.mark.asyncio
async def test_outbox_replay_on_startup():
    """Replay unconsumed events_outbox rows on collector startup."""
    storage = AsyncMock()
    storage.insert_pulse_event = AsyncMock(return_value=True)
    classifier = AsyncMock()

    collector = Collector(storage=storage, classifier=classifier)

    fake_conn_rows = [
        {"outbox_id": 1, "payload": '{"_outbox_id": 1, "event_version": "v1", "cell_id": "x", "cell_kind": "x", "pulse_id": "x", "pulse_timestamp": "2026-05-01T00:00:00Z", "phase": "x", "sensors": [], "pulse_result": {"classifier_self": "green"}, "homeostatic_state": {}, "scar_signals": [], "metadata": {}}'},
    ]

    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=fake_conn_rows)
    fake_conn.execute = AsyncMock()

    await collector._replay_outbox_unconsumed(fake_conn)

    storage.insert_pulse_event.assert_called_once()
    fake_conn.execute.assert_called()  # ack via consumed_at
```

- [ ] **Step 2: Implement**

`apps/cell-observatory-collector/cell_observatory/collector.py`:

```python
from __future__ import annotations
import asyncio
import json
import structlog
from typing import Any

import asyncpg

from cell_observatory.classifier import CircuitOpenError, MinimaxClassifier
from cell_observatory.config import Config
from cell_observatory.models import PulseEventV1
from cell_observatory.storage import Storage

log = structlog.get_logger(__name__)


class Collector:
    """Listens to cell_pulse_observed PG channel + replays unconsumed outbox rows."""

    def __init__(
        self,
        storage: Storage,
        classifier: MinimaxClassifier,
        classifier_max_inflight: int = 50,
        classifier_queue_maxsize: int = 10000,
    ):
        self.storage = storage
        self.classifier = classifier
        self._semaphore = asyncio.Semaphore(classifier_max_inflight)
        self._classification_queue: asyncio.Queue = asyncio.Queue(maxsize=classifier_queue_maxsize)
        self._classification_workers: list[asyncio.Task] = []

    def _enqueue_for_classification(self, payload: dict[str, Any]) -> None:
        """G1 fix: drop-oldest on overflow, log WARN."""
        try:
            self._classification_queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                dropped = self._classification_queue.get_nowait()
                log.warning("classification queue full, dropped oldest",
                            dropped_outbox_id=dropped.get("outbox_id"),
                            new_outbox_id=payload.get("outbox_id"))
                self._classification_queue.put_nowait(payload)
            except asyncio.QueueEmpty:
                pass

    async def _classification_worker(self) -> None:
        while True:
            payload = await self._classification_queue.get()
            try:
                async with self._semaphore:
                    event = PulseEventV1.model_validate(payload)
                    try:
                        result = await self.classifier.classify(event)
                        await self.storage.upsert_classification(result.model_dump())
                    except CircuitOpenError:
                        log.warning("classifier circuit open, skipping",
                                    outbox_id=event.outbox_id)
                    except Exception as exc:
                        log.error("classification failed",
                                  outbox_id=event.outbox_id, error=str(exc))
                        # Persist error row so backfill knows we tried
                        await self.storage.upsert_classification({
                            "outbox_id": event.outbox_id, "label": "uncertain",
                            "confidence": 0.0, "reasoning": "",
                            "label_diff": "agree", "model": "minimax-m2-v1",
                            "model_version": None, "cost_usd": 0.0,
                            "latency_ms": 0, "error": str(exc)[:500],
                        })
            finally:
                self._classification_queue.task_done()

    async def _replay_outbox_unconsumed(self, conn: asyncpg.Connection) -> None:
        rows = await conn.fetch(
            "SELECT outbox_id, payload FROM events_outbox "
            "WHERE channel='cell_pulse_observed' AND consumed_at IS NULL "
            "ORDER BY outbox_id ASC LIMIT 1000"
        )
        for row in rows:
            try:
                payload = json.loads(row["payload"])
                payload["_outbox_id"] = row["outbox_id"]
                inserted = await self.storage.insert_pulse_event(payload)
                if inserted:
                    self._enqueue_for_classification(payload)
                await conn.execute(
                    "UPDATE events_outbox SET consumed_at=NOW() WHERE outbox_id=$1",
                    row["outbox_id"],
                )
            except Exception as exc:
                log.warning("replay row failed", outbox_id=row["outbox_id"], error=str(exc))

    def _on_notify(self, conn, pid, channel, payload_str):
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            log.warning("invalid notify payload", payload=payload_str[:200])
            return
        # Schedule the async work without blocking the listener
        asyncio.create_task(self._handle_notification(payload))

    async def _handle_notification(self, payload: dict[str, Any]) -> None:
        try:
            inserted = await self.storage.insert_pulse_event(payload)
            if inserted:
                self._enqueue_for_classification(payload)
        except Exception as exc:
            log.error("notification handling failed", error=str(exc))

    async def run(self, db_url: str, num_workers: int = 4) -> None:
        # Start classification workers
        self._classification_workers = [
            asyncio.create_task(self._classification_worker())
            for _ in range(num_workers)
        ]

        while True:
            try:
                conn = await asyncpg.connect(db_url)
                try:
                    await conn.add_listener("cell_pulse_observed", self._on_notify)
                    log.info("listener attached, replaying outbox")
                    await self._replay_outbox_unconsumed(conn)
                    log.info("replay complete, awaiting events")
                    while True:
                        await asyncio.sleep(30)
                        # heartbeat
                        await conn.execute("SELECT 1")
                finally:
                    await conn.close()
            except (asyncpg.PostgresError, OSError) as exc:
                log.warning("listener disconnected, retry in 5s", error=str(exc))
                await asyncio.sleep(5)


async def run_collector():
    """Entrypoint used by __main__."""
    cfg = Config.from_env()
    storage = Storage(db_path=cfg.db_path)
    await storage.init()
    classifier = MinimaxClassifier(api_key=cfg.minimax_api_key)
    collector = Collector(
        storage=storage, classifier=classifier,
        classifier_max_inflight=cfg.classifier_max_inflight,
        classifier_queue_maxsize=cfg.classifier_queue_maxsize,
    )
    try:
        await collector.run(cfg.eventbus_database_url)
    finally:
        await classifier.aclose()
        await storage.close()
```

- [ ] **Step 3: Run + commit**

```bash
python -m pytest tests/test_collector.py -v
git add apps/cell-observatory-collector/cell_observatory/collector.py tests/test_collector.py
git commit -m "feat(observatory): collector with bounded queue + outbox replay

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.7: Rollup + prune jobs

- [ ] **Step 1: Test**

`apps/cell-observatory-collector/tests/test_rollup.py`:

```python
import pytest
from cell_observatory.rollup import compute_daily_rollup
from cell_observatory.storage import Storage


@pytest.mark.asyncio
async def test_compute_rollup(tmp_path):
    s = Storage(db_path=tmp_path / "x.db")
    await s.init()
    # seed 3 events for cell 'organism', 2 green 1 yellow
    for i, label in enumerate(["green", "green", "yellow"]):
        await s.insert_pulse_event({
            "outbox_id": i, "event_version": "v1", "cell_id": "organism",
            "cell_kind": "x", "pulse_id": f"01{i}",
            "pulse_timestamp": "2026-05-01T00:00:00.000Z",
            "phase": "x", "sensors": [],
            "pulse_result": {"classifier_self": label},
            "homeostatic_state": {}, "scar_signals": [], "metadata": {},
        })

    await compute_daily_rollup(s, "2026-05-01")
    rows = await s._fetchall(
        "SELECT * FROM pulse_daily_rollup WHERE day='2026-05-01' AND cell_id='organism'"
    )
    assert len(rows) == 1
    assert rows[0]["n_pulse"] == 3
    assert rows[0]["n_self_green"] == 2
    assert rows[0]["n_self_yellow"] == 1
    await s.close()
```

- [ ] **Step 2: Implement rollup.py**

```python
from cell_observatory.storage import Storage


async def compute_daily_rollup(storage: Storage, day: str) -> None:
    """Aggregate pulse_events + classifications into pulse_daily_rollup for `day` (YYYY-MM-DD WITA)."""
    sql = """
    INSERT OR REPLACE INTO pulse_daily_rollup
        (day, cell_id, n_pulse, n_self_green, n_self_yellow, n_self_red,
         n_classified, n_anomaly, n_critical, n_disagree, cost_usd)
    SELECT
        ?, e.cell_id,
        COUNT(*),
        SUM(CASE WHEN e.classifier_self='green' THEN 1 ELSE 0 END),
        SUM(CASE WHEN e.classifier_self='yellow' THEN 1 ELSE 0 END),
        SUM(CASE WHEN e.classifier_self='red' THEN 1 ELSE 0 END),
        COUNT(c.outbox_id),
        SUM(CASE WHEN c.label='anomaly' THEN 1 ELSE 0 END),
        SUM(CASE WHEN c.label='critical' THEN 1 ELSE 0 END),
        SUM(CASE WHEN c.label_diff='disagree' THEN 1 ELSE 0 END),
        COALESCE(SUM(c.cost_usd), 0.0)
    FROM pulse_events e
    LEFT JOIN pulse_classifications c ON c.outbox_id = e.outbox_id
    WHERE date(e.pulse_timestamp/1000, 'unixepoch', '+8 hours') = ?
    GROUP BY e.cell_id
    """
    assert storage._conn is not None
    await storage._conn.execute(sql, (day, day))
    await storage._conn.commit()
```

`apps/cell-observatory-collector/cell_observatory/prune.py`:

```python
import asyncio
import structlog
from datetime import datetime, timezone, timedelta

from cell_observatory.config import Config
from cell_observatory.storage import Storage

log = structlog.get_logger(__name__)


async def prune_old_events(storage: Storage, retention_days: int) -> int:
    """Delete pulse_events older than retention_days. Cascade deletes classifications via FK."""
    assert storage._conn is not None
    cutoff_ms = int((datetime.now(timezone.utc) - timedelta(days=retention_days)).timestamp() * 1000)

    cur = await storage._conn.execute(
        "DELETE FROM pulse_classifications WHERE outbox_id IN "
        "(SELECT outbox_id FROM pulse_events WHERE pulse_timestamp < ?)",
        (cutoff_ms,),
    )
    deleted_class = cur.rowcount

    cur = await storage._conn.execute(
        "DELETE FROM pulse_events WHERE pulse_timestamp < ?", (cutoff_ms,)
    )
    deleted_events = cur.rowcount
    await storage._conn.commit()

    log.info("pruned old events", deleted_events=deleted_events, deleted_classifications=deleted_class)
    return deleted_events


async def main():
    cfg = Config.from_env()
    s = Storage(db_path=cfg.db_path)
    await s.init()
    try:
        await prune_old_events(s, cfg.retention_days)
    finally:
        await s.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Run + commit**

```bash
python -m pytest tests/test_rollup.py -v
git add apps/cell-observatory-collector/cell_observatory/rollup.py \
        apps/cell-observatory-collector/cell_observatory/prune.py \
        apps/cell-observatory-collector/tests/test_rollup.py
git commit -m "feat(observatory): daily rollup + 90d prune

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.8: FastAPI loopback API

- [ ] **Step 1: Test**

`apps/cell-observatory-collector/tests/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from cell_observatory.api import build_app


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-fake")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("OBSERVATORY_API_KEY", "secret123")
    monkeypatch.setenv("OBSERVATORY_DB_PATH", str(tmp_path / "x.db"))
    app, _ = await build_app()
    yield app


def test_health_unauth(app):
    client = TestClient(app)
    resp = client.get("/api/observatory/health")
    assert resp.status_code == 401


def test_health_authed(app):
    client = TestClient(app)
    resp = client.get("/api/observatory/health", headers={"X-Observatory-Key": "secret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["alive"] is True
```

- [ ] **Step 2: Implement api.py**

```python
from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Header, HTTPException, Request
from typing import Optional

from cell_observatory.config import Config
from cell_observatory.storage import Storage


async def build_app() -> tuple[FastAPI, Storage]:
    cfg = Config.from_env()
    storage = Storage(db_path=cfg.db_path)
    await storage.init()

    app = FastAPI(title="Cell Observatory API", version="0.1.0")

    def _require_auth(x_observatory_key: Optional[str]) -> None:
        if not cfg.api_key:
            return
        if x_observatory_key != cfg.api_key:
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/api/observatory/health")
    async def health(x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key")):
        _require_auth(x_observatory_key)
        rows = await storage._fetchall("SELECT COUNT(*) AS n FROM pulse_events")
        events_24h = await storage._fetchall(
            "SELECT COUNT(*) AS n FROM pulse_events WHERE pulse_timestamp > ?",
            ((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp() * 1000,),
        )
        return {
            "alive": True, "uptime_s": 0,  # stub for fase 0
            "events_total": rows[0]["n"],
            "events_24h": events_24h[0]["n"],
        }

    @app.get("/api/observatory/pulse")
    async def list_pulses(
        cell_id: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
        x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key"),
    ):
        _require_auth(x_observatory_key)
        clauses, params = [], []
        if cell_id:
            clauses.append("cell_id = ?"); params.append(cell_id)
        if since:
            since_ms = int(datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp() * 1000)
            clauses.append("pulse_timestamp >= ?"); params.append(since_ms)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(min(limit, 1000))
        rows = await storage._fetchall(
            f"SELECT outbox_id, cell_id, pulse_id, pulse_timestamp, classifier_self "
            f"FROM pulse_events {where} ORDER BY pulse_timestamp DESC LIMIT ?",
            tuple(params),
        )
        return {"items": rows}

    @app.get("/api/observatory/anomalies")
    async def anomalies(
        since: Optional[str] = None,
        label: Optional[str] = None,
        x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key"),
    ):
        _require_auth(x_observatory_key)
        clauses, params = [], []
        if label:
            clauses.append("c.label = ?"); params.append(label)
        else:
            clauses.append("c.label IN ('anomaly', 'critical', 'uncertain')")
        if since:
            since_ms = int(datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp() * 1000)
            clauses.append("c.classified_at >= ?"); params.append(since_ms)
        where = "WHERE " + " AND ".join(clauses)
        rows = await storage._fetchall(
            f"SELECT c.outbox_id, c.label, c.confidence, c.reasoning, c.label_diff, "
            f"e.cell_id, e.pulse_timestamp "
            f"FROM pulse_classifications c JOIN pulse_events e ON e.outbox_id = c.outbox_id "
            f"{where} ORDER BY c.confidence DESC LIMIT 100",
            tuple(params),
        )
        return {"items": rows}

    @app.get("/api/observatory/rollup")
    async def rollup(
        day: str,
        cell_id: Optional[str] = None,
        x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key"),
    ):
        _require_auth(x_observatory_key)
        if cell_id:
            rows = await storage._fetchall(
                "SELECT * FROM pulse_daily_rollup WHERE day = ? AND cell_id = ?", (day, cell_id),
            )
        else:
            rows = await storage._fetchall("SELECT * FROM pulse_daily_rollup WHERE day = ?", (day,))
        return {"items": rows}

    @app.get("/api/observatory/cost")
    async def cost(
        since: Optional[str] = None,
        x_observatory_key: Optional[str] = Header(None, alias="X-Observatory-Key"),
    ):
        _require_auth(x_observatory_key)
        params = []
        clause = ""
        if since:
            since_ms = int(datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp() * 1000)
            clause = "WHERE classified_at >= ?"
            params.append(since_ms)
        rows = await storage._fetchall(
            f"SELECT SUM(cost_usd) AS total, COUNT(*) AS calls FROM pulse_classifications {clause}",
            tuple(params),
        )
        return {"total_usd": rows[0]["total"] or 0.0, "calls": rows[0]["calls"] or 0,
                "alert_threshold_usd": cfg.cost_alert_threshold_usd}

    return app, storage


async def run_api() -> None:
    """Entrypoint used by __main__."""
    import uvicorn
    cfg = Config.from_env()
    app, _ = await build_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=cfg.api_port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
```

- [ ] **Step 3: Run + commit**

```bash
python -m pytest tests/test_api.py -v
git add apps/cell-observatory-collector/cell_observatory/api.py tests/test_api.py
git commit -m "feat(observatory): FastAPI loopback API (health, pulse, anomalies, rollup, cost)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.9: LaunchAgents (collector + prune + selfcheck)

- [ ] **Step 1: Create collector plist**

`infra/launchagents/com.nuzantara.cell-observatory.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.cell-observatory</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/Desktop/nuzantara/apps/cell-observatory-collector/.venv/bin/python</string>
        <string>-m</string>
        <string>cell_observatory</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/cell-observatory/collector.out.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/cell-observatory/collector.err.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/cell-observatory-collector</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
        <key>MACHINE_ROLE</key>
        <string>Pro</string>
    </dict>
</dict>
</plist>
```

(Note: secrets `MINIMAX_API_KEY`, `EVENTBUS_DATABASE_URL`, `OBSERVATORY_API_KEY` MUST be loaded from `~/.nuzantara-secrets.env` via a wrapper script — NOT in plist. See Step 2.)

- [ ] **Step 2: Update plist to use secrets-loading wrapper**

Replace `ProgramArguments` with:

```xml
<key>ProgramArguments</key>
<array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>set -a; source ~/.nuzantara-secrets.env; set +a; exec ~/Desktop/nuzantara/apps/cell-observatory-collector/.venv/bin/python -m cell_observatory</string>
</array>
```

- [ ] **Step 3: Create prune plist**

`infra/launchagents/com.nuzantara.cell-observatory-prune.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.cell-observatory-prune</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-lc</string>
        <string>set -a; source ~/.nuzantara-secrets.env; set +a; exec ~/Desktop/nuzantara/apps/cell-observatory-collector/.venv/bin/python -m cell_observatory.prune</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>4</integer><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/cell-observatory/prune.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/cell-observatory/prune.log</string>
</dict>
</plist>
```

- [ ] **Step 4: Create M2 selfcheck plist**

`infra/launchagents/com.nuzantara.cell-observatory-selfcheck.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.cell-observatory-selfcheck</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-lc</string>
        <string>~/Desktop/nuzantara/apps/cell-observatory-collector/scripts/healthcheck.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/cell-observatory/selfcheck.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/cell-observatory/selfcheck.log</string>
</dict>
</plist>
```

- [ ] **Step 5: Healthcheck script**

`apps/cell-observatory-collector/scripts/healthcheck.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

set -a
source ~/.nuzantara-secrets.env
set +a

URL="http://127.0.0.1:${OBSERVATORY_API_PORT:-17891}/api/observatory/health"
KEY="${OBSERVATORY_API_KEY:-}"

resp=$(curl -fsS -m 5 -H "X-Observatory-Key: $KEY" "$URL" || echo "FAIL")

if [ "$resp" = "FAIL" ]; then
    echo "[$(date -u +%FT%TZ)] CRITICAL: cell-observatory unreachable" >&2
    exit 1
fi

echo "[$(date -u +%FT%TZ)] OK: $resp"
```

- [ ] **Step 6: Bootstrap script**

`apps/cell-observatory-collector/scripts/bootstrap_db.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p ~/.cell-observatory ~/logs/cell-observatory
set -a; source ~/.nuzantara-secrets.env; set +a
~/Desktop/nuzantara/apps/cell-observatory-collector/.venv/bin/python \
    -c "import asyncio; from cell_observatory.storage import Storage; from cell_observatory.config import Config; \
        async def main(): cfg=Config.from_env(); s=Storage(db_path=cfg.db_path); await s.init(); await s.close(); \
        asyncio.run(main())"
echo "DB initialized at ~/.cell-observatory/observatory.db"
```

- [ ] **Step 7: chmod scripts + commit**

```bash
chmod +x apps/cell-observatory-collector/scripts/*.sh
git add apps/cell-observatory-collector/scripts/ infra/launchagents/com.nuzantara.cell-observatory*.plist
git commit -m "feat(observatory): LaunchAgents (collector KeepAlive + prune daily + selfcheck 5m)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.10: Open PR-3 + CI green + merge

- [ ] **Step 1: Push, open PR**

```bash
git push -u origin feat/cell-observatory-pr3-collector
gh pr create --title "feat(observatory): cell-observatory-collector service (PR-3)" \
  --body "$(cat <<'EOF'
## Summary
- New \`apps/cell-observatory-collector/\` Python service
- LaunchAgents: collector (KeepAlive), prune (daily 04:00 WITA), selfcheck (5min)
- All §6+§7 of spec implemented

Resolves G1 (bounded queue), M2 (selfcheck), M3 (circuit breaker), A1 (upsert), G3 (aiosqlite).

## Test plan
- [ ] \`pytest apps/cell-observatory-collector/tests/ -v\` — all PASS

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr checks --watch
gh pr merge --squash --auto
```

---

## PR-4: Dashboard tab `/observatory`

**Branch:** `feat/cell-observatory-pr4-dashboard`
**Depends on:** PR-3 merged.

**Files:**
- All under `apps/admin-dashboard-local/src/app/observatory/` (10+ files)
- Tests under `apps/admin-dashboard-local/__tests__/observatory/`

This PR follows existing admin-dashboard-local conventions; adapt the snippets below to that codebase's patterns.

### Task 4.1: TypeScript types mirror Pydantic

- [ ] **Step 1: Create types**

`apps/admin-dashboard-local/src/app/observatory/lib/types.ts`:

```typescript
export type ClassificationLabel = 'normal' | 'anomaly' | 'critical' | 'uncertain';
export type LabelDiff = 'agree' | 'disagree';
export type ClassifierSelf = 'green' | 'yellow' | 'red';

export interface PulseEvent {
  outbox_id: number;
  cell_id: string;
  pulse_id: string;
  pulse_timestamp: number; // unix ms
  classifier_self: ClassifierSelf;
}

export interface PulseEventDetail extends PulseEvent {
  cell_kind: string;
  phase: string;
  payload_json: string;
  received_at: number;
  received_lag_ms: number;
}

export interface PulseClassification {
  outbox_id: number;
  classified_at: number;
  label: ClassificationLabel;
  confidence: number;
  reasoning: string;
  label_diff: LabelDiff;
  cost_usd: number;
}

export interface DailyRollup {
  day: string;
  cell_id: string;
  n_pulse: number;
  n_self_green: number;
  n_self_yellow: number;
  n_self_red: number;
  n_classified: number;
  n_anomaly: number;
  n_critical: number;
  n_disagree: number;
  cost_usd: number;
}

export interface CostSummary {
  total_usd: number;
  calls: number;
  alert_threshold_usd: number;
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/admin-dashboard-local/src/app/observatory/lib/types.ts
git commit -m "feat(dashboard): observatory TS types mirror Pydantic models

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 4.2: Typed fetch client

- [ ] **Step 1: Create client**

`apps/admin-dashboard-local/src/app/observatory/lib/observatory-client.ts`:

```typescript
import { PulseEvent, PulseClassification, DailyRollup, CostSummary } from './types';

const BASE = process.env.NEXT_PUBLIC_OBSERVATORY_BASE ?? 'http://127.0.0.1:17891';
const KEY = process.env.NEXT_PUBLIC_OBSERVATORY_API_KEY ?? '';

async function fetchAuth<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { 'X-Observatory-Key': KEY },
    cache: 'no-store',
  });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export const observatoryClient = {
  health: () => fetchAuth<{ alive: boolean; events_24h: number }>('/api/observatory/health'),
  pulses: (cellId?: string, since?: string) =>
    fetchAuth<{ items: PulseEvent[] }>(
      `/api/observatory/pulse?${new URLSearchParams({
        ...(cellId && { cell_id: cellId }),
        ...(since && { since }),
        limit: '500',
      })}`
    ),
  anomalies: (since?: string) =>
    fetchAuth<{ items: (PulseClassification & { cell_id: string; pulse_timestamp: number })[] }>(
      `/api/observatory/anomalies?${new URLSearchParams({ ...(since && { since }) })}`
    ),
  rollup: (day: string) =>
    fetchAuth<{ items: DailyRollup[] }>(`/api/observatory/rollup?day=${day}`),
  cost: (since?: string) =>
    fetchAuth<CostSummary>(`/api/observatory/cost?${new URLSearchParams({ ...(since && { since }) })}`),
};
```

- [ ] **Step 2: Commit**

```bash
git add apps/admin-dashboard-local/src/app/observatory/lib/observatory-client.ts
git commit -m "feat(dashboard): observatory typed fetch client (loopback + X-Observatory-Key)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 4.3: Page + components (cell breakdown, anomaly hot-list, cost ledger)

- [ ] **Step 1: Page shell**

`apps/admin-dashboard-local/src/app/observatory/page.tsx`:

```tsx
'use client';

import useSWR from 'swr';
import { observatoryClient } from './lib/observatory-client';
import { CellBreakdown } from './components/CellBreakdown';
import { AnomalyHotList } from './components/AnomalyHotList';
import { CostLedger } from './components/CostLedger';
import { DisagreementWatch } from './components/DisagreementWatch';

export default function ObservatoryPage() {
  const today = new Date().toISOString().slice(0, 10);
  const { data: rollup } = useSWR(
    `rollup-${today}`,
    () => observatoryClient.rollup(today),
    { refreshInterval: 30_000 }
  );
  const { data: anomalies } = useSWR('anomalies-24h', () => observatoryClient.anomalies(), {
    refreshInterval: 30_000,
  });
  const { data: cost } = useSWR('cost-24h', () => observatoryClient.cost(), {
    refreshInterval: 30_000,
  });

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Cell Pulse Observatory</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <CellBreakdown rollups={rollup?.items ?? []} />
        <CostLedger summary={cost ?? null} />
      </div>
      <DisagreementWatch anomalies={anomalies?.items ?? []} />
      <AnomalyHotList anomalies={anomalies?.items ?? []} />
    </div>
  );
}
```

- [ ] **Step 2: Components — CellBreakdown**

`apps/admin-dashboard-local/src/app/observatory/components/CellBreakdown.tsx`:

```tsx
import { DailyRollup } from '../lib/types';

export function CellBreakdown({ rollups }: { rollups: DailyRollup[] }) {
  return (
    <div className="border rounded p-4">
      <h2 className="font-semibold mb-2">Per-Cell Breakdown (today)</h2>
      <table className="w-full text-sm">
        <thead><tr><th className="text-left">Cell</th><th>Pulses</th><th>Anomaly%</th><th>Disagree%</th></tr></thead>
        <tbody>
          {rollups.length === 0 && <tr><td colSpan={4} className="text-gray-400 text-center">no data yet</td></tr>}
          {rollups.map(r => (
            <tr key={r.cell_id}>
              <td>{r.cell_id}</td>
              <td className="text-center">{r.n_pulse}</td>
              <td className="text-center">{r.n_pulse > 0 ? ((r.n_anomaly / r.n_pulse) * 100).toFixed(1) : '0.0'}%</td>
              <td className="text-center">{r.n_pulse > 0 ? ((r.n_disagree / r.n_pulse) * 100).toFixed(1) : '0.0'}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Components — CostLedger**

`apps/admin-dashboard-local/src/app/observatory/components/CostLedger.tsx`:

```tsx
import { CostSummary } from '../lib/types';

export function CostLedger({ summary }: { summary: CostSummary | null }) {
  if (!summary) return <div className="border rounded p-4">Loading cost…</div>;
  const overThreshold = summary.total_usd > summary.alert_threshold_usd;
  return (
    <div className="border rounded p-4">
      <h2 className="font-semibold mb-2">MiniMax Cost Ledger</h2>
      <p className={overThreshold ? 'text-red-600' : ''}>
        {overThreshold && '⚠ '}
        Today: ${summary.total_usd.toFixed(4)} ({summary.calls} calls)
      </p>
      <p className="text-xs text-gray-500">Alert threshold: ${summary.alert_threshold_usd.toFixed(2)}/day</p>
    </div>
  );
}
```

- [ ] **Step 4: Components — AnomalyHotList**

```tsx
import { PulseClassification } from '../lib/types';

export function AnomalyHotList({ anomalies }: {
  anomalies: (PulseClassification & { cell_id: string; pulse_timestamp: number })[]
}) {
  return (
    <div className="border rounded p-4">
      <h2 className="font-semibold mb-2">Anomaly Hot List</h2>
      <table className="w-full text-sm">
        <thead><tr><th>Time</th><th>Cell</th><th>Label</th><th>Confidence</th><th>Reasoning</th></tr></thead>
        <tbody>
          {anomalies.length === 0 && <tr><td colSpan={5} className="text-gray-400 text-center">no anomalies in window</td></tr>}
          {anomalies.map(a => (
            <tr key={a.outbox_id}>
              <td className="text-xs">{new Date(a.pulse_timestamp).toLocaleTimeString()}</td>
              <td>{a.cell_id}</td>
              <td><span className={
                a.label === 'critical' ? 'text-red-600 font-bold' :
                a.label === 'anomaly' ? 'text-yellow-600' : 'text-gray-500'
              }>{a.label}</span></td>
              <td className="text-center">{(a.confidence * 100).toFixed(0)}%</td>
              <td className="text-xs text-gray-600 truncate max-w-md">{a.reasoning}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 5: Components — DisagreementWatch**

```tsx
import { PulseClassification } from '../lib/types';

export function DisagreementWatch({ anomalies }: {
  anomalies: (PulseClassification & { cell_id: string; pulse_timestamp: number })[]
}) {
  const disagreements = anomalies.filter(a => a.label_diff === 'disagree');
  return (
    <div className="border rounded p-4 bg-amber-50">
      <h2 className="font-semibold mb-2">Disagreement Watch (LLM ≠ cell self-classifier)</h2>
      <p className="text-xs text-gray-600 mb-2">
        Cases where MiniMax labeled anomaly/critical but cell self-classified green —
        the most interesting signal for fase 1+.
      </p>
      {disagreements.length === 0 && <p className="text-gray-400 text-sm">no disagreements yet</p>}
      <ul className="text-sm space-y-1">
        {disagreements.map(a => (
          <li key={a.outbox_id}>
            <strong>{a.cell_id}</strong>: {a.label} ({(a.confidence * 100).toFixed(0)}%) — {a.reasoning}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 6: Test client**

`apps/admin-dashboard-local/__tests__/observatory/client.test.ts`:

```typescript
import { observatoryClient } from '@/app/observatory/lib/observatory-client';

describe('observatoryClient', () => {
  it('hits the loopback URL with auth header', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue({
      ok: true, json: async () => ({ alive: true, events_24h: 0 }),
    } as Response);
    await observatoryClient.health();
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/api/observatory/health'),
      expect.objectContaining({ headers: expect.objectContaining({ 'X-Observatory-Key': expect.any(String) }) }),
    );
  });
});
```

- [ ] **Step 7: Run + commit**

```bash
cd apps/admin-dashboard-local && npm test -- __tests__/observatory/
git add apps/admin-dashboard-local/src/app/observatory \
        apps/admin-dashboard-local/__tests__/observatory
git commit -m "feat(dashboard): observatory tab — breakdown, anomalies, disagreement, cost

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 8: Open PR-4 + merge**

```bash
git push -u origin feat/cell-observatory-pr4-dashboard
gh pr create --title "feat(dashboard): observatory tab (PR-4)" --body "Spec §7."
gh pr checks --watch
gh pr merge --squash --auto
```

---

## PR-5: Activate organism cell pilot

**Branch:** `feat/cell-observatory-pr5-organism-enable`
**Depends on:** PR-4 merged. Smoke test (Task 5.1) MUST pass first.

### Task 5.1: M1 smoke test

- [ ] **Step 1: Create script**

`scripts/test_observatory_pulse.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

set -a; source ~/.nuzantara-secrets.env; set +a

echo "1) Inject test pulse via cell_core.observatory.emit_pulse_observed..."
~/Desktop/nuzantara/apps/cell-observatory-collector/.venv/bin/python <<'PY'
import asyncio, os
os.environ["CELL_OBSERVATORY_EMIT"] = "true"
from cell_core import observatory
asyncio.run(observatory.emit_pulse_observed(
    cell_id="smoke-test", cell_kind="test",
    pulse_id="01SMOKE", pulse_timestamp_ms=int(__import__('time').time()*1000),
    phase="homeostatic", sensors=[{"name": "fake", "reachable": True, "status_code": 200}],
    pulse_result={"classifier_self": "green", "trend_window_min": 15, "trend_label": "stable"},
    homeostatic_state={"energy_pct": 90, "load_factor": 0.1},
))
print("emit OK")
PY

echo "2) Verify events_outbox row..."
psql "$EVENTBUS_DATABASE_URL" -c "SELECT outbox_id, channel FROM events_outbox WHERE channel='cell_pulse_observed' ORDER BY outbox_id DESC LIMIT 1;"

echo "3) Wait 5s for collector to consume..."
sleep 5

echo "4) Verify pulse in local SQLite..."
sqlite3 ~/.cell-observatory/observatory.db "SELECT outbox_id, cell_id FROM pulse_events WHERE cell_id='smoke-test' ORDER BY outbox_id DESC LIMIT 1;"

echo "5) Verify dashboard health endpoint..."
curl -fsS -H "X-Observatory-Key: $OBSERVATORY_API_KEY" http://127.0.0.1:17891/api/observatory/health | jq .

echo "✓ smoke test passed"
```

- [ ] **Step 2: chmod + commit**

```bash
chmod +x scripts/test_observatory_pulse.sh
git add scripts/test_observatory_pulse.sh
git commit -m "feat(observatory): M1 end-to-end smoke test

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 3: Run smoke test (manual gate before PR-5 enable)**

```bash
./scripts/test_observatory_pulse.sh
```

Expected output: 5 numbered steps each showing OK / data row. If FAIL, do NOT proceed to Task 5.2.

### Task 5.2: G2 rollback teardown script

- [ ] **Step 1: Create script**

`scripts/observatory_rollback.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "1) Disable env var on all cells with backup..."
scripts/patch_launchagents.sh --apply --add-observatory-emit --no-reload || true
# Manual: in each plist, change CELL_OBSERVATORY_EMIT to "false"
for plist in ~/Library/LaunchAgents/com.cell.organism.plist \
             ~/Library/LaunchAgents/com.balizero.seo-cell*.plist \
             ~/Library/LaunchAgents/com.balizero.evaluator*.plist; do
    [ -f "$plist" ] || continue
    chmod u+w "$plist"
    plutil -replace EnvironmentVariables.CELL_OBSERVATORY_EMIT -string "false" "$plist"
    chmod 0444 "$plist"
    launchctl kickstart -k "gui/$(id -u)/$(basename "$plist" .plist)"
done

echo "2) Stop collector + prune + selfcheck..."
for label in com.nuzantara.cell-observatory com.nuzantara.cell-observatory-prune com.nuzantara.cell-observatory-selfcheck; do
    launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
done

echo "3) Optional: wipe local SQLite..."
read -p "Wipe ~/.cell-observatory/observatory.db? [y/N] " ans
if [ "$ans" = "y" ]; then
    rm -f ~/.cell-observatory/observatory.db*
fi

echo "4) Outbox rows for cell_pulse_observed will remain in Postgres but are inert (no consumer)."
echo "   To purge: psql \"\$EVENTBUS_DATABASE_URL\" -c \"DELETE FROM events_outbox WHERE channel='cell_pulse_observed';\""

echo "✓ rollback complete"
```

- [ ] **Step 2: chmod + commit**

```bash
chmod +x scripts/observatory_rollback.sh
git add scripts/observatory_rollback.sh
git commit -m "feat(observatory): G2 rollback teardown script

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 5.3: Activate organism cell

- [ ] **Step 1: Verify smoke test passed (Task 5.1) — manual confirmation**

If Task 5.1 failed, do NOT continue. Investigate first.

- [ ] **Step 2: Apply patch_launchagents.sh to organism only**

```bash
scripts/patch_launchagents.sh --apply --add-observatory-emit --only com.cell.organism
```

Expected: `[ok] com.cell.organism.plist` + `.pre-observatory-emit` backup created.

- [ ] **Step 3: Reload organism**

```bash
launchctl kickstart -k "gui/$(id -u)/com.cell.organism"
```

- [ ] **Step 4: Tail collector log + verify events flowing**

```bash
tail -f ~/logs/cell-observatory/collector.err.log &
sleep 60
sqlite3 ~/.cell-observatory/observatory.db "SELECT cell_id, COUNT(*) FROM pulse_events WHERE pulse_timestamp > strftime('%s','now')*1000 - 60000 GROUP BY cell_id;"
```

Expected: `organism|N` where N matches the cell's pulse cadence.

- [ ] **Step 5: 48-hour observation window — DO NOT continue to PR-6 before this**

Manually monitor for 48 hours:
- Collector still running (`launchctl list | grep observatory`)
- No errors in `~/logs/cell-observatory/collector.err.log`
- Cost <$0.05 in 24h via `curl http://127.0.0.1:17891/api/observatory/cost`
- Cell organism pulse cadence unchanged (compare PRE/POST `pulse_logs`)

- [ ] **Step 6: Open PR-5 documenting activation**

```bash
git push -u origin feat/cell-observatory-pr5-organism-enable
gh pr create --title "feat(observatory): activate organism cell pilot (PR-5)" \
  --body "Activated CELL_OBSERVATORY_EMIT=true on com.cell.organism. 48h gate."
gh pr checks --watch
gh pr merge --squash --auto
```

---

## PR-6: Activate seo_cell + evaluator

**Depends on:** PR-5 merged + 48h observation window passed.

### Task 6.1: Activate remaining cells

- [ ] **Step 1: Verify 48h gate passed — manual confirmation from Task 5.3.5**

- [ ] **Step 2: Apply to seo_cell + evaluator**

```bash
scripts/patch_launchagents.sh --apply --add-observatory-emit \
  --only com.balizero.seo-cell,com.balizero.evaluator  # adapt to actual labels
```

- [ ] **Step 3: Reload**

```bash
for label in com.balizero.seo-cell com.balizero.evaluator; do
    launchctl kickstart -k "gui/$(id -u)/$label"
done
```

- [ ] **Step 4: 48h observation gate — same checks as Task 5.3.5**

- [ ] **Step 5: Commit + PR + merge**

---

## PR-7: Prune cron validation + retention test

### Task 7.1: Manual prune dry-run

- [ ] **Step 1: Insert mock 91-day-old row**

```bash
sqlite3 ~/.cell-observatory/observatory.db <<SQL
INSERT INTO pulse_events (outbox_id, cell_id, cell_kind, pulse_id, pulse_timestamp, phase, classifier_self, payload_json, received_at, received_lag_ms)
VALUES (-1, 'test-old', 'x', 'x', strftime('%s','now')*1000 - (91*86400*1000), 'x', 'green', '{}', strftime('%s','now')*1000, 0);
SQL
```

- [ ] **Step 2: Trigger prune manually**

```bash
~/Desktop/nuzantara/apps/cell-observatory-collector/.venv/bin/python -m cell_observatory.prune
```

Expected: log `pruned old events deleted_events=1`.

- [ ] **Step 3: Verify deletion**

```bash
sqlite3 ~/.cell-observatory/observatory.db "SELECT COUNT(*) FROM pulse_events WHERE outbox_id = -1;"
```

Expected: `0`.

- [ ] **Step 4: Verify cron LaunchAgent loaded**

```bash
launchctl list | grep cell-observatory-prune
```

Expected: line showing `com.nuzantara.cell-observatory-prune`.

- [ ] **Step 5: Document validation in PR-7**

```bash
git push -u origin feat/cell-observatory-pr7-prune-validation
gh pr create --title "chore(observatory): prune cron validation (PR-7)" \
  --body "Validated prune.py deletes >90d rows. LaunchAgent confirmed loaded."
gh pr merge --squash --auto
```

---

## Spec items deferred from this plan

After self-review, these spec items are NOT implemented in this plan but should be tracked:

| Item | Where | Why deferred |
|---|---|---|
| API `GET /api/observatory/pulse/{outbox_id}` (single event detail) | Spec §5.4 | Only used by dashboard `PulseDetailDrawer` which is also deferred. Add together. |
| API `POST /api/observatory/backfill` (reclassify trigger) | Spec §5.4 | Storage already supports A1 upsert; endpoint can be added when needed for ops. |
| Dashboard `PulseTimeline` SVG component | Spec §7 | High value but complex SVG rendering; the 4 implemented components already cover the core observation need. Build once dataset exists. |
| Dashboard `ConfidenceHistogram` | Spec §7 | Calibration analysis; defer until classifier has run for ≥7 days. |
| Dashboard `PulseDetailDrawer` | Spec §7 | Drill-down; needed only when investigating specific anomaly cases. |
| Dashboard `BackfillButton` | Spec §7 | Pairs with backfill endpoint above. |
| G4 `PulseWatchdog` (missed-pulse alert) | Spec §10 | Adds proactive alerting; fase 0 is read-only by design — the M2 selfcheck already monitors collector itself. PulseWatchdog catches the upstream cell silence, valuable but not blocking. |

These are noted in PR-3/PR-4 commit messages and should be created as separate follow-up tasks once observation data justifies them. **Not required for fase 0 success criteria**.

## Final verification (all PRs merged)

- [ ] **Smoke test passes:** `scripts/test_observatory_pulse.sh` exits 0.
- [ ] **3 cells emitting:** `sqlite3 ~/.cell-observatory/observatory.db "SELECT cell_id, COUNT(*) FROM pulse_events WHERE pulse_timestamp > strftime('%s','now')*1000 - 86400000 GROUP BY cell_id;"` shows organism + seo_cell + evaluator.
- [ ] **Cost <$0.30/24h:** `curl /api/observatory/cost` total_usd field.
- [ ] **No regression in cell behavior:** spot-check pulse cadence + decisions in cell logs PRE vs POST activation.
- [ ] **Daily rollup populates:** check next morning at 04:00+ that `pulse_daily_rollup` table has yesterday's row per cell.
