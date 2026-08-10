"""Round-3 DLQ hygiene (2026-08-10) — nuzantara-sentinel.py side of the class-audit.

dlq_autopilot.py's sweep_terminal_corpses() (scripts/dlq_autopilot.py) archives
TERMINAL DLQ entries out of ~/.agent/decisions/dlq.json into
dlq_terminal_archive.json. Two readers here depend on TERMINAL job names
staying visible after that move:

  - the W53 escalation-suppression gate (process_job's dlq_terminal_set param)
  - the W70 blind-heal-loop counter / dlq_phase_distribution["TERMINAL"]

Without unioning the archive in, both would silently go blind the moment a
corpse is archived: W53 would stop suppressing re-escalation for a job
dlq_autopilot already gave up on (re-arming the W61 storm-loop via
repairer.add_to_dlq's "TERMINAL stays TERMINAL" preserved-status logic, which
only fires when it finds an existing LIVE entry to preserve status from), and
the W70 alert would go permanently dark even though nothing was resolved.

Guilt: an archived-only job's name still comes back from the union helper.
Innocence: a job never seen in either file is absent; a read failure on one
file doesn't erase names already found in the other (fail-open per source,
same posture the original inline W53 code had for dlq.json alone).
"""
import importlib.util
import json
import os
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def sentinel(tmp_path, monkeypatch):
    """Load nuzantara-sentinel.py fresh with HOME redirected to a tmp dir so the
    module-level logging.FileHandler does not touch the real ~/logs."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agent" / "decisions").mkdir(parents=True, exist_ok=True)
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    spec = importlib.util.spec_from_file_location(
        "nuzantara_sentinel_terminal_archive", os.path.join(_SCRIPTS_DIR, "nuzantara-sentinel.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, tmp_path


def _write_dlq(home, queue):
    path = home / ".agent" / "decisions" / "dlq.json"
    path.write_text(json.dumps({"queue": queue}))


def _write_archive(home, archive):
    path = home / ".agent" / "decisions" / "dlq_terminal_archive.json"
    path.write_text(json.dumps({"archive": archive}))


# ── _load_dlq_terminal_job_names: guilt ─────────────────────────────────────

class TestUnionGuilt:
    def test_an_archived_only_job_is_still_suppressed(self, sentinel):
        """The exact regression this fixes: job was TERMINAL, dlq_autopilot
        archived it, dlq.json no longer mentions it at all."""
        mod, home = sentinel
        _write_dlq(home, [])  # archived — no longer in the live queue
        _write_archive(home, [{"job": "run_ops_briefing", "status": "TERMINAL"}])
        names = mod._load_dlq_terminal_job_names()
        assert "run_ops_briefing" in names

    def test_a_live_terminal_job_is_still_suppressed_unchanged(self, sentinel):
        """Regression guard: the original live-only path must still work."""
        mod, home = sentinel
        _write_dlq(home, [{"job": "dropbox_intake", "status": "TERMINAL"}])
        _write_archive(home, [])
        names = mod._load_dlq_terminal_job_names()
        assert "dropbox_intake" in names

    def test_names_from_both_files_are_unioned(self, sentinel):
        mod, home = sentinel
        _write_dlq(home, [{"job": "live_terminal", "status": "TERMINAL"}])
        _write_archive(home, [{"job": "archived_terminal"}])
        names = mod._load_dlq_terminal_job_names()
        assert names == {"live_terminal", "archived_terminal"}

    def test_archived_terminal_count_includes_archive_entries(self, sentinel):
        mod, home = sentinel
        _write_archive(home, [{"job": "a"}, {"job": "b"}, {"job": "c"}])
        assert mod._dlq_archived_terminal_count() == 3


# ── _load_dlq_terminal_job_names: innocence ─────────────────────────────────

class TestUnionInnocence:
    def test_a_job_seen_nowhere_is_absent(self, sentinel):
        mod, home = sentinel
        _write_dlq(home, [{"job": "healthy_job", "status": "ok"}])
        _write_archive(home, [{"job": "other_archived"}])
        names = mod._load_dlq_terminal_job_names()
        assert "healthy_job" not in names

    def test_non_terminal_live_entries_are_excluded(self, sentinel):
        """Only status==TERMINAL counts in the live queue — an 'escalated' or
        'needs_aider' entry must not be suppressed."""
        mod, home = sentinel
        _write_dlq(home, [{"job": "still_trying", "status": "escalated"}])
        _write_archive(home, [])
        names = mod._load_dlq_terminal_job_names()
        assert "still_trying" not in names

    def test_missing_archive_file_degrades_to_live_only_not_an_error(self, sentinel):
        mod, home = sentinel
        _write_dlq(home, [{"job": "solo_live", "status": "TERMINAL"}])
        # No dlq_terminal_archive.json written at all — pre-round-3 state.
        names = mod._load_dlq_terminal_job_names()
        assert names == {"solo_live"}

    def test_missing_dlq_file_does_not_erase_archive_names(self, sentinel):
        """Fail-open per SOURCE: a dlq.json read failure must not also wipe
        out names already found in the archive."""
        mod, home = sentinel
        # No dlq.json written — simulates the read failing.
        _write_archive(home, [{"job": "archived_survivor"}])
        names = mod._load_dlq_terminal_job_names()
        assert names == {"archived_survivor"}

    def test_corrupt_archive_file_degrades_gracefully(self, sentinel):
        mod, home = sentinel
        _write_dlq(home, [{"job": "live_one", "status": "TERMINAL"}])
        (home / ".agent" / "decisions" / "dlq_terminal_archive.json").write_text("{not json")
        names = mod._load_dlq_terminal_job_names()
        assert names == {"live_one"}  # live half survives the corrupt archive

    def test_archived_terminal_count_is_zero_not_negative_when_absent(self, sentinel):
        mod, home = sentinel
        # No archive file at all.
        assert mod._dlq_archived_terminal_count() == 0

    def test_archived_terminal_count_is_zero_on_corrupt_file(self, sentinel):
        mod, home = sentinel
        (home / ".agent" / "decisions" / "dlq_terminal_archive.json").write_text("[[[")
        assert mod._dlq_archived_terminal_count() == 0


# ── process_job wiring: the union actually reaches the W53 gate ────────────

class TestUnionReachesW53Gate:
    def test_an_archived_terminal_job_suppresses_process_job_escalation(self, sentinel, monkeypatch):
        """End-to-end: build the set the way run_sentinel() now does, feed it
        into process_job exactly like the real caller — an archived-only
        TERMINAL job must still hit the W53 suppression branch, not
        re-escalate."""
        mod, home = sentinel
        monkeypatch.setattr(mod, "get_state", lambda job_id: "CLOSED")
        monkeypatch.setattr(mod, "record_failure", lambda job_id: None)
        _write_dlq(home, [])
        _write_archive(home, [{"job": "chronically_dead_job"}])
        terminal_set = mod._load_dlq_terminal_job_names()
        state = {"status": "failed", "ts": 0, "last_error": "still broken"}
        result = mod.process_job(
            "chronically_dead_job", state, {}, dlq_terminal_set=terminal_set,
        )
        assert result["action"] == "skipped_dlq_terminal"
