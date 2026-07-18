"""Deterministic tests for the NLM pipeline circuit-breaker registry.

The tests exercise the finite-state machine, cascade boundaries, and atomic
JSON persistence without calling external services or using the real pipeline
state file.
"""

from __future__ import annotations

import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import pytest

from apps.evaluator.nlm_deep_research import circuit_breaker as cb
from apps.evaluator.nlm_deep_research.circuit_breaker import (
    CBName,
    CBState,
    CircuitBreaker,
    CircuitBreakerRegistry,
)


PIPELINE_CASES = (
    ("apps.evaluator.nlm_deep_research.pipeline", "NLMPipeline"),
    ("apps.evaluator.nlm_deep_research.nb3_pipeline", "NB3Pipeline"),
    ("apps.evaluator.nlm_deep_research.nb4_pipeline", "NB4Pipeline"),
    ("apps.evaluator.nlm_deep_research.nb5_pipeline", "NB5Pipeline"),
    ("apps.evaluator.nlm_deep_research.nb6_pipeline", "NB6Pipeline"),
    ("apps.evaluator.nlm_deep_research.nb7_pipeline", "NB7Pipeline"),
    ("apps.evaluator.nlm_deep_research.nb8_pipeline", "NB8Pipeline"),
    ("apps.evaluator.nlm_deep_research.nb10_pipeline", "NB10Pipeline"),
)


def _past(*, hours: int = 0, days: int = 0) -> str:
    """Return a timezone-aware timestamp safely in the past."""
    return (
        datetime.now(tz=timezone.utc) - timedelta(hours=hours, days=days)
    ).isoformat()


def _breaker(
    *,
    state: CBState = CBState.CLOSED,
    threshold: int = 3,
    timeout_hours: int = 4,
    failure_count: int = 0,
    opened_at: str | None = None,
) -> CircuitBreaker:
    return CircuitBreaker(
        name=CBName.CB_NLM,
        failure_threshold=threshold,
        timeout_hours=timeout_hours,
        state=state,
        failure_count=failure_count,
        opened_at=opened_at,
    )


