"""Migration 127: move `practice_types.base_price` of `company_pt_pma` 20M -> 25M.

Owner ruling 2026-10-12: Bali Zero's "New Company (PT PMA)" setup price moves
from IDR 20.000.000 to IDR 25.000.000. The canonical JSON
(`bali_zero_official_prices_2026.json`) is changed separately; this row was
seeded once by migration_066 and never re-synced, so the live table keeps
serving 20M.

Guarded `WHERE base_price = 20000000`: a no-op when the row is absent or its
price was already moved (or set to anything else by hand), so it is safe to
re-run and never clobbers a value it did not seed. `practices.quoted_price`
(historical client quotes) is deliberately NOT touched.

Cache: none keyed on this column is invalidated here (direct UPDATE).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

CODE = "company_pt_pma"
OLD_PRICE = 20_000_000
NEW_PRICE = 25_000_000


def _affected(status: str) -> int:
    """Rows affected from an asyncpg command tag such as 'UPDATE 1'."""
    try:
        return int(str(status).rsplit(" ", 1)[-1])
    except ValueError:
        return 0


async def apply(conn: Any) -> None:
    status = await conn.execute(
        "UPDATE practice_types SET base_price = $1, updated_at = CURRENT_TIMESTAMP "
        "WHERE code = $2 AND base_price = $3",
        NEW_PRICE,
        CODE,
        OLD_PRICE,
    )
    logger.info(
        "Migration 127: %s base_price %s -> %s, rows affected: %s",
        CODE,
        OLD_PRICE,
        NEW_PRICE,
        _affected(status),
    )


async def rollback(conn: Any) -> None:
    status = await conn.execute(
        "UPDATE practice_types SET base_price = $1, updated_at = CURRENT_TIMESTAMP "
        "WHERE code = $2 AND base_price = $3",
        OLD_PRICE,
        CODE,
        NEW_PRICE,
    )
    logger.info("Migration 127 rollback: rows affected: %s", _affected(status))
