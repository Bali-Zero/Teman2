"""Lifecycle contracts for the full and light service initializers."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.setup import service_initializer as initializer


def _module(name: str, **attributes: Any) -> ModuleType:
    module = ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    return module


def _configure_full_initializer(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SimpleNamespace, dict[str, Any]]:
    app = SimpleNamespace(
        state=SimpleNamespace(
            services_initialized=False,
            redis_manager=SimpleNamespace(available=True),
            cultural_rag=object(),
            alert_service=None,
            memory_service=None,
            intelligent_router=None,
            tool_executor=None,
        )
    )

    search_service = object()
    ai_client = object()
    tool_executor = object()
    query_router = object()
    db_pool = object()

    calls: dict[str, Any] = {
        "redis": MagicMock(),
        "critical": AsyncMock(return_value=(search_service, ai_client)),
        "tool_stack": AsyncMock(return_value=tool_executor),
        "faq": AsyncMock(),
        "rag": AsyncMock(return_value=query_router),
        "specialized": AsyncMock(return_value=(object(), object(), object())),
        "database": AsyncMock(return_value=db_pool),
        "crm": AsyncMock(),
        "intelligent": AsyncMock(),
        "channel": AsyncMock(),
    }
    monkeypatch.setattr(initializer, "_initialize_redis_manager", calls["redis"])
    monkeypatch.setattr(initializer, "_init_critical_services", calls["critical"])
    monkeypatch.setattr(initializer, "_init_tool_stack", calls["tool_stack"])
    monkeypatch.setattr(initializer, "initialize_faq_cache_service", calls["faq"])
    monkeypatch.setattr(initializer, "_init_rag_components", calls["rag"])
    monkeypatch.setattr(initializer, "_init_specialized_agents", calls["specialized"])
    monkeypatch.setattr(initializer, "initialize_database_services", calls["database"])
    monkeypatch.setattr(initializer, "initialize_crm_and_memory_services", calls["crm"])
    monkeypatch.setattr(initializer, "initialize_intelligent_router", calls["intelligent"])
    monkeypatch.setattr(initializer, "initialize_channel_router", calls["channel"])

    confirmation_service = SimpleNamespace(start=AsyncMock())
    health_monitor = SimpleNamespace(set_services=MagicMock(), start=AsyncMock())
    registry = MagicMock()
    registry.get_status.return_value = {"overall": "healthy"}
    monkeypatch.setattr(initializer, "service_registry", registry)

    modules = {
        "backend.services.rag.kg_cache": _module(
            "backend.services.rag.kg_cache",
            start_invalidation_listener=AsyncMock(return_value=object()),
        ),
        "backend.services.agents.confirmation_service": _module(
            "backend.services.agents.confirmation_service",
            ConfirmationService=MagicMock(return_value=confirmation_service),
        ),
        "backend.services.agents.tool_authorizer": _module(
            "backend.services.agents.tool_authorizer",
            ToolAuthorizer=MagicMock(return_value=object()),
        ),
        "backend.services.rag.agentic.tool_executor": _module(
            "backend.services.rag.agentic.tool_executor",
            configure_tool_executor=MagicMock(),
        ),
        "backend.services.crm.collaborator_service": _module(
            "backend.services.crm.collaborator_service",
            CollaboratorService=MagicMock(return_value=object()),
        ),
        "backend.services.monitoring.alert_service": _module(
            "backend.services.monitoring.alert_service",
            AlertService=MagicMock(return_value=object()),
        ),
        "backend.services.monitoring.health_monitor": _module(
            "backend.services.monitoring.health_monitor",
            HealthMonitor=MagicMock(return_value=health_monitor),
        ),
        "backend.services.misc.whatsapp_subscription_guardian": _module(
            "backend.services.misc.whatsapp_subscription_guardian",
            start_whatsapp_subscription_guardian_task=MagicMock(return_value=None),
        ),
        "backend.services.knowledge_graph.incremental_builder": _module(
            "backend.services.knowledge_graph.incremental_builder",
            start_kg_incremental_task=MagicMock(return_value=None),
        ),
        "backend.services.newsletter.daily_task": _module(
            "backend.services.newsletter.daily_task",
            start_newsletter_daily_task=MagicMock(return_value=None),
        ),
        "backend.app.agents.graph": _module(
            "backend.app.agents.graph",
            set_db_pool=MagicMock(),
            set_llm_gateway=MagicMock(),
            set_search_service=MagicMock(),
        ),
        "backend.services.rag.agentic.llm_gateway": _module(
            "backend.services.rag.agentic.llm_gateway",
            LLMGateway=MagicMock(return_value=object()),
        ),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    monkeypatch.setenv("DISABLE_BACKGROUND_WORKERS", "1")
    monkeypatch.setenv("SELF_HEALING_ENABLED", "false")
    return app, calls


@pytest.mark.asyncio
async def test_initialize_services_completes_once_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, calls = _configure_full_initializer(monkeypatch)

    await initializer.initialize_services(app)
    await initializer.initialize_services(app)

    assert app.state.services_initialized is True
    assert app.state.olympus is None
    calls["redis"].assert_called_once_with(app, "full")
    calls["critical"].assert_awaited_once_with(app)
    calls["tool_stack"].assert_awaited_once_with(app)
    calls["database"].assert_awaited_once_with(app)
    calls["channel"].assert_awaited_once_with(
        app, calls["critical"].return_value[1], calls["database"].return_value
    )


@pytest.mark.asyncio
async def test_initialize_services_does_not_mark_failed_critical_startup_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, calls = _configure_full_initializer(monkeypatch)
    calls["critical"].side_effect = RuntimeError("critical dependency unavailable")

    with pytest.raises(RuntimeError, match="critical dependency unavailable"):
        await initializer.initialize_services(app)

    assert app.state.services_initialized is False
    calls["tool_stack"].assert_not_awaited()


def test_clean_database_dsn_removes_only_sslmode() -> None:
    dsn, ssl_context = initializer._clean_database_dsn(
        "postgresql://user:pass@db.example/test?sslmode=disable&application_name=api"
    )

    assert dsn == "postgresql://user:pass@db.example/test?application_name=api"
    assert ssl_context is False

    unchanged_dsn, default_ssl_context = initializer._clean_database_dsn(
        "postgresql://user:pass@db.example/test"
    )
    assert unchanged_dsn == "postgresql://user:pass@db.example/test"
    assert default_ssl_context is None


@pytest.mark.asyncio
async def test_initialize_services_light_configures_pool_codecs_and_kill_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = SimpleNamespace(state=SimpleNamespace())
    db_pool = object()
    create_pool = AsyncMock(return_value=db_pool)
    registry = MagicMock()
    cache = object()

    monkeypatch.setattr(
        initializer.settings, "database_url", "postgresql://db/test?sslmode=disable"
    )
    monkeypatch.setattr(initializer.asyncpg, "create_pool", create_pool)
    monkeypatch.setattr(initializer, "service_registry", registry)
    monkeypatch.setattr(initializer, "_initialize_redis_manager", MagicMock())
    monkeypatch.setenv("DISABLE_BACKGROUND_WORKERS", "1")
    monkeypatch.setitem(
        sys.modules,
        "backend.core.cache",
        _module("backend.core.cache", CacheService=MagicMock(return_value=cache)),
    )

    await initializer.initialize_services_light(app)

    pool_options = create_pool.await_args.kwargs
    assert pool_options["dsn"] == "postgresql://db/test"
    assert pool_options["ssl"] is False
    assert pool_options["statement_cache_size"] == 0
    assert pool_options["min_size"] == 2
    assert pool_options["max_size"] == 10

    connection = SimpleNamespace(execute=AsyncMock(), set_type_codec=AsyncMock())
    await pool_options["init"](connection)
    connection.execute.assert_awaited_once_with("SET statement_timeout = '30s'")
    assert [call.args[0] for call in connection.set_type_codec.await_args_list] == ["jsonb", "json"]

    assert app.state.db_pool is db_pool
    assert app.state.cache is cache
    assert app.state.ts_service is None
    assert app.state.attendance_monitor is None
    assert app.state.olympus is None
    assert app.state.search_service is None
    assert app.state.ai_client is None
    assert app.state.orchestrator is None
    registry.register.assert_any_call("database", initializer.ServiceStatus.HEALTHY)
    registry.register.assert_any_call("cache", initializer.ServiceStatus.HEALTHY, critical=False)


@pytest.mark.asyncio
async def test_initialize_services_light_cache_failure_is_non_critical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = SimpleNamespace(state=SimpleNamespace())
    monkeypatch.setattr(initializer.settings, "database_url", "postgresql://db/test")
    monkeypatch.setattr(initializer.asyncpg, "create_pool", AsyncMock(return_value=object()))
    monkeypatch.setattr(initializer, "service_registry", MagicMock())
    monkeypatch.setattr(initializer, "_initialize_redis_manager", MagicMock())
    monkeypatch.setenv("DISABLE_BACKGROUND_WORKERS", "1")
    monkeypatch.setitem(
        sys.modules,
        "backend.core.cache",
        _module(
            "backend.core.cache",
            CacheService=MagicMock(side_effect=ConnectionError("redis unavailable")),
        ),
    )

    await initializer.initialize_services_light(app)

    assert app.state.cache is None
    assert app.state.db_pool is not None
    assert app.state.search_service is None


@pytest.mark.asyncio
async def test_initialize_services_light_database_failure_is_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = SimpleNamespace(state=SimpleNamespace())
    registry = MagicMock()
    monkeypatch.setattr(initializer.settings, "database_url", "postgresql://db/test")
    monkeypatch.setattr(
        initializer.asyncpg,
        "create_pool",
        AsyncMock(side_effect=ConnectionError("database unavailable")),
    )
    monkeypatch.setattr(initializer, "service_registry", registry)
    monkeypatch.setattr(initializer, "_initialize_redis_manager", MagicMock())

    with pytest.raises(RuntimeError, match="DB pool failed in light init"):
        await initializer.initialize_services_light(app)

    registry.register.assert_called_once_with(
        "database",
        initializer.ServiceStatus.UNAVAILABLE,
        error="database unavailable",
    )