class TestCircuitBreakerTransitions:
    def test_closed_breaker_allows_requests(self) -> None:
        breaker = _breaker()

        assert breaker.get_state() is CBState.CLOSED
        assert breaker.should_allow_request() is True
        assert breaker.is_open is False

    def test_failure_threshold_opens_breaker(self) -> None:
        breaker = _breaker(threshold=2)

        with patch.object(cb, "_now_iso", side_effect=["first", "second"]):
            breaker.record_failure()
            assert breaker.state is CBState.CLOSED
            assert breaker.failure_count == 1
            assert breaker.last_failure == "first"

            breaker.record_failure()

        assert breaker.state is CBState.OPEN
        assert breaker.failure_count == 2
        assert breaker.last_failure == "second"
        assert breaker.opened_at == "second"

    def test_success_in_closed_resets_consecutive_failures(self) -> None:
        breaker = _breaker(failure_count=2)

        breaker.record_success()

        assert breaker.state is CBState.CLOSED
        assert breaker.failure_count == 0

    def test_failed_half_open_probe_reopens_and_resets_timeout(self) -> None:
        breaker = _breaker(
            state=CBState.HALF_OPEN,
            failure_count=3,
            opened_at="old",
        )

        with patch.object(cb, "_now_iso", return_value="new"):
            breaker.record_failure()

        assert breaker.state is CBState.OPEN
        assert breaker.failure_count == 4
        assert breaker.last_failure == "new"
        assert breaker.opened_at == "new"

    def test_successful_half_open_probe_closes_and_resets(self) -> None:
        breaker = _breaker(
            state=CBState.HALF_OPEN,
            failure_count=3,
            opened_at="opened",
        )

        breaker.record_success()

        assert breaker.state is CBState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.opened_at is None

    def test_force_open_is_idempotent(self) -> None:
        breaker = _breaker()

        with patch.object(cb, "_now_iso", side_effect=["first", "second"]):
            breaker.force_open("upstream outage")
            breaker.force_open("duplicate signal")

        assert breaker.state is CBState.OPEN
        assert breaker.opened_at == "first"

    def test_force_close_resets_open_breaker(self) -> None:
        breaker = _breaker(
            state=CBState.OPEN,
            failure_count=7,
            opened_at="opened",
        )

        breaker.force_close()

        assert breaker.state is CBState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.opened_at is None

    def test_elapsed_timeout_promotes_to_half_open(self) -> None:
        breaker = _breaker(
            state=CBState.OPEN,
            timeout_hours=4,
            opened_at=_past(hours=5),
        )

        assert breaker.get_state() is CBState.HALF_OPEN
        assert breaker.should_allow_request() is True

    def test_unelapsed_timeout_keeps_breaker_open(self) -> None:
        breaker = _breaker(
            state=CBState.OPEN,
            timeout_hours=4,
            opened_at=_past(hours=1),
        )

        assert breaker.is_open is True
        assert breaker.should_allow_request() is False

    @pytest.mark.parametrize("opened_at", [None, _past(days=30)])
    def test_manual_close_breaker_never_auto_recovers(
        self,
        opened_at: str | None,
    ) -> None:
        breaker = _breaker(
            state=CBState.OPEN,
            timeout_hours=-1,
            opened_at=opened_at,
        )

        assert breaker.get_state() is CBState.OPEN

    def test_open_breaker_without_timestamp_stays_open(self) -> None:
        breaker = _breaker(state=CBState.OPEN, opened_at=None)

        assert breaker.get_state() is CBState.OPEN

    def test_half_open_allows_one_probe_until_success(self) -> None:
        breaker = _breaker(state=CBState.HALF_OPEN)

        assert breaker.should_allow_request() is True
        assert breaker.should_allow_request() is False

        breaker.record_success()

        assert breaker.state is CBState.CLOSED
        assert breaker.should_allow_request() is True

    def test_half_open_allows_exactly_one_concurrent_probe(self) -> None:
        breaker = _breaker(state=CBState.HALF_OPEN)
        barrier = Barrier(8)

        def request_probe() -> bool:
            barrier.wait()
            return breaker.should_allow_request()

        with ThreadPoolExecutor(max_workers=8) as executor:
            allowed = list(executor.map(lambda _: request_probe(), range(8)))

        assert allowed.count(True) == 1
        assert allowed.count(False) == 7
        assert breaker.should_allow_request() is False

        breaker.record_failure()

        assert breaker.state is CBState.OPEN
        assert breaker.should_allow_request() is False

    def test_abandoned_half_open_probe_is_failed_once(self) -> None:
        breaker = _breaker(state=CBState.HALF_OPEN)
        assert breaker.should_allow_request() is True

        assert breaker.record_probe_failure_if_in_flight() is True
        failure_count = breaker.failure_count

        assert breaker.state is CBState.OPEN
        assert breaker.should_allow_request() is False
        assert breaker.record_probe_failure_if_in_flight() is False
        assert breaker.failure_count == failure_count


class TestCircuitBreakerSerialization:
    def test_auto_close_breaker_serializes_timeout(self) -> None:
        breaker = _breaker(
            state=CBState.OPEN,
            failure_count=3,
            opened_at="2026-07-18T00:00:00+00:00",
        )
        breaker.last_failure = "2026-07-18T00:00:00+00:00"

        data = breaker.to_dict()

        assert data == {
            "state": "OPEN",
            "failure_count": 3,
            "last_failure": "2026-07-18T00:00:00+00:00",
            "opened_at": "2026-07-18T00:00:00+00:00",
            "auto_close_after_hours": 4,
        }

    def test_manual_breaker_serializes_manual_flag(self) -> None:
        data = _breaker(timeout_hours=-1).to_dict()

        assert data["manual_close_only"] is True
        assert "auto_close_after_hours" not in data

    def test_from_dict_uses_safe_defaults(self) -> None:
        breaker = CircuitBreaker.from_dict(
            CBName.CB_SOURCE,
            {},
            failure_threshold=5,
            timeout_hours=-1,
        )

        assert breaker.name is CBName.CB_SOURCE
        assert breaker.state is CBState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.last_failure is None
        assert breaker.opened_at is None

    def test_round_trip_preserves_runtime_state(self) -> None:
        original = _breaker(
            state=CBState.OPEN,
            failure_count=4,
            opened_at="2026-07-18T00:00:00+00:00",
        )
        original.last_failure = "2026-07-18T00:01:00+00:00"

        restored = CircuitBreaker.from_dict(
            CBName.CB_NLM,
            original.to_dict(),
            failure_threshold=3,
            timeout_hours=4,
        )

        assert restored == original


