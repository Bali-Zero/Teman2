"""D5's persistence adapter -- the ONLY module in this slice that talks to PostgreSQL.

`research_os_objects` is the one generic append-only store (migration 279); this module is
one of its writers, alongside `services/autonomous_lab/consul_executor.py` (`seal`/`_persist`),
whose column set, JSON encoding and idempotency check (`INSERT ... ON CONFLICT (object_id) DO
NOTHING` followed by a read-back hash comparison) this module mirrors deliberately rather than
inventing a second convention. The one other table this module writes is
`research_os_naga_admission` (migration 312), the ONE projection D5 authorises for NAGA
(R2-build-spec.md sections 0 D5 / 3 / 7). Nothing else. `test_naga_persistence_unit.py` scans
this file's own source for every INSERT/UPDATE/DELETE/TRUNCATE/COPY target and asserts that.

HASH VERIFICATION IS PYTHON-ONLY, NEVER SQL (migration 279:54-65, R2-build-spec.md section 3
rule 1). `validate_object` recomputes `object_hash` via `research_os.hashing.object_hash` --
RFC 8785 JCS canonicalization, omission set `{object_hash} | TRANSPORT_METADATA_FIELDS` -- and
compares it to the payload's own declared value. `sha256(payload::text)` in SQL is FORBIDDEN and
this module contains no such statement.

D2'S ASYMMETRY IS DELIBERATE AND STATED HERE, NOT "FIXED" BY A FUTURE READER (R2-build-spec.md
section 0 D2, section 3 rule 5): the READER (`naga_bitemporal_reader.instant_key`) FOLDS every
admitted spelling -- `t`/`T`, `Z`/`z`/`+00:00`, any fraction width -- into one 27-byte sort key,
because it must make sense of data this repository did not always write strictly. The WRITER
(this module, `validate_object`) REFUSES more strictly: a lowercase `t` date/time separator is
always rejected (R2-build-spec.md section 3 rule 5, literal text); a fraction longer than six
digits is always rejected (same rule); lowercase `z` is rejected too, but that one is a MEASURED
decision, not a copied one -- see "the lowercase-z measurement" below. The writer never rewrites
an instant to a stricter spelling before storing it (that would change `object_hash`); it either
accepts the byte-identical wire spelling as-is, or refuses the write outright.

THE LOWERCASE-Z MEASUREMENT. `research_os.primitives._UTC_OFFSET_PATTERN` -- the core's OWN
declared wire grammar for `UtcDateTime`, `r"(?:Z|\\+00:00)$"` -- admits `Z` and `+00:00`, never
lowercase `z`. Independently, `pydantic.BaseModel.model_dump(mode="json")` for a UTC-aware
`datetime` field was measured directly against this exact type (a one-field model reusing the
same `datetime` shape) in this session: it always emits uppercase `Z`
(`2026-01-01T03:00:00Z` / `2026-01-01T03:00:00.123456Z`), never lowercase, never `+00:00`. R1's
own canonical fixtures under
`research/operations/execution/research-os-v1.0.0/evidence/p06/ros-v1-p06-naga-prep-b01/fixtures/`
were grepped for every `...T...Z"`/`...z"` instant string in this session: every one is uppercase
`Z`; zero lowercase `z` occurrences exist anywhere in that fixture tree. So lowercase `z` is
rejected on write: the core's own pattern does not admit it, its own serializer never emits it,
and no fixture this build must agree with ever spells it that way -- the three-way measurement
the task named all point the same way, unlike `t`/`T` (which the reader's grammar admits
because *legacy* text -- `naga_bitemporal_reader`'s own module docstring cites
`consul_executor.py` "emits optional fractions" -- can be lowercase, but the canonical writer
never emits or should accept it).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import asyncpg

from backend.services.research_os import _core_path as _core_path

# isort: split

from research_os.enums import RiskClass, Sensitivity
from research_os.hashing import object_hash as _recompute_object_hash

from backend.services.research_os.naga_bitemporal_reader import (
    SUBJECT_KEY_NAMESPACE,
    instant_key,
    registered_family_name,
)

__all__ = [
    "AdmissionRow",
    "NagaWriteRejected",
    "ObjectWrite",
    "WriteResult",
    "load_subject_objects",
    "record_admissions",
    "validate_object",
    "write_objects",
    "write_successor",
]


class NagaWriteRejected(Exception):
    """One rule (R2-build-spec.md section 3, rules 1-10) refused a write BEFORE any INSERT."""

    def __init__(self, reason: str, *, detail: str | None = None) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(reason if detail is None else f"{reason}: {detail}")


@dataclass(frozen=True)
class ObjectWrite:
    """One canonical object, plus the sidecar identity `research_os_objects` needs to store it.

    `object_kind`/`object_id` are NOT copied JSON keys (migration 279's header): no canonical
    object carries a top-level `object_kind` field on itself, so the caller -- which always knows
    which Pydantic model it is persisting -- supplies them, matching
    `consul_executor._persist(conn, kind, identifier, model)`'s convention. `payload` is the
    complete canonical wire object (`model.model_dump(mode="json", exclude_unset=True)` or an
    already-JSON-shaped `Mapping` read back from a fixture), INCLUDING its own `object_hash`.
    """

    object_kind: str
    object_id: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class WriteResult:
    """What `write_objects`/`write_successor` actually did -- rule 8's two outcomes, never a count alone."""

    inserted_ids: tuple[str, ...]
    already_present_ids: tuple[str, ...]


@dataclass(frozen=True)
class AdmissionRow:
    """One row of the D5 projection `research_os_naga_admission` (migration 312's exact shape).

    `family_id`/`claim_object_id`/`claim_object_hash`/`reason` are `None` on an excluded record;
    the table's own CHECK constraints (`..._admitted_has_identity_no_reason`,
    `..._excluded_has_reason`) enforce the D4 shape, this dataclass does not re-enforce it.
    """

    run_id: str
    legacy_claim_id: str
    family_id: str | None
    claim_object_id: str | None
    claim_object_hash: str | None
    evidence_object_ids: tuple[str, ...]
    evidence_object_hashes: tuple[str, ...]
    source_snapshot_hash: str
    decision: str
    reason: str | None


#: Rule 5: uppercase `T` separator only, uppercase `Z` or literal `+00:00` terminator only
#: (never lowercase `z` -- see "the lowercase-z measurement" in the module docstring), fraction
#: 1-6 digits only when present (a 7th digit cannot match `(Z|\+00:00)` immediately after, so a
#: longer fraction fails the whole pattern rather than being silently truncated).
_WRITE_INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|\+00:00)$")

