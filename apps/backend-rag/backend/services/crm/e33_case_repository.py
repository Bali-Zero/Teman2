"""E33CaseRepository — asyncpg persistence for e33_cases (migration 259).

Mirrors the AlertRepository pattern (pool or single-connection binding for
transaction-scoped tests). Serialization of history/evidence/dependents to
JSONB happens here; the lifecycle model in ``e33_lifecycle.py`` stays
persistence-free and pure.

No-custody SOP applies at this boundary too: the table stores evidence
REFERENCES (document ids, dates, confirmations) — never account numbers,
balances or amounts (enforced upstream by
``e33_lifecycle.validate_evidence_metadata``).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

import asyncpg

from backend.services.crm.e33_lifecycle import (
    DependentLink,
    E33Case,
    E33Stage,
    EvidenceKind,
    EvidenceRef,
    GuaranteeBasis,
    StageTransition,
)

logger = logging.getLogger(__name__)


# ── (de)serialization helpers ──────────────────────────────────────────────────


def _evidence_to_dict(e: EvidenceRef) -> dict[str, Any]:
    return {
        "evidence_id": e.evidence_id,
        "kind": e.kind.value,
        "document_ref": e.document_ref,
        "issued_date": e.issued_date.isoformat() if e.issued_date else None,
        "filed_date": e.filed_date.isoformat() if e.filed_date else None,
        "confirmed_by": e.confirmed_by,
        "metadata": e.metadata,
    }


def _evidence_from_dict(d: dict[str, Any]) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=d["evidence_id"],
        kind=EvidenceKind(d["kind"]),
        document_ref=d["document_ref"],
        issued_date=date.fromisoformat(d["issued_date"]) if d.get("issued_date") else None,
        filed_date=date.fromisoformat(d["filed_date"]) if d.get("filed_date") else None,
        confirmed_by=d.get("confirmed_by"),
        metadata=d.get("metadata") or {},
    )


def _dependent_to_dict(d: DependentLink) -> dict[str, Any]:
    return {"code": d.code, "client_id": d.client_id, "relationship": d.relationship}


def _dependent_from_dict(d: dict[str, Any]) -> DependentLink:
    return DependentLink(code=d["code"], client_id=d["client_id"], relationship=d["relationship"])


def _transition_to_dict(t: StageTransition) -> dict[str, Any]:
    return {
        "from_stage": t.from_stage.value if t.from_stage else None,
        "to_stage": t.to_stage.value,
        "at": t.at.isoformat(),
        "actor": t.actor,
        "note": t.note,
    }


def _transition_from_dict(d: dict[str, Any]) -> StageTransition:
    return StageTransition(
        from_stage=E33Stage(d["from_stage"]) if d.get("from_stage") else None,
        to_stage=E33Stage(d["to_stage"]),
        at=datetime.fromisoformat(d["at"]),
        actor=d.get("actor"),
        note=d.get("note"),
    )


def _jsonb(value: Any) -> Any:
    """asyncpg returns jsonb as str on some drivers — normalize to Python."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def case_to_row(case: E33Case) -> dict[str, Any]:
    """Flatten an E33Case to e33_cases column values."""
    return {
        "case_id": case.case_id,
        "client_id": case.client_id,
        "practice_id": case.practice_id,
        "basis": case.basis.value,
        "stage": case.stage.value,
        "owner_email": case.owner,
        "entry_date": case.entry_date,
        "itas_date": case.itas_date,
        "guarantee_proof_deadline": case.guarantee_deadline,
        "dependent_code": case.dependent_code,
        "principal_case_id": case.principal_case_id,
        "dependents": json.dumps([_dependent_to_dict(d) for d in case.dependents]),
        "evidence": json.dumps([_evidence_to_dict(e) for e in case.evidence]),
        "stage_history": json.dumps([_transition_to_dict(t) for t in case.history]),
        "stayguard_eligible": case.stayguard_eligible,
        "created_at": case.created_at,
    }


def row_to_case(row: dict[str, Any]) -> E33Case:
    """Rebuild an E33Case from an e33_cases row."""
    case = E33Case(
        case_id=row["case_id"],
        client_id=row["client_id"],
        practice_id=row.get("practice_id"),
        basis=GuaranteeBasis(row["basis"]),
        stage=E33Stage(row["stage"]),
        owner=row.get("owner_email"),
        entry_date=row.get("entry_date"),
        itas_date=row.get("itas_date"),
        dependent_code=row.get("dependent_code"),
        principal_case_id=row.get("principal_case_id"),
        dependents=[_dependent_from_dict(d) for d in _jsonb(row.get("dependents")) or []],
        evidence=[_evidence_from_dict(d) for d in _jsonb(row.get("evidence")) or []],
        history=[_transition_from_dict(d) for d in _jsonb(row.get("stage_history")) or []],
        created_at=row.get("created_at") or datetime.now(),
    )
    return case


