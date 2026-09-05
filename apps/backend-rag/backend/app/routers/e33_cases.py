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
This now covers ``POST /cases`` too: a non-admin cannot open a case for a
client not assigned to them (403), and the client must exist and not be
archived (``deleted_at IS NULL``) (422).

No-custody / ITAP / dependent-code enforcement is NOT re-implemented here —
it lives in ``backend.services.crm.e33_lifecycle`` (the domain model) and
this router surfaces its exceptions as the appropriate HTTP status:
``CustodyViolationError`` / ``UnknownDependentCodeError`` -> 422,
``E33InvalidTransitionError`` (including the ITAP_EVAL gate) -> 409.

Concurrency: ``advance`` and ``evidence`` wrap load→mutate→save in a single
transaction with ``SELECT ... FOR UPDATE`` on the case row — two concurrent
requests against the same case_id serialize instead of racing a lost update
(the second waits, re-reads the already-advanced case, and is evaluated
against ITS current state, not a stale in-memory copy).

Field-mapping note: the ``POST .../evidence`` body carries ``issuing_party``
and ``note`` for UI convenience, but ``EvidenceRef`` has no dedicated fields
for either (only ``document_ref`` / ``issued_date`` / ``filed_date`` /
``confirmed_by`` / ``metadata``) — both are folded into ``metadata`` under
their own keys. When the caller's ``metadata`` dict also sets the same key,
the dedicated top-level field WINS (plain overwrite, not ``setdefault``).
Still subject to the no-custody KEY validation, and metadata VALUES must be
scalar (rejects a dict/list value — closes the nested-forbidden-key
smuggling path where a custody key hides one level deeper than the scan).
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
    ACTIVE_PERMIT_STAGES,
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


async def _fetch_client_for_create(db_pool: asyncpg.Pool, client_id: int) -> Any | None:
    """Full pre-insert check row: existence, archival state, ownership."""
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT full_name, assigned_to, deleted_at FROM clients WHERE id = $1", client_id
        )