#: `claim.py`'s own docstring: "the `_on`/`_at` suffix family in this spec is always a
#: timestamp" -- confirmed against every `..._at` name in `primitives.py`'s
#: `V1_RESERVED_EXTENSION_FIELD_NAMES`. `valid_from`/`valid_to` are the two timestamp fields that
#: do not end in `_at`.
_INSTANT_LIKE_KEYS = {"valid_from", "valid_to"}


def _iter_instant_fields(node: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield `(dotted_path, value)` for every string value under an instant-shaped key, recursively."""

    if isinstance(node, Mapping):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            if isinstance(value, str) and (key in _INSTANT_LIKE_KEYS or str(key).endswith("_at")):
                yield child_path, value
            else:
                yield from _iter_instant_fields(value, child_path)
    elif isinstance(node, (list, tuple)):
        for index, item in enumerate(node):
            yield from _iter_instant_fields(item, f"{path}[{index}]")


def validate_object(write: ObjectWrite) -> None:
    """Pure, no I/O. Raises `NagaWriteRejected` before any caller could possibly INSERT.

    Rule 1: recompute `object_hash` via core hashing and refuse a mismatch. Rule 5: refuse a
    write-path instant that is not `_WRITE_INSTANT_RE`-strict.
    """

    payload = dict(write.payload)
    if not write.object_id:
        raise NagaWriteRejected("object_id_missing")
    declared_hash = payload.get("object_hash")
    if not isinstance(declared_hash, str):
        raise NagaWriteRejected("object_hash_missing")
    try:
        expected_hash = _recompute_object_hash(payload)
    except (ValueError, TypeError, KeyError) as exc:
        raise NagaWriteRejected("object_hash_unrecomputable", detail=str(exc)) from exc
    if declared_hash != expected_hash:
        raise NagaWriteRejected("object_hash_mismatch")
    for field_path, value in _iter_instant_fields(payload):
        if _WRITE_INSTANT_RE.match(value) is None:
            raise NagaWriteRejected("malformed_instant", detail=field_path)


def _coerce_payload(value: Any) -> dict[str, Any]:
    """`payload` comes back either already-decoded (a JSON codec on `conn`) or as raw text --
    same defensive read `consul_executor.execute_synthetic` uses for the identical column."""

    return dict(value) if isinstance(value, Mapping) else json.loads(value)


async def _insert_object(conn: asyncpg.Connection, write: ObjectWrite) -> str:
    """Idempotent single-row insert, mirroring `consul_executor._persist`'s exact convention.

    Returns `"inserted"` or `"already_present"` (rule 8, same hash); raises
    `NagaWriteRejected("object_id_hash_collision")` when the stored hash differs (rule 8, other
    hash) -- never a silent overwrite, the table is append-only by trigger regardless.
    """

    payload = dict(write.payload)
    declared_hash = payload["object_hash"]
    status = await conn.execute(
        """INSERT INTO research_os_objects
           (object_kind, object_id, object_hash, contract_version, tenant, payload)
           VALUES ($1, $2, $3, $4, $5, $6::text::jsonb)
           ON CONFLICT (object_id) DO NOTHING""",
        write.object_kind,
        write.object_id,
        declared_hash,
        payload["contract_version"],
        payload.get("tenant", "bali-zero"),
        json.dumps(payload),
    )
    rows_inserted = int(status.rsplit(" ", 1)[-1])
    stored_hash = await conn.fetchval(
        "SELECT object_hash FROM research_os_objects WHERE object_id = $1", write.object_id
    )
    if stored_hash is None:
        raise NagaWriteRejected("object_insert_failed", detail=write.object_id)
    if stored_hash != declared_hash:
        raise NagaWriteRejected("object_id_hash_collision", detail=write.object_id)
    return "inserted" if rows_inserted == 1 else "already_present"


async def write_objects(conn: asyncpg.Connection, writes: Sequence[ObjectWrite]) -> WriteResult:
    """Write zero or more standalone canonical objects (no succession) in one transaction.

    Every `validate_object` call runs BEFORE the transaction opens, so a rejection touches no
    connection at all (rule 1's / rule 5's "zero-write" tests hold trivially). A hash collision
    discovered mid-batch (rule 8, different hash) raises inside the transaction, rolling back
    every insert this call attempted -- replaying the same batch twice (rule 9) inserts 0 new
    rows the second time, every id reported `already_present`.
    """

    for write in writes:
        validate_object(write)
    inserted: list[str] = []
    already_present: list[str] = []
    async with conn.transaction():
        for write in writes:
            outcome = await _insert_object(conn, write)
            (inserted if outcome == "inserted" else already_present).append(write.object_id)
    return WriteResult(inserted_ids=tuple(inserted), already_present_ids=tuple(already_present))


#: The two object kinds this slice's succession rules are defined over -- `claim` (NAGA's own
#: ledger) and `evidence` (CONTRACTS.md 3.1 applies the same edge shape to it). Anything else is
#: refused by name rather than guessed at (see the module's STOP-and-escalate posture).
_FAMILY_EXTRACTORS = {
    "claim": lambda payload: (
        registered_family_name(payload["claim_family_id"]) if payload.get("claim_family_id") else None
    ),
    "evidence": lambda payload: payload.get("evidence_family_id"),
}
_RECORDED_AT_EXTRACTORS = {
    "claim": lambda payload: (payload.get("time") or {}).get("recorded_at"),
    "evidence": lambda payload: (payload.get("times") or {}).get("recorded_at"),
}

_RISK_ORDER = {value: index for index, value in enumerate(RiskClass)}
_SENSITIVITY_ORDER = {value: index for index, value in enumerate(Sensitivity)}


def _is_classification_lowered(predecessor: Mapping[str, Any], successor: Mapping[str, Any]) -> bool:
    """Rule 4: `risk_class` OR `sensitivity` lower than the predecessor's, declaration order only."""

    pred_risk = _RISK_ORDER.get(predecessor.get("risk_class"))
    succ_risk = _RISK_ORDER.get(successor.get("risk_class"))
    pred_sensitivity = _SENSITIVITY_ORDER.get(predecessor.get("sensitivity"))
    succ_sensitivity = _SENSITIVITY_ORDER.get(successor.get("sensitivity"))
    if None in (pred_risk, succ_risk, pred_sensitivity, succ_sensitivity):
        raise NagaWriteRejected("classification_missing")
    return succ_risk < pred_risk or succ_sensitivity < pred_sensitivity


def _ref(mapping: Mapping[str, Any] | None, key: str) -> Any:
    return (mapping or {}).get(key)


async def write_successor(
    conn: asyncpg.Connection,
    *,
    predecessor_id: str,
    successor: ObjectWrite,
    edge: ObjectWrite,
) -> WriteResult:
    """Successor object + `ObjectSuccessorEdge` in ONE transaction (rule 2), each prior rule a
    zero-row refusal.

    Order: pure validation (rules 1, 5) before any connection use; then, inside the transaction,
    `pg_advisory_xact_lock` keyed on `predecessor_id` (rule 3, serializes concurrent successors
    of the SAME predecessor); predecessor existence; fork detection (rule 3: a second, DIFFERENT
    edge already claims this predecessor -- a REPLAY of the identical edge is not a fork and
    falls through to the idempotent insert, rule 9); `object_kind` agreement; family identity
    (rule 6, `naga_bitemporal_reader.registered_family_name` for `claim`, the bare
    `evidence_family_id` for `evidence` -- reused, not re-derived); classification-lowering
    (rule 4); `recorded_at` ordering compared via `instant_key`, never raw text (rule 7, and the
    exact bug class D2 exists to prevent). Only then the two inserts.
    """

    validate_object(successor)
    validate_object(edge)

    edge_predecessor_ref = _ref(dict(edge.payload), "predecessor_ref")
    edge_successor_ref = _ref(dict(edge.payload), "successor_ref")
    if _ref(edge_predecessor_ref, "object_id") != predecessor_id:
        raise NagaWriteRejected("edge_predecessor_ref_mismatch")
    if _ref(edge_successor_ref, "object_id") != successor.object_id:
        raise NagaWriteRejected("edge_successor_ref_mismatch")

    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", predecessor_id)

        predecessor_row = await conn.fetchrow(
            "SELECT object_kind, object_hash, payload FROM research_os_objects WHERE object_id = $1",
            predecessor_id,
        )
        if predecessor_row is None:
            raise NagaWriteRejected("predecessor_missing", detail=predecessor_id)
        predecessor_kind = predecessor_row["object_kind"]
        predecessor_payload = _coerce_payload(predecessor_row["payload"])
        if predecessor_row["object_hash"] != _ref(edge_predecessor_ref, "object_hash"):
            raise NagaWriteRejected("edge_predecessor_hash_stale")
        if predecessor_kind != successor.object_kind:
            raise NagaWriteRejected("object_kind_mismatch")

        existing_edge = await conn.fetchrow(
            """SELECT object_id FROM research_os_objects
               WHERE object_kind = 'object_successor_edge'
                 AND payload->'predecessor_ref'->>'object_id' = $1""",
            predecessor_id,
        )
        if existing_edge is not None and existing_edge["object_id"] != edge.object_id:
            raise NagaWriteRejected(
                "predecessor_already_superseded", detail=existing_edge["object_id"]
            )

        family_extractor = _FAMILY_EXTRACTORS.get(predecessor_kind)
        if family_extractor is None:
            raise NagaWriteRejected(
                "unsupported_object_kind_for_succession", detail=predecessor_kind
            )
        predecessor_family = family_extractor(predecessor_payload)
        successor_family = family_extractor(dict(successor.payload))
        edge_family = dict(edge.payload).get("family_id")
        if predecessor_family is None or predecessor_family != edge_family:
            raise NagaWriteRejected("family_identity_mismatch")
        if successor_family is None or successor_family != edge_family:
            raise NagaWriteRejected("family_identity_mismatch")

        if _is_classification_lowered(
            predecessor_payload.get("classification") or {},
            dict(successor.payload).get("classification") or {},
        ):
            raise NagaWriteRejected("classification_lowered")

        recorded_at_extractor = _RECORDED_AT_EXTRACTORS[predecessor_kind]
        predecessor_recorded_at = instant_key(recorded_at_extractor(predecessor_payload) or "")
        successor_recorded_at = instant_key(recorded_at_extractor(dict(successor.payload)) or "")
        if predecessor_recorded_at is None or successor_recorded_at is None:
            raise NagaWriteRejected("malformed_instant", detail="recorded_at")
        if successor_recorded_at <= predecessor_recorded_at:
            raise NagaWriteRejected("successor_recorded_at_not_later")

        successor_outcome = await _insert_object(conn, successor)
        edge_outcome = await _insert_object(conn, edge)

    outcomes = ((successor.object_id, successor_outcome), (edge.object_id, edge_outcome))
    inserted = tuple(object_id for object_id, outcome in outcomes if outcome == "inserted")
    already_present = tuple(
        object_id for object_id, outcome in outcomes if outcome == "already_present"
    )
    return WriteResult(inserted_ids=inserted, already_present_ids=already_present)


async def record_admissions(conn: asyncpg.Connection, rows: Sequence[AdmissionRow]) -> int:
    """`INSERT ... ON CONFLICT (run_id, legacy_claim_id) DO NOTHING`; returns rows actually inserted.

    D4: admission is a decision, zero admissions is valid, so an empty `rows` returns `0` without
    touching the connection. The function accepts the full contract shape (`Admitted` AND
    `Excluded` rows) even though the backfill lane is expected to call it with admitted rows
    only -- see the migration's own CHECK constraints for the shape each decision carries.
    """

    if not rows:
        return 0
    inserted = 0
    async with conn.transaction():
        for row in rows:
            status = await conn.execute(
                """INSERT INTO research_os_naga_admission
                   (run_id, legacy_claim_id, family_id, claim_object_id, claim_object_hash,
                    evidence_object_ids, evidence_object_hashes, source_snapshot_hash,
                    decision, reason)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                   ON CONFLICT (run_id, legacy_claim_id) DO NOTHING""",
                row.run_id,
                row.legacy_claim_id,
                row.family_id,
                row.claim_object_id,
                row.claim_object_hash,
                list(row.evidence_object_ids),
                list(row.evidence_object_hashes),
                row.source_snapshot_hash,
                row.decision,
                row.reason,
            )
            inserted += int(status.rsplit(" ", 1)[-1])
    return inserted


async def load_subject_objects(
    conn: asyncpg.Connection, subject_key: str
) -> dict[str, list[dict[str, Any]]]:
    """The `objects` bundle `naga_bitemporal_reader.read()` takes: `{"claims": [...],
    "object_successor_edges": [...]}`.

    Claims are filtered by `subject_key` in SQL, matching `subject_key_of`'s own extraction path
    (`extensions[SUBJECT_KEY_NAMESPACE].payload.subject_key`) exactly. Edges are NOT filtered by
    subject here -- `read()`'s own `_group` step matches an edge to a family by registered name
    OR by either ref naming a member of that family (R1 blocker 1's fix), so pre-filtering edges
    by subject_key here would risk silently dropping exactly the edge that fix exists to keep.
    """

    claim_rows = await conn.fetch(
        f"""SELECT payload FROM research_os_objects
            WHERE object_kind = 'claim'
              AND payload->'extensions'->'{SUBJECT_KEY_NAMESPACE}'->'payload'->>'subject_key' = $1""",
        subject_key,
    )
    edge_rows = await conn.fetch(
        "SELECT payload FROM research_os_objects WHERE object_kind = 'object_successor_edge'"
    )
    return {
        "claims": [_coerce_payload(row["payload"]) for row in claim_rows],
        "object_successor_edges": [_coerce_payload(row["payload"]) for row in edge_rows],
    }
