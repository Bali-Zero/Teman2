"""Parser for WEEKLY CASHOUT sheet rows.

BZ schema (9 cols): NAME | PROCESS | PNBP | URGENT | RPTKA/IMTA | TOTAL_INCOME | MARGIN_BS | MARGIN_BZ | NOTE
BS schema (7 cols): NAME | PROCESS | PNBP | URGENT | RPTKA/IMTA | MARGIN_BS | FINAL_PRICE
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CashoutRow:
    entity: str  # 'BZ' | 'BS'
    row_index: int
    client_name: str
    process: str | None
    pnbp_idr: int
    urgent_idr: int
    rptka_imta_idr: int
    total_income_idr: int  # only BZ, 0 for BS
    margin_bs_idr: int
    margin_bz_idr: int     # only BZ, 0 for BS
    final_price_idr: int   # only BS, 0 for BZ
    note: str | None


def parse_idr(value: Any) -> int:
    """Parse IDR string like 'Rp1,000,000' to int.

    Returns 0 for empty/None/invalid.
    """
    if value is None:
        return 0
    s = str(value).strip()
    if not s or s in ("-", "—"):
        return 0
    cleaned = s.replace("Rp", "").replace(",", "").replace(".", "").strip()
    if not cleaned:
        return 0
    try:
        return int(cleaned)
    except ValueError:
        logger.warning("[CASHOUT] Failed to parse IDR: %r", value)
        return 0


def parse_bz_tab(rows: list[list[str]]) -> list[CashoutRow]:
    raise NotImplementedError


def parse_bs_tab(rows: list[list[str]]) -> list[CashoutRow]:
    raise NotImplementedError
