"""Tests for backend.agents.services.unified_coverage_collector"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from backend.agents.services.unified_coverage_collector import (
    ComponentCoverage,
    CoverageDelta,
    UnifiedCoverageCollector,
    UnifiedCoverageReport,
)


@pytest.fixture
def collector(tmp_path):
    return UnifiedCoverageCollector(project_root=tmp_path)


# ── Dataclasses ─────────────────────────────────────────────────────────────


class TestDataclasses:
    def test_component_coverage_defaults(self):
        cc = ComponentCoverage(
            component_name="test",
            component_type="backend",
            coverage_percent=75.0,
            files_analyzed=10,
            files_below_threshold=2,
            total_lines=1000,
            covered_lines=750,
        )
        assert cc.missing_lines == []
        assert cc.coverage_gaps == []
        assert cc.report_path == ""

    def test_unified_coverage_report_defaults(self):
        report = UnifiedCoverageReport(
            timestamp="2026-01-01T00:00:00",
            overall_coverage=80.0,
        )
        assert report.components == {}
        assert report.total_files == 0

    def test_coverage_delta(self):
        delta = CoverageDelta(
            component_name="test",
            current_coverage=80.0,
            baseline_coverage=75.0,
            delta=5.0,
            delta_percent=6.67,
            regression=False,
            improvement=True,
        )
        assert delta.improvement is True
        assert delta.regression is False


# ── collect_backend_coverage ────────────────────────────────────────────────


class TestCollectBackendCoverage:
    def test_with_existing_coverage_json(self, collector, tmp_path):
        component_path = tmp_path / "backend"
        component_path.mkdir()

        coverage_data = {
            "totals": {
                "percent_covered": 65.5,
                "num_statements": 2000,
                "covered_lines": 1310,
            },
            "files": {
                "file_a.py": {
                    "summary": {"percent_covered": 90.0},
                    "missing_lines": [10, 20],
                },
                "file_b.py": {
                    "summary": {"percent_covered": 40.0},
                    "missing_lines": [1, 2, 3, 4, 5],
                },
            },
        }
        (component_path / "coverage.json").write_text(json.dumps(coverage_data))

        result = collector.collect_backend_coverage(component_path, "test-backend")
        assert result is not None
        assert result.coverage_percent == 65.5
        assert result.total_lines == 2000
        assert result.files_analyzed == 2
        assert result.files_below_threshold == 2  # Both below 99%
        assert len(result.coverage_gaps) == 2

    def test_no_coverage_json_subprocess_fail(self, collector, tmp_path):
        component_path = tmp_path / "backend_no_cov"
        component_path.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            result = collector.collect_backend_coverage(component_path, "test")
            assert result is None  # No coverage.json created

    def test_subprocess_timeout(self, collector, tmp_path):
        component_path = tmp_path / "backend_timeout"
        component_path.mkdir()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=30)):
            result = collector.collect_backend_coverage(component_path, "test")
            assert result is None

    def test_subprocess_timeout_with_existing_json(self, collector, tmp_path):
        component_path = tmp_path / "backend_timeout2"
        component_path.mkdir()

        coverage_data = {
            "totals": {"percent_covered": 50.0, "num_statements": 100, "covered_lines": 50},
            "files": {"a.py": {"summary": {"percent_covered": 50.0}}},
        }
        (component_path / "coverage.json").write_text(json.dumps(coverage_data))

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=30)):
            result = collector.collect_backend_coverage(component_path, "test")
            assert result is not None
            assert result.coverage_percent == 50.0

    def test_general_exception(self, collector, tmp_path):
        component_path = tmp_path / "backend_err"
        component_path.mkdir()

        with patch("subprocess.run", side_effect=Exception("unexpected")):
            result = collector.collect_backend_coverage(component_path, "test")
            assert result is None


# ── collect_frontend_coverage ───────────────────────────────────────────────


class TestCollectFrontendCoverage:
    def test_with_lcov(self, collector, tmp_path):
        component_path = tmp_path / "frontend"
        component_path.mkdir()
        cov_dir = component_path / "coverage"
        cov_dir.mkdir()

        lcov_content = """SF:src/App.tsx
