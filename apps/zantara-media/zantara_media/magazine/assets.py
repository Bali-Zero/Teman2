"""Closed asset-intent manifest and canonical packet binding."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from zantara_media.magazine.contracts import (
    AssetProvenanceV2,
    EditionPacketV1,
    StoryPacketV1,
)


class AssetIntentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    source_path: Path
    story_ids: tuple[str, ...] = Field(min_length=1)
    captured_at: str
    alt_text: str
    source: str
    source_url: str | None
    rights_basis: Literal[
        "internal-owned", "licensed", "public-domain", "official-use", "generated"
    ]
    rights_status: Literal["approved"]
    usage_status: Literal["approved"]
    dlp_status: Literal["passed"]
    sanitization_status: Literal["passed"]
    perceptual_dedup_status: Literal["unique", "intentional-reuse"]

    def provenance(self, packet_id: str) -> AssetProvenanceV2:
        values = self.model_dump(mode="python", exclude={"source_path", "story_ids"})
        return AssetProvenanceV2(packet_id=packet_id, **values)


class AssetIntentManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["asset-intents.v1"]
    intents: tuple[AssetIntentV1, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def unique_assets(self) -> AssetIntentManifestV1:
        ids = [item.asset_id for item in self.intents]
        if len(ids) != len(set(ids)):
            raise ValueError("asset intent ids must be unique")
        return self


def bind_canonical_assets(
    packet: dict[str, object],
    manifest: AssetIntentManifestV1,
    canonical: dict[str, str],
    *,
    breaking: bool,
) -> dict[str, object]:
    if set(canonical) != {item.asset_id for item in manifest.intents}:
        raise ValueError("canonical asset response set does not match manifest")
    story_assets: dict[str, set[str]] = {}
    for intent in manifest.intents:
        digest = canonical[intent.asset_id]
        for story_id in intent.story_ids:
            story_assets.setdefault(story_id, set()).add(digest)
    bound = dict(packet)
    if breaking:
        story = dict(bound["story"])  # type: ignore[arg-type]
        unknown = set(story_assets) - {str(story["story_id"])}
        if unknown:
            raise ValueError("asset intent references an unknown story")
        story["asset_digests"] = sorted(story_assets.get(str(story["story_id"]), set()))
        bound["story"] = story
        return StoryPacketV1.model_validate(bound).model_dump(mode="json")
    stories: list[dict[str, object]] = []
    known: set[str] = set()
    for raw_story in bound["stories"]:  # type: ignore[union-attr]
        story = dict(raw_story)
        story_id = str(story["story_id"])
        known.add(story_id)
        story["asset_digests"] = sorted(story_assets.get(story_id, set()))
        stories.append(story)
    if set(story_assets) - known:
        raise ValueError("asset intent references an unknown story")
    bound["stories"] = stories
    bound["asset_digests"] = sorted(canonical.values())
    return EditionPacketV1.model_validate(bound).model_dump(mode="json")
