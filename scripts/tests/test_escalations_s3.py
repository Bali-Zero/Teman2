"""S3 — tests for escalation-debt cleanup.

Covers the three artifacts shipped by the S3 escalation-debt session:
  1. escalations_rotate.py    — canonical-JSONL rotation (lossless, idempotent,
                                threshold, O_APPEND-vs-truncate race safety)
  2. dlq_autopilot fix        — escalate_to_claude_code cooldown gate (+ TERMINAL
                                bypass + suppressed-count bump)
  3. escalations_suppressed_digest.py — W55 weekly digest build + reset

Run:
    cd ~/nuzantara
    source apps/backend-rag/.venv/bin/activate
    python -m pytest scripts/tests/test_escalations_s3.py -v
"""
import gzip
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import escalations_rotate as R  # noqa: E402
import escalations_suppressed_digest as D  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
def _write_jsonl(path: Path, n: int, job: str = "nlm_nb1_daily_refresh") -> None:
    base = time.time() - 7 * 86400
    with path.open("w") as f:
        for i in range(n):
            f.write(json.dumps({
                "job": job, "type": "dlq_autopilot_escalation",
                "error_summary": "", "ts": base + i, "status": "pending",
                "_writer": "pro",
            }) + "\n")


@pytest.fixture()
def jsonl(tmp_path: Path) -> Path:
    p = tmp_path / "escalations_pro.jsonl"
    _write_jsonl(p, 6001)
    return p


