"""Cell pulse observatory emitter.

Writes pulse events directly to the EventBus events_outbox via asyncpg,
then triggers pg_notify on the 'cell_pulse_observed' channel. Designed
to run inside any cell process (standalone LaunchAgent or in-app), with
NO dependency on backend-rag's Python package — that was BLOCKER B1
from the 2026-05-01 cross-LLM review.

Failures are swallowed (WARN log) — pulse loop must NEVER block on
observability.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_pool_lock_pid: Optional[int] = None  # detect fork without inherit


def is_enabled() -> bool:
    """Return True iff CELL_OBSERVATORY_EMIT env var is the literal 'true' (case-insensitive)."""
    return os.environ.get("CELL_OBSERVATORY_EMIT", "").lower() == "true"