async def _fetch_client_name_and_owner(
    db_pool: asyncpg.Pool, client_id: int
) -> tuple[str | None, str | None]:
    """Read-only lookup (no lock needed — used by the GET detail endpoint)."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT full_name, assigned_to FROM clients WHERE id = $1", client_id
        )
    if row is None:
        return None, None
    return row["full_name"], row["assigned_to"]


async def _fetch_client_name_and_owner_conn(
    conn: asyncpg.Connection, client_id: int
) -> tuple[str | None, str | None]:
    """Same lookup as :func:`_fetch_client_name_and_owner` but on an ALREADY
    acquired connection — used inside the advance/evidence transactions so
    the whole load→mutate→save sequence stays on one connection (never a
    second, separately-acquired one) for the FOR UPDATE lock to be
    meaningful.
    """
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
            "guarantee_evidence_complete": case.guarantee_evidence_complete,
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
    document_ref: str = Field(min_length=1)
    issuing_party: str | None = None
    issued_on: date | None = None
    filed_on: date | None = None
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _metadata_values_must_be_scalar(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Reject dict/list values — a nested object can hide a forbidden
        custody key one level below the KEY scan (``validate_evidence_metadata``
        only inspects top-level keys), e.g.
        ``{"metadata": {"details": {"account_number": "..."}}}``.
        """
        for key, val in v.items():
            if isinstance(val, dict | list):
                raise ValueError(
                    f"metadata values must be scalar (key {key!r} is a {type(val).__name__})"
                )
        return v


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreateBody,
    current_user: dict[str, Any] = Depends(require_team_member),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Mint a new E33 case starting at ``fit_memo``.

    Property basis is out of V1 scope (pending addendum 007 —
    ``property_validation_standard``). Before any insert, validate the requested
    client's existence, archival state and caller access, and the optional
    principal client's existence, archival state and caller access. Principal and
    dependent may have different client IDs; this access check does not establish
    their family relationship.

    On a case_id collision (``asyncpg.UniqueViolationError``) re-mint once;
    a second collision is a 500 (astronomically unlikely — 6 hex chars).
    """
    if body.basis == GuaranteeBasis.PROPERTY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "property route not yet supported — pending addendum 007 "
                "(property_validation_standard)"
            ),
        )

    client_row = await _fetch_client_for_create(db_pool, body.client_id)
    if client_row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="client does not exist"
        )
    if client_row["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="client is archived"
        )
    _assert_client_access(current_user, client_row["assigned_to"])
    client_name = client_row["full_name"]

    repo = E33CaseRepository(db_pool)
    if body.principal_case_id is not None:
        unavailable = HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="principal case is not available",
        )
        principal = await repo.load(body.principal_case_id)
        if principal is None:
            raise unavailable
        principal_client = await _fetch_client_for_create(db_pool, principal.client_id)
        if principal_client is None or principal_client["deleted_at"] is not None:
            raise unavailable
        try:
            _assert_client_access(current_user, principal_client["assigned_to"])
        except HTTPException as exc:
            if exc.status_code != status.HTTP_403_FORBIDDEN:
                raise
            raise unavailable from None

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
            logger.warning(
                "e33.create_case.fk_violation client_id=%s practice_id=%s "
                "principal_case_id=%s error=%s",
                body.client_id,
                body.practice_id,
                body.principal_case_id,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="referenced client, practice or principal case does not exist",
            ) from exc

    if last_error is not None or case is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not mint a unique E33 case id after 2 attempts",
        ) from last_error

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
    """Advance a case's stage.

    load -> mutate -> save runs inside one transaction with a
    ``SELECT ... FOR UPDATE`` row lock so two concurrent advances against
    the same case serialize instead of the second silently clobbering the
    first's write with a stale in-memory copy.
    """
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT case_id FROM e33_cases WHERE case_id = $1 FOR UPDATE", case_id
            )
            repo = E33CaseRepository.with_connection(conn)
            case = await repo.load(case_id)
            if case is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="E33 case not found"
                )

            client_name, assigned_to = await _fetch_client_name_and_owner_conn(
                conn, case.client_id
            )
            _assert_client_access(current_user, assigned_to)

            if body.to_stage == case.stage:
                # validate_transition() treats same-stage as a no-op, but
                # advance() itself re-stamps entry_date/itas_date and
                # appends a history row — a same-stage call would silently
                # rewrite the Day-90 anchor date. Reject it explicitly.
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"case is already in stage '{case.stage.value}' — same-stage "
                        "re-dating is not allowed"
                    ),
                )

            if (
                case.stage == E33Stage.GUARANTEE_PROOF_DUE
                and body.to_stage == E33Stage.ANNUAL_MAINTENANCE
                and not case.guarantee_evidence_complete
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "record the guarantee evidence (bank confirmation / property "
                        "title filing) before closing the Day-90 gate"
                    ),
                )

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
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=str(exc)
                ) from exc

            await repo.save(case)

    return _case_detail_dict(case, client_name=client_name, today=date.today())


@router.post("/cases/{case_id}/evidence")
async def add_evidence(
    case_id: str,
    body: EvidenceBody,
    current_user: dict[str, Any] = Depends(require_team_member),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Attach an evidence reference to a case.

    Same transaction + ``FOR UPDATE`` pattern as :func:`advance_case` — see
    its docstring.
    """
    # issuing_party / note have no dedicated EvidenceRef field — see module
    # docstring. Folded into metadata under their own keys and OVERWRITE any
    # same-named key the caller also put in body.metadata (top-level field
    # wins) — still subject to the no-custody KEY validation performed by
    # EvidenceRef.__post_init__.
    metadata = dict(body.metadata or {})
    if body.issuing_party:
        metadata["issuing_party"] = body.issuing_party
    if body.note:
        metadata["note"] = body.note

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT case_id FROM e33_cases WHERE case_id = $1 FOR UPDATE", case_id
            )
            repo = E33CaseRepository.with_connection(conn)
            case = await repo.load(case_id)
            if case is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="E33 case not found"
                )

            client_name, assigned_to = await _fetch_client_name_and_owner_conn(
                conn, case.client_id
            )
            _assert_client_access(current_user, assigned_to)

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
        rbac_params.append((current_user.get("email") or "").lower())
        rbac_clause = (
            "e33_cases.client_id IN "
            f"(SELECT id FROM clients WHERE LOWER(assigned_to) = ${len(rbac_params)})"
        )

    async with db_pool.acquire() as conn:
        stage_where = f"WHERE {rbac_clause}" if rbac_clause else ""
        stage_rows = await conn.fetch(
            f"SELECT stage, COUNT(*) AS n FROM e33_cases {stage_where} GROUP BY stage",
            *rbac_params,
        )

        # "due" must be scoped to the scanner's own active-permit stage set
        # (itas_active / guarantee_proof_due / annual_maintenance) — a
        # terminal-stage case with a stale deadline still on the row must
        # NOT count as "due". Sourced from ACTIVE_PERMIT_STAGES, no string
        # literals, so the two never drift apart.
        due_params = list(rbac_params)
        active_stage_values = sorted(s.value for s in ACTIVE_PERMIT_STAGES)
        due_params.append(active_stage_values)
        due_conditions = [
            "guarantee_proof_deadline IS NOT NULL",
            "guarantee_proof_deadline <= CURRENT_DATE + 30",
            f"stage = ANY(${len(due_params)}::text[])",
        ]
        if rbac_clause:
            due_conditions.append(rbac_clause)
        due_where = "WHERE " + " AND ".join(due_conditions)
        guarantee_due_30d = await conn.fetchval(
            f"SELECT COUNT(*) FROM e33_cases {due_where}", *due_params
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
