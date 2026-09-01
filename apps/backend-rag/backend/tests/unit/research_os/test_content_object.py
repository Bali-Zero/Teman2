from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.hashing import object_hash
from research_os.models.content_object import ContentObject

FIXTURE_DIR = FIXTURES_ROOT / "content_object"


def _validated(payload: dict[str, Any], **updates: Any) -> ContentObject:
    candidate = deepcopy(payload)
    candidate.update(updates)
    candidate["object_hash"] = object_hash(candidate)
    return ContentObject.model_validate(candidate)


def _errors(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def _rehash(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["object_hash"] = object_hash(payload)
    return payload


# Per-fixture "undo exactly the one declared mutation" transforms, proving
# empirically (per the mandate's rule 5) that the declared defect is the
# SOLE cause of rejection: fixing only it must yield a fully valid document.
_FIXES: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
    "invalid_object_hash_mismatch": lambda p, valid_base: _rehash(p),
    "invalid_unknown_top_level_field": lambda p, valid_base: {
        k: v for k, v in p.items() if k != "unexpected_field"
    },
    "invalid_revision_one_with_supersedes": lambda p, valid_base: _rehash(
        {k: v for k, v in p.items() if k != "supersedes_content_object_ref"}
    ),
    "invalid_revision_missing_supersedes_ref": lambda p, valid_base: _rehash({**p, "revision": 1}),
    "invalid_supersedes_ref_is_self": lambda p, valid_base: _rehash(
        {
            **p,
            "supersedes_content_object_ref": {
                "content_object_id": valid_base["content_object_id"],
                "revision": 1,
                "object_hash": valid_base["object_hash"],
            },
        }
    ),
    "invalid_supersedes_ref_revision_not_less": lambda p, valid_base: _rehash(
        {
            **p,
            "supersedes_content_object_ref": {
                **p["supersedes_content_object_ref"],
                "revision": 1,
            },
        }
    ),
    "invalid_availability_severity_bad_literal": lambda p, valid_base: _rehash(
        {**p, "availability": {**p["availability"], "severity": "low"}}
    ),
    "invalid_availability_resolved_before_requested": lambda p, valid_base: _rehash(
        {
            **p,
            "availability": {
                **p["availability"],
                "resolved_at": "2026-08-17T12:00:00Z",
            },
        }
    ),
    "invalid_extension_shadows_core_field": lambda p, valid_base: _rehash(
        {
            **p,
            "extensions": {
                "com.example.wr2-note": {
                    "extension_version": "1.0.0",
                    "payload": {"synthetic_case_code": "fixture-only"},
                }
            },
        }
    ),
}


def _invalid_fixture_names() -> list[str]:
    return sorted(
        path.stem
        for path in FIXTURE_DIR.glob("invalid_*.json")
        if not path.name.endswith(".expect.json")
    )


def test_every_invalid_fixture_has_a_registered_fix() -> None:
    # Guards this test file itself against silently growing stale as new
    # invalid fixtures are added without a matching fix entry above.
    assert set(_invalid_fixture_names()) == set(_FIXES)


@pytest.mark.parametrize("name", _invalid_fixture_names())
def test_invalid_fixture_reason_code_is_a_singleton(name: str, load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / f"{name}.json")
    expected = load_json(FIXTURE_DIR / f"{name}.expect.json")["reason_code"]

    with pytest.raises(ValidationError) as caught:
        ContentObject.model_validate(payload)

    assert _errors(caught.value) == {expected}, name


@pytest.mark.parametrize("name", _invalid_fixture_names())
def test_fixing_only_the_declared_defect_makes_the_fixture_valid(name: str, load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / f"{name}.json")
    valid_base = load_json(FIXTURE_DIR / "valid_minimal_revision_one.json")

    fixed = _FIXES[name](payload, valid_base)

    # Must now validate cleanly -- proves the declared defect was the SOLE
    # cause of rejection, not one of several simultaneous problems.
    instance = ContentObject.model_validate(fixed)
    assert instance.object_hash == fixed["object_hash"]


def test_availability_clock_accepts_equal_resolved_and_requested_at(load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / "valid_availability_withdrawal_with_timestamps.json")
    instance = _validated(
        payload,
        availability={
            **payload["availability"],
            "resolved_at": payload["availability"]["requested_at"],
        },
    )
    assert instance.availability.resolved_at == instance.availability.requested_at


def test_extensions_accept_a_legitimate_namespaced_payload(load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / "valid_with_extension.json")
    instance = ContentObject.model_validate(payload)
    assert "com.example.wr2-note" in (instance.extensions or {})


def test_revision_two_without_supersedes_ref_is_rejected(load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / "valid_minimal_revision_one.json")
    with pytest.raises(ValidationError) as caught:
        _validated(payload, revision=2)
    assert "revision_missing_supersedes_ref" in _errors(caught.value)


def test_content_object_is_immutable(load_json: Any) -> None:
    payload = load_json(FIXTURE_DIR / "valid_minimal_revision_one.json")
    instance = ContentObject.model_validate(payload)
    with pytest.raises(ValidationError):
        instance.campaign_id = "com.example.mutation-attempt"
