"""E33 Second Home — case entrance router (F4a) and internal console API.

Prefix: /api/e33

Fills the gap identified in the ``/secondhome`` corner §4bis (2026-07-25):
``E33CaseRepository.insert()`` had no production caller — the lifecycle
model, repository and Day-90 scanner existed, but no case could ever be
created, so ``e33_cases`` stayed at 0 rows forever and the guarantee scanner
had nothing to scan. This router is that missing entrance.

Auth: every endpoint requires a team member (``require_team_member`` — 403
for client-portal JWTs; it already depends on ``get_current_user``, so a
single dependency covers both checks).

RBAC: admins (``is_crm_admin``) see every case. Non-admin team members are
restricted to cases whose client is assigned to them — mirrors the
``compliance_alerts.py`` / ``crm_practices.py`` ``assigned_to`` pattern.

No-custody / ITAP / dependent-code enforcement is NOT re-implemented here —
it lives in ``backend.services.crm.e33_lifecycle`` (the domain model) and
this router surfaces its exceptions as the appropriate HTTP status:
``CustodyViolationError`` / ``UnknownDependentCodeError`` -> 422,
``E33InvalidTransitionError`` (including the ITAP_EVAL gate) -> 409.

Field-mapping note: the ``POST .../evidence`` body carries ``issuing_party``
and ``note`` for UI convenience, but ``EvidenceRef`` has no dedicated fields
for either (only ``document_ref`` / ``issued_date`` / ``filed_date`` /
``confirmed_by`` / ``metadata``) — both are folded into ``metadata`` under
their own keys, still subject to the no-custody KEY validation.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.dependencies import get_database_pool, require_team_member
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.crm.e33_case_repository import E33CaseRepository
from backend.services.crm.e33_guarantee_scanner import ScanSwitchState, resolve_scan_switch
from backend.services.crm.e33_lifecycle import (
    E33_ITAP_EVAL_ENABLED,
    TERMINAL_STAGES,
    VALID_TRANSITIONS,
    CustodyViolationError,
    E33Case,
    E33InvalidTransitionError,
    E33Stage,
    EvidenceKind,
    EvidenceRef,
    GuaranteeBasis,
    UnknownDependentCodeError,
    guarantee_alert_schedule,
    severity_for_days_until,
    validate_dependent_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/e33", tags=["e33"])

_TERMINAL_STAGE_VALUES: frozenset[str] = frozenset(s.value for s in TERMINAL_STAGES)


# ── Serialization helpers ────────────────────────────────────────────────────


def _json_default(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _to_jsonable(value: Any) -> Any:
    """Recursively convert dataclasses/enums/dates to plain JSON-safe values."""
    return json.loads(json.dumps(value, default=_json_default))


def _mint_case_id(today: date) -> str:
    """``E33-<YYYY>-<6 lowercase hex>`` — uuid4-derived, collision-checked by insert()."""
    return f"E33-{today.year}-{uuid4().hex[:6]}"


def _assert_client_access(current_user: dict[str, Any], assigned_to: str | None) -> None:
    """403 unless the user is a CRM admin or the client is assigned to them."""
    if is_crm_admin(current_user):
        return
    user_email = (current_user.get("email") or "").lower()
    if not assigned_to or assigned_to.lower() != user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this E33 case",
        )


async def _fetch_client_name(db_pool: asyncpg.Pool, client_id: int) -> str | None:
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT full_name FROM clients WHERE id = $1", client_id)


async def _fetch_client_name_and_owner(
    db_pool: asyncpg.Pool, client_id: int
) -> tuple[str | None, str | None]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT full_name, assigned_to FROM clients WHERE id = $1", client_id
        )
    if row is None:
        return None, None
    return row["full_name"], row["assigned_to"]


def _case_summary_dict(case: E33Case, *, client_name: str | None) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "client_id": case.client_id,
        "client_name": client_name,
        "basis": case.basis.value,
        "stage": case.stage.value,
        "owner_email": case.owner,
        "guarantee_proof_deadline": case.guarantee_deadline.isoformat()
        if case.guarantee_deadline
        else None,
        "stayguard_eligible": case.stayguard_eligible,
        "dependent_code": case.dependent_code,
        "principal_case_id": case.principal_case_id,
        "created_at": case.created_at.isoformat(),
    }


def _row_to_summary_dict(row: dict[str, Any]) -> dict[str, Any]:
    deadline = row.get("guarantee_proof_deadline")
    created_at = row.get("created_at")
    return {
        "case_id": row["case_id"],
        "client_id": row["client_id"],
        "client_name": row.get("client_name"),
        "basis": row["basis"],
        "stage": row["stage"],
        "owner_email": row.get("owner_email"),
        "guarantee_proof_deadline": deadline.isoformat() if deadline else None,
        "stayguard_eligible": row.get("stayguard_eligible", False),
        "dependent_code": row.get("dependent_code"),
        "principal_case_id": row.get("principal_case_id"),
        "created_at": created_at.isoformat() if created_at else None,
    }


def _allowed_next_stages(stage: E33Stage) -> list[str]:
    allowed = VALID_TRANSITIONS.get(stage, set())
    return sorted(
        s.value for s in allowed if s != E33Stage.ITAP_EVAL or E33_ITAP_EVAL_ENABLED
    )


def _guarantee_dict(case: E33Case, *, today: date) -> dict[str, Any] | None:
    deadline = case.guarantee_deadline
    anchor = case.guarantee_anchor
    if deadline is None or anchor is None:
        return None
    schedule = guarantee_alert_schedule(anchor)
    return {
        "deadline": deadline.isoformat(),
        "days_remaining": (deadline - today).days,
        "alert_schedule": [
            {
                "date": milestone.at.isoformat(),
                "severity": severity_for_days_until(milestone.days_until_deadline),
            }
            for milestone in schedule
        ],
    }


def _case_detail_dict(case: E33Case, *, client_name: str | None, today: date) -> dict[str, Any]:
    detail = _case_summary_dict(case, client_name=client_name)
    detail.update(
        {
            "entry_date": case.entry_date.isoformat() if case.entry_date else None,
            "itas_date": case.itas_date.isoformat() if case.itas_date else None,
            "dependents": _to_jsonable(case.dependents),
            "evidence": _to_jsonable(case.evidence),
            "stage_history": _to_jsonable(case.history),
            "allowed_next_stages": _allowed_next_stages(case.stage),
            "guarantee": _guarantee_dict(case, today=today),
            "forecasts": _to_jsonable(case.build_case_forecasts(today=today)),
        }
    )
    return detail


# ── Request models ───────────────────────────────────────────────────────────


class CaseCreateBody(BaseModel):
    client_id: int
    basis: GuaranteeBasis
    practice_id: int | None = None
    owner_email: str | None = None
    dependent_code: str | None = None
    principal_case_id: str | None = None
    note: str | None = None

    @field_validator("dependent_code")
    @classmethod
    def _validate_dependent_code(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            return validate_dependent_code(v)
        except UnknownDependentCodeError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def _dependent_code_requires_principal(self) -> CaseCreateBody:
        if bool(self.dependent_code) != bool(self.principal_case_id):
            raise ValueError(
                "dependent_code and principal_case_id must be provided together"
            )
        return self


class AdvanceBody(BaseModel):
    to_stage: E33Stage
    note: str | None = None
    occurred_on: date | None = None


class EvidenceBody(BaseModel):
    kind: EvidenceKind
    document_ref: str
    issuing_party: str | None = None
    issued_on: date | None = None
    filed_on: date | None = None
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreateBody,
    current_user: dict[str, Any] = Depends(require_team_member),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Mint a new E33 case starting at ``fit_memo``.

    On a case_id collision (``asyncpg.UniqueViolationError``) re-mint once;
    a second collision is a 500 (astronomically unlikely — 6 hex chars).
    """
    repo = E33CaseRepository(db_pool)
    today = date.today()
    case: E33Case | None = None
    last_error: asyncpg.UniqueViolationError | None = None

    for attempt in range(2):
        case_id = _mint_case_id(today)
        case = E33Case(
            case_id=case_id,
            client_id=body.client_id,
            basis=body.basis,
            practice_id=body.practice_id,
            owner=body.owner_email,
            dependent_code=body.dependent_code,
            principal_case_id=body.principal_case_id,
        )
        try:
            await repo.insert(case)
            last_error = None
            break
        except asyncpg.UniqueViolationError as exc:
            last_error = exc
            logger.warning(
                "e33.create_case.case_id_collision case_id=%s attempt=%s", case_id, attempt
            )
            continue
        except asyncpg.ForeignKeyViolationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Referenced client, practice or principal case does not exist: "
                    f"{exc}"
                ),
            ) from exc

    if last_error is not None or case is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not mint a unique E33 case id after 2 attempts",
        ) from last_error

    client_name = await _fetch_client_name(db_pool, body.client_id)
    return _case_detail_dict(case, client_name=client_name, today=today)


