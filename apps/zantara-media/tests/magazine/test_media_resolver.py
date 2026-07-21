from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from zantara_media.magazine import media_resolver
from zantara_media.magazine.media_resolver import (
    AssetFingerprintLedger,
    _flowkit_generator,
    resolve_asset_manifest,
    select_asset_target,
)
from zantara_media.security.dlp import DLPResult


def test_standard_edition_selects_only_the_declared_lead(
    edition_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    lead = story_factory(
        story_id="story-lead",
        slug="lead-story",
        severity="critical",
        asset_digests=[],
    )
    secondary = story_factory(
        story_id="story-secondary",
        slug="secondary-story",
        severity="high",
        asset_digests=[],
    )
    packet = edition_factory(
        stories=[lead, secondary],
        placements=[
            {
                "story_id": "story-secondary",
                "version": 2,
                "section": "compliance",
                "order": 2,
                "lead": False,
            },
            {
                "story_id": "story-lead",
                "version": 2,
                "section": "compliance",
                "order": 1,
                "lead": True,
            },
        ],
        asset_digests=[],
    )

    target = select_asset_target(packet, breaking=False)

    assert target is not None
    assert target.story_id == "story-lead"
    assert target.slug == "lead-story"
    assert "story-secondary" not in target.prompt


def test_breaking_selects_the_canonical_story(
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(
        story=story_factory(
            story_id="breaking-story",
            slug="breaking-story",
            asset_digests=[],
        )
    )

    target = select_asset_target(packet, breaking=True)

    assert target is not None
    assert target.story_id == "breaking-story"
    assert target.captured_at == packet["verified_at"]


def test_quiet_edition_uses_typographic_fallback(
    edition_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = edition_factory(
        edition_kind="quiet",
        stories=[],
        placements=[],
        referenced_claim_ids=[],
        referenced_evidence_ids=[],
        asset_digests=[],
        reader_notices=["No verified material change detected."],
    )

    assert select_asset_target(packet, breaking=False) is None


def test_prompt_excludes_summary_and_uses_only_sanitized_editorial_fields(
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(
        story=story_factory(
            title="A new compliance deadline",
            deck="Official guidance changes the operational calendar.",
            why_it_matters="Bali Zero must review affected deadlines.",
            summary="SUMMARY_ONLY_MARKER synthetic-value-0000",
            asset_digests=[],
        )
    )

    target = select_asset_target(packet, breaking=True)

    assert target is not None
    assert "SUMMARY_ONLY_MARKER" not in target.prompt
    assert "synthetic-value-0000" not in target.prompt
    assert "A new compliance deadline" in target.prompt
    assert len(target.prompt) <= 1400


def _image_bytes(*, color: str = "#C8102E", animated: bool = False) -> bytes:
    stream = io.BytesIO()
    first = Image.new("RGB", (1200, 675), color)
    if animated:
        second = Image.new("RGB", (1200, 675), "#F4C430")
        first.save(stream, format="WEBP", save_all=True, append_images=[second], duration=100)
    else:
        first.save(stream, format="PNG")
    return stream.getvalue()


@pytest.mark.asyncio
async def test_generated_asset_is_verified_and_emitted_as_approved_intent(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(story=story_factory(asset_digests=[]))

    async def generate(_prompt: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_image_bytes())
        return destination

    async def describe(_data: bytes, _filename: str) -> tuple[str, dict[str, str]]:
        return "Abstract editorial scene with no visible text or people.", {"model": "local"}

    async def scan(_text: str, _filename: str) -> DLPResult:
        return DLPResult(has_pii=False)

    result = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "generated",
        ledger=AssetFingerprintLedger(tmp_path / "fingerprints.jsonl"),
        generate=generate,
        describe=describe,
        scan_dlp=scan,
    )

    assert result.fallback_reason is None
    assert len(result.manifest.intents) == 1
    intent = result.manifest.intents[0]
    assert intent.story_ids == ("story-1",)
    assert intent.rights_basis == "generated"
    assert intent.source_path.is_file()
    assert intent.dlp_status == "passed"


@pytest.mark.asyncio
async def test_generation_failure_keeps_typographic_fallback(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(story=story_factory(asset_digests=[]))

    async def generate(_prompt: str, _destination: Path) -> Path:
        raise RuntimeError("provider unavailable with private detail")

    result = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "generated",
        ledger=AssetFingerprintLedger(tmp_path / "fingerprints.jsonl"),
        generate=generate,
    )

    assert result.manifest.intents == ()
    assert result.fallback_reason == "generation_failed"
    assert "private detail" not in result.fallback_reason


@pytest.mark.asyncio
async def test_obvious_pii_is_rejected_before_cloud_generation(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        media_resolver,
        "INDONESIAN_PII_PATTERNS",
        {"TEST_TOKEN": r"BLOCKED_PROMPT_TOKEN"},
    )
    packet = breaking_factory(story=story_factory(title="BLOCKED_PROMPT_TOKEN", asset_digests=[]))

    async def generate(_prompt: str, _destination: Path) -> Path:
        raise AssertionError("PII-bearing prompt must never reach the generator")

    result = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "generated",
        ledger=AssetFingerprintLedger(tmp_path / "fingerprints.jsonl"),
        generate=generate,
    )

    assert result.manifest.intents == ()
    assert result.fallback_reason == "prompt_rejected"


@pytest.mark.asyncio
async def test_animated_or_pii_asset_fails_closed(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(story=story_factory(asset_digests=[]))

    async def generate(_prompt: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_image_bytes(animated=True))
        return destination

    animated = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "animated",
        ledger=AssetFingerprintLedger(tmp_path / "animated.jsonl"),
        generate=generate,
    )
    assert animated.manifest.intents == ()
    assert animated.fallback_reason == "invalid_raster"

    async def safe_generate(_prompt: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_image_bytes(color="#2C2F38"))
        return destination

    async def describe(_data: bytes, _filename: str) -> tuple[str, dict[str, str]]:
        return "A synthetic sensitive marker is visible.", {"model": "local"}

    async def pii(_text: str, _filename: str) -> DLPResult:
        return DLPResult(has_pii=True, patterns=["PASSPORT_ID"])

    detected = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "pii",
        ledger=AssetFingerprintLedger(tmp_path / "pii.jsonl"),
        generate=safe_generate,
        describe=describe,
        scan_dlp=pii,
    )
    assert detected.manifest.intents == ()
    assert detected.fallback_reason == "dlp_rejected"


@pytest.mark.asyncio
async def test_oversized_or_indeterminate_asset_fails_closed(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(story=story_factory(asset_digests=[]))

    async def oversized(_prompt: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"x" * (12 * 1024 * 1024 + 1))
        return destination

    too_large = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "oversized",
        ledger=AssetFingerprintLedger(tmp_path / "oversized.jsonl"),
        generate=oversized,
    )
    assert too_large.manifest.intents == ()
    assert too_large.fallback_reason == "invalid_raster"

    async def generate(_prompt: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_image_bytes(color="#2C2F38"))
        return destination

    async def describe(_data: bytes, _filename: str) -> tuple[str, dict[str, str]]:
        return "A dark abstract editorial composition.", {"model": "local"}

    async def indeterminate(_text: str, _filename: str) -> DLPResult:
        return DLPResult(has_pii=True, indeterminate=True)

    uncertain = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "indeterminate",
        ledger=AssetFingerprintLedger(tmp_path / "indeterminate.jsonl"),
        generate=generate,
        describe=describe,
        scan_dlp=indeterminate,
    )
    assert uncertain.manifest.intents == ()
    assert uncertain.fallback_reason == "dlp_rejected"


@pytest.mark.asyncio
async def test_malformed_flowkit_output_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Process:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"not-json", b"private provider detail"

    async def create(*_args: Any, **_kwargs: Any) -> Process:
        return Process()

    monkeypatch.setattr("asyncio.create_subprocess_exec", create)
    generate = _flowkit_generator(tmp_path / "flowkit_cli.py")

    with pytest.raises(RuntimeError, match="invalid output"):
        await generate("bounded prompt", tmp_path / "hero.png")


@pytest.mark.asyncio
async def test_perceptual_duplicate_is_not_silently_reused(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(story=story_factory(asset_digests=[]))
    ledger = AssetFingerprintLedger(tmp_path / "fingerprints.jsonl")

    async def generate(_prompt: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_image_bytes(color="#000000"))
        return destination

    async def describe(_data: bytes, _filename: str) -> tuple[str, dict[str, str]]:
        return "Dark abstract editorial composition.", {"model": "local"}

    async def scan(_text: str, _filename: str) -> DLPResult:
        return DLPResult(has_pii=False)

    first = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "first",
        ledger=ledger,
        generate=generate,
        describe=describe,
        scan_dlp=scan,
    )
    second = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "second",
        ledger=ledger,
        generate=generate,
        describe=describe,
        scan_dlp=scan,
    )

    assert len(first.manifest.intents) == 1
    assert second.manifest.intents == ()
    assert second.fallback_reason == "duplicate_asset"
