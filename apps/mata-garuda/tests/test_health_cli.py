"""Tests for `mata-garuda health` CLI + tools (Wave 3 of W4)."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest


class TestHealthTools:
    def test_streams_snapshot_handles_redis_down(self):
        from mata_garuda.tools import health_tools

        with patch.object(health_tools, "_redis_cmd", return_value=None):
            snap = health_tools.get_streams_snapshot()
        assert len(snap) == len(health_tools.HEALTH_STREAMS)
        assert all(s["length"] is None for s in snap)

    def test_streams_snapshot_parses_xlen(self):
        from mata_garuda.tools import health_tools

        def fake(*args, **kwargs):
            if args[:1] == ("XLEN",):
                return "42"
            return ""

        with patch.object(health_tools, "_redis_cmd", side_effect=fake):
            snap = health_tools.get_streams_snapshot()
        assert all(s["length"] == 42 for s in snap)

    def test_launchctl_parsing(self):
        from mata_garuda.tools import health_tools

        fake_output = (
            "PID\tStatus\tLabel\n"
            "1234\t0\tcom.matagaruda.watcher.daily\n"
            "-\t0\tcom.matagaruda.sentinel.daily\n"
            "5678\t-15\tcom.matagaruda.bridge.adaptive\n"
        )

        class _FakeResult:
            returncode = 0
            stdout = fake_output
            stderr = ""

        with patch("subprocess.run", return_value=_FakeResult()):
            loaded = health_tools.launchctl_list()
        assert loaded["com.matagaruda.watcher.daily"]["pid"] == 1234
        assert loaded["com.matagaruda.sentinel.daily"]["pid"] is None
        assert loaded["com.matagaruda.bridge.adaptive"]["status"] == "-15"

    def test_agents_snapshot_marks_missing(self):
        from mata_garuda.tools import health_tools

        def fake_loader():
            return {"com.matagaruda.watcher.daily": {"pid": 10, "status": "0"}}

        snap = health_tools.get_agents_snapshot(
            expected=[
                "com.matagaruda.watcher.daily",
                "com.matagaruda.public-channel",
            ],
            loader=fake_loader,
        )
        assert snap[0]["loaded"] is True
        assert snap[1]["loaded"] is False

    def test_overall_status_green(self):
        from mata_garuda.tools import health_tools

        streams = [{"length": 10} for _ in range(3)]
        agents = [{"loaded": True} for _ in range(3)]
        assert health_tools.overall_status(streams, agents) == "GREEN"

    def test_overall_status_yellow_when_agent_missing(self):
        from mata_garuda.tools import health_tools

        streams = [{"length": 10} for _ in range(3)]
        agents = [{"loaded": True}, {"loaded": False}]
        assert health_tools.overall_status(streams, agents) == "YELLOW"

    def test_overall_status_red_when_redis_down(self):
        from mata_garuda.tools import health_tools

        streams = [{"length": None} for _ in range(3)]
        agents = [{"loaded": True}]
        assert health_tools.overall_status(streams, agents) == "RED"

    def test_build_health_report_shape(self):
        from mata_garuda.tools import health_tools

        with patch.object(health_tools, "get_streams_snapshot",
                          return_value=[{"stream": "a", "length": 1, "last_added": None}]), \
             patch.object(health_tools, "get_agents_snapshot",
                          return_value=[{"label": "x", "loaded": True,
                                         "pid": 1, "status": "0"}]), \
             patch.object(health_tools, "get_kb_stats", return_value={"total": 3}), \
             patch.object(health_tools, "get_bridge_cursor",
                          return_value={"exists": False, "path": "/tmp/x"}), \
             patch.object(health_tools, "recent_errors_in_logs", return_value=[]):
            report = health_tools.build_health_report()
        assert "status" in report
        assert "streams" in report
        assert "agents" in report
        assert "kb" in report
        assert report["status"] in ("GREEN", "YELLOW", "RED")

    def test_format_report_renders_text(self):
        from mata_garuda.tools import health_tools

        report = {
            "generated_at": "2026-04-20T14:30:00+08:00",
            "status": "GREEN",
            "streams": [
                {"stream": "garuda:raw", "length": 100, "last_added": "2026-04-20T14:25"},
                {"stream": "garuda:enriched", "length": None, "last_added": None},
            ],
            "agents": [
                {"label": "com.matagaruda.watcher.daily", "loaded": True,
                 "pid": 123, "status": "0"},
                {"label": "com.matagaruda.public-channel", "loaded": False,
                 "pid": None, "status": None},
            ],
            "kb": {"total": 10, "arxiv": 5, "github": 5},
            "bridge_cursor": {"exists": True, "last_id": 42, "mtime": "2026-04-20T14:00"},
            "nlm": {"configured": 2, "total": 6},
            "recent_errors": [],
        }
        text = health_tools.format_report(report)
        assert "Mata Garuda Health" in text
        assert "GREEN" in text
        assert "garuda:raw" in text
        assert "✅" in text or "loaded" in text
        assert "NEXUS" in text or "Knowledge" in text

    def test_nlm_wired_count(self):
        from mata_garuda.tools import health_tools

        configured, total = health_tools.nlm_wired_count()
        assert total >= 1
        assert configured <= total

    def test_tail_log_missing_file_returns_empty(self, tmp_path: Path):
        from mata_garuda.tools import health_tools

        result = health_tools.tail_log(tmp_path / "does-not-exist.log")
        assert result == []

    def test_tail_log_reads_existing(self, tmp_path: Path):
        from mata_garuda.tools import health_tools

        log = tmp_path / "sample.log"
        log.write_text("line1\nline2\nline3\n")
        result = health_tools.tail_log(log, lines=2)
        assert result[-1] == "line3"


class TestHealthCli:
    def test_cli_health_subcommand_runs(self):
        """Smoke test the CLI end-to-end with stubs."""
        from mata_garuda import cli
        from mata_garuda.tools import health_tools

        fake_report = {
            "generated_at": "2026-04-20T14:00:00+08:00",
            "status": "GREEN",
            "streams": [],
            "agents": [],
            "kb": {"total": 0},
            "bridge_cursor": {"exists": False, "path": "/tmp/x"},
            "nlm": {"configured": 0, "total": 6},
            "recent_errors": [],
        }

        with patch.object(health_tools, "build_health_report", return_value=fake_report):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["health"])
            assert rc == 0
            output = buf.getvalue()
            assert "Mata Garuda Health" in output
            assert "GREEN" in output

    def test_cli_health_json(self):
        from mata_garuda import cli
        from mata_garuda.tools import health_tools

        fake_report = {
            "generated_at": "2026-04-20T14:00:00+08:00",
            "status": "GREEN",
            "streams": [],
            "agents": [],
            "kb": None,
            "bridge_cursor": None,
            "nlm": {"configured": 0, "total": 6},
            "recent_errors": [],
        }

        with patch.object(health_tools, "build_health_report", return_value=fake_report):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["health", "--json"])
            assert rc == 0
            parsed = json.loads(buf.getvalue())
            assert parsed["status"] == "GREEN"

    def test_cli_health_red_returns_nonzero(self):
        from mata_garuda import cli
        from mata_garuda.tools import health_tools

        fake_report = {
            "generated_at": "2026-04-20T14:00:00+08:00",
            "status": "RED",
            "streams": [],
            "agents": [],
            "kb": None,
            "bridge_cursor": None,
            "nlm": {"configured": 0, "total": 6},
            "recent_errors": [],
        }
        with patch.object(health_tools, "build_health_report", return_value=fake_report):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["health"])
            assert rc == 2