# ─────────────────────────────────────────────────────────────────────────────
# 1. Rotation
# ─────────────────────────────────────────────────────────────────────────────
class TestRotation:
    def test_over_threshold_rotates_lossless(self, jsonl: Path, tmp_path: Path):
        arch = tmp_path / "arch"
        res = R.rotate(jsonl, archive_dir=arch, max_lines=5000)
        assert res["rotated"] is True
        assert res["lines"] == 6001
        # canonical truncated
        assert jsonl.stat().st_size == 0
        # archive holds every original line, all valid JSON
        gz_files = list(arch.glob("*.jsonl.gz"))
        assert len(gz_files) == 1
        with gzip.open(gz_files[0], "rt") as gz:
            archived = [json.loads(l) for l in gz if l.strip()]
        assert len(archived) == 6001

    def test_under_threshold_noop(self, tmp_path: Path):
        p = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(p, 10)
        res = R.rotate(p, archive_dir=tmp_path / "arch", max_lines=5000, max_bytes=10**9)
        assert res["rotated"] is False
        assert p.stat().st_size > 0  # untouched

    def test_empty_file_noop(self, tmp_path: Path):
        p = tmp_path / "escalations_pro.jsonl"
        p.write_text("")
        res = R.rotate(p, archive_dir=tmp_path / "arch", force=True)
        assert res["rotated"] is False
        assert "empty" in res["reason"]

    def test_missing_file_noop(self, tmp_path: Path):
        res = R.rotate(tmp_path / "nope.jsonl", archive_dir=tmp_path / "arch", force=True)
        assert res["rotated"] is False
        assert "missing" in res["reason"]

    def test_idempotent_second_run(self, jsonl: Path, tmp_path: Path):
        arch = tmp_path / "arch"
        R.rotate(jsonl, archive_dir=arch, max_lines=5000)
        res2 = R.rotate(jsonl, archive_dir=arch, max_lines=5000)
        assert res2["rotated"] is False  # already empty

    def test_byte_threshold_trips(self, tmp_path: Path):
        p = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(p, 100)  # few lines, but force a tiny byte threshold
        res = R.rotate(p, archive_dir=tmp_path / "arch", max_lines=10**9, max_bytes=100)
        assert res["rotated"] is True

    def test_no_double_archive_same_day(self, tmp_path: Path):
        arch = tmp_path / "arch"
        p1 = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(p1, 6001)
        R.rotate(p1, archive_dir=arch, force=True)
        _write_jsonl(p1, 6001)
        R.rotate(p1, archive_dir=arch, force=True)
        # second run must NOT overwrite the first archive
        assert len(list(arch.glob("*.jsonl.gz"))) == 2

    def test_concurrent_append_during_truncate_no_corruption(self, tmp_path: Path):
        """The load-bearing safety claim: single-writer O_APPEND + truncate = 0
        corruption. We use 4 hammering writers (worse than the 1 real writer)."""
        p = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(p, 3000)
        arch = tmp_path / "arch"

        stop = threading.Event()

        def writer():
            i = 0
            while not stop.is_set():
                line = (json.dumps({"append": i, "ts": time.time()}) + "\n").encode()
                fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
                try:
                    os.write(fd, line)
                finally:
                    os.close(fd)
                i += 1

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for t in threads:
            t.start()
        time.sleep(0.2)
        R.rotate(p, archive_dir=arch, force=True)
        time.sleep(0.2)
        stop.set()
        for t in threads:
            t.join()

        # No torn lines anywhere, and no lines silently dropped by the rotate.
        gz = list(arch.glob("*.jsonl.gz"))[0]
        archived_lines = 0
        with gzip.open(gz, "rt") as fh:
            for l in fh:
                if l.strip():
                    json.loads(l)  # raises on corruption
                    archived_lines += 1
        live_lines = 0
        with p.open() as fh:
            for l in fh:
                if l.strip():
                    json.loads(l)  # raises on corruption
                    live_lines += 1
        # every one of the 3000 pre-rotation lines must have landed somewhere
        # (archive or, if a hammering writer's O_APPEND raced the truncate,
        # the live file) — a silent drop would pass the corruption-only check
        # above while still violating the "0 data loss" half of the claim.
        assert archived_lines + live_lines >= 3000, (
            f"expected >=3000 surviving lines, got archived={archived_lines} live={live_lines}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. FIX 1 — escalate_to_claude_code cooldown gate
# ─────────────────────────────────────────────────────────────────────────────
class TestEscalateCooldownGate:
    @pytest.fixture()
    def dlq(self, tmp_path, monkeypatch):
        """Import THIS worktree's dlq_autopilot (by explicit path, not sys.path —
        avoids resolving to a sibling checkout) with patched state dirs/telegram."""
        import importlib.util
        mod_path = Path(__file__).parent.parent / "dlq_autopilot.py"
        spec = importlib.util.spec_from_file_location("dlq_autopilot_s3test", mod_path)
        d = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(d)
        assert "bypass_cooldown" in d.escalate_to_claude_code.__code__.co_varnames, (
            f"loaded dlq_autopilot from {mod_path} lacks FIX 1"
        )
        # redirect side-effect dirs into tmp
        monkeypatch.setattr(d, "CLAUDE_TASKS_DIR", tmp_path / "claude_tasks")
        # capture JSONL writes + telegram
        written = []
        monkeypatch.setattr(d, "_write_escalation", lambda e: written.append(e))
        sent = []
        monkeypatch.setattr(d, "send_telegram", lambda *a, **k: sent.append(a))
        monkeypatch.setattr(d, "load_registry", lambda: {})
        return d, written, sent

    def test_first_escalation_passes_then_second_suppressed(self, dlq, monkeypatch):
        d, written, sent = dlq
        cooldown_state = {"on": False}
        monkeypatch.setattr(d, "_check_escalation_cooldown",
                            lambda job: cooldown_state["on"])
        marked = []
        monkeypatch.setattr(d, "_mark_escalation_sent",
                            lambda job: (marked.append(job), cooldown_state.update(on=True)))
        monkeypatch.setattr(d, "_record_suppressed", lambda job: None)

        entry = {"job": "nlm_nb1_daily_refresh", "error_summary": ""}
        d.escalate_to_claude_code(entry, None)   # first: passes
        d.escalate_to_claude_code(entry, None)   # second: cooldown on → suppressed

        assert len(written) == 1, "second escalation must NOT append to JSONL"
        assert marked == ["nlm_nb1_daily_refresh"]

    def test_terminal_bypasses_cooldown(self, dlq, monkeypatch):
        d, written, sent = dlq
        monkeypatch.setattr(d, "_check_escalation_cooldown", lambda job: True)  # always on
        monkeypatch.setattr(d, "_mark_escalation_sent", lambda job: None)
        monkeypatch.setattr(d, "_record_suppressed", lambda job: None)

        entry = {"job": "nlm_nb1_daily_refresh", "error_summary": ""}
        d.escalate_to_claude_code(entry, None, bypass_cooldown=True)
        assert len(written) == 1, "TERMINAL escalation must get through even on cooldown"

    def test_suppressed_recorded(self, dlq, monkeypatch):
        d, written, sent = dlq
        monkeypatch.setattr(d, "_check_escalation_cooldown", lambda job: True)
        monkeypatch.setattr(d, "_mark_escalation_sent", lambda job: None)
        rec = []
        monkeypatch.setattr(d, "_record_suppressed", lambda job: rec.append(job))

        d.escalate_to_claude_code({"job": "x", "error_summary": ""}, None)
        assert rec == ["x"]
        assert len(written) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. W55 digest
# ─────────────────────────────────────────────────────────────────────────────
class TestDigest:
    def test_build_with_suppressions(self, tmp_path, monkeypatch):
        state = tmp_path / "escalation_cooldown.json"
        now = time.time()
        state.write_text(json.dumps({
            "job_a": {"suppressed_count": 12, "last_suppressed_at": now - 100,
                      "escalation_sent_at": now - 100},
            "job_b": {"suppressed_count": 3, "last_suppressed_at": now - 200,
                      "escalation_sent_at": now - 200},
            "job_old": {"suppressed_count": 99, "last_suppressed_at": now - 30 * 86400},
        }))
        dedup = tmp_path / "alert_dedup.json"
        dedup.write_text(json.dumps({"hash1": {"ts": now - 50}}))
        monkeypatch.setattr(D, "ESCALATION_STATE_FILE", state)
        monkeypatch.setattr(D, "ALERT_DEDUP_FILE", dedup)

        digest = D.build_digest(now=now)
        assert digest["total_suppressed"] == 15  # job_old excluded (>7d)
        assert digest["suppressed_jobs"] == {"job_a": 12, "job_b": 3}
        assert digest["dedup_recent"] == 1
        assert "job_a: 12×" in digest["text"]

    def test_build_quiet_week(self, tmp_path, monkeypatch):
        state = tmp_path / "escalation_cooldown.json"
        state.write_text(json.dumps({"job_a": {"escalation_sent_at": time.time()}}))
        dedup = tmp_path / "alert_dedup.json"
        dedup.write_text(json.dumps({}))
        monkeypatch.setattr(D, "ESCALATION_STATE_FILE", state)
        monkeypatch.setattr(D, "ALERT_DEDUP_FILE", dedup)
        digest = D.build_digest()
        assert digest["total_suppressed"] == 0
        assert "No escalations" in digest["text"]

    def test_reset_counters(self, tmp_path, monkeypatch):
        state = tmp_path / "escalation_cooldown.json"
        state.write_text(json.dumps({
            "job_a": {"suppressed_count": 5, "escalation_sent_at": 1.0},
            "job_b": {"suppressed_count": 0},
        }))
        monkeypatch.setattr(D, "ESCALATION_STATE_FILE", state)
        n = D.reset_counters()
        assert n == 1  # only job_a had a nonzero counter
        after = json.loads(state.read_text())
        assert after["job_a"]["suppressed_count"] == 0
        assert after["job_a"]["escalation_sent_at"] == 1.0  # preserved
