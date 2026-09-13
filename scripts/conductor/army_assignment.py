"""Pure validator for the "dual-consul army" assignment-parent graph.

This module is a SIBLING vocabulary to `scripts.conductor.contracts`, not an
extension of it: `Role`/`Decision` there describe a session-local endpoint
plan, while `ArmyRole` here describes a mission-scoped command hierarchy
(imperator -> general -> specialist/builder/support). The two enums are
deliberately different names for different concepts and must never be
conflated.

`validate_plan` is pure, deterministic, and stdlib-only: no I/O, no clock, no
randomness, no mutation of its input. It answers exactly one question — is
this assignment-parent graph (plus its optional appointment block) internally
consistent — and returns a `ValidationResult` carrying a `Decision` from
`contracts.py` (`ALLOW` or `BLOCK` only; the other `Decision` members describe
outcomes this validator never produces) plus sorted, stable reason codes and
offending ids.

Explicit non-goals: no scheduler, no ledger, no persistence, no network, no
file I/O, no dispatch, no grant. This module decides validity only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

try:
    from scripts.conductor.contracts import Decision
except ImportError:  # pragma: no cover - exercised when imported standalone
    class Decision(StrEnum):
        """An outcome of pure planning, including a visible abstention."""

        ALLOW = "allow"
        DELEGATE_REQUIRED = "delegate_required"
        BLOCK = "block"
        DEGRADED = "degraded"
        ABSTAIN = "abstain"


SCHEMA_VERSION = "army-assignment/1"

_VALID_DUX_CANDIDATES = frozenset({"opus", "sol"})
_REQUIRED_IMPERATORS = frozenset({"fable", "astra"})


class ArmyRole(StrEnum):
    """A role in the army command hierarchy (mission-scoped, not session-local)."""

    IMPERATOR = "imperator"
    GENERAL = "general"
    SPECIALIST = "specialist"
    BUILDER = "builder"
    SUPPORT = "support"


_ROLES_REQUIRING_PARENT = frozenset({ArmyRole.SPECIALIST, ArmyRole.BUILDER, ArmyRole.SUPPORT})


@dataclass(frozen=True)
class Assignment:
    """One node in the assignment-parent graph."""

    assignment_id: str
    mission_id: str
    role: ArmyRole
    parent_id: str | None
    generation: int


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of `validate_plan`: a decision plus stable, sorted evidence."""

    decision: Decision
    reason_codes: tuple[str, ...]
    offending_ids: tuple[str, ...]


def _is_missing(value: object) -> bool:
    """True when a required field is absent, None, or an empty string."""
    return value is None or value == ""


def _block(reason_codes: set[str], offending_ids: set[str]) -> ValidationResult:
    return ValidationResult(
        decision=Decision.BLOCK,
        reason_codes=tuple(sorted(reason_codes)),
        offending_ids=tuple(sorted(offending_ids)),
    )


def _validate_appointment(
    appointment: object,
    reason_codes: set[str],
    offending_ids: set[str],
    payload_self_supplied: bool,
) -> None:
    """Validate the optional `appointment` block, mutating the two accumulators.

    `mission_uuid` is treated as an OPAQUE externally-supplied value: this
    function never generates, completes, or normalises it. It only checks
    that one was supplied by the caller and that the caller did not mark it
    self-supplied.
    """
    if not isinstance(appointment, dict):
        reason_codes.add("missing_required_field")
        offending_ids.add("appointment")
        return

    dux = appointment.get("dux")
    if dux not in _VALID_DUX_CANDIDATES:
        reason_codes.add("invalid_dux_candidate")
        offending_ids.add("appointment")

    approvals = appointment.get("approvals")
    if not isinstance(approvals, list):
        approvals = []
    hashes_by_imperator: dict[str, list[str | None]] = {}
    for approval in approvals:
        if not isinstance(approval, dict):
            continue
        imperator = approval.get("imperator")
        packet_hash = approval.get("packet_hash")
        if imperator in _REQUIRED_IMPERATORS:
            hashes_by_imperator.setdefault(imperator, []).append(packet_hash)

    # "Each imperator exactly once": zero OR more than one approval from the
    # same imperator both mean that imperator's single required approval is
    # absent — a repeat is not a stronger approval, it is a missing one.
    approved_once = {name for name, hashes in hashes_by_imperator.items() if len(hashes) == 1}
    missing_imperators = _REQUIRED_IMPERATORS - approved_once
    if missing_imperators:
        reason_codes.add("missing_imperator_approval")
        offending_ids.add("appointment")

    # Hash agreement is judged only across the imperators who approved exactly
    # once; a duplicate's hash(es) never feed this comparison, so a repeated
    # approval cannot accidentally cause (or hide) a packet_hash_mismatch.
    packet_hashes = {hashes_by_imperator[name][0] for name in approved_once}
    if len(packet_hashes) > 1:
        reason_codes.add("packet_hash_mismatch")
        offending_ids.add("appointment")

    mission_uuid = appointment.get("mission_uuid")
    uuid_self_supplied = payload_self_supplied or bool(appointment.get("uuid_self_supplied"))
    if _is_missing(mission_uuid) or not isinstance(mission_uuid, str) or uuid_self_supplied:
        reason_codes.add("self_supplied_uuid")
        offending_ids.add("appointment")


