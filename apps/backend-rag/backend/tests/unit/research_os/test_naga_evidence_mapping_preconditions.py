"""P06's declared precondition, turned from a sentence in a document into a guard.

WHY THIS EXISTS. The P06 (NAGA) preparation bundle maps NAGA's mutable rows onto P04's
canonical `Evidence`. Its own §2 carries a correction, added by an adversarial review,
saying the mapping is INCOMPLETE -- four fields in `evidence.schema.json`'s required sets
appear nowhere in it -- and that "a build lane following §2 as written would emit
schema-invalid Evidence objects on day one. Closing these four ... is a precondition for
the P06 build, not a detail."
(`research/operations/execution/research-os-v1.0.0/evidence/p06/ros-v1-p06-naga-prep-b01/02-p04-adapter-mapping.md`)

That is a claim in a markdown file. This module re-measures it against the real model, the
real schema, and the real document, and leaves the result executable.

THREE CORRECTIONS ARE BAKED IN, each from an adversarial round on this file. They are
recorded rather than smoothed away, because each one describes a way this module was
already wrong once:

1. THE CORRECTION WAS ITSELF INCOMPLETE, AND THE GAP IS NOW CLOSED. The bundle named four
   fields. Derived from the schema and the document -- not hand-copied -- the real count
   was larger: §2 never named FIFTEEN of the schema's thirty-two required paths. The first
   version of this module hardcoded the bundle's four and called them "the four fields the
   bundle omits", which restated the document's own undercount as a measurement; the
   second version asserted the four were a strict SUBSET of a derived set of fifteen, so
   the gap was measured instead of quoted.

   R1 (mission R1, 2026-09-11, base `9304392d1a`) then CLOSED the gap: §2 documents all
   thirty-two required paths, each with a real mapping or a named exclusion reason. The
   fifteen is therefore gone, and it is gone because the document changed -- not because
   anyone edited a number. This module does not pretend the gap never existed. It stops
   pinning the WIDTH of a gap that no longer exists and starts pinning two things that
   only became assertable once it closed: that §2 names every required path, and that the
   mapping §2 documents, when EXECUTED, produces a schema-valid `Evidence`. Flipping the
   `15` to a `0` would have been renumbering; deleting the width assertion and replacing
   it with an executed mapping is the cure the width assertion was standing in for.

2. THE OBJECT_HASH CONTROL WAS TAUTOLOGICAL. The positive control asserted
   `evidence.object_hash == payload["object_hash"]`, which only proves the value was
   copied through -- it holds whether or not the hash was ever recomputed. Measured: with
   `Evidence.validate_evidence`'s hash comparison disabled, all tests still passed. There
   is now a GUILT control that corrupts the hash and requires a raise, and the innocence
   claim no longer says a broken hashing path "fails here first".

3. WHAT THIS DOES NOT OBSERVE, stated so nobody reads more into a green run. No adapter,
   producer, repository, or persistence path is exercised anywhere in this module. It pins
   REQUIREDNESS on the pydantic model and on the published JSON Schema -- which are not
   independent of each other: the schema is a byte-identical regeneration of the model,
   enforced by `test_schemas.py`. It also pins the SHAPE OF THE GAP in one document. A
   regression in the code that eventually builds these objects leaves every test here
   green. The reject direction of the hash check is additionally covered outside this file
   by `test_models_and_fixtures.py::test_validation_context_cannot_bypass_exact_object_hash`;
   the guilt control below is this module's own, so its claims stand without that neighbour.

The baseline is the repository's OWN canonical fixture, `fixtures/evidence/valid_minimal.json`,
not an object this test invents: an earlier module in this lane proved a finding against a
hand-built stand-in and a refuter showed the proof was worthless.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError
from research_os.hashing import object_hash
from research_os.models.evidence import Evidence

from .naga_evidence_mapping_reference import UnmappableRecord, map_to_evidence
from .research_os_admission_reference import Excluded, admit

_REPO_ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "packages" / "research-os-core").is_dir()
)
_PACKAGE_ROOT = _REPO_ROOT / "packages" / "research-os-core"
_FIXTURE = _PACKAGE_ROOT / "fixtures" / "evidence" / "valid_minimal.json"
_SCHEMA = _PACKAGE_ROOT / "research_os" / "schemas" / "evidence.schema.json"
_BUNDLE = (
    _REPO_ROOT
    / "research/operations/execution/research-os-v1.0.0/evidence/p06"
    / "ros-v1-p06-naga-prep-b01"
    / "02-p04-adapter-mapping.md"
)

# The four the bundle's own correction names, verbatim from that document.
_NAMED_BY_THE_CORRECTION: tuple[tuple[str, ...], ...] = (
    ("evidence_family_id",),
    ("review_state",),
    ("classification", "rights"),
    ("times", "recorded_at"),
)

# Field names §2 demonstrably DOES discuss. Used as the innocence control on the section
# extractor below: if a heading is renamed and extraction silently yields nothing, every
# field would look absent and the measured gap would balloon instead of failing.
_DISCUSSED_IN_SECTION_TWO: tuple[str, ...] = (
    "document_id",
    "source_span",
    "stance",
    "provenance",
)


_SEED_COHORT = _BUNDLE.parent / "fixtures" / "seed_public_regulatory"

#: Passed in rather than read from a clock, so the mapping's output -- and therefore its
#: `object_hash` -- is deterministic across runs. §2's `times.recorded_at` row is explicit
#: that this instant belongs to the ADAPTER, never to the legacy row.
_SEED_RECORDED_AT = "2026-09-11T00:00:00Z"


def _load() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _seed_pairs() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Every `(record, source)` pair in the seed cohort, found by SHAPE, not by container.

    The pair is the legacy shape `research_os_admission_reference.admit` already consumes,
    so this module and that one cannot drift into two different notions of "a NAGA row".
    Discovery walks the JSON rather than assuming one container layout: a fixture bundle
    that reorganises its wrapper should not redden a mapping test.
    """

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            record = node.get("record")
            source = node.get("source")
            if isinstance(record, dict) and isinstance(source, dict):
                pairs.append((record, source))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in sorted(_SEED_COHORT.glob("*.json")):
        walk(json.loads(path.read_text(encoding="utf-8")))
    return pairs


