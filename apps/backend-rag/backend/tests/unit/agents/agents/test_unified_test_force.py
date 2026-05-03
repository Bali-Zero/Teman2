"""Unit tests for backend/agents/agents/unified_test_force_orchestrator.py"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_deps():
    """Mock all external dependencies so UnifiedTestForceOrchestrator can be imported."""
    patches = []

    # Patch heavyweight imports before importing the module
    p1 = patch(
        "backend.agents.services.differential_coverage_analyzer.DifferentialCoverageAnalyzer"
    )
    p2 = patch("backend.agents.services.llm_adapter.get_llm_adapter")
    p3 = patch("backend.agents.services.test_metrics.get_metrics_collector")
    p4 = patch(
        "backend.agents.services.unified_coverage_collector.UnifiedCoverageCollector"
    )

    mock_dca = p1.start()
    mock_llm = p2.start()
    mock_metrics = p3.start()
    mock_ucc = p4.start()

    patches.extend([p1, p2, p3, p4])

    # Configure metrics mock
    mock_metrics_inst = MagicMock()
    mock_agent_metrics = MagicMock()
    mock_metrics_inst.register_agent.return_value = mock_agent_metrics
    mock_metrics.return_value = mock_metrics_inst

    # Configure LLM adapter mock
    mock_llm_inst = AsyncMock()
    mock_llm.return_value = mock_llm_inst

    yield {
        "dca_cls": mock_dca,
        "llm_adapter_fn": mock_llm,
        "llm_adapter": mock_llm_inst,
        "metrics_fn": mock_metrics,
        "metrics": mock_metrics_inst,
        "agent_metrics": mock_agent_metrics,
        "ucc_cls": mock_ucc,
    }

    for p in patches:
        p.stop()


@pytest.fixture
def orchestrator(mock_deps):
    """Create orchestrator instance with mocked deps."""
    from backend.agents.agents.unified_test_force_orchestrator import (
        UnifiedTestForceOrchestrator,
    )

    return UnifiedTestForceOrchestrator(project_root=Path("/tmp/test_project"))


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_sets_project_root(self, orchestrator):
        assert orchestrator.project_root == Path("/tmp/test_project")

    def test_init_default_provider(self, orchestrator):
        assert orchestrator.llm_provider == "local"

    def test_init_has_orchestrator_metrics(self, mock_deps, orchestrator):
        # The orchestrator should have an orchestrator_metrics attribute
        assert orchestrator.orchestrator_metrics is not None


# ---------------------------------------------------------------------------
# run_full_analysis
# ---------------------------------------------------------------------------


class TestRunFullAnalysis:
    @pytest.mark.asyncio
    async def test_full_analysis_returns_expected_keys(self, orchestrator, mock_deps):
        """run_full_analysis should return dict with expected structure."""
        # Mock coverage report
        mock_comp = MagicMock()
        mock_comp.component_type = "backend"
        mock_comp.coverage_percent = 50.0
        mock_comp.files_analyzed = 10
        mock_comp.coverage_gaps = []

        mock_report = MagicMock()
        mock_report.overall_coverage = 55.0
        mock_report.components = {"backend": mock_comp}
        mock_report.coverage_by_type = {"backend": 55.0}
        mock_report.critical_gaps = []

        orchestrator.coverage_collector.collect_all_coverage.return_value = mock_report

        # Mock differential
        orchestrator.differential_analyzer.calculate_delta.return_value = None

        result = await orchestrator.run_full_analysis(
            {"generate_tests": False}
        )

        assert result["analysis_type"] == "unified_full"
        assert "coverage_report" in result
        assert "components_analyzed" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_full_analysis_saves_baseline_when_requested(
        self, orchestrator, mock_deps
    ):
        mock_report = MagicMock()
        mock_report.overall_coverage = 40.0
        mock_report.components = {}
        mock_report.coverage_by_type = {}
        mock_report.critical_gaps = []
        orchestrator.coverage_collector.collect_all_coverage.return_value = mock_report
        orchestrator.differential_analyzer.calculate_delta.return_value = None

        await orchestrator.run_full_analysis(
            {"save_baseline": True, "generate_tests": False}
        )

        orchestrator.differential_analyzer.save_baseline.assert_called_once_with(
            mock_report
        )

    @pytest.mark.asyncio
    async def test_full_analysis_records_metrics_on_success(
        self, orchestrator, mock_deps
    ):
        mock_report = MagicMock()
        mock_report.overall_coverage = 40.0
        mock_report.components = {}
        mock_report.coverage_by_type = {}
        mock_report.critical_gaps = []
        orchestrator.coverage_collector.collect_all_coverage.return_value = mock_report
        orchestrator.differential_analyzer.calculate_delta.return_value = None

        result = await orchestrator.run_full_analysis({"generate_tests": False})

        # The analysis should complete and have a duration
        assert "duration" in result
        assert result["duration"] > 0

    @pytest.mark.asyncio
    async def test_full_analysis_handles_exception(self, orchestrator, mock_deps):
        orchestrator.coverage_collector.collect_all_coverage.side_effect = (
            RuntimeError("kaboom")
        )

        result = await orchestrator.run_full_analysis({"generate_tests": False})

        assert result["success"] is False
        assert "kaboom" in result["error"]

    @pytest.mark.asyncio
    async def test_full_analysis_with_differential(self, orchestrator, mock_deps):
        """When differential analyzer returns a delta, it should appear in results."""
        from types import SimpleNamespace

        mock_comp = SimpleNamespace(
            component_type="backend",
            coverage_percent=60.0,
            files_analyzed=5,
            coverage_gaps=[],
        )
        mock_report = SimpleNamespace(
            overall_coverage=60.0,
            components={"backend": mock_comp},
            coverage_by_type={"backend": 60.0},
            critical_gaps=[],
        )
        # Reset side_effect in case a prior test set it
        orchestrator.coverage_collector.collect_all_coverage.side_effect = None
        orchestrator.coverage_collector.collect_all_coverage.return_value = mock_report

        mock_diff = SimpleNamespace(
            overall_delta=5.0,
            overall_delta_percent=2.0,
            regressions=[],
            improvements=["file1"],
            critical_regressions=[],
        )
        orchestrator.differential_analyzer.calculate_delta.return_value = mock_diff

        result = await orchestrator.run_full_analysis({"generate_tests": False})

        assert result.get("differential_report") is not None
        assert result["differential_report"]["overall_delta"] == 5.0


# ---------------------------------------------------------------------------
# _generate_tests_for_gaps
# ---------------------------------------------------------------------------


class TestGenerateTestsForGaps:
    @pytest.mark.asyncio
    async def test_empty_gaps_returns_zeros(self, orchestrator, mock_deps):
        mock_report = MagicMock()
        mock_report.components = {}

        result = await orchestrator._generate_tests_for_gaps(mock_report, 5)

        assert result["tests_generated"] == 0

    @pytest.mark.asyncio
    async def test_generates_tests_for_gaps(self, orchestrator, mock_deps):
        mock_comp = MagicMock()
        mock_comp.component_type = "backend"
        mock_comp.coverage_gaps = [
            {"file": "service.py", "coverage": 0.0, "missing_lines": [1, 2, 3]}
        ]

        mock_report = MagicMock()
        mock_report.components = {"backend": mock_comp}

        # Mock LLM generates test code
        with patch.object(
            orchestrator, "_generate_test_with_qwen", new_callable=AsyncMock
        ) as mock_gen, patch.object(
            orchestrator, "_save_test_file", return_value="/tmp/test.py"
        ), patch.object(
            orchestrator, "_run_test", new_callable=AsyncMock, return_value=True
        ):
            mock_gen.return_value = "def test_something(): pass"
            result = await orchestrator._generate_tests_for_gaps(mock_report, 5)

        assert result["tests_generated"] == 1
        assert result["tests_passed"] == 1


# ---------------------------------------------------------------------------
# _generate_test_with_qwen
# ---------------------------------------------------------------------------


class TestGenerateTestWithQwen:
    @pytest.mark.asyncio
    async def test_backend_prompt_uses_pytest(self, orchestrator, mock_deps):
        # Create a mock response whose .provider matches the OLLAMA check
        mock_response = MagicMock()
        # Set provider to match what the code checks:
        # ``if response.provider == LLMProvider.OLLAMA``
        from backend.agents.services.llm_adapter import LLMProvider

        mock_response.provider = LLMProvider.OLLAMA
        mock_response.text = "def test_foo(): pass"
        orchestrator.llm_adapter.generate = AsyncMock(return_value=mock_response)

        gap = {
            "component_type": "backend",
            "file": "services/foo.py",
            "coverage": 10.0,
            "missing_lines": [1, 2],
        }
        result = await orchestrator._generate_test_with_qwen(gap)

        assert result == "def test_foo(): pass"

    @pytest.mark.asyncio
    async def test_frontend_prompt(self, orchestrator, mock_deps):
        from backend.agents.services.llm_adapter import LLMProvider

        mock_response = MagicMock()
        mock_response.provider = LLMProvider.OLLAMA
        mock_response.text = "test('foo', () => {})"
        orchestrator.llm_adapter.generate = AsyncMock(return_value=mock_response)

        gap = {
            "component_type": "frontend",
            "file": "src/Component.tsx",
            "coverage": 5.0,
            "missing_lines_count": 50,
        }
        result = await orchestrator._generate_test_with_qwen(gap)
        assert result is not None

    @pytest.mark.asyncio
    async def test_qwen_unavailable_returns_none(self, orchestrator, mock_deps):
        from backend.agents.services.llm_adapter import LLMProvider

        mock_response = MagicMock()
        mock_response.provider = LLMProvider.MOCK
        orchestrator.llm_adapter.generate = AsyncMock(return_value=mock_response)

        gap = {"component_type": "backend", "file": "f.py", "coverage": 0.0}
        result = await orchestrator._generate_test_with_qwen(gap)
        assert result is None

    @pytest.mark.asyncio
    async def test_qwen_exception_returns_none(self, orchestrator, mock_deps):
        mock_deps["llm_adapter"].generate.side_effect = Exception("timeout")

        gap = {"component_type": "backend", "file": "f.py", "coverage": 0.0}
        result = await orchestrator._generate_test_with_qwen(gap)
        assert result is None


# ---------------------------------------------------------------------------
# _save_test_file
# ---------------------------------------------------------------------------


class TestSaveTestFile:
    def test_save_backend_test(self, orchestrator, tmp_path):
        from unittest.mock import mock_open as _mock_open

        gap = {
            "component": "backend-rag",
            "component_type": "backend",
            "file": "services/foo.py",
        }
        with patch("pathlib.Path.mkdir"):
            with patch("builtins.open", _mock_open()):
                result = orchestrator._save_test_file(gap, "def test(): pass")

        assert result is not None
        assert "test_foo.py" in result

    def test_save_frontend_test(self, orchestrator, tmp_path):
        from unittest.mock import mock_open as _mock_open

        gap = {
            "component": "mouth-frontend",
            "component_type": "frontend",
            "file": "src/Component.tsx",
        }
        with patch("pathlib.Path.mkdir"):
            with patch("builtins.open", _mock_open()):
                result = orchestrator._save_test_file(gap, "test code")

        assert result is not None
        assert "Component.test.ts" in result

    def test_save_error_returns_none(self, orchestrator):
        gap = {
            "component": "broken",
            "component_type": "backend",
            "file": "x.py",
        }
        with patch("pathlib.Path.mkdir", side_effect=OSError("perm denied")):
            result = orchestrator._save_test_file(gap, "code")
        assert result is None


# ---------------------------------------------------------------------------
# _run_test
# ---------------------------------------------------------------------------


class TestRunTest:
    @pytest.mark.asyncio
    async def test_run_backend_test_success(self, orchestrator):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = await orchestrator._run_test(
                "/tmp/test_foo.py", {"component_type": "backend", "component": "backend-rag"}
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_run_backend_test_failure(self, orchestrator):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="FAILED")
            result = await orchestrator._run_test(
                "/tmp/test_foo.py", {"component_type": "backend", "component": "backend-rag"}
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_run_frontend_test_success(self, orchestrator):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = await orchestrator._run_test(
                "/tmp/Component.test.ts",
                {"component_type": "frontend", "component": "mouth-frontend"},
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_run_test_exception(self, orchestrator):
        with patch("subprocess.run", side_effect=Exception("no pytest")):
            result = await orchestrator._run_test(
                "/tmp/test_foo.py", {"component_type": "backend", "component": "backend-rag"}
            )
        assert result is False


# ---------------------------------------------------------------------------
# _generate_summary / _log_summary / cleanup
# ---------------------------------------------------------------------------


class TestSummaryAndCleanup:
    def test_generate_summary_no_differential(self, orchestrator):
        results = {
            "duration": 1.5,
            "components_analyzed": ["a", "b"],
            "coverage_report": {"overall_coverage": 45.0},
            "test_generation": {"tests_generated": 3},
        }
        summary = orchestrator._generate_summary(results)
        assert summary["components_analyzed"] == 2
        assert summary["overall_coverage"] == 45.0
        assert summary["regressions"] == 0

    def test_generate_summary_with_differential(self, orchestrator):
        results = {
            "duration": 2.0,
            "components_analyzed": [],
            "coverage_report": {"overall_coverage": 50.0},
            "test_generation": {"tests_generated": 0},
            "differential_report": {"regressions": 2, "improvements": 3},
        }
        summary = orchestrator._generate_summary(results)
        assert summary["regressions"] == 2
        assert summary["improvements"] == 3

    def test_log_summary_runs_without_error(self, orchestrator):
        summary = {
            "duration": 1.0,
            "components_analyzed": 2,
            "overall_coverage": 45.0,
            "tests_generated": 1,
            "regressions": 0,
            "improvements": 1,
        }
        orchestrator._log_summary(summary)  # Should not raise

    @pytest.mark.asyncio
    async def test_cleanup(self, orchestrator):
        await orchestrator.cleanup()  # Should not raise
