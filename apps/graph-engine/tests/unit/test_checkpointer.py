"""Tests for the LangGraph checkpointer factory."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any

import pytest
from langgraph.checkpoint.base import empty_checkpoint

from nuzantara_graph.config import Settings
from nuzantara_graph.graph import checkpointer


def test_default_disabled_does_not_import_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    imports: list[str] = []

    def fail_on_import(name: str) -> Any:
        imports.append(name)
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(checkpointer, "import_module", fail_on_import, raising=False)

    with checkpointer.get_checkpointer(Settings(database_url="postgresql://default/db")) as saver:
        assert saver is None

    assert imports == []


def test_enabled_postgres_requires_dedicated_checkpointer_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_on_import(name: str) -> Any:
        raise AssertionError(f"unexpected import before config validation: {name}")

    monkeypatch.setattr(checkpointer, "import_module", fail_on_import, raising=False)
    cfg = Settings(
        checkpointer_enabled=True,
        checkpointer_backend="postgres",
        checkpointer_database_url="",
    )

    with pytest.raises(checkpointer.CheckpointerConfigurationError, match="CHECKPOINTER_DATABASE_URL"):
        with checkpointer.get_checkpointer(cfg):
            pass


def test_enabled_postgres_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_postgres(name: str) -> Any:
        if name == "langgraph.checkpoint.postgres":
            raise ModuleNotFoundError("No module named 'langgraph.checkpoint.postgres'")
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(checkpointer, "import_module", missing_postgres, raising=False)
    cfg = Settings(
        checkpointer_enabled=True,
        checkpointer_backend="postgres",
        checkpointer_database_url="postgresql://user:pass@localhost:5432/checkpoints",
    )

    with pytest.raises(checkpointer.CheckpointerDependencyError, match="langgraph-checkpoint-postgres"):
        with checkpointer.get_checkpointer(cfg):
            pass


def test_enabled_postgres_uses_configured_url_without_touching_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    calls: list[tuple[str, bool]] = []

    class FakePostgresSaver:
        @classmethod
        def from_conn_string(cls, conn_string: str, *, pipeline: bool = False) -> Any:
            calls.append((conn_string, pipeline))
            return nullcontext(sentinel)

    def fake_import(name: str) -> Any:
        assert name == "langgraph.checkpoint.postgres"
        return SimpleNamespace(PostgresSaver=FakePostgresSaver)

    monkeypatch.setattr(checkpointer, "import_module", fake_import, raising=False)
    cfg = Settings(
        checkpointer_enabled=True,
        checkpointer_backend="postgres",
        checkpointer_database_url="postgresql://user:pass@localhost:5432/checkpoints",
    )

    with checkpointer.get_checkpointer(cfg) as saver:
        assert saver is sentinel

    assert calls == [("postgresql://user:pass@localhost:5432/checkpoints", True)]


def test_explicit_memory_backend_round_trips_checkpoint_payload() -> None:
    cfg = Settings(checkpointer_enabled=True, checkpointer_backend="memory")

    with checkpointer.get_checkpointer(cfg) as saver:
        assert saver is not None
        config = {"configurable": {"thread_id": "unit-test", "checkpoint_ns": ""}}
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"]["payload"] = {"answer": "ok", "items": [1, 2]}
        checkpoint["channel_versions"]["payload"] = "1"

        saved_config = saver.put(config, checkpoint, {"source": "unit-test"}, {"payload": "1"})
        restored = saver.get(saved_config)

    assert restored is not None
    assert restored["channel_values"]["payload"] == {"answer": "ok", "items": [1, 2]}
