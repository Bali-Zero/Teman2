"""Migration 122: add D1 Tourism (Multiple Entry) tiers to practice_types.

Bali Zero sells D1 Multiple-Entry Tourism in three validity tiers:
  - 1 Year  →  6.000.000 IDR
  - 2 Years →  8.000.000 IDR
  - 5 Years → 14.000.000 IDR

Same pattern as D12 (1y / 2y). migration_066 is the idempotent seed, but live
databases need an explicit insert since 066 only runs at first boot.

Uses ON CONFLICT(code) DO UPDATE so rerunning is safe and picks up price
changes if someone pre-seeded the rows manually.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

SERVICES = [
    {
        "code": "visa_d1_tourism_1yr",
        "name": "D1 Tourism (1 Year)",
        "description": None,
        "category": "multiple_entry_visa",
        "base_price": 6000000,
        "typical_duration_days": 365,
    },
    {
        "code": "visa_d1_tourism_2yr",
        "name": "D1 Tourism (2 Years)",
        "description": None,
        "category": "multiple_entry_visa",
        "base_price": 8000000,
        "typical_duration_days": 730,
    },
    {
        "code": "visa_d1_tourism_5yr",
        "name": "D1 Tourism (5 Years)",
        "description": None,
        "category": "multiple_entry_visa",
        "base_price": 14000000,
        "typical_duration_days": 1825,
    },
]


async def apply(conn: Any) -> None:
    for svc in SERVICES:
        await conn.execute(
            """
            INSERT INTO practice_types (
                code, name, description, category, base_price,
                typical_duration_days, is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, true)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                category = EXCLUDED.category,
                base_price = EXCLUDED.base_price,
                typical_duration_days = EXCLUDED.typical_duration_days,
                is_active = true,
                updated_at = CURRENT_TIMESTAMP
            """,
            svc["code"],
            svc["name"],
            svc["description"],
            svc["category"],
            svc["base_price"],
            svc["typical_duration_days"],
        )
    logger.info(
        "Migration 122: D1 Tourism tiers (1y/2y/5y) inserted into practice_types"
    )


async def rollback(conn: Any) -> None:
    codes = [svc["code"] for svc in SERVICES]
    await conn.execute(
        "DELETE FROM practice_types WHERE code = ANY($1::text[])",
        codes,
    )
    logger.info("Migration 122 rollback: D1 Tourism tiers removed")
