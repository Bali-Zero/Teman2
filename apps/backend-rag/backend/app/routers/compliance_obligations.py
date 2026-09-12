"""Obligations reviewer API — HITL bridge from the obligations register into
compliance_alerts (PR A2, lane backend-rag / obligations-review-queue).

Prefix: /api/compliance/obligations

Flow (design: DESIGN-lane-A.md, "PR A2"): ``propose()`` (PR A1) fills
``client_obligations`` with ``status='proposed'`` rows. This router lets the tax
team (CRM admins, ``app.utils.crm_utils.is_crm_admin``) list/generate/approve/
reject them. ``approve`` is the ONLY place a row leaves the register and
becomes visible to a client: it writes exactly one ``compliance_alerts`` row
(category ``obligation``, dedup_key ``obligation:<client_id>:<rule_id>:<period_key>``)
through the existing ``AlertRepository`` (m114) — never raw SQL — and stamps
the obligation ``approved -> alerted`` with that alert_id, both inside ONE
database transaction: either both writes land, or neither does. Reject and
generate never touch compliance_alerts.

RBAC: every route (reads included) requires ``is_crm_admin`` — obligations
review is a CRM-admin/tax-team function with no per-user ownership axis (unlike
``intake_review``'s own-chat scoping, which does not apply here), matching the
gate DESIGN-lane-A.md specifies for the whole router.

C4 follow-up from PR A1's gate (#6122): the applicability-edge case (a
FOREIGN_PLATFORM client whose custom_fields set has_employees/pkp wrongly
matching PPh 21/BPJS/PPN rules) was closed catalog-side in
``backend/data/obligations_catalog.yaml`` (each of those rules now also
requires ``company_type`` to be one of the non-platform types), so it is fixed
before this router ever sees a proposal. The OTHER-classification edge
(``profile_from_rows`` mapping unrecognised company_type spellings to OTHER,
which silently drops LKPM/PPh 25/SPT Tahunan/RUPS) is surfaced HERE: POST
``/generate`` flags ``needs_manual_classification`` in its response instead of
silently producing an incomplete proposal set.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import date
from functools import lru_cache
from typing import Any

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.app.utils.json_utils import to_jsonb
from backend.services.compliance.alert_repository import AlertRepository, AlertRow
from backend.services.compliance.obligations_register import (
    ATTRIBUTES,
    BOOL_ATTRS,
    COMPANY_TYPES,
    INT_ATTRS,
    INVESTMENT_STAGES,
    ObligationRule,
    _as_bool,
    _as_int,
    _valid_fye,
    load_catalog,
    profile_from_rows,
    profile_inputs,
    propose,
)
from backend.services.compliance.obligations_repository import (
    STATUSES,
    ObligationsRepository,
)
from backend.services.compliance.obligations_repository import (
    ObligationRow as ObligationDbRow,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compliance/obligations", tags=["compliance-obligations"])

_NEEDS_MANUAL_CLASSIFICATION_MSG = (
    "profile_from_rows could not map this client's company_type to a known type "
    "(PT PMA / PT PMDN / CV / KP3A / KPPA / FOREIGN_PLATFORM) and defaulted to OTHER. "
    "LKPM, PPh 25, SPT Tahunan Badan and RUPS annual obligations are skipped for OTHER "
    "profiles (PR A1 gate #6122, C4) — classify the company manually before trusting "
    "this proposal set."
)


@lru_cache(maxsize=1)
def _cached_rules() -> tuple[ObligationRule, ...]:
    """Catalog rules, loaded once per process. The YAML never changes at runtime."""
    return tuple(load_catalog())


def _require_admin(user: dict[str, Any]) -> None:
    if not is_crm_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CRM admin required")


def _reviewer_email(user: dict[str, Any]) -> str:
    email = (user.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=403, detail="Reviewer email is required")
    return email


# --------------------------------------------------------------------------- #
# Response models
# --------------------------------------------------------------------------- #
class ObligationOut(BaseModel):
    id: int
    client_id: int
    rule_id: str
    period_key: str
    due_date: date
    status: str
    needs_review_reason: str | None
    reviewer_email: str | None
    reviewed_at: Any | None
    review_note: str | None
    alert_id: str | None
    created_at: Any | None
    updated_at: Any | None


def _to_out(row: ObligationDbRow) -> ObligationOut:
    return ObligationOut(
        id=row.id,
        client_id=row.client_id,
        rule_id=row.rule_id,
        period_key=row.period_key,
        due_date=row.due_date,
        status=row.status,
        needs_review_reason=row.needs_review_reason,
        reviewer_email=row.reviewer_email,
        reviewed_at=row.reviewed_at,
        review_note=row.review_note,
        alert_id=row.alert_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ObligationListOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ObligationOut]


class GenerateBody(BaseModel):
    client_id: int
    horizon_days: int = Field(90, ge=1, le=730)


class GenerateOut(BaseModel):
    client_id: int
    inserted_count: int
    company_type: str
    needs_manual_classification: bool
    warning: str | None
    rows: list[ObligationOut]


class ApproveBody(BaseModel):
    note: str | None = None


class ApproveOut(BaseModel):
    obligation: ObligationOut
    alert_id: str


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# GET "" — list (filters client_id/status, paginated like intake_review)
# --------------------------------------------------------------------------- #
@router.get("")
async def list_obligations(
    client_id: int | None = Query(None),
    status_filter: str | None = Query(
        "proposed",
        alias="status",
        description=f"One of {sorted(STATUSES)}, or 'all' for no status filter.",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ObligationListOut:
    _require_admin(user)
    normalized_status = None if status_filter in (None, "all") else status_filter
    if normalized_status is not None and normalized_status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"unknown status {status_filter!r}")

    repo = ObligationsRepository(pool)
    total = await repo.count_filtered(client_id=client_id, status=normalized_status)
    rows = await repo.list_filtered(
        client_id=client_id, status=normalized_status, limit=limit, offset=offset
    )
    return ObligationListOut(
        total=total, limit=limit, offset=offset, items=[_to_out(r) for r in rows]
    )


# --------------------------------------------------------------------------- #
# GET /catalog, GET /profile/{client_id}, PATCH /profile/{client_id}
#
# These MUST stay registered BEFORE "/{obligation_id}" below: FastAPI matches
# routes in registration order, so with the order reversed "/catalog" would hit
# the int path converter of the detail route and answer 422 instead of 200.
# --------------------------------------------------------------------------- #
class CatalogRuleOut(BaseModel):
    """One catalog rule, flattened for the reviewer screen. No client data."""

    id: str
    name: str
    authority: str
    legal_source: str
    verified: bool
    frequency: str
    roll: str
    needs_review_reason: str | None
    trigger: str | None
    notes: str | None


class ProfileOut(BaseModel):
    """The computed ClientProfile plus the provenance the reviewer UI needs."""

    client_id: int
    profile: dict[str, Any]
    present_keys: list[str]
    missing_keys: list[str]
    company_type_raw: str | None
    needs_manual_classification: bool


@router.get("/catalog")
async def get_catalog(
    user: dict[str, Any] = Depends(get_current_user),
) -> list[CatalogRuleOut]:
    """The obligations catalog the reviewer screen labels proposals with.

    Rule metadata only — no client data and no database read (``_cached_rules``
    is the process-wide YAML load). The UI must render `rule_id` through THIS
    endpoint instead of duplicating the catalog in the frontend.
    """
    _require_admin(user)
    return [
        CatalogRuleOut(
            id=rule.id,
            name=rule.name,
            authority=rule.authority,
            legal_source=rule.legal_source,
            verified=rule.verified,
            frequency=rule.due.frequency,
            roll=rule.due.roll,
            needs_review_reason=rule.needs_review_reason,
            trigger=rule.trigger,
            notes=rule.notes,
        )
        for rule in _cached_rules()
    ]


def _profile_out(
    client_id: int, client_row: dict[str, Any] | None, company_row: dict[str, Any] | None
) -> ProfileOut:
    inputs = profile_inputs(client_row, company_row)
    raw_type = (company_row or {}).get("company_type")
    return ProfileOut(
        client_id=client_id,
        profile=asdict(inputs.profile),
        present_keys=list(inputs.present_keys),
        missing_keys=list(inputs.missing_attributes),
        company_type_raw=None if raw_type is None else str(raw_type),
        needs_manual_classification=inputs.profile.company_type == "OTHER",
    )


@router.get("/profile/{client_id}")
async def get_client_profile(
    client_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ProfileOut:
    """The profile ``POST /generate`` would compute for this client, with provenance.

    ``present_keys`` are the custom_fields keys the engine recognised AND parsed;
    ``missing_keys`` the engine ATTRIBUTES still sitting at their ClientProfile
    default, which is what makes ``applies()`` propose the minimum. 404 when the
    client does not exist. A client with no company row is NOT an error here (the
    profile is simply all defaults); only PATCH needs a row to write to, and says
    409 instead.
    """
    _require_admin(user)
    async with pool.acquire() as conn:
        client_row, company_row = await _load_client_and_company(conn, client_id)
    if client_row is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return _profile_out(client_id, client_row, company_row)


# company_type is stored under its OWN custom_fields key so it never collides
# with the companies.company_type column it overrides (see profile_inputs).
_PATCH_CUSTOM_KEY = {"company_type": "compliance_company_type"}
_PATCH_DOMAINS: dict[str, frozenset[str]] = {
    "company_type": COMPANY_TYPES,
    "investment_stage": INVESTMENT_STAGES,
}


def _validated_patch(body: dict[str, Any]) -> dict[str, Any]:
    """Translate an ATTRIBUTES patch into custom_fields values, or raise 422.

    Values are normalised through the engine's OWN parsers (``_as_bool`` /
    ``_as_int`` / ``_valid_fye``), so what is stored is exactly what
    ``profile_inputs`` will read back. Error details name the rejected KEY and
    the allowed domain, never the submitted value.
    """
    if not body:
        raise HTTPException(
            status_code=422, detail=f"body must set at least one of {sorted(ATTRIBUTES)}"
        )
    unknown = sorted(set(body) - ATTRIBUTES)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown attribute(s) {unknown}; allowed: {sorted(ATTRIBUTES)}",
        )
    out: dict[str, Any] = {}
    for name, raw in body.items():
        value: Any
        if name in BOOL_ATTRS:
            value = _as_bool(raw)
        elif name in INT_ATTRS:
            value = _as_int(raw)
        elif name == "fiscal_year_end":
            value = raw if _valid_fye(raw) else None
        else:  # company_type / investment_stage: a closed domain
            candidate = raw.strip().upper() if isinstance(raw, str) else None
            if name == "investment_stage" and isinstance(raw, str):
                candidate = raw.strip().lower()
            value = candidate if candidate in _PATCH_DOMAINS[name] else None  # None: not a member
        if value is None:
            allowed = _PATCH_DOMAINS.get(name)
            hint = f"; allowed: {sorted(allowed)}" if allowed else ""
            raise HTTPException(status_code=422, detail=f"invalid value for {name!r}{hint}")
        out[_PATCH_CUSTOM_KEY.get(name, name)] = value
    return out


@router.patch("/profile/{client_id}")
async def patch_client_profile(
    client_id: int = Path(..., ge=1),
    body: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ProfileOut:
    """Merge engine ATTRIBUTES into the client's companies.custom_fields.

    Body = any subset of ATTRIBUTES. ``company_type`` is accepted only as one of
    COMPANY_TYPES and is stored under the custom_fields key
    ``compliance_company_type``, which ``profile_inputs`` honours BEFORE the
    companies.company_type string mapping — that precedence is what lets the
    reviewer fix a company the string reads as OTHER, and it is documented at the
    single place that implements it (``profile_inputs``'s docstring).

    The write is the JSONB merge ``crm_enhanced.py`` already uses
    (``COALESCE(custom_fields, '{}'::jsonb) || $1::text::jsonb``), so unrelated
    keys survive untouched and no read-modify-write race can drop one. Nothing is
    created: 409 when the client has no linked company row, 404 when the client
    does not exist. A PATCH only ever SETS keys; it never removes one.

    Logs the keys written, never their values (they are client data).
    """
    _require_admin(user)
    patch = _validated_patch(body)

    async with pool.acquire() as conn, conn.transaction():
        client_row, company_row = await _load_client_and_company(conn, client_id)
        if client_row is None:
            raise HTTPException(status_code=404, detail="Client not found")
        company_id = (company_row or {}).get("company_id")
        if company_id is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Client has no company row to store the compliance profile on "
                    "(no client_company_links entry). Link a company first; this endpoint "
                    "creates nothing."
                ),
            )
        await conn.execute(
            """
            UPDATE companies
               SET custom_fields = COALESCE(custom_fields, '{}'::jsonb) || $1::text::jsonb,
                   updated_at = NOW()
             WHERE id = $2
            """,
            to_jsonb(patch),
            company_id,
        )
        client_row, company_row = await _load_client_and_company(conn, client_id)

    logger.info(
        "compliance.obligations.profile.patch client_id=%s keys=%s",
        client_id,
        sorted(patch),
    )
    return _profile_out(client_id, client_row, company_row)


# --------------------------------------------------------------------------- #
# GET /{id} — detail
# --------------------------------------------------------------------------- #
@router.get("/{obligation_id}")
async def get_obligation(
    obligation_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ObligationOut:
    _require_admin(user)
    repo = ObligationsRepository(pool)
    row = await repo.get(obligation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return _to_out(row)


# --------------------------------------------------------------------------- #
# POST /generate — profile_from_rows + propose() + upsert (idempotent)
# --------------------------------------------------------------------------- #
async def _load_client_and_company(
    conn: asyncpg.Connection, client_id: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    client_row = await conn.fetchrow(
        "SELECT id, custom_fields FROM clients WHERE id = $1 AND deleted_at IS NULL",
        client_id,
    )
    if client_row is None:
        return None, None
    company_row = await conn.fetchrow(
        """
        SELECT c.id AS company_id, c.company_type, c.custom_fields
          FROM client_company_links ccl
          JOIN companies c ON c.id = ccl.company_id
         WHERE ccl.client_id = $1
         ORDER BY ccl.is_primary DESC NULLS LAST, ccl.id ASC
         LIMIT 1
        """,
        client_id,
    )
    return dict(client_row), (dict(company_row) if company_row is not None else None)


@router.post("/generate")
async def generate_obligations(
    body: GenerateBody,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> GenerateOut:
    _require_admin(user)

    async with pool.acquire() as conn:
        client_row, company_row = await _load_client_and_company(conn, body.client_id)
    if client_row is None:
        raise HTTPException(status_code=404, detail="Client not found")

    profile = profile_from_rows(client_row, company_row)
    proposals = propose(_cached_rules(), profile, date.today(), body.horizon_days)

    repo = ObligationsRepository(pool)
    inserted_count = await repo.upsert_proposals(body.client_id, proposals)
    # Idempotent: existing (client, rule, period) rows are never duplicated
    # (ON CONFLICT DO NOTHING in upsert_proposals), so a re-run of /generate
    # over the same horizon returns inserted_count=0 and the same rows.
    current_rows = await repo.list_filtered(
        client_id=body.client_id, status="proposed", limit=200, offset=0
    )

    needs_manual = profile.company_type == "OTHER"
    logger.info(
        "compliance.obligations.generate client_id=%s inserted=%s company_type=%s "
        "needs_manual_classification=%s",
        body.client_id,
        inserted_count,
        profile.company_type,
        needs_manual,
    )
    return GenerateOut(
        client_id=body.client_id,
        inserted_count=inserted_count,
        company_type=profile.company_type,
        needs_manual_classification=needs_manual,
        warning=_NEEDS_MANUAL_CLASSIFICATION_MSG if needs_manual else None,
        rows=[_to_out(r) for r in current_rows],
    )


# --------------------------------------------------------------------------- #
# POST /{id}/approve — proposed -> approved, then bridge into compliance_alerts
# --------------------------------------------------------------------------- #
def _obligation_dedup_key(client_id: int, rule_id: str, period_key: str) -> str:
    return f"obligation:{client_id}:{rule_id}:{period_key}"


@router.post("/{obligation_id}/approve")
async def approve_obligation(
    obligation_id: int = Path(..., ge=1),
    body: ApproveBody = Body(default_factory=ApproveBody),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ApproveOut:
    """Approve a proposal and bridge it into compliance_alerts, atomically.

    Both writes (client_obligations proposed->approved->alerted, and the ONE
    compliance_alerts insert) happen inside a single transaction on the SAME
    connection (``ObligationsRepository.with_connection`` /
    ``AlertRepository.with_connection``): a failure anywhere — including the
    alert insert — rolls back the obligation transition too, so a caller never
    observes an obligation stuck ``approved`` with no alert, nor an alert with
    no matching ``alerted`` obligation. No compensation logic is needed because
    nothing is committed until the end of the ``async with conn.transaction()``
    block. A concurrent second approve/reject loses the race at the guarded
    ``UPDATE ... WHERE status='proposed'`` inside ``set_status`` (0 rows
    returned under READ COMMITTED once the winner commits) and gets 409.
    """
    _require_admin(user)
    reviewer_email = _reviewer_email(user)

    async with pool.acquire() as conn, conn.transaction():
        obl_repo = ObligationsRepository.with_connection(conn)
        approved = await obl_repo.set_status(obligation_id, "approved", reviewer_email, body.note)
        if approved is None:
            existing = await conn.fetchrow(
                "SELECT status FROM client_obligations WHERE id = $1", obligation_id
            )
            if existing is None:
                raise HTTPException(status_code=404, detail="Obligation not found")
            raise HTTPException(
                status_code=409,
                detail=f"Obligation must be proposed (status={existing['status']}).",
            )

        dedup_key = _obligation_dedup_key(approved.client_id, approved.rule_id, approved.period_key)
        alert_repo = AlertRepository.with_connection(conn)
        alert = await alert_repo.find_active_by_dedup_key(dedup_key)
        if alert is None:
            alert = await alert_repo.insert(
                AlertRow(
                    alert_id=f"alert_obligation_{approved.client_id}_{uuid.uuid4().hex[:8]}",
                    client_id=approved.client_id,
                    category="obligation",
                    severity="warning",
                    status="pending",
                    deadline=approved.due_date,
                    days_until=(approved.due_date - date.today()).days,
                    compliance_item_ref=approved.rule_id,
                    dedup_key=dedup_key,
                    message_it=None,
                    message_en=(
                        f"Obligation {approved.rule_id} ({approved.period_key}) due "
                        f"{approved.due_date.isoformat()}."
                    ),
                    message_id=None,
                    suggested_action=approved.needs_review_reason,
                    estimated_cost_idr=None,
                    evidence_refs=[],
                    nb2_ref=None,
                )
            )

        alerted = await obl_repo.mark_alerted(obligation_id, alert.alert_id)
        if alerted is None:  # pragma: no cover — guarded by the same-transaction lock above
            raise HTTPException(
                status_code=500, detail="Failed to bridge obligation into compliance_alerts."
            )

    logger.info(
        "compliance.obligations.approve id=%s reviewer=%s alert_id=%s",
        obligation_id,
        reviewer_email,
        alert.alert_id,
    )
    return ApproveOut(obligation=_to_out(alerted), alert_id=alert.alert_id)


# --------------------------------------------------------------------------- #
# POST /{id}/reject — proposed -> rejected (terminal, no compliance_alerts write)
# --------------------------------------------------------------------------- #
@router.post("/{obligation_id}/reject")
async def reject_obligation(
    obligation_id: int = Path(..., ge=1),
    body: RejectBody = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ObligationOut:
    _require_admin(user)
    reviewer_email = _reviewer_email(user)

    async with pool.acquire() as conn, conn.transaction():
        repo = ObligationsRepository.with_connection(conn)
        rejected = await repo.set_status(obligation_id, "rejected", reviewer_email, body.reason)
        if rejected is None:
            existing = await conn.fetchrow(
                "SELECT status FROM client_obligations WHERE id = $1", obligation_id
            )
            if existing is None:
                raise HTTPException(status_code=404, detail="Obligation not found")
            raise HTTPException(
                status_code=409,
                detail=f"Obligation must be proposed (status={existing['status']}).",
            )

    logger.info(
        "compliance.obligations.reject id=%s reviewer=%s reason=%s",
        obligation_id,
        reviewer_email,
        body.reason[:200],
    )
    return _to_out(rejected)


__all__ = ["router"]
