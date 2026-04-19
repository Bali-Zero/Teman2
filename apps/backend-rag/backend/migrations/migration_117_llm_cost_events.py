"""
Migration 117: llm_cost_events — indestructible cost ledger for every LLM call.

Every LLM call in the system (backend + Pro/Air cron agents) appends one
row here. Used for:
- Per-endpoint cost attribution (which feature is burning budget).
- Per-model / per-provider rollups (Gemini 3 Flash vs DeepSeek vs Claude OAuth).
- Alerting when hourly spend crosses a threshold.
- Reconciliation with provider invoices.

Persistence strategy (defense in depth) — see
``backend/services/observability/llm_cost_recorder.py``:
1. Prometheus counters (real-time dashboards).
2. This Postgres table (audit + aggregations).
3. Append-only JSONL on the `/data` volume (last-resort: survives DB outage).

Schema
------
- id               BIGSERIAL PK
- ts_utc           TIMESTAMPTZ NOT NULL (default NOW())
- provider         VARCHAR(32) NOT NULL — 'gemini' | 'deepseek' | 'claude_oauth' | 'openrouter' | 'ollama' | …
- model            VARCHAR(128) NOT NULL — model slug the provider sees
- input_tokens     INT NOT NULL (>=0)
- output_tokens    INT NOT NULL (>=0)
- cache_hit_tokens INT NOT NULL DEFAULT 0 — subset of input_tokens served from cache
- cost_usd         NUMERIC(12,6) NOT NULL — computed from pricing table at call time
- endpoint         VARCHAR(128) — caller module ('article_composer', 'conversations', …)
- request_id       VARCHAR(64) — correlation id if the caller has one
- success          BOOLEAN NOT NULL
- error_class      VARCHAR(64) — exception class name when success=FALSE
- latency_ms       INT NOT NULL (>=0) — wall-clock duration of the call

Indexes optimise the three hot query patterns:
- ``WHERE ts_utc BETWEEN ... ORDER BY ts_utc DESC`` (recent traffic)
- ``WHERE endpoint = ... AND ts_utc > now() - interval '1 day'`` (per-caller)
- ``WHERE model = ... AND ts_utc > now() - interval '1 day'`` (per-model)

Author: Claude Opus 4.7
Date: 2026-04-18
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_cost_events (
            id               BIGSERIAL PRIMARY KEY,
            ts_utc           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            provider         VARCHAR(32) NOT NULL,
            model            VARCHAR(128) NOT NULL,
            input_tokens     INT NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
            output_tokens    INT NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
            cache_hit_tokens INT NOT NULL DEFAULT 0 CHECK (cache_hit_tokens >= 0),
            cost_usd         NUMERIC(12, 6) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
            endpoint         VARCHAR(128),
            request_id       VARCHAR(64),
            success          BOOLEAN NOT NULL,
            error_class      VARCHAR(64),
            latency_ms       INT NOT NULL DEFAULT 0 CHECK (latency_ms >= 0)
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_llm_cost_ts
        ON llm_cost_events (ts_utc DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_llm_cost_endpoint_ts
        ON llm_cost_events (endpoint, ts_utc DESC)
        WHERE endpoint IS NOT NULL;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_llm_cost_model_ts
        ON llm_cost_events (model, ts_utc DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_llm_cost_provider_ts
        ON llm_cost_events (provider, ts_utc DESC);
    """)
    logger.info("✅ Migration 117: llm_cost_events table + 4 indexes created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS llm_cost_events CASCADE;")
    logger.info("Migration 117 rollback: llm_cost_events dropped")
