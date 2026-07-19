from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from zantara_media.magazine.contracts import (
    AssetUploadMetadataV2,
    CollectorRunProjectionV1,
    EditionPacketV1,
    StoryPacketV1,
)


SITE_FIXTURES = (
    Path(__file__).parents[3] / "bali-zero-magazine" / "tests" / "fixtures"
)


def test_asset_upload_v2_has_exact_typescript_fixture_parity() -> None:
    for name in ("asset-upload-v2.json", "asset-upload-v2-collision-source.json"):
        raw = json.loads((SITE_FIXTURES / name).read_text(encoding="utf-8"))
        parsed = AssetUploadMetadataV2.model_validate(raw)
        assert parsed.model_dump(mode="json") == raw
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            AssetUploadMetadataV2.model_validate({**raw, "filename": "secret.jpg"})


def test_models_are_frozen_and_extra_forbidden(
    edition_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = EditionPacketV1.model_validate(edition_factory())
    with pytest.raises(ValidationError, match="frozen"):
        packet.edition_kind = "quiet"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EditionPacketV1.model_validate({**edition_factory(), "raw_payload": "secret"})


def test_story_and_edition_match_typescript_closed_contracts(
    breaking_factory: Callable[..., dict[str, Any]],
    edition_factory: Callable[..., dict[str, Any]],
) -> None:
    breaking = breaking_factory()
    edition = edition_factory()
    assert StoryPacketV1.model_validate(breaking).model_dump(mode="json") == breaking
    assert EditionPacketV1.model_validate(edition).model_dump(mode="json") == edition


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda packet: packet["story"]["claims"][0].update(evidence_ids=[]), "evidence"),
        (lambda packet: packet["story"].update(version=1), "expected_current_version"),
        (lambda packet: packet["story"]["claims"][0].update(breaking_gate=None), "Breaking"),
        (lambda packet: packet["story"].update(severity="medium"), "high or critical"),
    ],
)
def test_breaking_rejects_same_invalid_cases_as_typescript(
    breaking_factory: Callable[..., dict[str, Any]],
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    raw = breaking_factory()
    mutation(raw)
    with pytest.raises(ValidationError, match=message):
        StoryPacketV1.model_validate(raw)


def test_collector_projection_is_closed_and_consistent() -> None:
    raw = {
        "schema_version": "collector-run.v1",
        "run_id": "run-1",
        "system_id": "intel-lake",
        "collector_id": "routing",
        "started_at": "2026-07-18T00:00:00Z",
        "completed_at": "2026-07-18T00:05:00Z",
        "status": "healthy",
        "freshness": "fresh",
        "items_seen": 42,
        "items_eligible": 7,
        "source_count": 18,
        "unreachable_source_count": 2,
        "watermark": "opaque-nonsecret-value",
        "verified_at": "2026-07-18T00:05:02Z",
    }
    assert CollectorRunProjectionV1.model_validate(raw).model_dump(mode="json") == raw
    with pytest.raises(ValidationError, match="items_eligible"):
        CollectorRunProjectionV1.model_validate({**raw, "items_eligible": 43})


def test_shared_python_and_typescript_contract_corpus(
    breaking_factory: Callable[..., dict[str, Any]],
    edition_factory: Callable[..., dict[str, Any]],
) -> None:
    corpus = json.loads(
        (SITE_FIXTURES / "magazine-contract-corpus.json").read_text(encoding="utf-8")
    )
    collector = {
        "schema_version": "collector-run.v1",
        "run_id": "run-1",
        "system_id": "intel-lake",
        "collector_id": "daily",
        "started_at": "2026-07-18T00:00:00Z",
        "completed_at": "2026-07-18T00:01:00Z",
        "status": "healthy",
        "freshness": "fresh",
        "items_seen": 1,
        "items_eligible": 1,
        "source_count": 1,
        "unreachable_source_count": 0,
        "watermark": "wm-1",
        "verified_at": "2026-07-18T00:01:01Z",
    }
    asset = json.loads((SITE_FIXTURES / "asset-upload-v2.json").read_text(encoding="utf-8"))
    parsers = {
        "story": StoryPacketV1,
        "edition": EditionPacketV1,
        "collector": CollectorRunProjectionV1,
        "asset": AssetUploadMetadataV2,
    }
    for case in corpus["cases"]:
        if case["contract"] == "story":
            value = breaking_factory()
        elif case["contract"] == "edition":
            value = edition_factory()
        elif case["contract"] == "collector":
            value = dict(collector)
        else:
            value = dict(asset)
        if case["mutation"] == "invalid-url-port":
            if case["contract"] == "story":
                value["story"]["evidence_refs"][0]["canonical_url"] = case["value"]
            else:
                value["source_url"] = case["value"]
        elif case["mutation"] == "missing-legal-effect":
            del value["stories"][0]["claims"][0]["legal_effect"]
        elif case["mutation"] == "extra-field":
            value["raw_payload"] = "forbidden"
        if case["accept"]:
            parsers[case["contract"]].model_validate(value)
        else:
            with pytest.raises(ValidationError, match="."):
                parsers[case["contract"]].model_validate(value)