@router.get("/cases")
async def list_cases(
    stage: str | None = Query(None),
    client_id: int | None = Query(None),
    basis: str | None = Query(None),
    active_only: bool = Query(False),
    current_user: dict[str, Any] = Depends(require_team_member),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []

    if not is_crm_admin(current_user):
        clauses.append(
            f"e33_cases.client_id IN (SELECT id FROM clients WHERE LOWER(assigned_to) = ${len(params) + 1})"
        )
        params.append((current_user.get("email") or "").lower())

    if stage:
        clauses.append(f"e33_cases.stage = ${len(params) + 1}")
        params.append(stage)
    if client_id is not None:
        clauses.append(f"e33_cases.client_id = ${len(params) + 1}")
        params.append(client_id)
    if basis:
        clauses.append(f"e33_cases.basis = ${len(params) + 1}")
        params.append(basis)
    if active_only:
        terminal_list = ", ".join(f"'{v}'" for v in sorted(_TERMINAL_STAGE_VALUES))
        clauses.append(f"e33_cases.stage NOT IN ({terminal_list})")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    query = f"""
        SELECT e33_cases.case_id, e33_cases.client_id, clients.full_name AS client_name,
               e33_cases.basis, e33_cases.stage, e33_cases.owner_email,
               e33_cases.guarantee_proof_deadline, e33_cases.stayguard_eligible,
               e33_cases.dependent_code, e33_cases.principal_case_id, e33_cases.created_at
        FROM e33_cases
        JOIN clients ON clients.id = e33_cases.client_id
        {where}
        ORDER BY e33_cases.created_at DESC
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    cases = [_row_to_summary_dict(dict(r)) for r in rows]
    return {"cases": cases, "total": len(cases)}


@router.get("/cases/{case_id}")
async def get_case(
    case_id: str,
    current_user: dict[str, Any] = Depends(require_team_member),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    repo = E33CaseRepository(db_pool)
    case = await repo.load(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="E33 case not found")

    client_name, assigned_to = await _fetch_client_name_and_owner(db_pool, case.client_id)
    _assert_client_access(current_user, assigned_to)

    return _case_detail_dict(case, client_name=client_name, today=date.today())


@router.post("/cases/{case_id}/advance")
async def advance_case(
    case_id: str,
    body: AdvanceBody,
    current_user: dict[str, Any] = Depends(require_team_member),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    repo = E33CaseRepository(db_pool)
    case = await repo.load(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="E33 case not found")

    client_name, assigned_to = await _fetch_client_name_and_owner(db_pool, case.client_id)
    _assert_client_access(current_user, assigned_to)

    try:
        case.advance(
            body.to_stage,
            at=datetime.now(tz=timezone.utc),
            actor=current_user.get("email"),
            note=body.note,
            occurred_on=body.occurred_on,
            itap_eval_enabled=E33_ITAP_EVAL_ENABLED,
        )
    except E33InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await repo.save(case)
    return _case_detail_dict(case, client_name=client_name, today=date.today())


@router.post("/cases/{case_id}/evidence")
async def add_evidence(
    case_id: str,
    body: EvidenceBody,
    current_user: dict[str, Any] = Depends(require_team_member),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    repo = E33CaseRepository(db_pool)
    case = await repo.load(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="E33 case not found")

    client_name, assigned_to = await _fetch_client_name_and_owner(db_pool, case.client_id)
    _assert_client_access(current_user, assigned_to)

    # issuing_party / note have no dedicated EvidenceRef field — see module
    # docstring. Folded into metadata (still subject to the no-custody KEY
    # validation performed by EvidenceRef.__post_init__).
    metadata = dict(body.metadata or {})
    if body.issuing_party:
        metadata.setdefault("issuing_party", body.issuing_party)
    if body.note:
        metadata.setdefault("note", body.note)

    try:
        evidence = EvidenceRef(
            evidence_id=str(uuid4()),
            kind=body.kind,
            document_ref=body.document_ref,
            issued_date=body.issued_on,
            filed_date=body.filed_on,
            confirmed_by=current_user.get("email"),
            metadata=metadata,
        )
    except CustodyViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    case.add_evidence(evidence)
    await repo.save(case)
    return _case_detail_dict(case, client_name=client_name, today=date.today())


@router.get("/summary")
async def get_summary(
    current_user: dict[str, Any] = Depends(require_team_member),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    rbac_clause: str | None = None
    rbac_params: list[Any] = []
    if not is_crm_admin(current_user):
        rbac_clause = (
            "e33_cases.client_id IN (SELECT id FROM clients WHERE LOWER(assigned_to) = $1)"
        )
        rbac_params = [(current_user.get("email") or "").lower()]

    async with db_pool.acquire() as conn:
        stage_where = f"WHERE {rbac_clause}" if rbac_clause else ""
        stage_rows = await conn.fetch(
            f"SELECT stage, COUNT(*) AS n FROM e33_cases {stage_where} GROUP BY stage",
            *rbac_params,
        )

        due_conditions = [
            "guarantee_proof_deadline IS NOT NULL",
            "guarantee_proof_deadline <= CURRENT_DATE + 30",
        ]
        if rbac_clause:
            due_conditions.append(rbac_clause)
        due_where = "WHERE " + " AND ".join(due_conditions)
        guarantee_due_30d = await conn.fetchval(
            f"SELECT COUNT(*) FROM e33_cases {due_where}", *rbac_params
        )

    scan_switch: ScanSwitchState = await resolve_scan_switch(db_pool)

    by_stage = {row["stage"]: row["n"] for row in stage_rows}
    active_total = sum(
        n for stage_value, n in by_stage.items() if stage_value not in _TERMINAL_STAGE_VALUES
    )

    return {
        "by_stage": by_stage,
        "active_total": active_total,
        "guarantee_due_30d": guarantee_due_30d or 0,
        "scan_switch": scan_switch.value,
    }


__all__ = ["router"]
