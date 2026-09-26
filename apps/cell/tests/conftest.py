"""Keep every Cell test out of the host's live organism.

``cell.utils.organ_emitter.emit_organ_last_seen`` writes to
``~/.organism/last_seen/`` unless a caller passes ``out_dir``. Sensors such as
``HealthSensor.read()`` call it on every reading, so a test that feeds them a
mocked 503 used to leave ``backend.api.json`` = degraded (503, 500 ms) in the
REAL organism of whatever machine ran the suite. On M5 nothing rewrites that
organ (its writer is Cell on Pro), so the fixture sat there for days and the
stale detector reported ``backend.api`` degraded while Fly answered 200.
"""
from __future__ import annotations

import pytest

import cell.utils.organ_emitter as organ_emitter


@pytest.fixture(autouse=True)
def _isolated_last_seen_dir(tmp_path, monkeypatch):
    target = tmp_path / "organism_last_seen"
    monkeypatch.setattr(organ_emitter, "DEFAULT_LAST_SEEN_DIR", target)
    return target