def _first_seed_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    pairs = _seed_pairs()
    assert pairs, (
        f"no (record, source) pair found under {_SEED_COHORT}. The seed cohort is R1's "
        "own synthetic fixture set; without it §2's mapping cannot be executed over "
        "anything, and a mapping nobody runs is the defect this module exists to close."
    )
    return pairs[0]


def _has_path(payload: dict[str, Any], path: tuple[str, ...]) -> bool:
    cursor: Any = payload
    for key in path:
        if not isinstance(cursor, dict) or key not in cursor:
            return False
        cursor = cursor[key]
    return cursor is not None


def _schema() -> dict[str, Any]:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _without(payload: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    cursor: Any = out
    for key in path[:-1]:
        cursor = cursor[key]
    del cursor[path[-1]]
    return out


def _resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        node = schema["$defs"][node["$ref"].rsplit("/", 1)[-1]]
    return node


def _required_paths(schema: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    """Every required path in the published schema, walked recursively through $refs."""

    found: list[tuple[str, ...]] = []

    def walk(node: dict[str, Any], prefix: tuple[str, ...]) -> None:
        node = _resolve(schema, node)
        for name in node.get("required", []):
            path = (*prefix, name)
            found.append(path)
            child = node.get("properties", {}).get(name)
            if child is None:
                continue
            child = _resolve(schema, child)
            if child.get("type") == "object" and child.get("required"):
                walk(child, path)

    walk(schema, ())
    return tuple(found)


def _section_two() -> str:
    """§2 of the bundle -- the Evidence mapping table -- as raw text."""

    text = _BUNDLE.read_text(encoding="utf-8")
    match = re.search(r"^## 2\..*?(?=^## 3\.)", text, re.MULTILINE | re.DOTALL)
    assert match is not None, (
        f"could not locate '## 2.' in {_BUNDLE}. This module measures that section by "
        "name; if the bundle was restructured, re-read it rather than deleting this test."
    )
    return match.group(0)


def _never_named_in_section_two() -> set[tuple[str, ...]]:
    """Required paths whose leaf name never appears in §2.

    Name-absence is a CONSERVATIVE test for 'not mapped': a field §2 never mentions is
    certainly not mapped by it. The converse does not hold -- §2 names `times.published_at`
    only to say NAGA cannot supply it -- so presence is deliberately not read as coverage.
    The error runs one way only, and it is the safe way: this set understates the gap.
    """

    section = _section_two()
    return {
        path
        for path in _required_paths(_schema())
        if not re.search(rf"\b{re.escape(path[-1])}\b", section)
    }


def test_the_baseline_fixture_is_genuinely_valid() -> None:
    """Innocence control. Without it every assertion below could pass vacuously.

    Correction from an adversarial round: this used `is not None` read-backs and claimed
    they proved the fixture carried the four fields. They proved nothing -- after
    `model_validate` succeeds a non-Optional field is non-None by construction, so those
    asserts could not fail. Presence is now asked of the PAYLOAD, before parsing, which is
    the only place the question can actually be answered. It does NOT claim to exercise
    the hash self-check -- that is the guilt control's job, see correction 2.
    """

    payload = _load()

    # The fixture must actually CARRY the four fields, or every negative test below is
    # deleting something that was never there.
    for path in _NAMED_BY_THE_CORRECTION:
        cursor: Any = payload
        for key in path:
            assert key in cursor, f"the canonical fixture is missing {'.'.join(path)}"
            cursor = cursor[key]

    evidence = Evidence.model_validate(payload)
    assert evidence.evidence_family_id == payload["evidence_family_id"]
    assert evidence.classification.rights == payload["classification"]["rights"]

    assert jsonschema.Draft202012Validator(_schema()).is_valid(payload)


def test_a_corrupted_object_hash_is_refused() -> None:
    """Guilt control for the hash self-check -- the innocence half cannot see it.

    Measured 2026-08-26: with `Evidence.validate_evidence`'s comparison disabled, all
    other tests in this module stayed green, because asserting that a parsed value equals
    the raw value it came from is true whether or not anything recomputed it.
    """

    payload = _load()
    payload["object_hash"] = "f" * 64

    with pytest.raises(ValidationError) as excinfo:
        Evidence.model_validate(payload)

    assert any(error["type"] == "object_hash_mismatch" for error in excinfo.value.errors()), (
        f"expected an object_hash_mismatch, got {excinfo.value.errors()}"
    )


def test_the_section_extractor_actually_reads_the_section() -> None:
    """Innocence control on this module's own measuring instrument.

    A renamed heading would make `_section_two` yield nothing, every field would look
    unnamed, and the derived gap below would silently inflate to the full required set --
    a broken probe reporting a catastrophe. Pin the instrument before trusting its number.
    """

    section = _section_two()
    assert len(section) > 500
    for name in _DISCUSSED_IN_SECTION_TWO:
        assert re.search(rf"\b{name}\b", section), f"§2 no longer discusses {name}"


@pytest.mark.parametrize("path", _NAMED_BY_THE_CORRECTION, ids=lambda p: ".".join(p))
def test_each_field_named_by_the_correction_is_independently_required(
    path: tuple[str, ...],
) -> None:
    """Per-field, not per-batch.

    Dropping all four at once and seeing a failure would not tell you WHICH is
    load-bearing -- three could be optional and the suite would look just as green.
    """

    with pytest.raises(ValidationError) as excinfo:
        Evidence.model_validate(_without(_load(), path))

    missing = {
        tuple(str(part) for part in error["loc"])
        for error in excinfo.value.errors()
        if error["type"] == "missing"
    }
    assert missing == {path}


@pytest.mark.parametrize("path", _NAMED_BY_THE_CORRECTION, ids=lambda p: ".".join(p))
def test_the_published_schema_agrees_with_the_model(path: tuple[str, ...]) -> None:
    """The PUBLISHED artifact says the same thing the model does.

    Correction, from an adversarial round: this is NOT proof of two independent
    enforcement surfaces, as an earlier version of this docstring implied. The checked-in
    schema is a regeneration of the model -- `test_schemas.py`'s
    `test_checked_in_schemas_are_byte_identical_to_fresh_regeneration` enforces byte
    identity -- so the two CANNOT diverge while that guard holds, and a mutation to either
    reddens both. What this pins is the artifact an outside producer actually builds
    against, which is worth pinning on its own terms; it is not an independence proof.
    """

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_without(_load(), path), _schema())


def test_section_two_documents_every_required_path() -> None:
    """The successor of the gap-width assertion: coverage, not the width of a hole.

    Both sides are DERIVED -- the schema's recursive required set, and the section's own
    text -- so this cannot agree with a stale sentence. If §2 is restructured and a path
    stops being named, this reddens and names the missing paths instead of silently
    reporting a smaller gap.
    """

    absent = _never_named_in_section_two()
    required = _required_paths(_schema())

    assert len(required) == 32, (
        "the schema's required set changed size. That is a contract change, not a "
        f"bookkeeping one: re-read evidence.schema.json; got {len(required)}"
    )
    assert absent == set(), (
        "§2 must document all 32 required Evidence paths; missing: "
        f"{sorted('.'.join(path) for path in absent)}"
    )


def test_the_documented_mapping_produces_a_schema_valid_evidence() -> None:
    """The test this module never had: §2's mapping EXECUTED, not merely mentioned.

    Everything else here pins requiredness on a model and a schema, or pins that a
    document mentions a name. None of that catches the failure that actually matters --
    a document that names all 32 paths and still describes a mapping whose output is
    schema-invalid. `naga_evidence_mapping_reference.map_to_evidence` is §2 written out as
    code; this runs it over a canonical, synthetic, NAGA-shaped seed record from the P06
    bundle and requires the result to survive both the pydantic model and the published
    JSON Schema, with a self-consistent `object_hash`.
    """

    record, source = _first_seed_pair()
    payload = map_to_evidence(record, source, recorded_at=_SEED_RECORDED_AT)

    Evidence.model_validate(payload)
    jsonschema.validate(payload, _schema())

    recomputed = object_hash({k: v for k, v in payload.items() if k != "object_hash"})
    assert payload["object_hash"] == recomputed, (
        "the mapping must COMPUTE object_hash over its own payload, never carry one "
        "through from the legacy row"
    )


def test_the_executed_mapping_covers_every_required_path() -> None:
    """Coverage measured on the OUTPUT, with the path list derived from the schema.

    `test_section_two_documents_every_required_path` measures the document; this measures
    what the document, executed, actually produces. The two can disagree -- a row can name
    a path and describe a mapping that never populates it -- and when they do, this is the
    one that is right.
    """

    record, source = _first_seed_pair()
    payload = map_to_evidence(record, source, recorded_at=_SEED_RECORDED_AT)

    missing = [path for path in _required_paths(_schema()) if not _has_path(payload, path)]
    assert missing == [], (
        "the executed mapping left required paths unpopulated: "
        f"{sorted('.'.join(path) for path in missing)}"
    )


def test_a_record_admission_excludes_is_never_mapped() -> None:
    """The contract between the two reference modules, asserted in the direction that bites.

    `map_to_evidence` refuses instead of defaulting, so a legacy-shaped record -- URL hash,
    hint span, no IntelEvent identity -- must RAISE rather than emit a half-invented
    Evidence. This is the guilt control for the mapping: without it, a mapping that quietly
    filled the holes would keep every assertion above green.
    """

    record, source = _first_seed_pair()
    legacy_shaped = copy.deepcopy(dict(record))
    # Cripple ONLY the span's exactness, keeping `quoted_text` so the statement is still
    # derivable from the source. Dropping the whole span instead would trip rule 1
    # (`statement_not_from_source`) first and this test would pass for the wrong reason --
    # measured: it did, on the first version of this test. The ordered vocabulary is part of
    # the contract, so a test about rule 4 must isolate rule 4.
    legacy_shaped["source_span"] = {"hint": "somewhere in article 4", "quoted_text": (record["source_span"] or {}).get("quoted_text")}

    decision = admit(legacy_shaped, source)
    assert isinstance(decision, Excluded), "the crippled record must not be admissible"
    assert decision.reason == "exact_span_missing"

    with pytest.raises(UnmappableRecord):
        map_to_evidence(legacy_shaped, source, recorded_at=_SEED_RECORDED_AT)


def test_the_four_the_correction_named_are_load_bearing_on_the_model() -> None:
    """The four, pinned on the pydantic model rather than on the document.

    Renamed by R1 from `test_the_bundle_mapping_as_written_produces_an_invalid_evidence`.
    The old name asserted a claim about the BUNDLE -- that §2 as written yields an invalid
    Evidence -- and §2 no longer omits these four, so the name had become false while the
    body stayed true. The body is unchanged and still worth keeping: it proves the four are
    required by the model, which is a different mechanism from
    `test_each_field_named_by_the_correction_is_independently_required`'s schema-level
    check. Scope, stated because an earlier docstring here over-claimed: this removes the
    four fields from the canonical fixture; it does not replay §2's mapping --
    `test_the_documented_mapping_produces_a_schema_valid_evidence` is what does that now.
    """

    crippled = _load()
    for path in _NAMED_BY_THE_CORRECTION:
        crippled = _without(crippled, path)

    with pytest.raises(ValidationError) as excinfo:
        Evidence.model_validate(crippled)

    missing = {
        tuple(str(part) for part in error["loc"])
        for error in excinfo.value.errors()
        if error["type"] == "missing"
    }
    assert missing == set(_NAMED_BY_THE_CORRECTION), (
        f"expected exactly the four fields the correction names, got {sorted(missing)}"
    )


def test_evidence_classification_requires_rights_where_claim_does_not() -> None:
    """The asymmetry most likely to be missed, pinned explicitly.

    An adapter author who has already mapped a `Claim.classification` will reasonably
    assume `Evidence.classification` has the same shape. It does not: `rights` is required
    here and does not exist there. Asserted from the models, never from the prose.
    """

    from research_os.models.evidence import EvidenceClassification
    from research_os.primitives import Classification

    assert "rights" in EvidenceClassification.model_fields
    assert "rights" not in Classification.model_fields
    assert EvidenceClassification.model_fields["rights"].is_required()