DA:1,1
DA:2,0
DA:3,1
LF:3
LH:2
end_of_record
SF:src/index.tsx
DA:1,1
LF:1
LH:1
end_of_record
"""
        (cov_dir / "lcov.info").write_text(lcov_content)

        result = collector.collect_frontend_coverage(component_path, "test-frontend")
        assert result is not None
        assert result.component_type == "frontend"
        assert result.files_analyzed == 2
        assert result.total_lines == 4
        assert result.covered_lines == 3

    def test_with_vitest_json(self, collector, tmp_path):
        component_path = tmp_path / "frontend2"
        component_path.mkdir()
        cov_dir = component_path / "coverage"
        cov_dir.mkdir()

        vitest_data = {
            "src/App.tsx": {
                "s": {"0": 1, "1": 0, "2": 1},
            },
            "src/utils.ts": {
                "s": {"0": 1, "1": 1},
            },
        }
        (cov_dir / "coverage-final.json").write_text(json.dumps(vitest_data))

        result = collector.collect_frontend_coverage(component_path, "test-frontend2")
        assert result is not None
        assert result.total_lines == 5
        assert result.covered_lines == 4

    def test_no_coverage_files(self, collector, tmp_path):
        component_path = tmp_path / "frontend_empty"
        component_path.mkdir()

        result = collector.collect_frontend_coverage(component_path, "test")
        assert result is None

    def test_tries_to_generate_with_package_json(self, collector, tmp_path):
        component_path = tmp_path / "frontend3"
        component_path.mkdir()

        pkg = {"scripts": {"test:coverage": "vitest run --coverage"}}
        (component_path / "package.json").write_text(json.dumps(pkg))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = collector.collect_frontend_coverage(component_path, "test")
            # Still None since no coverage file was created
            assert result is None

    def test_exception_handling(self, collector, tmp_path):
        component_path = tmp_path / "frontend_err"
        component_path.mkdir()
        cov_dir = component_path / "coverage"
        cov_dir.mkdir()
        (cov_dir / "lcov.info").write_text("INVALID CONTENT\x00\x01")

        # _parse_lcov may fail with weird content but shouldn't crash
        # If it does parse, that's fine too
        result = collector.collect_frontend_coverage(component_path, "test")
        # Just verify no exception propagates


# ── _parse_lcov ─────────────────────────────────────────────────────────────


class TestParseLcov:
    def test_empty_file(self, collector, tmp_path):
        lcov = tmp_path / "empty.lcov"
        lcov.write_text("")
        result = collector._parse_lcov(lcov, "test", tmp_path)
        assert result.coverage_percent == 0.0
        assert result.files_analyzed == 0


# ── _parse_vitest_json ──────────────────────────────────────────────────────


class TestParseVitestJson:
    def test_zero_lines(self, collector, tmp_path):
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(json.dumps({"file.ts": {"s": {}}}))
        result = collector._parse_vitest_json(cov_file, "test", tmp_path)
        assert result.coverage_percent == 0.0

    def test_non_dict_entries_skipped(self, collector, tmp_path):
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(json.dumps({"file.ts": "not a dict", "ok.ts": {"s": {"0": 1}}}))
        result = collector._parse_vitest_json(cov_file, "test", tmp_path)
        assert result.total_lines == 1


# ── collect_all_coverage ────────────────────────────────────────────────────


class TestCollectAllCoverage:
    def test_no_components_exist(self, collector):
        report = collector.collect_all_coverage()
        assert isinstance(report, UnifiedCoverageReport)
        assert report.overall_coverage == 0.0
        assert len(report.components) == 0

    def test_with_backend_component(self, collector, tmp_path):
        backend_path = tmp_path / "apps" / "backend-rag"
        backend_path.mkdir(parents=True)

        coverage_data = {
            "totals": {"percent_covered": 60.0, "num_statements": 500, "covered_lines": 300},
            "files": {
                "good.py": {"summary": {"percent_covered": 100.0}},
                "bad.py": {
                    "summary": {"percent_covered": 20.0},
                    "missing_lines": list(range(1, 41)),
                    "missing_lines_count": 40,
                },
            },
        }
        (backend_path / "coverage.json").write_text(json.dumps(coverage_data))

        report = collector.collect_all_coverage()
        assert report.overall_coverage == 60.0
        assert "backend-rag" in report.components
        assert report.coverage_by_type.get("backend", 0) == 60.0
        assert len(report.critical_gaps) >= 1  # bad.py < 50%
