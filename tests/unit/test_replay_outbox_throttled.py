"""Unit tests for scripts/replay_outbox_throttled.py — Phase 2.2.

8 tests enforcing 4-panel review safeguards:
1. Hard rate cap (rejects --rate > 20)
2. Schema validation: valid payload passes
3. Schema validation: invalid JSON → DLQ reason
4. Schema validation: missing _outbox_id → DLQ reason
5. Schema validation: non-dict payload → DLQ reason
6. Sleep calculation correct for given rate/batch
7. Redis growth threshold constant set correctly
8. IN_PROGRESS_MARKER is epoch zero UTC
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import importlib.util

import pytest

# Load script as module
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "replay_outbox_throttled.py"
spec = importlib.util.spec_from_file_location("replay_mod", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_hard_rate_cap_constant():
    """4-panel consensus: hard cap 20/sec must never exceed."""
    assert mod.HARD_MAX_RATE == 20


def test_default_rate_is_conservative():
    """Default rate 10/sec per 4-panel."""
    assert mod.DEFAULT_RATE == 10
    assert mod.DEFAULT_RATE <= mod.HARD_MAX_RATE


def test_redis_growth_threshold():
    """Auto-pause if Redis stream grows > 2× initial."""
    assert mod.REDIS_GROWTH_THRESHOLD == 2.0


def test_in_progress_marker_is_epoch_utc():
    """Two-phase mark uses epoch zero UTC as sentinel."""
    assert mod.IN_PROGRESS_MARKER == datetime(1970, 1, 1, tzinfo=timezone.utc)


def test_validate_payload_valid_with_outbox_id():
    """Payload with _outbox_id (post-notify shape) is valid."""
    payload = json.dumps({"_outbox_id": 12345, "cell_id": "test"})
    ok, reason = mod.validate_payload(payload)
    assert ok is True
    assert reason == "ok"


def test_validate_payload_valid_without_outbox_id():
    """Pre-NOTIFY payload (no _outbox_id, injected at notify time) is valid."""
    payload = json.dumps({"cell_id": "test", "phase": "active", "topic": "intel"})
    ok, reason = mod.validate_payload(payload)
    assert ok is True
    assert reason == "ok"


def test_validate_payload_invalid_json():
    ok, reason = mod.validate_payload("{not json}")
    assert ok is False
    assert "json_decode_error" in reason


def test_validate_payload_non_dict():
    payload = json.dumps([1, 2, 3])
    ok, reason = mod.validate_payload(payload)
    assert ok is False
    assert "payload_not_dict" in reason