# ── Repository ─────────────────────────────────────────────────────────────────

_COLUMNS = (
    "case_id, client_id, practice_id, basis, stage, owner_email,"
    " entry_date, itas_date, guarantee_proof_deadline,"
    " dependent_code, principal_case_id,"
    " dependents, evidence, stage_history, stayguard_eligible, created_at"
)


class E33CaseRepository:
    """CRUD for e33_cases. Read-heavy paths stay idempotent."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool
        self._conn: asyncpg.Connection | None = None

    @classmethod
    def with_connection(cls, conn: asyncpg.Connection) -> E33CaseRepository:
        """Bind the repo to a single pre-acquired connection (tests)."""
        inst = cls.__new__(cls)
        inst._pool = None  # type: ignore[assignment]
        inst._conn = conn
        return inst

    async def _exec(self, fn_name: str, query: str, *args: Any) -> Any:
        if self._conn is not None:
            return await getattr(self._conn, fn_name)(query, *args)
        async with self._pool.acquire() as conn:
            return await getattr(conn, fn_name)(query, *args)

    async def insert(self, case: E33Case) -> E33Case:
        """Insert a new case. Raises asyncpg.UniqueViolationError on dup id."""
        r = case_to_row(case)
        await self._exec(
            "execute",
            f"""
            INSERT INTO e33_cases ({_COLUMNS})
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13::jsonb,$14::jsonb,$15,$16)
            """,
            r["case_id"],
            r["client_id"],
            r["practice_id"],
            r["basis"],
            r["stage"],
            r["owner_email"],
            r["entry_date"],
            r["itas_date"],
            r["guarantee_proof_deadline"],
            r["dependent_code"],
            r["principal_case_id"],
            r["dependents"],
            r["evidence"],
            r["stage_history"],
            r["stayguard_eligible"],
            r["created_at"],
        )
        logger.info("E33 case inserted: %s (client=%s)", case.case_id, case.client_id)
        return case

    async def save(self, case: E33Case) -> None:
        """Persist mutable state after advance()/add_evidence() calls."""
        r = case_to_row(case)
        await self._exec(
            "execute",
            """
            UPDATE e33_cases
               SET practice_id = $2,
                   stage = $3,
                   owner_email = $4,
                   entry_date = $5,
                   itas_date = $6,
                   guarantee_proof_deadline = $7,
                   dependents = $8::jsonb,
                   evidence = $9::jsonb,
                   stage_history = $10::jsonb,
                   stayguard_eligible = $11,
                   updated_at = now()
             WHERE case_id = $1
            """,
            r["case_id"],
            r["practice_id"],
            r["stage"],
            r["owner_email"],
            r["entry_date"],
            r["itas_date"],
            r["guarantee_proof_deadline"],
            r["dependents"],
            r["evidence"],
            r["stage_history"],
            r["stayguard_eligible"],
        )

    async def load(self, case_id: str) -> E33Case | None:
        record = await self._exec(
            "fetchrow",
            f"SELECT {_COLUMNS} FROM e33_cases WHERE case_id = $1",
            case_id,
        )
        return row_to_case(dict(record)) if record else None

    async def list_by_client(self, client_id: int) -> list[E33Case]:
        records = await self._exec(
            "fetch",
            f"SELECT {_COLUMNS} FROM e33_cases WHERE client_id = $1 ORDER BY created_at",
            client_id,
        )
        return [row_to_case(dict(r)) for r in records]

    async def list_open_guarantee_cases(self) -> list[E33Case]:
        """Cases whose Day-90 gate or annual maintenance may need alerts.

        Returns non-terminal cases at ITAS_ACTIVE or later — the alert
        builder (``E33Case.build_case_forecasts``) decides what is actually
        due; this query is the coarse DB-side filter for a future scanner.
        """
        records = await self._exec(
            "fetch",
            f"""
            SELECT {_COLUMNS} FROM e33_cases
             WHERE stage IN ('itas_active', 'guarantee_proof_due', 'annual_maintenance')
             ORDER BY guarantee_proof_deadline NULLS LAST
            """,
        )
        return [row_to_case(dict(r)) for r in records]


__all__ = ["E33CaseRepository", "case_to_row", "row_to_case"]
