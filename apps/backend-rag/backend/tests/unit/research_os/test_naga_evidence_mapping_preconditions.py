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

1. THE CORRECTION IS ITSELF INCOMPLETE. The bundle names four fields. Derived here from
   the schema and the document -- not hand-copied -- the real count is larger: §2 never
   names FIFTEEN of the schema's thirty-two required paths. The first version of this
   module hardcoded the bundle's four and called them "the four fields the bundle omits",
   which restated the document's own undercount as a measurement. The four are now
   asserted to be a strict SUBSET of a derived set, so the gap is measured and the
   undercount is itself pinned.

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
from research_os.models.evidence import Evidence

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


def _load() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


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


def test_the_bundles_own_correction_undercounts_the_gap() -> None:
    """The finding the first version of this module missed by trusting the document.

    §2 omits far more than the four its correction names. Both numbers are DERIVED here --
    from the schema's recursive required set and from the section's own text -- so if
    anyone closes part of the gap, this fails and forces a re-read instead of quietly
    agreeing with a stale sentence.
    """

    absent = _never_named_in_section_two()
    named = set(_NAMED_BY_THE_CORRECTION)

    assert named < absent, (
        "the bundle's four should be a strict subset of the fields §2 never names; got "
        f"named={sorted(named)} absent={sorted(absent)}"
    )
    assert len(_required_paths(_schema())) == 32
    assert len(absent) == 15, (
        "the measured gap in §2 changed. Re-read the bundle and this module's docstring "
        f"before touching this number; absent={sorted(absent)}"
    )


def test_the_bundle_mapping_as_written_produces_an_invalid_evidence() -> None:
    """The bundle's prose claim, executed for the four fields it names.

    Scope, stated because an earlier docstring here over-claimed: this removes the four
    fields the correction names from the canonical fixture. It does not replay §2's
    mapping -- nothing in this repository executes that document -- so it proves those
    four are load-bearing, not that §2 as a whole was faithfully reproduced.
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
