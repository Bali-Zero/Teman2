"""Historical persistence adapter for the ``garuda_voa_checks`` archive.

The public creator and result pages are retired. Existing rows remain
readable through the owner-only archive GET; the active internal preview is
stateless and never calls ``save_voa_check``. Historical counters remain in
the row shape for backward-compatible decoding.

The verdict (decision + Safe Clock dates) is FROZEN at submission time and
simply read back on owner GET — it is not recomputed against "today" during
archive review.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from backend.services.garuda_flow.eligibility import Decision
from backend.services.garuda_flow.intake import CaseType, Purpose
from backend.services.visa_check.repository import new_visa_hash

logger = logging.getLogger(__name__)

__all__ = ["GarudaVoaRepository", "VoaCheckResult", "new_visa_hash"]


@dataclass(frozen=True)
class VoaCheckResult:
    hash: str
    case_type: CaseType
    nationality: str
    entry_date: date
    passport_expiry_date: date
    voa_expiry_date: date | None
    extension_already_used: bool
    purpose: Purpose
    travellers: int
    self_pay: bool
    decision: Decision
    decline_reasons: list[str]
    decline_codes: list[str]
    expiry_date: date
    last_legal_day: date
    expiry_is_estimated: bool
    published_filing_deadline: date
    # Issuance-only (owner ruling 2026-07-27, `garuda_flow.operating_calendar`):
    # Bali Zero's OWN submit-by commitment, never an immigration deadline.
    # Always None for an extension case, and for an issuance case whose
    # entry date is outside the materialized operating-calendar coverage.
    submit_by_date: date | None
    price_idr: int | None
    price_source: str | None
    view_count: int
    share_count: int
    created_at: datetime


class GarudaVoaRepository:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def save_voa_check(
        self,
        *,
        case_type: CaseType,
        nationality: str,
        entry_date: date,
        passport_expiry_date: date,
        voa_expiry_date: date | None,
        extension_already_used: bool,
        purpose: Purpose,
        travellers: int,
        self_pay: bool,
        decision: Decision,
        decline_reasons: list[str],
        decline_codes: list[str],
        expiry_date: date,
        last_legal_day: date,
        expiry_is_estimated: bool,
        published_filing_deadline: date,
        submit_by_date: date | None,
        price_idr: int | None,
        price_source: str | None,
    ) -> VoaCheckResult:
        hash_ = new_visa_hash()
        created_at = datetime.utcnow()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO garuda_voa_checks
                    (hash, created_at,
                     case_type, nationality, entry_date, passport_expiry_date,
                     voa_expiry_date, extension_already_used, purpose,
                     travellers, self_pay,
                     decision, decline_reasons, decline_codes,
                     expiry_date, last_legal_day, expiry_is_estimated,
                     published_filing_deadline, submit_by_date,
                     price_idr, price_source)
                VALUES ($1, $2,
                        $3, $4, $5, $6,
                        $7, $8, $9,
                        $10, $11,
                        $12, $13::jsonb, $14::jsonb,
                        $15, $16, $17,
                        $18, $19,
                        $20, $21)
                """,
                hash_,
                created_at,
                case_type.value,
                nationality,
                entry_date,
                passport_expiry_date,
                voa_expiry_date,
                extension_already_used,
                purpose.value,
                travellers,
                self_pay,
                decision.value,
                json.dumps(decline_reasons),
                json.dumps(decline_codes),
                expiry_date,
                last_legal_day,
                expiry_is_estimated,
                published_filing_deadline,
                submit_by_date,
                price_idr,
                price_source,
            )
        return VoaCheckResult(
            hash=hash_,
            case_type=case_type,
            nationality=nationality,
            entry_date=entry_date,
            passport_expiry_date=passport_expiry_date,
            voa_expiry_date=voa_expiry_date,
            extension_already_used=extension_already_used,
            purpose=purpose,
            travellers=travellers,
            self_pay=self_pay,
            decision=decision,
            decline_reasons=decline_reasons,
            decline_codes=decline_codes,
            expiry_date=expiry_date,
            last_legal_day=last_legal_day,
            expiry_is_estimated=expiry_is_estimated,
            published_filing_deadline=published_filing_deadline,
            submit_by_date=submit_by_date,
            price_idr=price_idr,
            price_source=price_source,
            view_count=0,
            share_count=0,
            created_at=created_at,
        )

    async def get_voa_check(self, hash_: str) -> VoaCheckResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT hash, created_at, view_count, share_count,
                       case_type, nationality, entry_date, passport_expiry_date,
                       voa_expiry_date, extension_already_used, purpose,
                       travellers, self_pay,
                       decision, decline_reasons, decline_codes,
                       expiry_date, last_legal_day, expiry_is_estimated,
                       published_filing_deadline, submit_by_date,
                       price_idr, price_source
                  FROM garuda_voa_checks
                 WHERE hash = $1
                """,
                hash_,
            )
        if not row:
            return None

        reasons = row["decline_reasons"]
        if isinstance(reasons, str):
            reasons = json.loads(reasons)

        codes = row["decline_codes"]
        if isinstance(codes, str):
            codes = json.loads(codes)

        return VoaCheckResult(
            hash=row["hash"],
            case_type=CaseType(row["case_type"]),
            nationality=row["nationality"],
            entry_date=row["entry_date"],
            passport_expiry_date=row["passport_expiry_date"],
            voa_expiry_date=row["voa_expiry_date"],
            extension_already_used=row["extension_already_used"],
            purpose=Purpose(row["purpose"]),
            travellers=row["travellers"],
            self_pay=row["self_pay"],
            decision=Decision(row["decision"]),
            decline_reasons=list(reasons or []),
            decline_codes=list(codes or []),
            expiry_date=row["expiry_date"],
            last_legal_day=row["last_legal_day"],
            expiry_is_estimated=row["expiry_is_estimated"],
            published_filing_deadline=row["published_filing_deadline"],
            submit_by_date=row["submit_by_date"],
            price_idr=row["price_idr"],
            price_source=row["price_source"],
            view_count=row["view_count"] or 0,
            share_count=row["share_count"] or 0,
            created_at=row["created_at"],
        )
