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


def test_media_manifest_carries_no_family_revision_or_recorded_at_fields(load_json: Any) -> None:
    # Section 10's wire shape is confirmed to omit these -- unlike every
    # other successor-chained kind in this contract family (see the module
    # docstring). A stray field here would mean an accidental invention.
    payload = load_json(FIXTURE_DIR / "valid_minimal_carousel.json")
    forbidden = {
        "media_manifest_family_id",
        "revision",
        "supersedes_media_manifest_ref",
        "recorded_at",
    }
    assert forbidden.isdisjoint(payload)


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
