"""The D3 bitemporal reader, as an EXECUTABLE SPECIFICATION — not the production reader.

WHAT THIS IS. `R-research-os.md` D3 decides the semantics of the one question the Research OS
exists to answer: *what did we hold true at valid time T, as known at system time S?* R2 will
implement that against `research_os_objects` in `services/research_os/naga_bitemporal_reader.py`.
R1 may not write under `services/**` or `packages/research-os-core/**`, so the decision lands
here, in the test tree, as a reference implementation over an in-memory corpus. R2's acceptance
is that its SQL reader answers the same way on the same fixtures.

WHY A REFERENCE IMPLEMENTATION AND NOT PROSE. D3 is a five-step algorithm whose ORDER is
load-bearing — integrity before temporal filtering, system time before valid time, and no
ranking at the end. A paragraph can describe that order; only code can be wrong about it in a
way a test catches. The module's docstrings say which line of `CONTRACTS.md` each rule serves,
so a reader can check the code against the frozen contract rather than against this file's
opinion.

WHAT IT DELIBERATELY DOES NOT DO. It does not touch PostgreSQL, it does not hash, it does not
validate schemas (the fixtures are validated separately), and it does not know what a claim
MEANS. It answers with an identity — `claim_id` plus `object_hash` — and never with a value,
because a reader that returns a value invites a caller to trust the value without the hash.

INSTANTS. Every comparison here is between PARSED instants. That is not a detail: the canonical
wire form is text, the fraction is optional, and `.` (0x2E) sorts before `Z` (0x5A), so the
microsecond-zero instant sorts LAST in raw text although it is chronologically FIRST. That is
exactly the defect `PENDING-ARMS.md:21` has carried open since 2026-08-26, and D2 repairs it in
storage with an IMMUTABLE key function. This reader is the semantic side of the same repair:
it parses, so it is right for free, and `test_research_os_temporal_rows.py` pins the
disagreement between text order and chronological order so nobody "optimises" the parse away.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

__all__ = [
    "SUBJECT_KEY_NAMESPACE",
    "Answer",
    "Abstain",
    "Quarantine",
    "ReadResult",
    "parse_instant",
    "instant_sort_key",
    "subject_key_of",
    "read",
]

#: The one namespace in which `subject_key` lives. Reverse-DNS, per
#: `research_os.primitives._REVERSE_DNS_RE`; the extension carries no core field name, per
#: `research_os.primitives.V1_RESERVED_EXTENSION_FIELD_NAMES`. Defined ONCE, here, and asserted
#: against the real primitives in `test_research_os_subject_key_extension.py`.
SUBJECT_KEY_NAMESPACE = "com.balizero.research-os.naga"

#: Every spelling of a UTC instant the published `UtcDateTime` schema admits: an optional
#: fraction of any width, `Z` or `+00:00` as the terminator, and a lowercase `t` separator.
_INSTANT_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[Tt](?P<clock>\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d+)?(?P<zone>Z|z|\+00:00)$"
)


def parse_instant(text: str) -> datetime:
    """Parse a canonical UTC instant into a comparable value.

    Accepts every spelling the published schema admits and folds them: `Z` == `+00:00`,
    `t` == `T`, `.1Z` == `.100000Z`, and an absent fraction == `.000000Z`. Rejects anything
    else loudly — a reader that silently accepts a non-UTC offset would answer a bitemporal
    question in the wrong timezone, which is worse than not answering.
    """

    match = _INSTANT_RE.match(text)
    if match is None:
        raise ValueError(f"not a canonical UTC instant: {text!r}")
    fraction = (match.group("fraction") or ".0")[1:]
    microseconds = int((fraction + "000000")[:6])
    return datetime.fromisoformat(
        f"{match.group('date')}T{match.group('clock')}"
    ).replace(microsecond=microseconds, tzinfo=timezone.utc)


def instant_sort_key(text: str) -> str:
    """The 27-byte fixed-width key D2 puts in PostgreSQL, computed here in Python.

    Same grammar, same truncation policy (exact to the microsecond; sub-microsecond
    differences are not orderable by it), same output shape `YYYY-MM-DDTHH:MM:SS.ffffffZ`.
    It exists so R1's tests can pin the property R2's SQL function must have: byte order over
    the KEY agrees with chronological order over the parsed instant, for every admitted
    spelling. If the two ever disagree, one of the two implementations is wrong and the test
    says which pair of instants proves it.
    """

    moment = parse_instant(text)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond:06d}Z"


#: The registered-name prefix a claim family carries on an `ObjectSuccessorEdge`. The two fields
#: are DIFFERENT TYPES by contract: `Claim.claim_family_id` is `format: uuid`, while
#: `ObjectSuccessorEdge.family_id` and `graph.GraphMember.family_id` (`graph.py:24`) are
#: `RegisteredName`. Both shipped fixtures spell the edge side `naga.claim_family.<uuid>`
#: (`supersession/01`, the seed cohort's `correction_pair`).
CLAIM_FAMILY_NAMESPACE = "naga.claim_family."


def registered_family_name(claim_family_id: str) -> str:
    """The `RegisteredName` an edge must carry to bind a claim of this `claim_family_id`."""

    return f"{CLAIM_FAMILY_NAMESPACE}{claim_family_id}"


def _ref_id(ref: Mapping[str, Any]) -> str | None:
    """The claim a canonical `ExactObjectRef` names — `object_id`, never an invented `claim_id`.

    Gemini second reader N1: the reader used to index `ref["claim_id"]`, a key no canonical
    `ObjectSuccessorEdge` ref carries (`object_kind`, `object_id`, `object_hash`), so every
    schema-valid edge raised `KeyError` and only the tests' private edge shape ever worked.
    """

    if ref.get("object_kind") != "claim":
        return None
    object_id = ref.get("object_id")
    return object_id if isinstance(object_id, str) else None


def subject_key_of(claim: Mapping[str, Any]) -> str | None:
    """The `subject_key` this claim's family answers under, or None if it carries none.

    A claim without the extension is not an error — most canonical claims will not have one —
    but it can never be reached by `read`, which is keyed on it. The reader says
    `no_family_for_subject_key` rather than scanning the corpus for something plausible.
    """

    extensions = claim.get("extensions") or {}
    extension = extensions.get(SUBJECT_KEY_NAMESPACE)
    if not extension:
        return None
    payload = extension.get("payload") or {}
    key = payload.get("subject_key")
    return key if isinstance(key, str) else None


@dataclass(frozen=True)
class Answer:
    """Exactly one admissible answer. Carries an identity, never a value."""

    claim_id: str
    object_hash: str
    claim_family_id: str


@dataclass(frozen=True)
class Abstain:
    """No admissible answer, and the graph is sound.

    `reason` is one of `no_family_for_subject_key`, `no_version_recorded_by_known_at`,
    `no_valid_interval_covers_valid_at`. It is a VALUE, not a `None`: a caller that forgets to
    branch on it gets an `Abstain` object it cannot mistake for a claim, which is the whole
    point of not returning `None` (`CONTRACTS.md:141` — abstention is an outcome, not a gap).
    """

    reason: str


@dataclass(frozen=True)
class Quarantine:
    """The graph or the key is unsound. NEVER a winner.

    `CONTRACTS.md:141`: "Forks, missing nodes, hash mismatches, or cycles quarantine the family
    instead of selecting a winner." A quarantined family is REPORTED — if any family under the
    key quarantines, the whole read quarantines, because answering from the sound families
    would be exactly the bypass the contract forbids.
    """

    family_ids: tuple[str, ...]
    reasons: tuple[str, ...]


ReadResult = Answer | Abstain | Quarantine


@dataclass
class _Family:
    family_id: str
    members: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    edges: list[Mapping[str, Any]] = field(default_factory=list)


def _integrity_reasons(family: _Family) -> set[str]:
    """`research_os.graph`'s vocabulary, applied to one family.

    Deliberately a re-derivation and not a call into `graph.py`: R1 must not depend on the
    core's private traversal to state the READER's rule, and the reasons must be assertable
    on fixtures that the core's own graph helper is not shaped to take. The vocabulary is
    copied exactly so R2 can move to the core's helper later without renaming an outcome.
    """

    reasons: set[str] = set()
    outgoing: dict[str, set[str]] = {}
    for edge in family.edges:
        predecessor = _ref_id(edge["predecessor_ref"])
        successor = _ref_id(edge["successor_ref"])
        for ref, claim_id in (
            (edge["predecessor_ref"], predecessor),
            (edge["successor_ref"], successor),
        ):
            member = family.members.get(claim_id)
            if member is None:
                reasons.add("missing_node")
                continue
            if member["object_hash"] != ref.get("object_hash"):
                reasons.add("hash_mismatch")
            if registered_family_name(member["claim_family_id"]) != edge.get("family_id"):
                reasons.add("family_identity_mismatch")
        before, after = family.members.get(predecessor), family.members.get(successor)
        if before is not None and after is not None:
            if parse_instant(after["time"]["recorded_at"]) <= parse_instant(
                before["time"]["recorded_at"]
            ):
                reasons.add("successor_recorded_at_not_later")
        successors = outgoing.setdefault(predecessor, set())
        successors.add(successor)
        if len(successors) > 1:
            reasons.add("fork")

    if _has_cycle(outgoing):
        reasons.add("cycle")

    # STRUCTURAL terminal-member check (B6 cure, codex round 1 finding 6), mirroring
    # `graph.py::select_current_member`'s `current_keys = member_keys - outgoing_keys`: a
    # family must have EXACTLY one member with no outgoing successor edge, and this is a
    # property of the edge TOPOLOGY alone -- it does not depend on `known_at` at all.
    # R1-build-spec.md §2 step 2 runs integrity "BEFORE any temporal filter -- the order IS the
    # specification"; the defect this fixes is that `non_unique_current_member` used to be
    # computed only AFTER filtering candidates by `known_at` (inside `_current_at`), so a family
    # with two edge-less (therefore structurally non-unique) members whose `recorded_at` both
    # postdate `known_at` produced an EMPTY filtered set and the caller saw `Abstain` instead of
    # `Quarantine` -- the structural defect hid behind a query that happened to ask about the
    # past. Computing it here, over ALL members unconditionally, closes that.
    member_ids = set(family.members)
    outgoing_ids = {predecessor for predecessor, successors in outgoing.items() if successors}
    current_ids = member_ids - outgoing_ids
    if len(current_ids) != 1:
        reasons.add("non_unique_current_member")

    return reasons


def _has_cycle(adjacency: Mapping[str, set[str]]) -> bool:
    colour: dict[str, int] = {}
    for start in list(adjacency):
        stack = [(start, iter(adjacency.get(start, ())))]
        colour[start] = 1
        while stack:
            node, children = stack[-1]
            found = next(children, None)
            if found is None:
                colour[node] = 2
                stack.pop()
                continue
            if colour.get(found) == 1:
                return True
            if colour.get(found) is None:
                colour[found] = 1
                stack.append((found, iter(adjacency.get(found, ()))))
    return False


def _current_at(family: _Family, known_at: datetime) -> list[Mapping[str, Any]]:
    """The family members that are CURRENT as known at S.

    A version is a candidate when it was recorded at or before S — a system that did not know
    a claim yet cannot have believed it. A candidate is CURRENT when nothing had superseded it
    yet at S: either it has no successor edge at all, or its successor was recorded AFTER S and
    so was still in the future from S's point of view. This is what makes "what did we believe
    on date Y" a different question from "what is true now", and it is derived entirely from
    immutable `recorded_at` values and the edge — the predecessor is never mutated
    (`CONTRACTS.md:88`, `:267`, RULING B1 2026-08-26).
    """

    successor_by_predecessor = {
        _ref_id(edge["predecessor_ref"]): _ref_id(edge["successor_ref"]) for edge in family.edges
    }
    current: list[Mapping[str, Any]] = []
    for claim_id, member in family.members.items():
        if parse_instant(member["time"]["recorded_at"]) > known_at:
            continue
        successor_id = successor_by_predecessor.get(claim_id)
        if successor_id is not None:
            successor = family.members.get(successor_id)
            if successor is not None and parse_instant(
                successor["time"]["recorded_at"]
            ) <= known_at:
                continue
        current.append(member)
    return current


def _covers(member: Mapping[str, Any], valid_at: datetime) -> bool:
    """Half-open, always: `valid_from <= T < valid_to`, `null` end meaning open.

    `CONTRACTS.md:88` and `:267` both say half-open, and the boundary is the case that decides
    whether a scheduled rate change answers twice on its changeover instant or exactly once.
    `T == valid_from` is IN; `T == valid_to` is OUT.
    """

    times = member["time"]
    start = times.get("valid_from")
    end = times.get("valid_to")
    if start is not None and parse_instant(start) > valid_at:
        return False
    if end is not None and parse_instant(end) <= valid_at:
        return False
    return True


def _is_consequential(member: Mapping[str, Any]) -> bool:
    """`CONTRACTS.md:266` — consequential numeric and regulatory claims need explicit valid time.

    Derived from the canonical statement, never from a flag the caller sets (Gemini second
    reader N2): a claim is consequential when its `object_ref_or_value` is a NUMBER, or when its
    `subject_ref` names a `regulation`. Both are structural fields of the canonical `Claim`, so
    the rule still refuses natural-language classification — and a canonical claim can no
    longer escape the quarantine by simply not carrying an invented `consequential` key, which
    no schema defines.
    """

    statement = member.get("statement") or {}
    value = statement.get("object_ref_or_value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    subject = statement.get("subject_ref")
    return isinstance(subject, Mapping) and subject.get("object_kind") == "regulation"


def read(
    claims: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any]],
    subject_key: str,
    valid_at: str | datetime,
    known_at: str | datetime,
) -> ReadResult:
    """`read(subject_key, valid_at=T, known_at=S)` — D3, in the order D3 specifies.

    The order is the specification:

    1. GROUP the families carrying `subject_key`. None → `Abstain(no_family_for_subject_key)`.
    2. INTEGRITY, per family, BEFORE any temporal filter. Any reason → the whole read
       quarantines. Checking integrity after the filters would let a sound family answer past a
       forked one, which is the bypass `CONTRACTS.md:141` forbids.
    3. SYSTEM TIME. Candidates are versions with `recorded_at <= S`; a candidate is current when
       its successor is absent or recorded after S. Two current members in ONE family is
       `non_unique_current_member` — `graph.py` quarantines that without ever looking at valid
       intervals, which is exactly why two scheduled intervals are two FAMILIES and not two
       members (D3(ii)).
    4. VALID TIME, half-open, on each family's current member. A finite `valid_to` is never
       extended by succession: the successor's interval is its own and the predecessor's end
       stands as written. A `null` `valid_from` on a consequential claim is inadmissible
       (`CONTRACTS.md:266`) and quarantines rather than answering.
    5. ACROSS FAMILIES: zero → abstain, one → answer, two or more →
       `Quarantine(ambiguous_subject_key)`. Two families answering the same (T, S) is a
       modelling defect and the reader says so instead of ranking them.
    """

    moment_valid = valid_at if isinstance(valid_at, datetime) else parse_instant(valid_at)
    moment_known = known_at if isinstance(known_at, datetime) else parse_instant(known_at)

    families = _group(claims, edges, subject_key)
    if not families:
        return Abstain("no_family_for_subject_key")

    quarantined: dict[str, set[str]] = {}
    for family in families.values():
        reasons = _integrity_reasons(family)
        if reasons:
            quarantined[family.family_id] = reasons

    admissible: list[tuple[str, Mapping[str, Any]]] = []
    saw_any_candidate = False
    for family in families.values():
        if family.family_id in quarantined:
            continue
        current = _current_at(family, moment_known)
        if not current:
            continue
        saw_any_candidate = True
        if len(current) > 1:
            quarantined.setdefault(family.family_id, set()).add("non_unique_current_member")
            continue
        member = current[0]
        if member["time"].get("valid_from") is None and _is_consequential(member):
            quarantined.setdefault(family.family_id, set()).add(
                "null_valid_from_on_consequential_claim"
            )
            continue
        if _covers(member, moment_valid):
            admissible.append((family.family_id, member))

    if len(admissible) > 1:
        for family_id, _ in admissible:
            quarantined.setdefault(family_id, set()).add("ambiguous_subject_key")

    if quarantined:
        return Quarantine(
            family_ids=tuple(sorted(quarantined)),
            reasons=tuple(sorted({reason for reasons in quarantined.values() for reason in reasons})),
        )
    if not saw_any_candidate:
        return Abstain("no_version_recorded_by_known_at")
    if not admissible:
        return Abstain("no_valid_interval_covers_valid_at")

    family_id, member = admissible[0]
    return Answer(
        claim_id=member["claim_id"],
        object_hash=member["object_hash"],
        claim_family_id=family_id,
    )


def _group(
    claims: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any]],
    subject_key: str,
) -> dict[str, _Family]:
    """Group claims into families and attach each edge to the family it names.

    B5 cure (codex round 1 finding 5). An edge binds a family through its `RegisteredName`,
    `registered_family_name(claim_family_id)`, compared EXACTLY — the same exact equality
    `graph.py:118` applies, after the one typed conversion the contract itself implies
    (`Claim.claim_family_id` is a uuid, `ObjectSuccessorEdge.family_id` a registered name). The
    predecessor compared the two raw values, so the shipped correction edge
    (`naga.claim_family.bdd…` against claims carrying `bdd…`) was never attached and every
    temporal test stayed green over edges manufactured in the reader's private shape.

    An edge that touches this read is never silently dropped: one whose `family_id` names no
    family here but whose refs name a member of one is attached to that member's family, where
    `_integrity_reasons` quarantines it as `family_identity_mismatch` — ignoring it would be the
    very defect this function was cured of. An edge whose family AND refs name nothing under this
    `subject_key` belongs to another key's read and is not considered here (kimi round 2, LOW:
    the earlier wording promised more than that).
    """

    families: dict[str, _Family] = {}
    family_of_member: dict[str, _Family] = {}
    for claim in claims:
        if subject_key_of(claim) != subject_key:
            continue
        family_id = claim["claim_family_id"]
        family = families.setdefault(family_id, _Family(family_id=family_id))
        family.members[claim["claim_id"]] = claim
        family_of_member[claim["claim_id"]] = family
    by_registered_name = {registered_family_name(family_id): family for family_id, family in families.items()}
    for edge in edges:
        family = by_registered_name.get(edge.get("family_id", ""))
        if family is None:
            for ref in (edge.get("predecessor_ref") or {}, edge.get("successor_ref") or {}):
                family = family_of_member.get(_ref_id(ref) or "")
                if family is not None:
                    break
        if family is not None:
            family.edges.append(edge)
    return families


def corpus_from_fixture(document: Mapping[str, Any]) -> tuple[
    Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]
]:
    """Split a P06 bundle fixture into (claims, edges).

    The bundle's fixtures are worked examples with a descriptive envelope around their
    canonical objects; this is the ONE place that knows the envelope's shape, so a change to
    it costs one function and not every test.
    """

    objects = document.get("objects") or {}
    claims = list(objects.get("claims") or [])
    edges = list(objects.get("object_successor_edges") or [])
    return claims, edges