class TestCircuitBreakerRegistry:
    def test_get_returns_each_named_breaker(self, tmp_path: Path) -> None:
        registry = CircuitBreakerRegistry(state_path=tmp_path / "state.json")

        assert registry.get(CBName.CB_NLM) is registry.nlm
        assert registry.get(CBName.CB_SOURCE) is registry.source
        assert registry.get(CBName.CB_INTEGRATION) is registry.integration

    def test_get_rejects_unknown_name(self, tmp_path: Path) -> None:
        registry = CircuitBreakerRegistry(state_path=tmp_path / "state.json")

        with pytest.raises(KeyError, match="Unknown circuit breaker"):
            registry.get("CB_UNKNOWN")  # type: ignore[arg-type]

    def test_old_nlm_outage_cascades_to_source(self, tmp_path: Path) -> None:
        registry = CircuitBreakerRegistry(state_path=tmp_path / "state.json")
        registry.nlm.state = CBState.OPEN
        registry.nlm.opened_at = _past(days=cb.CASCADE_NLM_TO_SOURCE_DAYS + 1)

        registry.evaluate_cascades()

        assert registry.source.state is CBState.OPEN
        assert registry.source.opened_at is not None
        assert registry.integration.state is CBState.CLOSED

    def test_old_source_outage_cascades_to_integration(
        self,
        tmp_path: Path,
    ) -> None:
        registry = CircuitBreakerRegistry(state_path=tmp_path / "state.json")
        registry.source.state = CBState.OPEN
        registry.source.opened_at = _past(
            days=cb.CASCADE_SOURCE_TO_INTEGRATION_DAYS + 1,
        )

        registry.evaluate_cascades()

        assert registry.integration.state is CBState.OPEN

    @pytest.mark.parametrize(
        ("state", "opened_at"),
        [
            (CBState.CLOSED, _past(days=30)),
            (CBState.OPEN, None),
            (CBState.OPEN, _past(days=1)),
        ],
    )
    def test_ineligible_upstream_does_not_cascade(
        self,
        tmp_path: Path,
        state: CBState,
        opened_at: str | None,
    ) -> None:
        registry = CircuitBreakerRegistry(state_path=tmp_path / "state.json")
        registry.nlm.state = state
        registry.nlm.opened_at = opened_at

        registry.evaluate_cascades()

        assert registry.source.state is CBState.CLOSED


