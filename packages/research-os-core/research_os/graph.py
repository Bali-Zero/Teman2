"""Pure successor-family selection with fail-closed quarantine semantics."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from research_os.models.successor_edge import ObjectSuccessorEdge
from research_os.primitives import (
    ExactObjectRef,
    FrozenCoreModel,
    Identifier,
    RegisteredName,
    Sha256Hex,
    UtcDateTime,
)


class GraphMember(FrozenCoreModel):
    object_kind: Identifier
    object_id: str
    object_hash: Sha256Hex
    tenant: str
    family_id: RegisteredName
    recorded_at: UtcDateTime

    @property
    def exact_ref(self) -> ExactObjectRef:
        return ExactObjectRef(
            object_kind=self.object_kind,
            object_id=self.object_id,
            object_hash=self.object_hash,
        )


@dataclass(frozen=True)
class Current:
    member: GraphMember


@dataclass(frozen=True)
class Quarantined:
    reason_codes: tuple[str, ...]


def _member_key(member: GraphMember) -> tuple[str, str]:
    return member.object_kind, member.object_id


def _ref_key(reference: ExactObjectRef) -> tuple[str, str]:
    return reference.object_kind, reference.object_id


def _has_cycle(adjacency: dict[tuple[str, str], set[tuple[str, str]]]) -> bool:
    unseen, visiting, visited = 0, 1, 2
    states: dict[tuple[str, str], int] = {}

    for start in adjacency:
        if states.get(start, unseen) != unseen:
            continue
        states[start] = visiting
        stack: list[tuple[tuple[str, str], Iterator[tuple[str, str]]]] = [
            (start, iter(adjacency.get(start, set())))
        ]
        while stack:
            node, successors = stack[-1]
            try:
                successor = next(successors)
            except StopIteration:
                states[node] = visited
                stack.pop()
                continue

            successor_state = states.get(successor, unseen)
            if successor_state == visiting:
                return True
            if successor_state == unseen:
                states[successor] = visiting
                stack.append((successor, iter(adjacency.get(successor, set()))))
    return False


def select_current_member(
    edges: Sequence[ObjectSuccessorEdge],
    members: Sequence[GraphMember],
) -> Current | Quarantined:
    """Select the unique current member or quarantine every broken family."""

    reasons: list[str] = []
    family_identities = {
        (member.object_kind, member.tenant, member.family_id) for member in members
    }
    if len(family_identities) > 1:
        reasons.append("family_identity_mismatch")
    members_by_key: dict[tuple[str, str], GraphMember] = {}
    for member in members:
        key = _member_key(member)
        if key in members_by_key:
            reasons.append("duplicate_member")
        members_by_key[key] = member

    adjacency: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for edge in edges:
        predecessor_key = _ref_key(edge.predecessor_ref)
        successor_key = _ref_key(edge.successor_ref)
        predecessor = members_by_key.get(predecessor_key)
        successor = members_by_key.get(successor_key)
        if predecessor is None or successor is None:
            reasons.append("missing_node")
        if predecessor is not None and predecessor.object_hash != edge.predecessor_ref.object_hash:
            reasons.append("hash_mismatch")
        if successor is not None and successor.object_hash != edge.successor_ref.object_hash:
            reasons.append("hash_mismatch")
        for related_member in (predecessor, successor):
            if related_member is not None and (
                related_member.object_kind != edge.object_kind
                or related_member.tenant != edge.tenant
                or related_member.family_id != edge.family_id
            ):
                reasons.append("family_identity_mismatch")
        if (
            predecessor is not None
            and successor is not None
            and successor.recorded_at <= predecessor.recorded_at
        ):
            reasons.append("successor_recorded_at_not_later")
        successors = adjacency.setdefault(predecessor_key, set())
        successors.add(successor_key)
        if len(successors) > 1:
            reasons.append("fork")

    if _has_cycle(adjacency):
        reasons.append("cycle")

    member_keys = set(members_by_key)
    outgoing_keys = {key for key, successors in adjacency.items() if successors}
    current_keys = member_keys - outgoing_keys
    if len(current_keys) != 1:
        reasons.append("non_unique_current_member")

    if reasons:
        return Quarantined(tuple(dict.fromkeys(reasons)))
    if not current_keys:
        return Quarantined(("non_unique_current_member",))
    current_key = next(iter(current_keys))
    return Current(members_by_key[current_key])
