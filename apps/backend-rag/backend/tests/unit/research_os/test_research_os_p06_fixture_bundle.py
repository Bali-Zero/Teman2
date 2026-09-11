"""The Bites observation for R1-build-spec.md §5b/§5c -- the P06 bundle's fixtures, made canonical.

WHY THIS EXISTS. `test_research_os_temporal_rows.py`'s own module docstring names this module as
the one that does "hashing and schema validation ... against the real fixtures, with the real
schemas" -- this is that module. Before this PR, `bitemporal/03` and `supersession/01` carried
placeholder references ("4444...", "7777...", "8888...", "9999...") presented as provenance, and
`supersession/01` bound the SAME predecessor claim to TWO DIFFERENT placeholder hashes across
`supersedes_claim_ref` and `object_successor_edge.predecessor_ref`. This module is the check that
that class of defect cannot survive silently: it discovers every canonical object in every P06
fixture from DISK (never a hardcoded file list for the per-object checks), validates each against
its exported JSON Schema and its pydantic model, and recomputes every `object_hash` reference --
both a canonical object's own hash and every in-file reference to one -- rather than trusting the
value the fixture happens to carry.

WHAT "CANONICAL" MEANS HERE. A JSON object (dict) carrying both `contract_version` and
`object_hash` is a full canonical Research OS object
(`Claim`/`Evidence`/`ObjectSuccessorEdge`/`IntelEvent`); most fixtures in this bundle
(`abstention/*`, `contradiction/*`, `evidence_independence/*`,
`sanitization/*`, `scope_jurisdiction/*`, `source_span/*`, `invalidation/*`, and the
not-yet-rewritten `bitemporal/01`/`02`) are deliberately ILLUSTRATIVE and carry none -- this
module's schema/pydantic/hash checks are parametrised over whatever canonical objects are
actually found, so those fixtures correctly contribute zero cases to them, and `invalidation/01`
is asserted elsewhere in this module to carry none on purpose (R1-build-spec.md §5b: it "stays
DEFERRED").

NO SKIP, NO XFAIL, NO IMPORTORSKIP anywhere in this module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from research_os.hashing import object_hash
from research_os.primitives import _REVERSE_DNS_RE, V1_RESERVED_EXTENSION_FIELD_NAMES
from research_os.schemas import SCHEMA_DIRECTORY, SCHEMA_MODELS

from .research_os_reader_reference import SUBJECT_KEY_NAMESPACE, corpus_from_fixture

_REPO_ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "packages" / "research-os-core").is_dir()
)
_BUNDLE_FIXTURES = (
    _REPO_ROOT
    / "research/operations/execution/research-os-v1.0.0/evidence/p06"
    / "ros-v1-p06-naga-prep-b01"
    / "fixtures"
)
_BITEMPORAL_03_PATH = _BUNDLE_FIXTURES / "bitemporal" / "03_time_travel_query_example.json"
_SUPERSESSION_01_PATH = _BUNDLE_FIXTURES / "supersession" / "01_amendment_supersedes_original.json"
_INVALIDATION_01_PATH = _BUNDLE_FIXTURES / "invalidation" / "01_evidence_withdrawn_event.json"

#: Every fixture JSON on disk under this bundle, discovered fresh -- never hardcoded, so a new
#: fixture file is covered automatically, exactly as the mandate requires.
_FIXTURE_FILES: tuple[Path, ...] = tuple(sorted(_BUNDLE_FIXTURES.rglob("*.json")))

#: The 64-char-hex-of-a-single-repeated-digit shape the old placeholders used
#: ("4444...", "7777...", "8888...", "9999...") -- a real sha256 digest is not this shape
#: except with probability 16 * 2^-256, so a match here is always a placeholder, never a
#: false positive against genuine hash data.
_REPEATED_DIGIT_HEX_RE = re.compile(r"([0-9a-fA-F])\1{63}")

#: The fixtures R1 made canonical in THIS slice (R1-build-spec.md §5b/§5c) -- the same set
#: `fixtures/_recompute_hashes.py._TARGET_FILES` recomputes. The placeholder-hash scan below is
#: scoped to these, not to every file `_FIXTURE_FILES` discovers: `abstention/*`,
#: `bitemporal/01`/`02`, `contradiction/*` and `source_span/01` are pre-existing ILLUSTRATIVE
#: fixtures (no `contract_version`+`object_hash` canonical object at all -- confirmed by
#: `test_canonical_object_discovery_finds_more_than_the_two_rewritten_fixtures` and the fact
#: they contribute nothing to `_CANONICAL_OBJECTS`/`_REFERENCES` above) that R1-build-spec.md's
#: "Your work" section never asks this PR to canonicalise, and their own placeholder-looking
#: repeated-letter strings (`aaaa...`, `1111...`, `2222...`, `5555...`, `6666...`, `bbbb...`) are
#: a DIFFERENT lane's fixtures, out of this PR's fence. Scanning them here would fail a test on
#: a file this PR is not allowed to fix without exceeding its mandate.
_CANONICAL_IN_THIS_SLICE: tuple[Path, ...] = (
    _BITEMPORAL_03_PATH,
    _SUPERSESSION_01_PATH,
    *sorted((_BUNDLE_FIXTURES / "seed_public_regulatory").glob("*.json")),
)

#: R1-build-spec.md §1 rule 2: each `subject_key` component (`jurisdiction`/`instrument`/
#: `provision`) matches this pattern. Distinct from `primitives.RegisteredName`/`Identifier` --
#: this rule is R1's own, stated in the build spec, not inherited from the frozen contract.
_SUBJECT_KEY_PART_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _kind_of(node: dict[str, Any]) -> str | None:
    if "claim_id" in node:
        return "claim"
    if "evidence_id" in node:
        return "evidence"
    if "object_successor_edge_id" in node:
        return "object_successor_edge"
    if "event_id" in node:
        return "intel_event"
    return None


def _walk_dicts(node: Any):
    """Yield every dict in a JSON tree, pre-order, including nested ones."""

    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_dicts(item)


def _canonical_objects(doc: Any) -> list[tuple[str, dict[str, Any]]]:
    """Every full canonical object (`contract_version` + `object_hash` both present) in `doc`."""

    found: list[tuple[str, dict[str, Any]]] = []
    for node in _walk_dicts(doc):
        if "contract_version" in node and "object_hash" in node:
            kind = _kind_of(node)
            assert kind is not None, (
                f"canonical-shaped object (contract_version + object_hash) with no "
                f"recognisable id field: {sorted(node)}"
            )
            found.append((kind, node))
    return found


def _in_file_references(doc: Any) -> list[dict[str, Any]]:
    """Every reference dict (`object_hash` alongside an id, but no `contract_version`) whose
    target object is present elsewhere in the SAME document -- resolved by `claim_id`,
    `evidence_id`, `event_id`, or an `{object_kind, object_id}` pair naming `claim`/`evidence`.

    A reference to something NOT present in the file (e.g. `Claim.statement.subject_ref` naming
    an external "regulation" document, or an `Evidence.source_event_ref` naming an `IntelEvent`
    a particular fixture does not instantiate) is not returned here -- there is nothing to
    recompute it against, and asserting equality against nothing would be vacuous.
    `seed_public_regulatory/01_z2_seed_cohort.json` DOES instantiate a real `IntelEvent` per
    record, so its `source_event_ref` occurrences resolve here via `event_id`.
    """

    id_map: dict[str, dict[str, str]] = {"claim": {}, "evidence": {}, "intel_event": {}}
    for kind, node in _canonical_objects(doc):
        if kind == "claim":
            id_map["claim"][node["claim_id"]] = node["object_hash"]
        elif kind == "evidence":
            id_map["evidence"][node["evidence_id"]] = node["object_hash"]
        elif kind == "intel_event":
            id_map["intel_event"][node["event_id"]] = node["object_hash"]

    references: list[dict[str, Any]] = []
    for node in _walk_dicts(doc):
        if "object_hash" not in node or "contract_version" in node:
            continue
        target: str | None = None
        if "claim_id" in node and node["claim_id"] in id_map["claim"]:
            target = id_map["claim"][node["claim_id"]]
        elif "evidence_id" in node and node["evidence_id"] in id_map["evidence"]:
            target = id_map["evidence"][node["evidence_id"]]
        elif "event_id" in node and node["event_id"] in id_map["intel_event"]:
            target = id_map["intel_event"][node["event_id"]]
        else:
            kind = node.get("object_kind")
            object_id = node.get("object_id")
            if kind in id_map and object_id in id_map[kind]:
                target = id_map[kind][object_id]
        if target is not None:
            references.append({"node": node, "expected_hash": target})
    return references


def _fixture_id(path: Path) -> str:
    return str(path.relative_to(_BUNDLE_FIXTURES))


def _discover_canonical_objects() -> list[tuple[Path, str, dict[str, Any]]]:
    items: list[tuple[Path, str, dict[str, Any]]] = []
    for path in _FIXTURE_FILES:
        for kind, node in _canonical_objects(_load(path)):
            items.append((path, kind, node))
    return items


def _discover_references() -> list[tuple[Path, dict[str, Any]]]:
    items: list[tuple[Path, dict[str, Any]]] = []
    for path in _FIXTURE_FILES:
        for reference in _in_file_references(_load(path)):
            items.append((path, reference))
    return items


_CANONICAL_OBJECTS = _discover_canonical_objects()
_CANONICAL_OBJECT_IDS = [
    f"{_fixture_id(path)}::{kind}::"
    f"{node.get('claim_id') or node.get('evidence_id') or node.get('object_successor_edge_id') or node.get('event_id')}"
    for path, kind, node in _CANONICAL_OBJECTS
]

_REFERENCES = _discover_references()
_REFERENCE_IDS = [
    f"{_fixture_id(path)}::"
    f"{reference['node'].get('claim_id') or reference['node'].get('evidence_id') or reference['node'].get('object_id') or reference['node'].get('event_id')}"
    for path, reference in _REFERENCES
]

_CLAIMS_WITH_SUBJECT_KEY = [
    (path, node)
    for path, kind, node in _CANONICAL_OBJECTS
    if kind == "claim" and SUBJECT_KEY_NAMESPACE in (node.get("extensions") or {})
]
_CLAIMS_WITH_SUBJECT_KEY_IDS = [f"{_fixture_id(path)}::{node['claim_id']}" for path, node in _CLAIMS_WITH_SUBJECT_KEY]


# ---------------------------------------------------------------------------------------------
# Discovery innocence controls -- a broken glob/walker would make every test below vacuously
# pass by iterating over nothing. Pin the instrument before trusting what it reports.
# ---------------------------------------------------------------------------------------------


def test_fixture_discovery_finds_every_known_p06_fixture_file() -> None:
    names = {_fixture_id(path) for path in _FIXTURE_FILES}
    assert len(_FIXTURE_FILES) >= 15, f"expected at least 15 fixture files, found {sorted(names)}"
    for expected in (
        "bitemporal/03_time_travel_query_example.json",
        "supersession/01_amendment_supersedes_original.json",
        "invalidation/01_evidence_withdrawn_event.json",
        "seed_public_regulatory/01_z2_seed_cohort.json",
    ):
        assert expected in names, f"{expected} missing from fixture discovery: {sorted(names)}"


def test_canonical_object_discovery_finds_more_than_the_two_rewritten_fixtures() -> None:
    # bitemporal/03 (2 claims) + supersession/01 (2 claims + 1 edge) + seed cohort (>=3 claims,
    # >=3 evidences) is at least 2 + 3 + 3 + 3 = 11.
    assert len(_CANONICAL_OBJECTS) >= 11, _CANONICAL_OBJECT_IDS


def test_reference_discovery_finds_in_file_resolvable_references() -> None:
    # supersession/01 alone contributes >= 3 (supersedes_claim_ref, predecessor_ref, successor_ref).
    assert len(_REFERENCES) >= 3, _REFERENCE_IDS


def test_at_least_one_claim_carries_the_subject_key_extension() -> None:
    assert len(_CLAIMS_WITH_SUBJECT_KEY) >= 2, _CLAIMS_WITH_SUBJECT_KEY_IDS


# ---------------------------------------------------------------------------------------------
# 1. Every fixture file: valid JSON, marked synthetic.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_path", _FIXTURE_FILES, ids=[_fixture_id(p) for p in _FIXTURE_FILES])
def test_every_fixture_is_valid_json_and_marked_synthetic(fixture_path: Path) -> None:
    doc = _load(fixture_path)
    assert isinstance(doc, dict), f"{fixture_path}: top-level JSON must be an object"
    assert doc.get("synthetic") is True, f'{fixture_path}: must carry top-level "synthetic": true'


# ---------------------------------------------------------------------------------------------
# 2. Every canonical object: schema-valid AND round-trips through its pydantic model.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path,kind,node", _CANONICAL_OBJECTS, ids=_CANONICAL_OBJECT_IDS)
def test_every_canonical_object_validates_against_schema_and_model(
    path: Path, kind: str, node: dict[str, Any]
) -> None:
    schema = json.loads((SCHEMA_DIRECTORY / f"{kind}.schema.json").read_text(encoding="utf-8"))
    violations = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(node),
        key=lambda error: list(error.absolute_path),
    )
    assert not violations, f"{path} ({kind} {_kind_of(node)}): " + "; ".join(
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in violations
    )

    parsed = SCHEMA_MODELS[kind].model_validate(node)
    assert (parsed.contract_version, parsed.object_hash) == (
        node["contract_version"],
        node["object_hash"],
    ), f"{path} ({kind} {_kind_of(node)}): the pydantic round-trip did not preserve the object's identity"


# ---------------------------------------------------------------------------------------------
# 3. Every object_hash -- a canonical object's own, and every in-file reference to one -- is the
#    RECOMPUTED value, never a value that merely happens to be present. Separately: no
#    repeated-single-digit-hex placeholder survives anywhere in the raw text.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path,kind,node", _CANONICAL_OBJECTS, ids=_CANONICAL_OBJECT_IDS)
def test_every_canonical_objects_own_hash_is_the_recomputed_hash(
    path: Path, kind: str, node: dict[str, Any]
) -> None:
    assert node["object_hash"] == object_hash(node), (
        f"{path} ({kind} {_kind_of(node)}): stored object_hash does not match "
        "research_os.hashing.object_hash(node)"
    )


@pytest.mark.parametrize("path,reference", _REFERENCES, ids=_REFERENCE_IDS)
def test_every_in_file_reference_matches_its_targets_recomputed_hash(
    path: Path, reference: dict[str, Any]
) -> None:
    node = reference["node"]
    assert node["object_hash"] == reference["expected_hash"], (
        f"{path}: reference {sorted(node)} carries a stale object_hash that no longer matches "
        "the object it names"
    )


@pytest.mark.parametrize(
    "fixture_path", _CANONICAL_IN_THIS_SLICE, ids=[_fixture_id(p) for p in _CANONICAL_IN_THIS_SLICE]
)
def test_no_repeated_digit_placeholder_hash_survives(fixture_path: Path) -> None:
    text = fixture_path.read_text(encoding="utf-8")
    match = _REPEATED_DIGIT_HEX_RE.search(text)
    assert match is None, (
        f"{fixture_path} still contains a placeholder repeated-digit 64-char hex value "
        f"({match.group(0) if match else '?'}) -- run fixtures/_recompute_hashes.py"
    )


# ---------------------------------------------------------------------------------------------
# 4. supersession/01 binds ONE predecessor hash in both places, and they are equal.
# ---------------------------------------------------------------------------------------------


def test_supersession_01_binds_one_predecessor_hash_in_both_places() -> None:
    doc = _load(_SUPERSESSION_01_PATH)
    claims = {claim["claim_id"]: claim for claim in doc["objects"]["claims"]}
    edges = doc["objects"]["object_successor_edges"]
    assert len(edges) == 1, "supersession/01 must carry exactly one object_successor_edge"
    edge = edges[0]

    successors = [claim for claim in claims.values() if claim.get("supersedes_claim_ref")]
    assert len(successors) == 1, "supersession/01 must carry exactly one successor claim"
    successor = successors[0]
    predecessor_ref = successor["supersedes_claim_ref"]
    predecessor = claims[predecessor_ref["claim_id"]]

    assert predecessor_ref["object_hash"] == edge["predecessor_ref"]["object_hash"], (
        "claim_v2.supersedes_claim_ref.object_hash and "
        "object_successor_edge.predecessor_ref.object_hash must be the SAME hash"
    )
    assert predecessor_ref["object_hash"] == predecessor["object_hash"], (
        "the bound predecessor hash must equal the predecessor claim's own real object_hash"
    )
    assert edge["successor_ref"]["object_hash"] == successor["object_hash"]

    # RULING B1 (2026-08-26): the predecessor is never mutated by the amendment.
    assert predecessor["status"] == "supported"
    assert predecessor["time"]["valid_to"] is None


# ---------------------------------------------------------------------------------------------
# 5. bitemporal/03 is two families under one subject_key, with NO successor edge between them.
# ---------------------------------------------------------------------------------------------


def test_bitemporal_03_is_two_families_one_subject_key_no_edge_between_them() -> None:
    doc = _load(_BITEMPORAL_03_PATH)
    claims, edges = corpus_from_fixture(doc)

    assert len(claims) == 2, "bitemporal/03 must carry exactly two claims"
    assert edges == [], "bitemporal/03 must carry NO object_successor_edge"

    family_ids = {claim["claim_family_id"] for claim in claims}
    assert len(family_ids) == 2, "the two claims must belong to two DIFFERENT families"

    subject_keys = {
        claim["extensions"][SUBJECT_KEY_NAMESPACE]["payload"]["subject_key"] for claim in claims
    }
    assert len(subject_keys) == 1, "both families must share exactly one subject_key"


# ---------------------------------------------------------------------------------------------
# 6. The subject_key extension rules of R1-build-spec.md §1, re-verified against the real
#    `primitives` reserved-name set at runtime -- never hardcoded.
# ---------------------------------------------------------------------------------------------


def test_subject_key_namespace_is_reverse_dns() -> None:
    assert _REVERSE_DNS_RE.fullmatch(SUBJECT_KEY_NAMESPACE), (
        f"{SUBJECT_KEY_NAMESPACE!r} must match research_os.primitives._REVERSE_DNS_RE"
    )


@pytest.mark.parametrize("path,claim", _CLAIMS_WITH_SUBJECT_KEY, ids=_CLAIMS_WITH_SUBJECT_KEY_IDS)
def test_subject_key_extension_is_derivable_and_reserved_field_free(
    path: Path, claim: dict[str, Any]
) -> None:
    extension = claim["extensions"][SUBJECT_KEY_NAMESPACE]
    payload = extension["payload"]

    for field in ("subject_key", "jurisdiction", "instrument", "provision"):
        assert field in payload, f"{path}: subject_key extension payload missing {field!r}"

    assert payload["subject_key"] == "/".join(
        (payload["jurisdiction"], payload["instrument"], payload["provision"])
    ), f"{path}: subject_key must equal '/'.join((jurisdiction, instrument, provision))"

    for part_name in ("jurisdiction", "instrument", "provision"):
        part = payload[part_name]
        assert _SUBJECT_KEY_PART_RE.fullmatch(part), (
            f"{path}: subject_key part {part_name}={part!r} fails ^[a-z0-9][a-z0-9._-]*$"
        )

    # No core field name introduced at any depth -- re-derived from primitives at runtime,
    # never a hardcoded copy of the 251-name list.
    reserved_found: set[str] = set()
    stack: list[Any] = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            reserved_found.update(V1_RESERVED_EXTENSION_FIELD_NAMES.intersection(value))
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)
    assert not reserved_found, (
        f"{path}: subject_key extension payload introduces reserved field(s) {sorted(reserved_found)}"
    )

    # Rule 4 -- the Claim carrying the extension still validates and its object_hash still
    # verifies. Covered generically above; re-asserted here on the specific claim carrying it.
    SCHEMA_MODELS["claim"].model_validate(claim)
    assert claim["object_hash"] == object_hash(claim)


# ---------------------------------------------------------------------------------------------
# 7. invalidation/01 stays DEFERRED. No test anywhere may treat it as canonical.
# ---------------------------------------------------------------------------------------------


def test_invalidation_01_is_marked_deferred_and_carries_no_canonical_object() -> None:
    doc = _load(_INVALIDATION_01_PATH)
    assert doc.get("canonical_status") == "deferred", (
        "invalidation/01 must say near its top that it is deferred, per R1-build-spec.md §5b"
    )
    assert _canonical_objects(doc) == [], (
        "invalidation/01 must carry NO full canonical object (contract_version + object_hash) "
        "-- it is a behavior spec, not a schema-valid instance, and stays that way in this slice"
    )
