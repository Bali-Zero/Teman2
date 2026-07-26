"""Regression tests for FastAPI startup and shutdown lifecycle contracts."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.setup import app_factory


def _module(name: str, **attributes: Any) -> ModuleType:
    module = ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    return module


def _close_created_coroutine(coroutine: Any) -> MagicMock:
    close = getattr(coroutine, "close", None)
    if callable(close):
        close()
    task = MagicMock()
    task.done.return_value = True
    return task


def _configure_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SimpleNamespace, dict[str, Any]]:
    db_pool = SimpleNamespace(close=AsyncMock())
    scheduler = SimpleNamespace(stop=AsyncMock())
    calls: dict[str, Any] = {
        "initialize_services": AsyncMock(),
        "initialize_plugins": AsyncMock(),
        "init_scheduler": AsyncMock(return_value=scheduler),
        "webhook_start": AsyncMock(),
        "close_checkpointer": AsyncMock(),
        "close_crm_push": AsyncMock(),
        "close_qdrant": AsyncMock(),
        "close_kbli": AsyncMock(),
    }
    app = SimpleNamespace(state=SimpleNamespace(db_pool=db_pool, channel_router=None))

    observability = _module(
        "backend.core.observability",
        init_observability=MagicMock(),
        shutdown_observability=MagicMock(),
    )
    modules: dict[str, ModuleType] = {
        "backend.core.observability": observability,
        "backend.services.monitoring.alert_service": _module(
            "backend.services.monitoring.alert_service",
            AlertService=MagicMock(return_value=object()),
        ),
        "backend.app.setup.service_initializer": _module(
            "backend.app.setup.service_initializer",
            initialize_services=calls["initialize_services"],
        ),
        "backend.app.setup.plugin_initializer": _module(
            "backend.app.setup.plugin_initializer",
            initialize_plugins=calls["initialize_plugins"],
        ),
        "backend.app.modules.notifications.scheduler": _module(
            "backend.app.modules.notifications.scheduler",
            init_scheduler=calls["init_scheduler"],
        ),
        "backend.services.intake.writer": _module(
            "backend.services.intake.writer",
            log_writer_status=MagicMock(),
        ),
        "backend.services.rag.reranker": _module(
            "backend.services.rag.reranker",
            CrossEncoderReranker=MagicMock(return_value=SimpleNamespace(model=object())),
        ),
        "backend.services.workflow.checkpointer": _module(
            "backend.services.workflow.checkpointer",
            get_checkpointer=AsyncMock(return_value=object()),
            close_checkpointer=calls["close_checkpointer"],
        ),
        "backend.services.intake.crm_push": _module(
            "backend.services.intake.crm_push",
            close_client=calls["close_crm_push"],
        ),
        "backend.app.routers.health": _module(
            "backend.app.routers.health",
            close_qdrant_health_client=calls["close_qdrant"],
        ),
        "backend.app.routers.kbli_notebook": _module(
            "backend.app.routers.kbli_notebook",
            close_kbli_http_client=calls["close_kbli"],
        ),
        "backend.services.rag.kg_subgraph_property": _module(
            "backend.services.rag.kg_subgraph_property",
            close_property_subgraph_client=AsyncMock(),
        ),
        "backend.services.misc.autonomous_scheduler": _module(
            "backend.services.misc.autonomous_scheduler",
            close_scheduler_client=AsyncMock(),
        ),
        "backend.services.rag.agentic.tools": _module(
            "backend.services.rag.agentic.tools",
            close_agentic_tools_client=AsyncMock(),
        ),
        "backend.services.llm_clients.openrouter_client": _module(
            "backend.services.llm_clients.openrouter_client",
            openrouter_client=SimpleNamespace(close=AsyncMock()),
        ),
        "backend.llm.ollama_client": _module(
            "backend.llm.ollama_client",
            close_ollama_client=AsyncMock(),
        ),
        "backend.llm.deepseek_client": _module(
            "backend.llm.deepseek_client",
            close_deepseek_client=AsyncMock(),
        ),
        "backend.services.notifications.email_http": _module(
            "backend.services.notifications.email_http",
            close_email_client=AsyncMock(),
        ),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    monkeypatch.setattr(app_factory.asyncio, "to_thread", AsyncMock())
    monkeypatch.setenv("DISABLE_BACKGROUND_WORKERS", "1")
    return app, calls


@pytest.mark.asyncio
async def test_lifespan_success_sets_readiness_and_starts_plugins_and_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, calls = _configure_runtime(monkeypatch)

    async with app_factory.lifespan(app):
        await app.state._init_task
        assert app.state.startup_complete is True
        assert app.state.startup_failed is False
        assert app.state.process_mode == "rag"

    calls["initialize_services"].assert_awaited_once_with(app)
    calls["initialize_plugins"].assert_awaited_once_with(app)
    calls["init_scheduler"].assert_awaited_once_with(app.state.db_pool)
    calls["close_checkpointer"].assert_awaited_once()
    calls["close_crm_push"].assert_awaited_once()
    app.state.db_pool.close.assert_awaited_once()


@pytest.mark.parametrize("failure_mode", ["import", "runtime", "unexpected"])
@pytest.mark.asyncio
async def test_lifespan_critical_service_failure_sets_failed_state_and_stops_startup(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    app, calls = _configure_runtime(monkeypatch)
    if failure_mode == "import":
        monkeypatch.setitem(sys.modules, "backend.app.setup.service_initializer", None)
    elif failure_mode == "runtime":
        calls["initialize_services"].side_effect = RuntimeError(
            "database is unavailable"
        )
    else:
        calls["initialize_services"].side_effect = ValueError(
            "service configuration is invalid"
        )

    async with app_factory.lifespan(app):
        await app.state._init_task
        assert app.state.startup_complete is False
        assert app.state.startup_failed is True
        if failure_mode == "import":
            assert "import of backend.app.setup.service_initializer halted" in (
                app.state.startup_error
            )
        elif failure_mode == "runtime":
            assert app.state.startup_error == "database is unavailable"
        else:
            assert app.state.startup_error == "service configuration is invalid"

    calls["initialize_plugins"].assert_not_awaited()
    calls["init_scheduler"].assert_not_awaited()


@pytest.mark.parametrize("failure_mode", ["import", "initializer"])
@pytest.mark.asyncio
async def test_plugin_failure_is_non_critical_and_scheduler_still_starts(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    app, calls = _configure_runtime(monkeypatch)
    if failure_mode == "import":
        monkeypatch.setitem(sys.modules, "backend.app.setup.plugin_initializer", None)
    else:
        calls["initialize_plugins"].side_effect = RuntimeError("plugin discovery failed")

    async with app_factory.lifespan(app):
        await app.state._init_task
        assert app.state.plugin_registry is None
        assert app.state.startup_complete is True

    calls["init_scheduler"].assert_awaited_once_with(app.state.db_pool)


@pytest.mark.asyncio
async def test_scheduler_failure_is_non_critical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, calls = _configure_runtime(monkeypatch)
    calls["init_scheduler"].side_effect = RuntimeError("scheduler unavailable")

    async with app_factory.lifespan(app):
        await app.state._init_task
        assert app.state.startup_complete is True
        assert not hasattr(app.state, "notification_scheduler")


@pytest.mark.asyncio
async def test_webhook_failure_is_non_critical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, calls = _configure_runtime(monkeypatch)
    monkeypatch.delenv("DISABLE_BACKGROUND_WORKERS", raising=False)

    checkpointer_module = sys.modules["backend.services.workflow.checkpointer"]
    checkpointer_module.get_checkpointer = AsyncMock(side_effect=RuntimeError("queue unavailable"))
    monkeypatch.setitem(
        sys.modules,
        "backend.services.ingestion.legal_full_ingestion_worker",
        _module("backend.services.ingestion.legal_full_ingestion_worker"),
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.services.crm.practice_status_listener",
        _module(
            "backend.services.crm.practice_status_listener",
            PracticeStatusListener=MagicMock(side_effect=RuntimeError("listener unavailable")),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.services.events.event_bus",
        _module(
            "backend.services.events.event_bus",
            EventBus=MagicMock(side_effect=RuntimeError("event bus unavailable")),
        ),
    )
    webhook_processor = SimpleNamespace(start=calls["webhook_start"])
    calls["webhook_start"].side_effect = RuntimeError("webhook processor unavailable")
    monkeypatch.setitem(
        sys.modules,
        "backend.services.channels.webhook_processor",
        _module(
            "backend.services.channels.webhook_processor",
            WebhookProcessor=MagicMock(return_value=webhook_processor),
        ),
    )

    async with app_factory.lifespan(app):
        await app.state._init_task
        assert app.state.startup_complete is True
        assert not hasattr(app.state, "webhook_processor")

    calls["webhook_start"].assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_closes_sync_and_async_services_and_continues_after_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _ = _configure_runtime(monkeypatch)
    async_close = AsyncMock()
    sync_close = MagicMock()
    failing_close = MagicMock(side_effect=RuntimeError("close failed"))
    close_after_failure = MagicMock()
    app.state.search_service = SimpleNamespace(close=async_close)
    app.state.ai_client = SimpleNamespace(close=sync_close)
    app.state.memory_service = SimpleNamespace(close=failing_close)
    app.state.conversation_service = SimpleNamespace(close=close_after_failure)
    monkeypatch.setattr(app_factory.asyncio, "create_task", _close_created_coroutine)

    async with app_factory.lifespan(app):
        pass

    async_close.assert_awaited_once()
    sync_close.assert_called_once()
    failing_close.assert_called_once()
    close_after_failure.assert_called_once()
