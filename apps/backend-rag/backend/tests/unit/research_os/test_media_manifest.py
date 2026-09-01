from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.hashing import object_hash
from research_os.models.media_manifest import MediaManifest

FIXTURE_DIR = FIXTURES_ROOT / "media_manifest"


def _rehash(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["object_hash"] = object_hash(payload)
    return payload


def _errors(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


_FIXES: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
    "invalid_object_hash_mismatch": lambda p, valid_base: _rehash(p),
    "invalid_unknown_top_level_field": lambda p, valid_base: {
        k: v for k, v in p.items() if k != "unexpected_field"
    },
    "invalid_content_object_ref_missing_revision": lambda p, valid_base: {
        **p,
        "content_object_ref": valid_base["content_object_ref"],
    },
    "invalid_media_type_bad_literal": lambda p, valid_base: {**p, "media_type": "carousel"},
    "invalid_asset_missing_rights": lambda p, valid_base: {
        **p,
        "assets": [{**p["assets"][0], "rights": valid_base["assets"][0]["rights"]}],
    },
    "invalid_asset_sha256_uppercase": lambda p, valid_base: {
        **p,
        "assets": [{**p["assets"][0], "sha256": p["assets"][0]["sha256"].lower()}],
    },
    "invalid_audio_loudness_lufs_not_numeric": lambda p, valid_base: {
        **p,
        "audio": {**p["audio"], "loudness_lufs": -14.2},
    },
    "invalid_audio_sync_result_bad_pattern": lambda p, valid_base: {
        **p,
        "audio": {**p["audio"], "sync_result": "wr3.sync-result.pass"},
    },
    "invalid_identity_anchor_ref_content_hash_bad_pattern": lambda p, valid_base: {
        **p,
        "identity": {
            **p["identity"],
            "anchor_ref": {
                **p["identity"]["anchor_ref"],
                "content_hash": p["identity"]["anchor_ref"]["content_hash"].lower(),
            },
        },
    },
}


def _invalid_fixture_names() -> list[str]:
    return sorted(
        path.stem
        for path in FIXTURE_DIR.glob("invalid_*.json")
        if not path.name.endswith(".expect.json")
    )


def test_every_invalid_fixture_has_a_registered_fix() -> None:
    assert set(_invalid_fixture_names()) == set(_FIXES)


@pytest.mark.parametrize("name", _invalid_fixture_names())
def test_invalid_fixture_reason_code_is_a_singleton(name: str, load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / f"{name}.json")
    expected = load_json(FIXTURE_DIR / f"{name}.expect.json")["reason_code"]

    with pytest.raises(ValidationError) as caught:
        MediaManifest.model_validate(payload)

    assert _errors(caught.value) == {expected}, name


@pytest.mark.parametrize("name", _invalid_fixture_names())
def test_fixing_only_the_declared_defect_makes_the_fixture_valid(name: str, load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / f"{name}.json")
    valid_base = load_json(FIXTURE_DIR / "valid_minimal_carousel.json")

    fixed = _FIXES[name](payload, valid_base)

    # Must now validate cleanly -- proves the declared defect was the SOLE
    # cause of rejection, not one of several simultaneous problems.
    instance = MediaManifest.model_validate(fixed)
    assert instance.object_hash == fixed["object_hash"]


def test_media_manifest_is_immutable(load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / "valid_minimal_carousel.json")
    instance = MediaManifest.model_validate(payload)
    with pytest.raises(ValidationError):
        instance.media_type = "video"


def test_quality_check_entries_reject_mutation(load_json: Any) -> None:
    # Rule 4 / section 2: object_hash always means the hash of the COMPLETE
    # canonical object. Quality.checks used to be tuple[dict[str, Any], ...]
    # -- the outer FrozenCoreModel's frozen=True blocks reassigning the
    # tuple itself, but does nothing to a bare dict's own mutable entries,
    # so a live instance could be mutated after validation while still
    # reporting its original, now-stale object_hash. Each checks[] entry is
    # now its own frozen QualityCheck submodel, so mutating a field on it
    # goes through the same pydantic frozen guard every other object in
    # this package already gets.
    payload = load_json(FIXTURE_DIR / "valid_video_with_audio_and_identity.json")
    instance = MediaManifest.model_validate(payload)

    with pytest.raises(ValidationError):
        instance.quality.checks[0].result = "MUTATED"  # type: ignore[attr-defined]


def test_object_hash_still_matches_after_an_attempted_quality_check_mutation(
    load_json: Any,
) -> None:
    payload = load_json(FIXTURE_DIR / "valid_video_with_audio_and_identity.json")
    instance = MediaManifest.model_validate(payload)

    with pytest.raises(ValidationError):
        instance.quality.checks[0].result = "MUTATED"  # type: ignore[attr-defined]

    # The attempted mutation above did not go through -- object_hash(), which
    # recomputes the canonical hash from the instance's CURRENT state, must
    # still agree with the value the instance itself carries and validated
    # against at construction time.
    assert object_hash(instance) == instance.object_hash


def test_media_manifest_carries_no_family_revision_or_recorded_at_fields() -> None:
    # Section 10's wire shape is confirmed to omit these -- unlike every
    # other successor-chained kind in this contract family (see the module
    # docstring). Asserted against the MODEL's own field set, not a fixture
    # payload: a fixture merely being honest about what it happens to carry
    # would not catch the model itself growing one of these fields as
    # optional -- the fixture would keep validating and this test would
    # keep passing while the real invariant silently broke.
    forbidden = {
        "media_manifest_family_id",
        "revision",
        "supersedes_media_manifest_ref",
        "recorded_at",
    }
    assert forbidden.isdisjoint(MediaManifest.model_fields)


def test_extensions_accept_a_legitimate_namespaced_payload(load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / "valid_with_extension.json")
    instance = MediaManifest.model_validate(payload)
    assert "com.example.wr2-note" in (instance.extensions or {})


def test_video_manifest_carries_audio_and_identity_metadata(load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / "valid_video_with_audio_and_identity.json")
    instance = MediaManifest.model_validate(payload)
    assert instance.audio is not None
    assert instance.identity is not None
    assert instance.media_type == "video"
    # An ORDINARY, non-exceptional specimen (corrected 2026-08-23): the
    # manifest classification is >= its lone asset's, not lower than it --
    # see test_manifest_classification_may_be_lowered_by_an_invisible_receipt
    # below for the deliberately-exceptional counterpart.
    assert instance.classification.risk_class == instance.assets[0].risk_class
    assert instance.classification.sensitivity == instance.assets[0].sensitivity


def test_manifest_classification_may_be_lowered_by_an_invisible_receipt(load_json: Any) -> None:
    """Section 10 permits a distinct derivative manifest to hold a LOWER
    classification than the component-wise maximum of its ContentObject
    revision and every asset input, when backed by a valid
    SanitizationReceipt/RiskReclassificationReceipt "indexed by that exact
    output hash" -- a receipt this manifest structurally cannot embed (see
    ``MediaManifest.validate_media_manifest``'s own INTERPRETATION comment
    on why the true ``classification >= max(assets)`` floor is deliberately
    NOT enforced in-model).

    This fixture is the labeled escape-hatch specimen: its manifest
    classification (green/public) is genuinely lower than its lone asset's
    (amber/internal), and that is legitimate ONLY because a receipt not
    visible in this document is assumed to back it -- kept as its own named
    fixture, separate from the ordinary valid_video_with_audio_and_identity
    .json (an unexceptional specimen since 2026-08-23), so nobody reading
    the fixture directory has to infer the receipt escape from an
    unlabeled example.
    """
    payload = load_json(FIXTURE_DIR / "valid_manifest_classification_lowered_by_receipt.json")
    instance = MediaManifest.model_validate(payload)
    assert instance.classification.risk_class == "green"
    assert instance.assets[0].risk_class == "amber"
    assert instance.classification.sensitivity == "public"
    assert instance.assets[0].sensitivity == "internal"
