"""Migration 123: add B1 Visa on Arrival (VOA) + VOA Extension to practice_types.

Bali Zero ora vende anche il VOA come pratica gestita:
  - B1 Visa on Arrival (VOA)              →   750.000 IDR — 30 days
  - B1 Visa on Arrival Extension (+30)    →   850.000 IDR — extension

Stesso pattern di migration_122 (D1 tiers). migration_066 e' l'idempotent seed
storico, ma i DB gia' in vita hanno bisogno di un insert esplicito perche' 066
gira solo al first boot. ON CONFLICT(code) DO UPDATE per essere rerunnable e
raccogliere eventuali aggiornamenti di prezzo.

Categoria scelta:
  - VOA base       → single_entry_visa (e' una pratica single-entry 30gg)
  - VOA Extension  → visa_extension    (estensione onshore)

Codes:
  - `visa_voa`       — nuovo, coerente con pattern `visa_<code>`
  - `voa_extension`  — gia' presente in `hr_bonus_rates` (migration_069b live).
                       Mantenuto per evitare orphan ledger.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

SERVICES = [
    {
        "code": "visa_voa",
        "name": "B1 Visa on Arrival (VOA)",
        "description": "Visa on Arrival 30 days, extendable once. Tourism / family / short business.",
        "category": "single_entry_visa",
        "base_price": 750000,
        "typical_duration_days": 30,
    },
    {
        "code": "voa_extension",
        "name": "B1 Visa on Arrival Extension",
        "description": "Onshore extension of VOA for +30 days.",
        "category": "visa_extension",
        "base_price": 850000,
        "typical_duration_days": 30,
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

    # HR bonus rate for visa_voa — Rp 30.000 (Antonello directive 2026-05-27).
    # voa_extension bonus rate already inserted by migration_069b (Rp 10.000).
    # Use the same ON CONFLICT pattern as 069b for rerunnability.
    await conn.execute(
        """
        INSERT INTO hr_bonus_rates (practice_type_code, amount_idr, effective_from, is_active, notes)
        VALUES ('visa_voa', 30000, '2026-01-01', TRUE, 'B1 Visa on Arrival (VOA) — airport pickup')
        ON CONFLICT (practice_type_code) DO UPDATE SET
            amount_idr = EXCLUDED.amount_idr,
            is_active = EXCLUDED.is_active,
            notes = EXCLUDED.notes,
            updated_at = NOW()
        """
    )

    logger.info(
        "Migration 123: VOA + VOA Extension inserted into practice_types; "
        "HR bonus rate for visa_voa added (Rp 30.000)"
    )


async def rollback(conn: Any) -> None:
    codes = [svc["code"] for svc in SERVICES]
    await conn.execute(
        "DELETE FROM hr_bonus_rates WHERE practice_type_code = 'visa_voa'"
    )
    await conn.execute(
        "DELETE FROM practice_types WHERE code = ANY($1::text[])",
        codes,
    )
    logger.info("Migration 123 rollback: VOA + VOA Extension + bonus rate removed")
