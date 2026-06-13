"""W70 (2026-06-14) — Mythos P1 immune-system fixes for nuzantara-sentinel.py.

Covers the two structural cures shipped on top of #1344's blind-heal-loop detector:

1. ``_enrich_last_error_from_cron_log`` — the cron wrappers write a bare
   ``last_error="exit N"`` to the state file (zero diagnostic signal), so the
   classifier returns UNKNOWN and the heal-loop acts blind. The enricher appends
   the tail of the job's REAL cron log. The 2026-06-13 orphan attempt had two
   bugs this test pins shut: (a) a regex that required "exit N after M attempts"
   (never emitted by the wrapper) so it never fired on the bare "exit 1"; (b) it
   read only ~/logs/cron (empty for these jobs) instead of ~/logs/cron-tmp.

2. ``process_job`` auto-resurrection — a job parked DLQ-TERMINAL that has since
   recovered (state=ok AND fresh) must have its corpse cleared, else dlq_terminal
   only ever grows (pre-fix: 19 of 33 TERMINAL entries were already-healthy).
   A stale (ok-but-old) job must NOT resurrect (it hasn't proven recovery).

The sentinel module name is hyphenated and runs logging.basicConfig at import,
so it is loaded via importlib with HOME pointed at a tmp dir.
"""
import importlib.util
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)


@pytest.fixture()
def sentinel(tmp_path, monkeypatch):
    """Load nuzantara-sentinel.py fresh with HOME redirected to a tmp dir so the
    module-level logging.FileHandler does not touch the real ~/logs."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    spec = importlib.util.spec_from_file_location(
        "nuzantara_sentinel_w70", os.path.join(_SCRIPTS_DIR, "nuzantara-sentinel.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Neutralise circuit-breaker / repairer side effects for unit isolation.
    monkeypatch.setattr(mod, "get_state", lambda job_id: "CLOSED")
    monkeypatch.setattr(mod, "record_success", lambda job_id: None)
    monkeypatch.setattr(mod, "record_failure", lambda job_id: None)
    return mod, tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# _enrich_last_error_from_cron_log
# ─────────────────────────────────────────────────────────────────────────────

class TestEnrichLastError:
    def test_bare_exit_1_is_enriched_from_cron_tmp(self, sentinel):
        mod, home = sentinel
        log = home / "logs" / "cron-tmp" / "garuda-indexer.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("starting\nasyncpg.InvalidPasswordError: password auth failed\n")
        out = mod._enrich_last_error_from_cron_log("garuda_indexer", "exit 1")
        assert "InvalidPasswordError" in out
        assert out.startswith("exit 1")  # original summary preserved as prefix

    def test_underscore_jobname_maps_to_dashed_log(self, sentinel):
        mod, home = sentinel
        log = home / "logs" / "cron-tmp" / "knowledge-graph-builder.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("NUZANTARA_API_KEY non impostata\n")
        out = mod._enrich_last_error_from_cron_log("knowledge_graph_builder", "exit 1")
        assert "NUZANTARA_API_KEY" in out

    def test_empty_last_error_still_enriches(self, sentinel):
        mod, home = sentinel
        log = home / "logs" / "dropbox-intake.log"
        log.write_text("rclone: drive upload limit reached\n")
        out = mod._enrich_last_error_from_cron_log("dropbox_intake", "")
        assert "drive upload limit" in out

    def test_real_error_is_left_untouched(self, sentinel):
        mod, _ = sentinel
        real = "Postgres relation kg_proposals does not exist"
        assert mod._enrich_last_error_from_cron_log("curiosity_loop", real) == real

    def test_bare_exit_with_no_log_returns_unchanged(self, sentinel):
        mod, _ = sentinel
        assert mod._enrich_last_error_from_cron_log("no_such_job_xyz", "exit 1") == "exit 1"

    def test_large_log_is_tail_bounded_not_fully_loaded(self, sentinel):
        # Adversary-found OOM: readlines() on a multi-MB log would bloat memory.
        # The enricher must read only the tail and still surface the real error.
        mod, home = sentinel
        log = home / "logs" / "cron-tmp" / "big-job.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "w") as fh:
            fh.write("noise line\n" * 400_000)          # ~4.4 MB of noise
            fh.write("FATAL: real tail error here\n")
        out = mod._enrich_last_error_from_cron_log("big_job", "exit 1")
        assert "FATAL: real tail error here" in out
        assert len(out) < 20_000  # bounded output, not the whole 4.4 MB file

    def test_exit_127_matches_bare_pattern(self, sentinel):
        mod, home = sentinel
        log = home / "logs" / "cron-tmp" / "zantara-vision-warmup.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("bash: warmup-vision.sh: No such file or directory\n")
        out = mod._enrich_last_error_from_cron_log("zantara_vision_warmup", "exit 127")
        assert "No such file" in out


# ─────────────────────────────────────────────────────────────────────────────
# process_job — auto-resurrection
# ─────────────────────────────────────────────────────────────────────────────

class TestResurrection:
    def test_fresh_ok_job_in_terminal_set_is_resurrected(self, sentinel, monkeypatch):
        mod, _ = sentinel
        clear = MagicMock()
        monkeypatch.setattr(mod, "clear_dlq_entry", clear)
        state = {"status": "ok", "ts": time.time(), "last_error": ""}
        registry = {"job1": {"staleness_threshold_s": 999999}}
        result = mod.process_job("job1", state, registry, dlq_terminal_set={"job1"})
        assert result["action"] == "resurrected_terminal"
        assert result["success"] is True
        clear.assert_called_once_with("job1")

    def test_stale_ok_job_in_terminal_set_is_NOT_resurrected(self, sentinel, monkeypatch):
        mod, _ = sentinel
        clear = MagicMock()
        monkeypatch.setattr(mod, "clear_dlq_entry", clear)
        # ok but ts very old → staleness downgrades to "stale" → W53 suppression,
        # not resurrection (a stale job hasn't proven it recovered).
        state = {"status": "ok", "ts": time.time() - 10_000_000, "last_error": ""}
        registry = {"job1": {"staleness_threshold_s": 93600}}
        result = mod.process_job("job1", state, registry, dlq_terminal_set={"job1"})
        assert result["action"] == "skipped_dlq_terminal"
        clear.assert_not_called()

    def test_healthy_job_not_in_terminal_set_is_not_cleared(self, sentinel, monkeypatch):
        mod, _ = sentinel
        clear = MagicMock()
        monkeypatch.setattr(mod, "clear_dlq_entry", clear)
        state = {"status": "ok", "ts": time.time(), "last_error": ""}
        registry = {"job1": {"staleness_threshold_s": 999999}}
        result = mod.process_job("job1", state, registry, dlq_terminal_set=set())
        assert result["action"] == "healthy"
        clear.assert_not_called()

    def test_resurrection_clear_failure_falls_back_to_healthy(self, sentinel, monkeypatch):
        mod, _ = sentinel
        monkeypatch.setattr(mod, "clear_dlq_entry", MagicMock(side_effect=OSError("locked")))
        state = {"status": "ok", "ts": time.time(), "last_error": ""}
        registry = {"job1": {"staleness_threshold_s": 999999}}
        result = mod.process_job("job1", state, registry, dlq_terminal_set={"job1"})
        # A clear failure must never break the cycle — degrade to healthy.
        assert result["action"] == "healthy"
        assert result["success"] is True