class TestCircuitBreakerPersistence:
    def test_save_preserves_unrelated_pipeline_state(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "pipeline_state.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps({"run_count": 8, "circuit_breakers": {"stale": {}}}),
            encoding="utf-8",
        )
        registry = CircuitBreakerRegistry(state_path=path)
        registry.nlm.record_failure()

        registry.save()

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["run_count"] == 8
        assert data["circuit_breakers"]["CB_NLM"]["failure_count"] == 1
        assert set(data["circuit_breakers"]) == {
            "CB_NLM",
            "CB_SOURCE",
            "CB_INTEGRATION",
        }
        assert datetime.fromisoformat(data["updated"]).tzinfo is not None
        assert not path.with_suffix(".json.tmp").exists()

    def test_save_recovers_from_malformed_existing_json(self, tmp_path: Path) -> None:
        path = tmp_path / "pipeline_state.json"
        path.write_text("not-json", encoding="utf-8")
        registry = CircuitBreakerRegistry(state_path=path)

        registry.save()

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["circuit_breakers"]["CB_SOURCE"]["manual_close_only"] is True

    def test_load_missing_file_returns_default_registry(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.json"

        registry = CircuitBreakerRegistry.load(path)

        assert registry.state_path == path
        assert registry.nlm.state is CBState.CLOSED
        assert registry.source.state is CBState.CLOSED
        assert registry.integration.state is CBState.CLOSED

    def test_load_malformed_file_falls_back_to_defaults(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "pipeline_state.json"
        path.write_text("{broken", encoding="utf-8")

        registry = CircuitBreakerRegistry.load(path)

        assert registry.nlm.state is CBState.CLOSED

    def test_load_restores_all_breakers(self, tmp_path: Path) -> None:
        path = tmp_path / "pipeline_state.json"
        source = CircuitBreakerRegistry(state_path=path)
        source.nlm.state = CBState.OPEN
        source.nlm.failure_count = 3
        source.nlm.opened_at = "2026-07-18T00:00:00+00:00"
        source.source.state = CBState.OPEN
        source.integration.state = CBState.HALF_OPEN
        source.save()

        loaded = CircuitBreakerRegistry.load(path)

        assert loaded.nlm.state is CBState.OPEN
        assert loaded.nlm.failure_count == 3
        assert loaded.source.state is CBState.OPEN
        assert loaded.integration.state is CBState.HALF_OPEN

    def test_atomic_write_removes_temp_file_when_replace_fails(
        self,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "pipeline_state.json"
        registry = CircuitBreakerRegistry(state_path=path)

        with patch.object(Path, "replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                registry.save()

        assert not path.exists()
        assert not path.with_suffix(".json.tmp").exists()


class TestPipelineCircuitBreakerIntegration:
    @staticmethod
    def _open_registry(tmp_path: Path) -> CircuitBreakerRegistry:
        return CircuitBreakerRegistry(
            nlm=_breaker(
                state=CBState.OPEN,
                opened_at=datetime.now(tz=timezone.utc).isoformat(),
            ),
            state_path=tmp_path / "state.json",
        )

    @pytest.mark.parametrize(("module_name", "class_name"), PIPELINE_CASES)
    def test_open_breaker_blocks_before_query(
        self,
        tmp_path: Path,
        module_name: str,
        class_name: str,
    ) -> None:
        pipeline_module = importlib.import_module(module_name)
        pipeline_class = getattr(pipeline_module, class_name)
        pipeline = pipeline_class(
            state_file=str(tmp_path / "state.json"),
            claims_file=str(tmp_path / "claims.jsonl"),
            registry_file=str(tmp_path / "registry.json"),
            dry_run=True,
        )
        pipeline.circuit_breakers = self._open_registry(tmp_path)

        with (
            patch.object(pipeline, "_preflight", return_value=True),
            patch.object(pipeline, "_run_query") as run_query,
            patch.object(pipeline, "save_state"),
            patch.object(pipeline_module, "load_claims_count", return_value=0),
        ):
            result = pipeline.run()

        assert result["halted_at"] == "l1_circuit_open"
        assert result["degradation"] == "DEGRADED_L1"
        run_query.assert_not_called()

    @pytest.mark.parametrize(("module_name", "class_name"), PIPELINE_CASES)
    def test_run_exception_fails_reserved_half_open_probe(
        self,
        tmp_path: Path,
        module_name: str,
        class_name: str,
    ) -> None:
        pipeline_module = importlib.import_module(module_name)
        pipeline_class = getattr(pipeline_module, class_name)
        pipeline = pipeline_class(
            state_file=str(tmp_path / "state.json"),
            claims_file=str(tmp_path / "claims.jsonl"),
            registry_file=str(tmp_path / "registry.json"),
            dry_run=True,
        )
        registry = CircuitBreakerRegistry(
            nlm=_breaker(state=CBState.HALF_OPEN),
            state_path=tmp_path / "state.json",
        )
        pipeline.circuit_breakers = registry

        with (
            patch.object(pipeline, "_preflight", return_value=True),
            patch.object(
                pipeline,
                "_today_cluster",
                side_effect=RuntimeError("cluster lookup failed"),
            ),
            patch.object(pipeline, "save_state"),
            patch.object(pipeline_module, "load_claims_count", return_value=0),
        ):
            result = pipeline.run()

        assert result["error"] == "cluster lookup failed"
        assert result["degradation"] == "DEGRADED_L2"
        assert registry.nlm.state is CBState.OPEN
        assert registry.nlm.should_allow_request() is False
