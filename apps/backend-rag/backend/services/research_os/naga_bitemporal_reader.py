"""D3's bitemporal reader, in production, over `research_os_objects`-shaped in-memory data.

WHAT ANSWERS THIS MODULE IMPLEMENTS. `read(subject_key, valid_at, known_at, objects)` answers
*what did we hold true at valid time T, as known at system time S?* — R2-build-spec.md §4. The
algorithm and its ORDER are not this module's invention: they are R1's contract, executed here
as `objects` a live `research_os_objects`-shaped payload rather than a test-tree fixture.
`research_os_reader_reference.py` (`apps/backend-rag/backend/tests/unit/research_os/`) is the
EXECUTABLE SPECIFICATION this module is measured against — `test_naga_bitemporal_reader.py`
parametrizes both over the same corpora and asserts agreement. This module may not import that
one (production code does not import from `tests/`), so the algorithm is re-derived here,
independently, to the same contract.

ORDER IS THE SPECIFICATION (R2-build-spec.md §4, restating R1's D3 five steps):

1. GROUP the families carrying `subject_key`.
2. INTEGRITY FIRST, per family, regardless of `known_at` — `hash_mismatch`,
   `family_identity_mismatch`, `successor_recorded_at_not_later`, `fork`, `cycle`,
   `non_unique_current_member`. R1 blocker 2: a structurally invalid family whose duplicate
   terminal members sit in the FUTURE still quarantines, because this step runs unconditionally
   over the whole family, never after a `known_at` filter has already thinned it out.
3. SYSTEM TIME: a member is a candidate when `recorded_at <= known_at`; it is CURRENT when its
   successor is absent or was itself recorded after `known_at`.
4. VALID TIME, half-open: `valid_from <= T < valid_to`, `null` end = open. A finite `valid_to`
   is never extended by succession. A `null` `valid_from` on a consequential claim (a numeric
   value, or a `regulation` subject) is inadmissible.
5. At most ONE admissible answer across families; zero → Abstain, two or more →
   `Quarantine(ambiguous_subject_key)`. A quarantined family is REPORTED, never filtered away.

TWO DELIBERATE STRENGTHENINGS OVER R1'S REFERENCE (both spec-directed, both never disagree with
R1 on the fixtures R1 ships, because those fixtures are already internally consistent):

- `hash_mismatch` RECOMPUTES via `research_os.hashing.object_hash` (R2-build-spec.md §4 step 2:
  "hash_mismatch (recompute via core hashing)"), rather than trusting a claim's own declared
  `object_hash` field the way the reference implementation does. A member's declared hash is
  first checked against a recomputed one; an `ObjectSuccessorEdge` ref's stated hash is then
  checked against the RECOMPUTED value, never against the (possibly tampered) declared one.
  When the object does not carry enough to hash (no `contract_version` — never true for a
  persisted canonical object, since `naga_persistence.py` rejects a write whose hash does not
  already verify), this falls back to the declared value, matching R1's reference exactly on the
  reader-shaped minimal test rows that omit it.
- `unparseable_instant` is a NEW Quarantine reason (module-local addition; R1's own vocabulary
  has no case for it because every fixture it ships parses). A `recorded_at`, `valid_from` or
  `valid_to` that does not parse under `instant_key`'s grammar quarantines the family rather than
  raising or silently sorting first/last — the same "never crash on this data, always name a
  reason" posture D4 states explicitly for admission.
- `malformed_member` / `malformed_edge` are NEW Quarantine reasons on the same footing, for the
  same reason one step earlier: `research_os_objects` is a polymorphic store with a second
  writer and no payload-shape CHECK, so a row can arrive without the keys every traversal below
  subscripts. Structure is checked FIRST and returns early, so a malformed row is named and
  quarantined instead of raising a `KeyError` that would take `read()` down for the whole
  `subject_key`, sound families included.

INSTANTS. Every temporal comparison in this module goes through `instant_key`, never through a
parsed `datetime` and never through raw text — R2-build-spec.md §4: "All temporal comparisons go
through instant_key." Byte order over the 27-byte key agrees with chronological order over the
parsed instant for every admitted spelling (`test_naga_bitemporal_reader.py`'s
`TestInstantKeyDomain` pins this against R1's `instant_sort_key`), so string comparison alone
is correct and avoids a second parsing implementation.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from research_os.hashing import object_hash as _recompute_object_hash

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)

__all__ = [
    "CLAIM_FAMILY_NAMESPACE",
    "SUBJECT_KEY_NAMESPACE",
    "Abstain",
    "Answer",
    "Quarantine",
    "ReadResult",
    "instant_key",
    "read",
    "registered_family_name",
    "subject_key_of",
]

#: The one namespace `subject_key` lives in — mirrors
#: `research_os_reader_reference.SUBJECT_KEY_NAMESPACE` byte for byte (R2-build-spec.md §1.1).
SUBJECT_KEY_NAMESPACE = "com.balizero.research-os.naga"

#: The registered-name prefix a claim family carries on an `ObjectSuccessorEdge`.
#: `Claim.claim_family_id` is `format: uuid`; `ObjectSuccessorEdge.family_id` is a
#: `RegisteredName` carrying this prefix plus that uuid — two different types by contract.
CLAIM_FAMILY_NAMESPACE = "naga.claim_family."

#: Byte-for-byte the grammar `R2-build-spec.md` §1.1 quotes from R1's committed
#: `research_os_reader_reference._INSTANT_RE`: separator `T`/`t`, terminator `Z`/`z`/`+00:00`,
#: an optional fraction of any width. `z` lowercase is admitted; the mandate text names only
#: `t`, the code admits both — built against the code, per spec.
_INSTANT_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[Tt](?P<clock>\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d+)?(?P<zone>Z|z|\+00:00)$"
)


def instant_key(text: str) -> str | None:
    """The 27-byte fixed-width sort key `YYYY-MM-DDTHH:MM:SS.ffffffZ`, or `None`.

    Same grammar and folding as R1's `instant_sort_key`: `Z` == `+00:00`, `t` == `T`,
    `.1Z` == `.100000Z`, an absent fraction == `.000000Z`, and a fraction longer than six digits
    is TRUNCATED (exact to the microsecond; sub-microsecond differences are not orderable by
    this key — D2's declared precision policy).

    Returns `None`, never raises, wherever R1's `parse_instant` would raise `ValueError` —
    measured directly against it (not assumed) over: a structurally wrong string (empty, no
    zone, a non-UTC `+07:00` offset, free text); and a string the regex admits SYNTACTICALLY but
    that is not a real calendar instant — 2026-02-30, a non-leap-year February 29th, hour 24,
    second 60, year 0000, month 13, day 00 all raise inside the underlying
    `datetime.fromisoformat`/`datetime.replace` construction, and Python's `\\d` is
    Unicode-aware so a non-ASCII-digit spelling (e.g. Arabic-Indic) matches the regex. That
    last one is rejected by `datetime.fromisoformat`'s ASCII-only parser ONLY when the Unicode
    digit sits in the DATE or CLOCK. A Unicode digit in the FRACTION ALONE
    (`2026-09-11T10:00:00.١Z`) never reaches `fromisoformat` -- it goes to `int()`, which
    accepts it -- so this function returns a key while migration 312's POSIX `[0-9]` pattern
    returns NULL for the same text. That divergence is R1's (`_INSTANT_RE` is mirrored from
    R1's reference and R2 may not edit it); R2 fences it at the only path that could reach
    storage, `naga_persistence._WRITE_INSTANT_RE`, which spells digits `[0-9]`. Measured and
    pinned in `backend.tests.migrations.test_migration_312_instant_key_parity`
    ::test_non_ascii_digits_in_the_fraction_diverge_and_the_writer_fences_it. The full
    measurement table lives in `test_naga_bitemporal_reader.py::TestInstantKeyDomain`.
    """

    match = _INSTANT_RE.match(text)
    if match is None:
        return None
    fraction = (match.group("fraction") or ".0")[1:]
    try:
        microseconds = int((fraction + "000000")[:6])
        moment = datetime.fromisoformat(
            f"{match.group('date')}T{match.group('clock')}"
        ).replace(microsecond=microseconds, tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond:06d}Z"


def registered_family_name(claim_family_id: str) -> str:
    """The `RegisteredName` an edge must carry to bind a claim of this `claim_family_id`."""

    return f"{CLAIM_FAMILY_NAMESPACE}{claim_family_id}"


def _ref_id(ref: Mapping[str, Any]) -> str | None:
    """The claim an `ExactObjectRef` names — `object_id`, never an invented `claim_id` key."""

    if ref.get("object_kind") != "claim":
        return None
    object_id = ref.get("object_id")
    return object_id if isinstance(object_id, str) else None


def subject_key_of(claim: Mapping[str, Any]) -> str | None:
    """The `subject_key` this claim's family answers under, or `None` if it carries none."""

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
    `no_valid_interval_covers_valid_at` — a VALUE, never `None`.
    """

    reason: str


@dataclass(frozen=True)
class Quarantine:
    """The graph or a key inside it is unsound. NEVER a winner, ALWAYS reported."""

    family_ids: tuple[str, ...]
    reasons: tuple[str, ...]


ReadResult = Answer | Abstain | Quarantine


@dataclass
class _Family:
    family_id: str
    members: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    edges: list[Mapping[str, Any]] = field(default_factory=list)


def _recomputed_hash(member: Mapping[str, Any]) -> str | None:
    """The member's payload hash, recomputed via core hashing — never trusted from the field.

    `None` when the object does not carry a `contract_version` (so `object_hash` has nothing to
    select an omission set by) — never true for a persisted canonical object, since
    `naga_persistence.py` refuses a write whose declared hash does not already verify. Callers
    fall back to the declared value in that case, which matches R1's simpler reference exactly
    on reader-shaped minimal test rows that omit non-reader fields.
    """

    if "contract_version" not in member:
        return None
    try:
        return _recompute_object_hash(member)
    except (ValueError, TypeError):
        return None


def _integrity_reasons(family: _Family) -> set[str]:
    """R1's integrity vocabulary, over one family, with the two spec-directed strengthenings.

    Deliberately a re-derivation rather than a call into `research_os.graph` — the same
    posture R1's own reference took (`research_os_reader_reference._integrity_reasons`
    docstring): the reasons must be assertable on reader-shaped rows the core's own traversal
    helper is not built to take, and the vocabulary is copied exactly so a future move to the
    core's helper renames nothing.
    """

    reasons: set[str] = set()

    # STRUCTURE BEFORE SEMANTICS, and it returns early on purpose.
    #
    # Every line below this block hard-subscripts keys a sound row always carries
    # (`member["time"]`, `edge["predecessor_ref"]`, `member["claim_family_id"]`, ...).
    # `research_os_objects` is a polymorphic store with a SECOND writer (`consul_executor`)
    # and no payload-shape CHECK constraint, so a structurally malformed row CAN reach this
    # reader -- and a `KeyError` is neither of D3's two non-answers. It is not an explicit
    # abstention and it is not a quarantine: it takes down `read()` for the whole
    # `subject_key`, including the sound families under it, which is exactly the failure mode
    # the contract forbids. Found by the Kimi K3 council seat; the probe that proved it was a
    # claim with no `time` block, which raised `KeyError: 'time'` out of this function.
    for member in family.members.values():
        if not isinstance(member.get("time"), Mapping):
            reasons.add("malformed_member")
        elif any(
            member.get(field_name) is None
            for field_name in ("claim_id", "claim_family_id", "object_hash")
        ):
            reasons.add("malformed_member")
    for edge in family.edges:
        if not isinstance(edge.get("predecessor_ref"), Mapping) or not isinstance(
            edge.get("successor_ref"), Mapping
        ):
            reasons.add("malformed_edge")
    if reasons:
        return reasons

    outgoing: dict[str | None, set[str | None]] = {}

    recomputed: dict[str, str | None] = {
        claim_id: _recomputed_hash(member) for claim_id, member in family.members.items()
    }
    for claim_id, member in family.members.items():
        trusted = recomputed[claim_id]
        if trusted is not None and member.get("object_hash") != trusted:
            reasons.add("hash_mismatch")
        for field_name in ("recorded_at",):
            if instant_key(member["time"][field_name]) is None:
                reasons.add("unparseable_instant")
        for field_name in ("valid_from", "valid_to"):
            value = member["time"].get(field_name)
            if value is not None and instant_key(value) is None:
                reasons.add("unparseable_instant")

    for edge in family.edges:
        predecessor = _ref_id(edge["predecessor_ref"])
        successor = _ref_id(edge["successor_ref"])
        for ref, claim_id in (
            (edge["predecessor_ref"], predecessor),
            (edge["successor_ref"], successor),
        ):
            member = family.members.get(claim_id) if claim_id is not None else None
            if member is None:
                reasons.add("missing_node")
                continue
            trusted_hash = recomputed.get(claim_id) if claim_id is not None else None
            if trusted_hash is None:
                trusted_hash = member.get("object_hash")
            if trusted_hash != ref.get("object_hash"):
                reasons.add("hash_mismatch")
            if registered_family_name(member["claim_family_id"]) != edge.get("family_id"):
                reasons.add("family_identity_mismatch")
        before = family.members.get(predecessor) if predecessor is not None else None
        after = family.members.get(successor) if successor is not None else None
        if before is not None and after is not None:
            before_key = instant_key(before["time"]["recorded_at"])
            after_key = instant_key(after["time"]["recorded_at"])
            if before_key is not None and after_key is not None and after_key <= before_key:
                reasons.add("successor_recorded_at_not_later")
        successors = outgoing.setdefault(predecessor, set())
        successors.add(successor)
        if len(successors) > 1:
            reasons.add("fork")

    if _has_cycle(outgoing):
        reasons.add("cycle")

    # STRUCTURAL terminal-member check, unconditional on `known_at` (R1 blocker 2, R2-build-spec
    # §1.1 / §4 step 2: "Integrity runs BEFORE any temporal filter"). A family with two
    # edge-less members both recorded in the future is still structurally non-unique NOW.
    member_ids = set(family.members)
    outgoing_ids = {predecessor for predecessor, successors in outgoing.items() if successors}
    current_ids = member_ids - outgoing_ids
    if len(current_ids) != 1:
        reasons.add("non_unique_current_member")

    return reasons


def _has_cycle(adjacency: Mapping[str | None, set[str | None]]) -> bool:
    colour: dict[str | None, int] = {}
    for start in list(adjacency):
        stack: list[tuple[str | None, Iterator[str | None]]] = [
            (start, iter(adjacency.get(start, ())))
        ]
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


def _current_at(family: _Family, known_at_key: str) -> list[Mapping[str, Any]]:
    """The family members CURRENT as known at S (`known_at_key`, an `instant_key` string).

    A candidate is a version recorded at or before S; it is CURRENT when nothing had superseded
    it yet at S — no successor edge, or a successor recorded strictly after S.
    """

    successor_by_predecessor = {
        _ref_id(edge["predecessor_ref"]): _ref_id(edge["successor_ref"]) for edge in family.edges
    }
    current: list[Mapping[str, Any]] = []
    for claim_id, member in family.members.items():
        recorded_key = instant_key(member["time"]["recorded_at"])
        if recorded_key is None or recorded_key > known_at_key:
            continue
        successor_id = successor_by_predecessor.get(claim_id)
        if successor_id is not None:
            successor = family.members.get(successor_id)
            if successor is not None:
                successor_key = instant_key(successor["time"]["recorded_at"])
                if successor_key is not None and successor_key <= known_at_key:
                    continue
        current.append(member)
    return current


def _covers(member: Mapping[str, Any], valid_at_key: str) -> bool:
    """Half-open, always: `valid_from <= T < valid_to`, `null` end meaning open."""

    times = member["time"]
    start = times.get("valid_from")
    end = times.get("valid_to")
    if start is not None:
        start_key = instant_key(start)
        if start_key is None or start_key > valid_at_key:
            return False
    if end is not None:
        end_key = instant_key(end)
        if end_key is None or end_key <= valid_at_key:
            return False
    return True


def _is_consequential(member: Mapping[str, Any]) -> bool:
    """`CONTRACTS.md:266` — derived from the canonical statement, never from a caller flag.

    A claim is consequential when its `object_ref_or_value` is a NUMBER, or when its
    `subject_ref` names a `regulation`.
    """

    statement = member.get("statement") or {}
    value = statement.get("object_ref_or_value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    subject = statement.get("subject_ref")
    return isinstance(subject, Mapping) and subject.get("object_kind") == "regulation"


def _group(
    claims: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any]],
    subject_key: str,
) -> dict[str, _Family]:
    """Group claims into families and attach each edge to the family it names.

    An edge binds a family through its `RegisteredName`, `registered_family_name(family_id)`,
    compared EXACTLY (R1 blocker 1 / codex round-1 finding 5). An edge whose `family_id` names
    no family here but whose refs name a member of one is still attached to that member's
    family, where `_integrity_reasons` quarantines it as `family_identity_mismatch` — it is
    never silently dropped, which is exactly the defect the blocker names.
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
    by_registered_name = {
        registered_family_name(family_id): family for family_id, family in families.items()
    }
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


