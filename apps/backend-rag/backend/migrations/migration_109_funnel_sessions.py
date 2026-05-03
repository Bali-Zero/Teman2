"""
Migration 109: funnel_sessions — generalizzazione cross-funnel.

Crea la tabella `funnel_sessions` per tracciare sessioni anonime (pre-auth)
su tutti e 4 i funnel: visa, kbli, tax, property, + home.
Estende il pattern già in prod per `visa_oracle_sessions` (migration 080b).

Rapporto con visa_oracle_sessions:
- visa_oracle_sessions resta in uso per quiz/chat dettagli specifici del visa
- funnel_sessions è la tabella di lead-tracking cross-funnel, indicizzata per
  `bz_session` cookie
- Bridge: quando user converte (SSO login), `converted_to_client_id` viene popolato

Schema:
- session_id VARCHAR(64) PK: UUID v4 dal cookie `bz_session`
- funnel ENUM: visa, kbli, tax, property, home
- step_state JSONB: stato corrente (quali step fatti)
- lead_profile JSONB: dati estratti dal quiz/tool (nationality, visa_recommended, ...)
- first_touched_at, last_touched_at: timestamp
- converted_to_client_id UUID NULL: FK a clients.id quando SSO login completato
- ip_hash VARCHAR(64): SHA-256 per abuse/rate-limit (no PII)
- expires_at: 90-day TTL

Reference: design 2026-04-17-v2-subdomain-rollout-design.md §3.1

Author: Claude Opus 4.7
Date: 2026-04-17
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    # Postgres non supporta CREATE TYPE IF NOT EXISTS; emulate via DO block
    await conn.execute("""
        DO $$ BEGIN
            CREATE TYPE funnel_type_enum AS ENUM (
                'visa', 'kbli', 'tax', 'property', 'home'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS funnel_sessions (
            session_id              VARCHAR(64) PRIMARY KEY,
            funnel                  funnel_type_enum NOT NULL,
            step_state              JSONB DEFAULT '{}'::jsonb,
            lead_profile            JSONB DEFAULT '{}'::jsonb,
            first_touched_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_touched_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            converted_to_client_id  UUID NULL,
            ip_hash                 VARCHAR(64),
            expires_at              TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_funnel_sessions_funnel_last_touched
        ON funnel_sessions (funnel, last_touched_at DESC);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_funnel_sessions_converted
        ON funnel_sessions (converted_to_client_id)
        WHERE converted_to_client_id IS NOT NULL;
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_funnel_sessions_expires_at
        ON funnel_sessions (expires_at);
    """)

    # Attribution table — permette query "da quale funnel è arrivato cliente X"
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS funnel_attributions (
            id                      BIGSERIAL PRIMARY KEY,
            client_id               UUID NOT NULL,
            session_id              VARCHAR(64) NOT NULL,
            first_funnel            funnel_type_enum NOT NULL,
            touchpoints             JSONB DEFAULT '[]'::jsonb,
            first_touch_at          TIMESTAMP WITH TIME ZONE NOT NULL,
            converted_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_funnel_attributions_client
        ON funnel_attributions (client_id);
    """)

    logger.info("migration 109: funnel_sessions + funnel_attributions created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS funnel_attributions;")
    await conn.execute("DROP TABLE IF EXISTS funnel_sessions;")
    await conn.execute("DROP TYPE IF EXISTS funnel_type_enum;")
    logger.info("migration 109: rolled back")
