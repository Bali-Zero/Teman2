"""2026-06-21 — DLQ corpse-sweep organism-heartbeat fallback (W81b extension).

Root cause this pins shut: the launchagent-state-bridge (a HOME-fork edited
2026-06-06) silently stopped refreshing ~/.agent/decisions/state/<job>.last.json
for a subset of jobs (zombie_hunter, post_publish_poller, post_publish_webhook).
Their .last.json froze at a stale "ok" (357h old), so sweep_recovered_corpses'
fail-closed freshness check parked them DLQ-TERMINAL forever even though the jobs
are healthy and still writing a FRESH "ok" to their organism heartbeat sidecar
(~/.organism/last_seen/<node>.<job>.json).

Fix: consult the organism sidecar as an independent SECOND freshness source. This
never weakens fail-closed — a stale/absent agent-state file AND a stale/absent/
non-ok organism sidecar still keeps the entry parked for audit.

The module name is loaded via importlib with HOME pointed at a tmp dir so the
module-level logging.FileHandler (~/logs/dlq_autopilot.log) does not touch the
real home, mirroring test_sentinel_w70_resurrect_enrich.py.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_FRESH = time.time() - 60          # 1 min old → within the 6h window
_STALE = time.time() - 1_000_000   # ~11.5 days old → outside any sane window


@pytest.fixture()
def dlq(tmp_path, monkeypatch):
    """Load dlq_autopilot.py fresh with HOME redirected to a tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    spec = importlib.util.spec_from_file_location(
        "dlq_autopilot_organism", os.path.join(_SCRIPTS_DIR, "dlq_autopilot.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, tmp_path


def _write_agent_state(home: Path, job: str, status: str, ts: float):
    d = home / ".agent" / "decisions" / "state"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{job}.last.json").write_text(json.dumps({"job": job, "status": status, "ts": ts}))


def _write_organism(home: Path, job: str, status: str, ts: float, node: str = "pro"):
    d = home / ".organism" / "last_seen"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{node}.{job}.json").write_text(
        json.dumps({"organ_id": f"{node}.{job}", "status": status, "ts": ts})
    )


def _entry(job: str) -> dict:
    return {"job": job, "status": "TERMINAL", "autopilot_attempts": 3}


class TestCorpseSweepOrganismFallback:
    def test_stale_agent_state_but_fresh_organism_drains(self, dlq):
        """The exact 2026-06-21 zombie_hunter case: stale .last.json, fresh organism ok."""
        mod, home = dlq
        _write_agent_state(home, "zombie_hunter", "ok", _STALE)
        _write_organism(home, "zombie_hunter", "ok", _FRESH)
        kept, cleared = mod.sweep_recovered_corpses([_entry("zombie_hunter")])
        assert cleared == ["zombie_hunter"]
        assert kept == []

    def test_no_agent_state_but_fresh_organism_drains(self, dlq):
        """Jobs with NO .last.json at all are still drained if organism proves recovery."""
        mod, home = dlq
        _write_organism(home, "some_job", "ok", _FRESH)
        kept, cleared = mod.sweep_recovered_corpses([_entry("some_job")])
        assert cleared == ["some_job"]
        assert kept == []

    def test_stale_agent_state_and_no_organism_kept(self, dlq):
        """Fail-closed: stale .last.json + no organism sidecar → entry stays parked."""
        mod, home = dlq
        _write_agent_state(home, "post_publish_poller", "ok", _STALE)
        kept, cleared = mod.sweep_recovered_corpses([_entry("post_publish_poller")])
        assert cleared == []
        assert len(kept) == 1

    def test_stale_organism_kept(self, dlq):
        """Fail-closed: a stale organism "ok" is NOT proof of recovery."""
        mod, home = dlq
        _write_agent_state(home, "j", "ok", _STALE)
        _write_organism(home, "j", "ok", _STALE)
        kept, cleared = mod.sweep_recovered_corpses([_entry("j")])
        assert cleared == []
        assert len(kept) == 1

    def test_organism_fail_status_kept(self, dlq):
        """Fail-closed: a fresh organism heartbeat with status!='ok' is not recovery."""
        mod, home = dlq
        _write_organism(home, "j", "fail", _FRESH)
        kept, cleared = mod.sweep_recovered_corpses([_entry("j")])
        assert cleared == []
        assert len(kept) == 1

    def test_fresh_agent_state_still_drains(self, dlq):
        """Regression: the original primary path (fresh agent-state ok) still drains."""
        mod, home = dlq
        _write_agent_state(home, "drive_intake_drain", "ok", _FRESH)
        kept, cleared = mod.sweep_recovered_corpses([_entry("drive_intake_drain")])
        assert cleared == ["drive_intake_drain"]
        assert kept == []
