"""GARUDA VOA — step 8 staff surface: the transition producer.

Owns the transactional core of `POST .../transitions` (STATE-MACHINE.md rows
PR-02..PR-11) — the guarded compare-and-set UPDATE, the append-only evidence
write, the journal append and the outbox enqueue — so `garuda_staff_router.py`
stays a thin HTTP-shape layer (round-3 disposition item E: "the producer
lives in a service module ... the router stays thin"). `_visible_or_403` also
lives here rather than staying router-private, since this module's own
`apply_transition` needs the identical check the router's read routes
(`list_staff_practices`/`get_staff_practice`) already run — one definition,
not two that could drift.

Every guard raises `fastapi.HTTPException` with the contract's own error
codes directly. That is a deliberate departure from a "framework-free
service layer" ideal: this whole backend already treats FastAPI as a hard
dependency (`repository.py`'s siblings do the same), and
`garuda_staff_router.py`'s `_ContractErrorRoute` is what turns these
exceptions into the frozen contract's JSON envelope — a second translation
layer here would just be an extra hop for no isolation actually gained.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import asyncpg
from fastapi import HTTPException

from backend.services.garuda_orders import journal

__all__ = [
    "BLOCK_RESUME_TARGET",
    "RESUME_EXPECTED_TARGET",
    "TRANSITIONS",
    "TransitionSpec",
    "apply_transition",
    "validate_transition_body",
    "visible_or_403",
]


@dataclass(frozen=True, slots=True)
class TransitionSpec:
    kind: str
    from_states: tuple[str, ...]
    to_state: str
    event_name: str


#: STATE-MACHINE.md PR-02..PR-11. No `outbox_job_type` field here on
#: purpose — see `_job_type_for` below for why the enqueue call site
#: computes it via a literal if/elif chain instead of an attribute lookup.
TRANSITIONS: dict[str, TransitionSpec] = {
    "PR-02": TransitionSpec("begin", ("Received",), "In_review", "practice.in_review"),
    "PR-03": TransitionSpec("block", ("Received",), "Blocked", "practice.blocked"),
    "PR-05": TransitionSpec("block", ("In_review",), "Blocked", "practice.blocked"),
    "PR-08": TransitionSpec("block", ("Submitted",), "Blocked", "practice.blocked"),
    "PR-04": TransitionSpec("submit", ("In_review",), "Submitted", "practice.submitted"),
    "PR-06": TransitionSpec("approve", ("Submitted",), "Approved", "practice.approved"),
    "PR-07": TransitionSpec("reject", ("Submitted",), "Rejected", "practice.rejected"),
    "PR-09": TransitionSpec("resume", ("Blocked",), "In_review", "practice.resumed"),
    "PR-10": TransitionSpec("resume", ("Blocked",), "Submitted", "practice.resumed"),
    "PR-11": TransitionSpec("deliver", ("Approved",), "Delivered", "practice.delivered"),
}

BLOCK_RESUME_TARGET: dict[str, str] = {"PR-03": "In_review", "PR-05": "In_review", "PR-08": "Submitted"}
RESUME_EXPECTED_TARGET: dict[str, str] = {"PR-09": "In_review", "PR-10": "Submitted"}
_REASON_PATTERN = "garuda_voa.practice."
_ACTION_PATTERN = "garuda_voa.action."
_EVIDENCE_KIND: dict[str, str] = {"submit": "filing", "approve": "approval", "reject": "rejection"}

#: Same character class as `garuda_practice_evidence`'s `evidence_id` CHECK
#: constraint (`305_garuda_practices_assignment.sql:148`) -- cross-family
#: refuter MAJOR finding #1 (Codex): a value that passed this function's
#: previous length-only check (16-128 chars, any character) but failed the
#: DB's character class reached `apply_transition`'s INSERT and crashed with
#: an unhandled `asyncpg.CheckViolationError` (HTTP 500 INTERNAL_ERROR)
#: instead of this contract's 422 INVALID_REQUEST. Reused verbatim for
#: `artifact_id` and `resolved_block_id` too: neither has its own DB CHECK
#: (they live on `garuda_practices` directly, not the evidence table), but
#: they are staff-supplied opaque identifiers of the identical shape and
#: deserve the identical guard, not a laxer one by omission.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def visible_or_403(row: asyncpg.Record, actor: dict[str, Any]) -> None:
    if actor["is_admin"]:
        return
    if (row["assigned_to"] or "").lower() != actor["email"]:
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "retryable": False})


def validate_transition_body(transition_id: str, body: dict) -> dict[str, Any]:
    """PR-02..PR-11 body-shape validation, mirroring the frozen contract's
    `oneOf` discriminated on `transition_id` (`PracticeTransitionRequest`).
    Raises 422 INVALID_REQUEST on any mismatch."""

    def _fail() -> None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False})

    spec = TRANSITIONS.get(transition_id)
    if spec is None:
        _fail()

    if spec.kind == "begin":
        return {}
    if spec.kind == "block":
        reason = body.get("customer_reason_key")
        action = body.get("required_action_key")
        if (
            not isinstance(reason, str)
            or not reason.startswith(_REASON_PATTERN)
            or not isinstance(action, str)
            or not action.startswith(_ACTION_PATTERN)
        ):
            _fail()
        note = body.get("private_staff_note")
        if note is not None and (not isinstance(note, str) or len(note) > 4000):
            _fail()
        return {"customer_reason_key": reason, "required_action_key": action, "private_staff_note": note}
    if spec.kind in ("submit", "approve"):
        evidence_id = body.get("evidence_id")
        if not isinstance(evidence_id, str) or not _ID_PATTERN.match(evidence_id):
            _fail()
        return {"evidence_id": evidence_id}
    if spec.kind == "reject":
        evidence_id = body.get("evidence_id")
        reason = body.get("customer_reason_key")
        if (
            not isinstance(evidence_id, str)
            or not _ID_PATTERN.match(evidence_id)
            or not isinstance(reason, str)
            or not reason.startswith(_REASON_PATTERN)
        ):
            _fail()
        note = body.get("private_staff_note")
        if note is not None and (not isinstance(note, str) or len(note) > 4000):
            _fail()
        return {"evidence_id": evidence_id, "customer_reason_key": reason, "private_staff_note": note}
    if spec.kind == "resume":
        resolved_block_id = body.get("resolved_block_id")
        if not isinstance(resolved_block_id, str) or not _ID_PATTERN.match(resolved_block_id):
            _fail()
        return {"resolved_block_id": resolved_block_id}
    if spec.kind == "deliver":
        artifact_id = body.get("artifact_id")
        artifact_digest = body.get("artifact_digest")
        if (
            not isinstance(artifact_id, str)
            or not _ID_PATTERN.match(artifact_id)
            or not isinstance(artifact_digest, str)
            or len(artifact_digest) != 64
        ):
            _fail()
        return {"artifact_id": artifact_id, "artifact_digest": artifact_digest}
    _fail()  # pragma: no cover - unreachable, spec is None already caught above
    raise AssertionError  # pragma: no cover


async def apply_transition(
    conn: asyncpg.Connection,
    *,
    practice_id: str,
    transition_id: str,
    actor: dict[str, Any],
    fields: dict[str, Any],
    key_digest: bytes,
    payload_digest: bytes,
) -> asyncpg.Record:
    """Runs INSIDE the caller's transaction (same convention `journal.py`
    itself documents). Returns the `updated` row (state + customer-visible
    columns) the router turns into the response body."""

    spec = TRANSITIONS[transition_id]
    row = await conn.fetchrow(
        """
        SELECT practice_id, order_id, state, assigned_to, resume_target, active_block_id,
               customer_reason_key, required_action_key, artifact_available
          FROM garuda_practices WHERE practice_id = $1 FOR UPDATE
        """,
        practice_id,
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail={"code": "PRACTICE_NOT_FOUND", "retryable": False}
        )
    visible_or_403(row, actor)

    if row["state"] not in spec.from_states:
        raise HTTPException(
            status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "retryable": False}
        )
    if spec.kind == "resume":
        if row["resume_target"] != RESUME_EXPECTED_TARGET[transition_id]:
            raise HTTPException(
                status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "retryable": False}
            )
        # cross-family refuter finding #9: a bare `resume_target` match only
        # proves the STATE-SHAPE lines up, not that the staff-supplied
        # `resolved_block_id` names THIS block rather than an unrelated,
        # already-superseded one. `active_block_id` is the journal event id
        # of the `practice.blocked` event that most recently blocked this
        # practice (305's own column comment) -- comparing against it is
        # what makes "resolved the right block" a real, checked fact.
        if fields["resolved_block_id"] != row["active_block_id"]:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False}
            )

    if spec.kind in _EVIDENCE_KIND:
        # An evidence_id already bound to a DIFFERENT practice is a
        # client-side mistake (evidence identifiers are meant to be
        # practice-scoped), not a genuine conflict worth 409. A replay of
        # the SAME (practice_id, evidence_id) pair is handled by the
        # INSERT ... ON CONFLICT DO NOTHING below, not here.
        other_owner = await conn.fetchval(
            """
            SELECT practice_id FROM garuda_practice_evidence
             WHERE evidence_id = $1 AND practice_id != $2
             LIMIT 1
            """,
            fields["evidence_id"],
            practice_id,
        )
        if other_owner is not None:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_REQUEST", "retryable": False}
            )

    # Pre-generated so the SAME UPDATE that flips state to Blocked can also
    # store this id as `active_block_id`, and the journal row written below
    # can be given that exact id via `journal.append_event`'s `event_id=`
    # override -- one identity, not two independently-generated ones that
    # would happen to usually agree.
    block_event_id = journal.new_opaque_id("evt") if spec.kind == "block" else None

    set_clauses = ["state = $2"]
    params: list[Any] = [practice_id, spec.to_state, list(spec.from_states)]

    def _add(column: str, value: Any) -> None:
        params.append(value)
        set_clauses.append(f"{column} = ${len(params)}")

    if spec.kind == "block":
        _add("customer_reason_key", fields["customer_reason_key"])
        _add("required_action_key", fields["required_action_key"])
        _add("private_staff_note", fields["private_staff_note"])
        _add("resume_target", BLOCK_RESUME_TARGET[transition_id])
        _add("active_block_id", block_event_id)
    elif spec.kind == "reject":
        _add("customer_reason_key", fields["customer_reason_key"])
        _add("private_staff_note", fields["private_staff_note"])
    elif spec.kind == "resume":
        set_clauses += [
            "resume_target = NULL",
            "active_block_id = NULL",
            "customer_reason_key = NULL",
            "required_action_key = NULL",
            "private_staff_note = NULL",
        ]
    elif spec.kind == "deliver":
        _add("artifact_id", fields["artifact_id"])
        _add("artifact_digest", fields["artifact_digest"])
        set_clauses.append("artifact_available = TRUE")

    updated = await conn.fetchrow(
        f"""
        UPDATE garuda_practices SET {', '.join(set_clauses)}
         WHERE practice_id = $1 AND state = ANY($3::text[])
         RETURNING practice_id, state, customer_reason_key, required_action_key,
                   artifact_available
        """,
        *params,
    )
    if updated is None:  # pragma: no cover - defensive, FOR UPDATE prevents this
        raise HTTPException(
            status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "retryable": False}
        )

    if spec.kind in _EVIDENCE_KIND:
        # UNIQUE(practice_id, evidence_id) (305) makes an idempotent replay
        # of the same command a no-op INSERT, never a duplicate row -- the
        # exact replay path never reaches here at all (it returns from
        # `idempotency.reserve`'s replay outcome before this function is
        # ever called), but ON CONFLICT DO NOTHING is still the correct
        # posture for a retry that reaches this far and re-executes.
        await conn.execute(
            """
            INSERT INTO garuda_practice_evidence
                (practice_id, transition_id, evidence_id, kind, recorded_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (practice_id, evidence_id) DO NOTHING
            """,
            practice_id,
            transition_id,
            fields["evidence_id"],
            _EVIDENCE_KIND[spec.kind],
            actor["email"],
        )

    event_id = await journal.append_event(
        conn,
        event_name=spec.event_name,
        aggregate_type="practice",
        aggregate_id=practice_id,
        transition_id=transition_id,
        customer_visible=True,
        idempotency_key_digest=key_digest,
        canonical_payload_digest=payload_digest,
        detail={k: v for k, v in fields.items() if k != "private_staff_note"},
        event_id=block_event_id,
    )
    # A literal if/elif chain assigning `job_type`, not `spec.field` or a
    # dict lookup, ON PURPOSE and INLINE (not a helper function) so the
    # assignment sits in `enqueue_outbox`'s OWN enclosing function scope:
    # `test_outbox_job_type_coverage.py`'s AST walker
    # (`_constant_strings`/`_resolve_name`) proves every `enqueue_outbox`
    # call site's `job_type=` statically by walking the call's enclosing
    # `FunctionDef` for assignments to the referenced name — it explicitly
    # REFUSES an attribute access (`spec.outbox_job_type`), a mapping
    # subscript (`mapping[key]`), and a call (`helper(x)`) as
    # unresolvable-and-therefore-a-build-failure (that file's own
    # `test_checker_refuses_shapes_it_cannot_prove`), and an assignment
    # living in a DIFFERENT function than the call site is invisible to
    # `_enclosing_function` + `_resolve_name` the same way. Each branch
    # below is a separate `ast.Assign` of a bare string literal in THIS
    # function, which the walker resolves.
    if transition_id == "PR-02":
        job_type = "practice_in_review_email"
    elif transition_id in ("PR-03", "PR-05", "PR-08"):
        job_type = "practice_blocked_email"
    elif transition_id == "PR-04":
        job_type = "practice_submitted_email"
    elif transition_id == "PR-06":
        job_type = "practice_approved_email"
    elif transition_id == "PR-07":
        job_type = "practice_rejected_email"
    elif transition_id in ("PR-09", "PR-10"):
        job_type = "practice_resumed_email"
    else:
        job_type = "practice_delivered_email"

    await journal.enqueue_outbox(
        conn,
        order_id=row["order_id"],
        journal_event_id=event_id,
        job_type=job_type,
    )
    return updated
