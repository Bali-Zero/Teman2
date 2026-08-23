from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from research_os.graph import Current, GraphMember, Quarantined, select_current_member
from research_os.hashing import object_hash as compute_object_hash
from research_os.models.successor_edge import ObjectSuccessorEdge

UTC = timezone.utc


def _member(index: int, *, object_hash: str | None = None) -> GraphMember:
    return GraphMember(
        object_kind="synthetic_record",
        object_id=f"record-{index}",
        object_hash=object_hash or f"{index + 1:064x}",
        tenant="bali-zero",
        family_id="com.example.family-1",
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
    )


def _edge(predecessor: GraphMember, successor: GraphMember) -> ObjectSuccessorEdge:
    payload = {
        "object_successor_edge_id": str(uuid4()),
        "contract_version": "research-os/v1.0.0",
        "tenant": "bali-zero",
        "object_kind": predecessor.object_kind,
        "family_id": predecessor.family_id,
        "predecessor_ref": predecessor.exact_ref.model_dump(mode="json"),
        "successor_ref": successor.exact_ref.model_dump(mode="json"),
        "reason_code": "com.example.corrected",
        "recorded_at": successor.recorded_at.isoformat().replace("+00:00", "Z"),
        "producer": {"name": "synthetic.test", "version": "1.0.0"},
        "lineage": {"input_hashes": []},
        "retention": {"retention_class": "audit", "legal_hold": False},
    }
    payload["object_hash"] = compute_object_hash(payload)
    return ObjectSuccessorEdge.model_validate(payload)


def test_graph_selects_unique_current_member() -> None:
    first, second = _member(0), _member(1)
    result = select_current_member([_edge(first, second)], [first, second])
    assert isinstance(result, Current)
    assert result.member == second


def test_fork_quarantines_family() -> None:
    first, second, third = _member(0), _member(1), _member(2)
    result = select_current_member(
        [_edge(first, second), _edge(first, third)], [first, second, third]
    )
    assert isinstance(result, Quarantined)
    assert "fork" in result.reason_codes


def test_cycle_quarantines_family() -> None:
    first, second = _member(0), _member(1)
    result = select_current_member([_edge(first, second), _edge(second, first)], [first, second])
    assert isinstance(result, Quarantined)
    assert "cycle" in result.reason_codes


def test_missing_node_quarantines_family() -> None:
    first, second = _member(0), _member(1)
    result = select_current_member([_edge(first, second)], [first])
    assert isinstance(result, Quarantined)
    assert "missing_node" in result.reason_codes


def test_hash_mismatch_quarantines_family() -> None:
    first, second = _member(0), _member(1)
    mismatched_second = _member(1, object_hash="f" * 64)
    result = select_current_member([_edge(first, second)], [first, mismatched_second])
    assert isinstance(result, Quarantined)
    assert "hash_mismatch" in result.reason_codes


def test_non_increasing_recorded_at_quarantines_family() -> None:
    first, second = _member(1), _member(0)
    result = select_current_member([_edge(first, second)], [first, second])
    assert isinstance(result, Quarantined)
    assert "successor_recorded_at_not_later" in result.reason_codes


def test_members_from_multiple_families_quarantine_without_edges() -> None:
    first = _member(0)
    second = _member(1).model_copy(update={"family_id": "com.example.family-2"})
    result = select_current_member([], [first, second])
    assert isinstance(result, Quarantined)
    assert "family_identity_mismatch" in result.reason_codes


def test_long_linear_chain_returns_current_member_without_recursion_failure() -> None:
    members = [_member(index) for index in range(5_001)]
    edges = [_edge(members[index], members[index + 1]) for index in range(5_000)]

    result = select_current_member(edges, members)

    assert isinstance(result, Current)
    assert result.member == members[-1]


def test_long_cyclic_chain_quarantines_without_recursion_failure() -> None:
    members = [_member(index) for index in range(5_001)]
    edges = [_edge(members[index], members[index + 1]) for index in range(5_000)]
    edges.append(_edge(members[-1], members[0]))

    result = select_current_member(edges, members)

    assert isinstance(result, Quarantined)
    assert "cycle" in result.reason_codes