def validate_plan(payload: dict) -> ValidationResult:
    """Validate an assignment-parent graph plus its optional appointment block.

    Pure and deterministic: the same `payload` always yields an equal
    `ValidationResult`, with `reason_codes` and `offending_ids` sorted so
    ordering never depends on dict/set iteration order. `payload` is never
    mutated. A `"messages"` list, if present, is TRAFFIC and is ignored
    entirely for cycle detection.
    """
    if not isinstance(payload, dict):
        return _block({"missing_required_field"}, set())

    reason_codes: set[str] = set()
    offending_ids: set[str] = set()

    schema_version = payload.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        reason_codes.add("unknown_schema_version")

    raw_assignments = payload.get("assignments")
    if not isinstance(raw_assignments, list):
        raw_assignments = []

    # by_id maps to the FIRST occurrence only; later duplicate ids are recorded
    # separately so the caller still sees every offending id.
    by_id: dict[str, Assignment] = {}
    duplicate_ids: set[str] = set()
    conflicting_parent_ids: set[str] = set()

    for raw in raw_assignments:
        if not isinstance(raw, dict):
            reason_codes.add("missing_required_field")
            continue

        assignment_id = raw.get("assignment_id")
        mission_id = raw.get("mission_id")
        role_raw = raw.get("role")
        parent_id = raw.get("parent_id")
        generation = raw.get("generation")

        if _is_missing(assignment_id) or _is_missing(mission_id) or _is_missing(role_raw):
            reason_codes.add("missing_required_field")
            if not _is_missing(assignment_id):
                offending_ids.add(assignment_id)
            continue

        try:
            role = ArmyRole(role_raw)
        except ValueError:
            reason_codes.add("missing_required_field")
            offending_ids.add(assignment_id)
            continue

        if not (isinstance(generation, int) and not isinstance(generation, bool) and generation >= 0):
            reason_codes.add("invalid_generation")
            offending_ids.add(assignment_id)

        if parent_id is not None and (not isinstance(parent_id, str) or parent_id == ""):
            reason_codes.add("missing_required_field")
            offending_ids.add(assignment_id)
            continue

        assignment = Assignment(
            assignment_id=assignment_id,
            mission_id=mission_id,
            role=role,
            parent_id=parent_id,
            generation=generation if isinstance(generation, int) else 0,
        )

        if assignment_id in by_id:
            duplicate_ids.add(assignment_id)
            if by_id[assignment_id].parent_id != assignment.parent_id:
                conflicting_parent_ids.add(assignment_id)
            continue

        by_id[assignment_id] = assignment

    if duplicate_ids:
        reason_codes.add("duplicate_assignment_id")
        offending_ids |= duplicate_ids

    if conflicting_parent_ids:
        reason_codes.add("two_operational_parents")
        offending_ids |= conflicting_parent_ids

    for assignment in by_id.values():
        if assignment.parent_id is None:
            if assignment.role in _ROLES_REQUIRING_PARENT:
                reason_codes.add("unassigned_parent")
                offending_ids.add(assignment.assignment_id)
            continue

        parent = by_id.get(assignment.parent_id)
        if parent is None:
            reason_codes.add("dangling_parent")
            offending_ids.add(assignment.assignment_id)
            continue

        if parent.mission_id != assignment.mission_id:
            reason_codes.add("cross_mission_edge")
            offending_ids.add(assignment.assignment_id)

    # Cycle detection over the parent-only graph (never "messages"). A
    # self-parent is a cycle of length 1 and is caught by this same walk.
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node_id: WHITE for node_id in by_id}
    cyclic_ids: set[str] = set()

    def visit(node_id: str, stack: list[str]) -> None:
        color[node_id] = GRAY
        stack.append(node_id)
        parent_id = by_id[node_id].parent_id
        if parent_id is not None and parent_id in by_id:
            if color[parent_id] == GRAY:
                cycle_start = stack.index(parent_id)
                cyclic_ids.update(stack[cycle_start:])
            elif color[parent_id] == WHITE:
                visit(parent_id, stack)
        stack.pop()
        color[node_id] = BLACK

    for node_id in sorted(by_id):
        if color[node_id] == WHITE:
            visit(node_id, [])

    if cyclic_ids:
        reason_codes.add("parent_cycle")
        offending_ids |= cyclic_ids

    if "appointment" in payload:
        payload_self_supplied = bool(payload.get("uuid_self_supplied"))
        _validate_appointment(payload["appointment"], reason_codes, offending_ids, payload_self_supplied)

    if reason_codes:
        return _block(reason_codes, offending_ids)

    return ValidationResult(decision=Decision.ALLOW, reason_codes=(), offending_ids=())
