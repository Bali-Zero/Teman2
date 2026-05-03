"""Persistence for the visa_checks table.

Append-only semantics for result rows. Edits happen only to
`view_count` and `share_count`.
"""

from __future__ import annotations

import json
import logging
import secrets
import string
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from backend.services.visa_check.catalogue import VisaType

logger = logging.getLogger(__name__)

_HASH_ALPHABET = string.ascii_lowercase + string.digits


def new_visa_hash(length: int = 16) -> str:
    """16-char alphanumeric hash. 36^16 ≈ 7.9×10^24 collision space."""
    return "".join(secrets.choice(_HASH_ALPHABET) for _ in range(length))


@dataclass(frozen=True)
class VisaClockResult:
    hash: str
    visa_type: VisaType
    entry_date: date
    expiry_date: date
    extensions_possible: int
    extension_days: int
    created_at: datetime


@dataclass(frozen=True)
class VisaMatchResult:
    hash: str
    nationality: str
    purpose: str
    duration_months: int
    budget_band: str
    recommended_visa: VisaType | None
    recommendation_reason: str
    pre_arrival_steps: list[str]
    alternatives: list[str]
    expected_arrival_date: date | None
    estimated_cost_idr: int | None
    created_at: datetime


class VisaCheckRepository:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def save_clock(
        self,
        *,
        visa_type: VisaType,
        entry_date: date,
        expiry_date: date,
        extensions_possible: int,
        extension_days: int,
        client_fp: str | None,
    ) -> VisaClockResult:
        hash_ = new_visa_hash()
        created_at = datetime.utcnow()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO visa_checks
                    (hash, branch, client_fp, created_at,
                     visa_type, entry_date, expiry_date,
                     extensions_possible, extension_days)
                VALUES ($1, 'clock', $2, $3, $4, $5, $6, $7, $8)
                """,
                hash_,
                client_fp,
                created_at,
                visa_type.value,
                entry_date,
                expiry_date,
                extensions_possible,
                extension_days,
            )
        return VisaClockResult(
            hash=hash_,
            visa_type=visa_type,
            entry_date=entry_date,
            expiry_date=expiry_date,
            extensions_possible=extensions_possible,
            extension_days=extension_days,
            created_at=created_at,
        )

    async def save_match(
        self,
        *,
        nationality: str,
        purpose: str,
        duration_months: int,
        budget_band: str,
        recommended_visa: VisaType | None,
        recommendation_reason: str,
        pre_arrival_steps: list[str],
        alternatives: list[str],
        expected_arrival_date: date | None,
        estimated_cost_idr: int | None,
        client_fp: str | None,
    ) -> VisaMatchResult:
        hash_ = new_visa_hash()
        created_at = datetime.utcnow()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO visa_checks
                    (hash, branch, client_fp, created_at,
                     nationality, purpose, duration_months, budget_band,
                     recommended_visa, recommendation_reason,
                     pre_arrival_steps, alternatives,
                     expected_arrival_date, estimated_cost_idr)
                VALUES ($1, 'match', $2, $3,
                        $4, $5, $6, $7,
                        $8, $9,
                        $10::jsonb, $11::jsonb,
                        $12, $13)
                """,
                hash_,
                client_fp,
                created_at,
                nationality,
                purpose,
                duration_months,
                budget_band,
                recommended_visa.value if recommended_visa else None,
                recommendation_reason,
                json.dumps(pre_arrival_steps),
                json.dumps(alternatives),
                expected_arrival_date,
                estimated_cost_idr,
            )
        return VisaMatchResult(
            hash=hash_,
            nationality=nationality,
            purpose=purpose,
            duration_months=duration_months,
            budget_band=budget_band,
            recommended_visa=recommended_visa,
            recommendation_reason=recommendation_reason,
            pre_arrival_steps=pre_arrival_steps,
            alternatives=alternatives,
            expected_arrival_date=expected_arrival_date,
            estimated_cost_idr=estimated_cost_idr,
            created_at=created_at,
        )

    async def load_clock(self, hash_: str) -> VisaClockResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT hash, visa_type, entry_date, expiry_date,
                       extensions_possible, extension_days, created_at
                  FROM visa_checks
                 WHERE hash = $1 AND branch = 'clock'
                """,
                hash_,
            )
        if not row:
            return None
        return VisaClockResult(
            hash=row["hash"],
            visa_type=VisaType(row["visa_type"]),
            entry_date=row["entry_date"],
            expiry_date=row["expiry_date"],
            extensions_possible=row["extensions_possible"] or 0,
            extension_days=row["extension_days"] or 0,
            created_at=row["created_at"],
        )

    async def load_match(self, hash_: str) -> VisaMatchResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT hash, nationality, purpose, duration_months, budget_band,
                       recommended_visa, recommendation_reason,
                       pre_arrival_steps, alternatives,
                       expected_arrival_date, estimated_cost_idr, created_at
                  FROM visa_checks
                 WHERE hash = $1 AND branch = 'match'
                """,
                hash_,
            )
        if not row:
            return None

        rec = VisaType(row["recommended_visa"]) if row["recommended_visa"] else None
        steps = row["pre_arrival_steps"]
        if isinstance(steps, str):
            steps = json.loads(steps)
        alts = row["alternatives"]
        if isinstance(alts, str):
            alts = json.loads(alts)

        return VisaMatchResult(
            hash=row["hash"],
            nationality=row["nationality"],
            purpose=row["purpose"],
            duration_months=row["duration_months"],
            budget_band=row["budget_band"],
            recommended_visa=rec,
            recommendation_reason=row["recommendation_reason"] or "",
            pre_arrival_steps=list(steps or []),
            alternatives=list(alts or []),
            expected_arrival_date=row["expected_arrival_date"],
            estimated_cost_idr=row["estimated_cost_idr"],
            created_at=row["created_at"],
        )

    async def bump_view_count(self, hash_: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE visa_checks SET view_count = view_count + 1 WHERE hash = $1",
                hash_,
            )
