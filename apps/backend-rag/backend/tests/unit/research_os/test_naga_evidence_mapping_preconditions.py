"""P06's declared precondition, turned from a sentence in a document into a guard.

WHY THIS EXISTS. The P06 (NAGA) preparation bundle maps NAGA's mutable rows onto P04's
canonical `Evidence`. Its own §2 carries a correction, added by an adversarial review,
saying the mapping is INCOMPLETE — four fields in `evidence.schema.json`'s required sets
appear nowhere in it — and that "a build lane following §2 as written would emit
schema-invalid Evidence objects on day one. Closing these four ... is a precondition for
the P06 build, not a detail."
(`research/operations/execution/research-os-v1.0.0/evidence/p06/ros-v1-p06-naga-prep-b01/02-p04-adapter-mapping.md`)

That is a claim in a markdown file. This module re-measures it against the real model and
the real schema, and leaves the result executable, because a precondition nobody can run
is a precondition nobody will notice missing. Verified before writing a line of adapter:
all four are genuinely required —

  evidence_family_id       required, top level
  review_state             required, top level
  classification.rights    required in EvidenceClassification (Claim's has no `rights`)
  times.recorded_at        required in EvidenceTimes, alongside `observed_at`

The baseline is the repository's OWN canonical fixture, `fixtures/evidence/valid_minimal.json`,
not an object this test invents. That matters: an earlier module in this lane proved a
finding against a hand-built stand-in and a refuter showed the proof was worthless, so the
rule here is that the thing under test is the thing production uses.

Note for whoever writes the adapter: `Evidence` self-validates `object_hash` against
`object_hash(self)`, so a mapping that gets the fields right and the hash wrong still
fails. The positive control below exercises that path deliberately.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError
from research_os.models.evidence import Evidence

_PACKAGE_ROOT = next(
    p / "packages" / "research-os-core"
    for p in Path(__file__).resolve().parents
    if (p / "packages" / "research-os-core").is_dir()
)
_FIXTURE = _PACKAGE_ROOT / "fixtures" / "evidence" / "valid_minimal.json"
_SCHEMA = _PACKAGE_ROOT / "research_os" / "schemas" / "evidence.schema.json"

# Exactly what the bundle's §2 leaves out, expressed as paths into the object.
_OMITTED_BY_THE_BUNDLE: tuple[tuple[str, ...], ...] = (
    ("evidence_family_id",),
    ("review_state",),
    ("classification", "rights"),
    ("times", "recorded_at"),
)


def _load() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _without(payload: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    cursor: Any = out
    for key in path[:-1]:
        cursor = cursor[key]
    del cursor[path[-1]]
    return out


def test_the_baseline_fixture_is_genuinely_valid() -> None:
    """Positive control. Without it every assertion below could pass vacuously.

    Exercises the model AND the published schema AND the `object_hash` self-check — the
    fixture's hash is the real one, so a broken hashing path fails here first.

    Asserts explicitly rather than leaning on "did not raise": a validator that silently
    stopped validating would keep a raise-only control green forever, and the four fields
    are read back so this control also proves the fixture is not itself missing them.
    """

    payload = _load()

    evidence = Evidence.model_validate(payload)
    assert evidence.object_hash == payload["object_hash"]
    assert evidence.evidence_family_id == payload["evidence_family_id"]
    assert evidence.review_state is not None
    assert evidence.classification.rights == payload["classification"]["rights"]
    assert evidence.times.recorded_at is not None

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert jsonschema.Draft202012Validator(schema).is_valid(payload)


def test_the_bundle_mapping_as_written_produces_an_invalid_evidence() -> None:
    """The precondition itself: §2 as written does not survive validation.

    This is the whole claim the bundle makes in prose, executed. It fails on FOUR fields,
    named — not merely "it fails", which would also be satisfied by a typo.
    """

    crippled = _load()
    for path in _OMITTED_BY_THE_BUNDLE:
        crippled = _without(crippled, path)

    with pytest.raises(ValidationError) as excinfo:
        Evidence.model_validate(crippled)

    missing = {
        tuple(str(part) for part in error["loc"])
        for error in excinfo.value.errors()
        if error["type"] == "missing"
    }
    assert missing == set(_OMITTED_BY_THE_BUNDLE), (
        f"expected exactly the four fields the bundle omits, got {sorted(missing)}"
    )


@pytest.mark.parametrize("path", _OMITTED_BY_THE_BUNDLE, ids=lambda p: ".".join(p))
def test_each_omitted_field_is_independently_required(path: tuple[str, ...]) -> None:
    """Per-field, not per-batch.

    Dropping all four at once and seeing a failure would not tell you WHICH of them is
    load-bearing — three could be optional and the suite would look just as green.
    """

    with pytest.raises(ValidationError) as excinfo:
        Evidence.model_validate(_without(_load(), path))

    missing = {
        tuple(str(part) for part in error["loc"])
        for error in excinfo.value.errors()
        if error["type"] == "missing"
    }
    assert missing == {path}


@pytest.mark.parametrize("path", _OMITTED_BY_THE_BUNDLE, ids=lambda p: ".".join(p))
def test_the_published_schema_agrees_with_the_model(path: tuple[str, ...]) -> None:
    """Two enforcement surfaces, one answer — or the adapter can satisfy one and not both.

    The pydantic model is what production constructs; the JSON Schema is what an
    independent producer builds against. A field required by one and optional by the other
    is a gap an adapter falls straight through, so the divergence is the thing under test.
    """

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_without(_load(), path), schema)


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
