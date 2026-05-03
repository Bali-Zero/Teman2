"""
Migration 114: pii_violations — durable audit trail of PII matches that
PIIScannerMiddleware redacted from outbound responses.

Rationale (UU PDP No. 27/2022 Art. 35/36/38 + PB1 §2):
The in-memory PII scanner already logs violations to console, but those
lines are lost on Fly rolling deploy and cannot be aggregated over time.
This table makes the audit persistent so we can answer:

  - which endpoints leak PII most often?
  - which pattern (KTP / NPWP / Passport / Phone / Email) dominates?
  - what is the 7-day trend after a model or prompt change?

Schema:
- id               BIGSERIAL PK
- request_id       VARCHAR(64)   — correlation ID from RequestTracingMiddleware
                                  (contextvar-backed, nullable when scanner
                                  runs outside a request scope)
- route            VARCHAR(256)  — request path (e.g. "/api/agentic/ask")
- pattern_matched  VARCHAR(64)   — recognizer name (ID_KTP, ID_NPWP, ...)
- severity         VARCHAR(16)   — "low" | "medium" | "high" | "critical"
                                  (policy: high for Indonesian gov IDs, medium
                                  for contact data)
- user_hash        VARCHAR(64)   — sha256(user_email or client_ip) NULL ok.
                                  Hashed so the violation log itself doesn't
                                  become a new PII vector.
- occurrence_count INT           — how many times this pattern appeared in
                                  the SAME response body (1 row per pattern
                                  per request, not per match)
- created_at       TIMESTAMPTZ   default NOW()

Indexes:
- (created_at DESC, route)             → admin "recent violations" query
- (pattern_matched, created_at DESC)   → "which pattern dominates" agg
- (request_id)                         → lookup by correlation ID

Rollback drops the table.

Author: Claude Opus 4.7
Date: 2026-04-18
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS pii_violations (
            id                BIGSERIAL PRIMARY KEY,
            request_id        VARCHAR(64),
            route             VARCHAR(256) NOT NULL,
            pattern_matched   VARCHAR(64)  NOT NULL,
            severity          VARCHAR(16)  NOT NULL DEFAULT 'medium',
            user_hash         VARCHAR(64),
            occurrence_count  INTEGER      NOT NULL DEFAULT 1,
            created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pii_violations_recent
        ON pii_violations (created_at DESC, route);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pii_violations_pattern_trend
        ON pii_violations (pattern_matched, created_at DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pii_violations_request
        ON pii_violations (request_id);
    """)
    logger.info("migration 114: pii_violations created with 3 indexes")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS pii_violations;")
    logger.info("migration 114: rolled back")
