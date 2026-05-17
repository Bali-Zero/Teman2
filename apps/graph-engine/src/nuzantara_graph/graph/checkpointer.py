"""LangGraph checkpointer factory.

Checkpoint persistence is feature-gated and disabled by default. Enabling
Postgres requires a dedicated checkpointer DSN so the graph cannot silently
write checkpoints to the app database just because ``database_url`` has a
development default.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from typing import Any

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver

from nuzantara_graph.config import Settings, settings

logger = structlog.get_logger()


class CheckpointerError(RuntimeError):
    """Base exception for graph checkpointer setup failures."""


class CheckpointerConfigurationError(CheckpointerError):
    """Raised when checkpoint persistence is enabled with invalid config."""


class CheckpointerDependencyError(CheckpointerError):
    """Raised when the selected checkpoint backend is not installed."""


@contextmanager
def get_checkpointer(config: Settings | None = None) -> Iterator[BaseCheckpointSaver | None]:
    """Yield a configured LangGraph checkpointer or ``None``.

    The function is a context manager because ``PostgresSaver.from_conn_string``
    owns a database connection. Callers that compile a graph with persistence
    should keep this context open for the lifetime of the compiled graph.
    """
    cfg = config or settings

    if not cfg.checkpointer_enabled:
        logger.info("graph_checkpointer_disabled")
        yield None
        return

    if cfg.checkpointer_backend == "memory":
        saver = _make_memory_saver()
        logger.warning("graph_checkpointer_memory_enabled")
        yield saver
        return

    if cfg.checkpointer_backend == "postgres":
        database_url = cfg.checkpointer_database_url.strip()
        if not database_url:
            raise CheckpointerConfigurationError(
                "NUZANTARA_CHECKPOINTER_DATABASE_URL is required when "
                "NUZANTARA_CHECKPOINTER_ENABLED=true and backend=postgres"
            )

        postgres_saver = _load_postgres_saver()
        logger.info("graph_checkpointer_postgres_enabled")
        with postgres_saver.from_conn_string(
            database_url,
            pipeline=cfg.checkpointer_postgres_pipeline,
        ) as saver:
            yield saver
        return

    raise CheckpointerConfigurationError(
        f"Unsupported checkpointer backend: {cfg.checkpointer_backend}"
    )


def _load_postgres_saver() -> type[Any]:
    try:
        module = import_module("langgraph.checkpoint.postgres")
    except ModuleNotFoundError as exc:
        raise CheckpointerDependencyError(
            "Install langgraph-checkpoint-postgres to enable Postgres checkpointing"
        ) from exc
    return module.PostgresSaver


def _make_memory_saver() -> BaseCheckpointSaver:
    try:
        module = import_module("langgraph.checkpoint.memory")
    except ModuleNotFoundError as exc:
        raise CheckpointerDependencyError(
            "langgraph.checkpoint.memory is required for the explicit memory checkpointer"
        ) from exc

    saver_cls = getattr(module, "MemorySaver", None) or getattr(module, "InMemorySaver", None)
    if saver_cls is None:
        raise CheckpointerDependencyError("LangGraph memory checkpointer is unavailable")
    return saver_cls()