def read(
    subject_key: str,
    valid_at: str,
    known_at: str,
    objects: Mapping[str, Sequence[Mapping[str, Any]]],
) -> ReadResult:
    """`read(subject_key, valid_at=T, known_at=S, objects)` — D3, in the order D3 specifies.

    `objects` is a `research_os_objects`-shaped payload: a mapping carrying `"claims"` and
    `"object_successor_edges"` sequences — the same envelope key names the P06 bundle fixtures
    use (`corpus_from_fixture` in R1's reference reads the identical two keys off `"objects"`),
    chosen so a caller who already has a bundle document or a `research_os_objects` query result
    grouped by kind can pass it straight through without reshaping it first.

    `valid_at`/`known_at` are canonical UTC instant strings (the wire form) — never `datetime`,
    per D2: the wire form stays byte-identical, and every temporal comparison in this module
    goes through `instant_key`. A `valid_at`/`known_at` that does not parse is a CALLER error
    (the query itself is malformed, not the data), so this raises `ValueError` rather than
    quarantining a graph that may be perfectly sound.
    """

    valid_at_key = instant_key(valid_at)
    if valid_at_key is None:
        raise ValueError(f"valid_at is not a canonical UTC instant: {valid_at!r}")
    known_at_key = instant_key(known_at)
    if known_at_key is None:
        raise ValueError(f"known_at is not a canonical UTC instant: {known_at!r}")

    claims = objects.get("claims") or ()
    edges = objects.get("object_successor_edges") or ()

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
        current = _current_at(family, known_at_key)
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
        if _covers(member, valid_at_key):
            admissible.append((family.family_id, member))

    if len(admissible) > 1:
        for family_id, _ in admissible:
            quarantined.setdefault(family_id, set()).add("ambiguous_subject_key")

    if quarantined:
        return Quarantine(
            family_ids=tuple(sorted(quarantined)),
            reasons=tuple(
                sorted({reason for reasons in quarantined.values() for reason in reasons})
            ),
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
