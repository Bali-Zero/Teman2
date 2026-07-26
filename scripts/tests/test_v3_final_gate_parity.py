from __future__ import annotations

"""Tripwire: V3_FINAL_GATE_READY may only become True once
check_worker_plane_review.py's route/identity/schema constants have parity
with launch_worker_plane_review_panel.py's real production values.

Today V3_FINAL_GATE_READY is False, so every assertion below reads
`not V3_FINAL_GATE_READY or <parity>` -- true regardless of parity while the
flag is False, which is why these tests pass right now even though parity
does NOT currently hold (see the warning comment above V3_FINAL_GATE_READY
in check_worker_plane_review.py for the full list of what's still stale).
The moment someone flips the flag to True without doing that reconciliation
work, these assertions become live and fail loudly in CI -- instead of the
validator silently accepting a stale v2-generation route/identity/schema set
as if it were v3.

Repo rule this encodes rather than merely documents: if a critical
constraint is violable, encode it.
"""

from scripts import check_worker_plane_review as validator
from scripts import launch_worker_plane_review_panel as launcher


def _launcher_route_set() -> frozenset[str]:
    """The route labels a real v3 launch actually produces: each parallel
    reviewer seat's requested_route, plus the separate Fable final-gate
    seat's requested_route."""
    return frozenset(
        {seat.requested_route for seat in launcher.SEATS}
        | {launcher.FABLE_GATE.requested_route}
    )


def test_v3_final_gate_ready_requires_route_set_parity_with_launcher() -> None:
    launcher_routes = _launcher_route_set()
    parity = validator.EXPECTED_ROUTES == launcher_routes
    assert not validator.V3_FINAL_GATE_READY or parity, (
        "V3_FINAL_GATE_READY is True but check_worker_plane_review."
        f"EXPECTED_ROUTES {sorted(validator.EXPECTED_ROUTES)} does not match "
        f"the launcher's real v3 route set {sorted(launcher_routes)} -- "
        "reconcile the validator's route constants (see the warning comment "
        "above V3_FINAL_GATE_READY) before flipping the flag."
    )


def test_v3_final_gate_ready_requires_fable_identity_parity_with_launcher() -> None:
    launcher_fable_identity = launcher.PRODUCTION_IDENTITIES["fable"]
    launcher_fable_path = str(launcher.PRODUCTION_CLIENTS.fable)
    validator_identity = validator.EXPECTED_EXECUTABLE_IDENTITIES.get(
        "claude-fable-5"
    )
    parity = (
        validator_identity is not None
        and validator.CLAUDE_EXECUTABLE == launcher_fable_path
        and validator_identity["sha256"] == launcher_fable_identity.sha256
        and validator_identity["cdhash"] == launcher_fable_identity.cdhash
    )
    assert not validator.V3_FINAL_GATE_READY or parity, (
        "V3_FINAL_GATE_READY is True but the validator's pinned Fable "
        f"executable ({validator.CLAUDE_EXECUTABLE!r}, sha256="
        f"{(validator_identity['sha256'] if validator_identity else None)!r}) "
        f"does not match the launcher's production Fable identity "
        f"({launcher_fable_path!r}, sha256={launcher_fable_identity.sha256!r}) "
        "-- reconcile before flipping the flag."
    )


def test_v3_final_gate_ready_requires_schema_version_parity_with_launcher() -> None:
    parity = validator.INVOCATION_SCHEMA == launcher.LAUNCHER_SCHEMA
    assert not validator.V3_FINAL_GATE_READY or parity, (
        "V3_FINAL_GATE_READY is True but validator INVOCATION_SCHEMA "
        f"({validator.INVOCATION_SCHEMA!r}) is a different protocol "
        f"generation than launcher LAUNCHER_SCHEMA "
        f"({launcher.LAUNCHER_SCHEMA!r}) -- reconcile before flipping the "
        "flag."
    )
