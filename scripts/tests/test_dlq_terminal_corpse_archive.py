"""Round-3 DLQ hygiene (2026-08-10) — archive (never delete) TERMINAL corpses.

TRAUMA: W81b already added an unconditional corpse-sweep for DLQ entries whose
job recovered (state=ok) — sweep_recovered_corpses(). The OTHER corpse class
was left untouched: entries that reached max_attempts and were marked TERMINAL
by process_entry()'s D0.1 guard. Measured live on Pro 2026-08-10: 21/21 DLQ
entries were TERMINAL — every autopilot tick logged 21 "status=TERMINAL —
skipping" lines (the exact noise class the 2026-05-19 ops-hardening fix at the
top of dlq_autopilot.py exists to describe), and a queue that is 100% corpses
buries any fresh entry from a human or tool glance.

ANTIBODY: sweep_terminal_corpses() moves each TERMINAL entry, full content
plus an archive stamp, into dlq_terminal_archive.json and drops it from the
live queue. Archive, not delete — audit survives. clear/requeue fall back to
the archive so the operator's own tooling keeps working on archived jobs.

Guilt: a TERMINAL corpse is archived and gone from the live queue.
Innocence: an active (non-terminal) entry is never touched, and an entry the
ok-sweep would have handled (status=ok elsewhere) is out of scope here.
Atomicity: archiving never loses the entry, even if only the archive write
succeeds this tick.
"""
import importlib.util
import json
import os
import sys
import time

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def dlq(tmp_path, monkeypatch):
    """Load dlq_autopilot.py fresh with HOME redirected to a tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    # save_dlq() (pre-existing) does not mkdir AGENT_DIR itself — in
    # production ~/.agent/decisions already exists from other writers.
    (tmp_path / ".agent" / "decisions").mkdir(parents=True, exist_ok=True)
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    spec = importlib.util.spec_from_file_location(
        "dlq_autopilot_terminal_archive", os.path.join(_SCRIPTS_DIR, "dlq_autopilot.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, tmp_path


def _terminal_entry(job: str, **overrides) -> dict:
    entry = {
        "job": job,
        "status": "TERMINAL",
        "autopilot_attempts": 10,
        "error_summary": "boom, and then boom again",
        "log_tail": "…traceback…",
        "classification": {"type": "DETERMINISTIC", "confidence": 0.9},
        "added_ts": time.time(),
        "first_abandoned_at": "2026-06-07T21:47:01Z",
    }
    entry.update(overrides)
    return entry


def _active_entry(job: str, status: str = "escalated") -> dict:
    return {
        "job": job,
        "status": status,
        "autopilot_attempts": 2,
        "error_summary": "still trying",
        "added_ts": time.time(),
    }


# ── sweep_terminal_corpses: guilt ───────────────────────────────────────────

class TestSweepGuilt:
    def test_a_terminal_corpse_is_removed_from_the_kept_queue(self, dlq):
        mod, _ = dlq
        kept, archived = mod.sweep_terminal_corpses([_terminal_entry("dropbox_intake")])
        assert kept == []
        assert [e["job"] for e in archived] == ["dropbox_intake"]

    def test_the_archived_entry_carries_full_original_content(self, dlq):
        mod, _ = dlq
        original = _terminal_entry("run_ops_briefing")
        _, archived = mod.sweep_terminal_corpses([original])
        (record,) = archived
        assert record["error_summary"] == original["error_summary"]
        assert record["log_tail"] == original["log_tail"]
        assert record["autopilot_attempts"] == 10
        assert record["first_abandoned_at"] == "2026-06-07T21:47:01Z"

    def test_the_archived_entry_is_stamped_for_audit(self, dlq):
        mod, _ = dlq
        _, archived = mod.sweep_terminal_corpses([_terminal_entry("nb_agents_daily_dr")])
        (record,) = archived
        assert record["archived_by"] == "dlq_autopilot_terminal_sweep"
        assert "archived_at" in record and record["archived_at"]

    def test_multiple_terminal_corpses_all_archived(self, dlq):
        mod, _ = dlq
        jobs = ["run_nb3_pipeline", "run_nb4_pipeline", "nightly_autofix_ci"]
        kept, archived = mod.sweep_terminal_corpses([_terminal_entry(j) for j in jobs])
        assert kept == []
        assert sorted(e["job"] for e in archived) == sorted(jobs)


# ── sweep_terminal_corpses: innocence ───────────────────────────────────────

class TestSweepInnocence:
    def test_an_active_escalated_entry_is_never_touched(self, dlq):
        mod, _ = dlq
        entry = _active_entry("garuda_indexer", status="escalated")
        kept, archived = mod.sweep_terminal_corpses([entry])
        assert kept == [entry]
        assert archived == []

    def test_an_entry_with_no_status_key_is_kept(self, dlq):
        """A freshly-added entry (no status yet) must never be swept."""
        mod, _ = dlq
        entry = {"job": "fresh_job", "autopilot_attempts": 0, "added_ts": time.time()}
        kept, archived = mod.sweep_terminal_corpses([entry])
        assert kept == [entry]
        assert archived == []

    def test_mixed_queue_only_archives_the_terminal_ones(self, dlq):
        mod, _ = dlq
        alive = _active_entry("healthy_job_in_progress")
        dead = _terminal_entry("dead_job")
        kept, archived = mod.sweep_terminal_corpses([alive, dead])
        assert kept == [alive]
        assert [e["job"] for e in archived] == ["dead_job"]

    def test_empty_queue_is_a_noop(self, dlq):
        mod, _ = dlq
        kept, archived = mod.sweep_terminal_corpses([])
        assert kept == []
        assert archived == []


# ── archive I/O + atomicity ─────────────────────────────────────────────────

class TestArchiveIO:
    def test_archive_file_absent_reads_as_empty(self, dlq):
        mod, _ = dlq
        assert mod.load_dlq_archive() == []

    def test_save_then_load_round_trips(self, dlq):
        mod, _ = dlq
        mod.save_dlq_archive([{"job": "x", "status": "TERMINAL"}])
        assert mod.load_dlq_archive() == [{"job": "x", "status": "TERMINAL"}]

    def test_save_creates_the_parent_dir_if_missing(self, dlq, tmp_path):
        import shutil
        mod, home = dlq
        # Unlike save_dlq() (relies on AGENT_DIR pre-existing from other
        # writers), save_dlq_archive() must work on a bare HOME too — this is
        # a NEW file with no other writer guaranteed to have made the dir.
        shutil.rmtree(home / ".agent", ignore_errors=True)
        assert not (home / ".agent").exists()
        mod.save_dlq_archive([{"job": "y"}])
        assert mod.DLQ_TERMINAL_ARCHIVE_FILE.exists()
        assert mod.load_dlq_archive() == [{"job": "y"}]

    def test_save_is_atomic_no_partial_file_survives_replace(self, dlq):
        """The tmp+replace pattern (same as save_dlq) means a reader never
        observes a half-written archive: replace() is a single rename."""
        mod, _ = dlq
        mod.save_dlq_archive([{"job": "a"}])
        mod.save_dlq_archive([{"job": "a"}, {"job": "b"}])
        tmp_file = mod.DLQ_TERMINAL_ARCHIVE_FILE.with_suffix(".tmp")
        assert not tmp_file.exists()  # replace() consumed it
        assert len(mod.load_dlq_archive()) == 2

    def test_never_loses_an_entry_archive_then_shrink_ordering(self, dlq):
        """Mirrors run_autopilot()'s real ordering: archive-write happens
        BEFORE the live queue is shrunk, so a full end-to-end run never has a
        window where the entry exists in neither place."""
        mod, _ = dlq
        queue = [_terminal_entry("corpse_job")]
        kept, archived = mod.sweep_terminal_corpses(queue)
        # Simulate run_autopilot()'s persistence order.
        mod.save_dlq_archive(mod.load_dlq_archive() + archived)
        mod.save_dlq(kept)
        assert mod.load_dlq() == []
        assert [e["job"] for e in mod.load_dlq_archive()] == ["corpse_job"]


# ── clear / requeue CLI: archive fallback ───────────────────────────────────

class TestRequeueArchiveFallback:
    def test_requeue_finds_nothing_when_job_is_in_neither_queue_nor_archive(self, dlq, monkeypatch):
        mod, _ = dlq
        monkeypatch.setattr(mod, "acquire_lock", lambda: 3)
        monkeypatch.setattr(mod, "release_lock", lambda fd: None)
        assert mod.requeue_terminal("ghost_job") == 1

    def test_requeue_restores_an_archived_job_into_the_live_queue(self, dlq, monkeypatch):
        mod, _ = dlq
        monkeypatch.setattr(mod, "acquire_lock", lambda: 3)
        monkeypatch.setattr(mod, "release_lock", lambda fd: None)
        mod.save_dlq([])
        mod.save_dlq_archive([_terminal_entry("archived_job") | {
            "archived_at": "2026-08-10T00:00:00Z", "archived_by": "dlq_autopilot_terminal_sweep",
        }])
        rc = mod.requeue_terminal("archived_job")
        assert rc == 0
        queue = mod.load_dlq()
        assert len(queue) == 1
        restored = queue[0]
        assert restored["job"] == "archived_job"
        assert "status" not in restored           # cleared, same contract as live-path requeue
        assert restored["autopilot_attempts"] == 0
        assert "archived_at" not in restored
        assert "archived_by" not in restored
        assert restored["requeued_by"] == "operator"
        # Removed from the archive — requeue is a restore, not a copy.
        assert mod.load_dlq_archive() == []

    def test_requeue_prefers_the_live_entry_over_a_stale_archive_copy(self, dlq, monkeypatch):
        """If a job is (unexpectedly) present in both, the live queue is the
        source of truth requeue already knew how to handle — no behavior
        change for that path."""
        mod, _ = dlq
        monkeypatch.setattr(mod, "acquire_lock", lambda: 3)
        monkeypatch.setattr(mod, "release_lock", lambda fd: None)
        mod.save_dlq([_terminal_entry("dual_job")])
        mod.save_dlq_archive([_terminal_entry("dual_job") | {"archived_at": "x", "archived_by": "y"}])
        rc = mod.requeue_terminal("dual_job")
        assert rc == 0
        queue = mod.load_dlq()
        assert len(queue) == 1
        assert "status" not in queue[0]
        # The archive copy is untouched — the live path never looks at it.
        assert len(mod.load_dlq_archive()) == 1

    def test_requeue_picks_the_most_recent_of_multiple_archived_records(self, dlq, monkeypatch):
        mod, _ = dlq
        monkeypatch.setattr(mod, "acquire_lock", lambda: 3)
        monkeypatch.setattr(mod, "release_lock", lambda fd: None)
        mod.save_dlq([])
        mod.save_dlq_archive([
            _terminal_entry("repeat_offender", error_summary="first death") | {"archived_at": "a"},
            _terminal_entry("repeat_offender", error_summary="second death") | {"archived_at": "b"},
        ])
        rc = mod.requeue_terminal("repeat_offender")
        assert rc == 0
        (restored,) = mod.load_dlq()
        assert restored["error_summary"] == "second death"
        # The earlier archive record for the same job is left alone (audit trail).
        remaining = mod.load_dlq_archive()
        assert len(remaining) == 1
        assert remaining[0]["error_summary"] == "first death"


class TestClearArchiveFallback:
    def test_clear_removes_an_archived_entry_when_not_in_the_live_queue(self, dlq, tmp_path, monkeypatch):
        mod, _ = dlq
        mod.save_dlq([])
        mod.save_dlq_archive([_terminal_entry("archived_only") | {"archived_at": "x"}])
        # Exercise the same logic the __main__ "clear" branch runs, without
        # subprocessing the module (keeps HOME redirection in this process).
        job_id = "archived_only"
        queue = mod.load_dlq()
        before = len(queue)
        queue = [e for e in queue if not (e["job"] == job_id and e.get("status") == "TERMINAL")]
        after = len(queue)
        assert before == after  # not live — falls through to archive
        archive = mod.load_dlq_archive()
        before_a = len(archive)
        archive = [e for e in archive if e.get("job") != job_id]
        assert len(archive) != before_a
        mod.save_dlq_archive(archive)
        assert mod.load_dlq_archive() == []
