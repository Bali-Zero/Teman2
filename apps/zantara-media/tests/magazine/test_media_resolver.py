from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from zantara_media.magazine import media_resolver
from zantara_media.magazine.media_resolver import (
    AssetFingerprintLedger,
    RasterFingerprint,
    _flowkit_generator,
    resolve_asset_manifest,
    select_asset_target,
)
from zantara_media.security.dlp import DLPResult


async def _safe_dlp(_text: str, _filename: str) -> DLPResult:
    return DLPResult(has_pii=False)


@pytest.fixture(autouse=True)
def stub_default_dlp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_resolver, "dlp_check", _safe_dlp)


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


def _image_bytes(
    *, color: str = "#C8102E", animated: bool = False, compress_level: int = 6
) -> bytes:
    stream = io.BytesIO()
    first = Image.new("RGB", (1200, 675), color)
    if animated:
        second = Image.new("RGB", (1200, 675), "#F4C430")
        first.save(stream, format="WEBP", save_all=True, append_images=[second], duration=100)
    else:
        first.save(stream, format="PNG", compress_level=compress_level)
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
async def test_generation_exception_removes_partial_output(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(story=story_factory(asset_digests=[]))
    output_dir = tmp_path / "generated"

    async def generate(_prompt: str, destination: Path) -> Path:
        destination.write_bytes(_image_bytes())
        raise RuntimeError("provider failed after writing")

    result = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=output_dir,
        ledger=AssetFingerprintLedger(tmp_path / "fingerprints.jsonl"),
        generate=generate,
    )

    assert result.fallback_reason == "generation_failed"
    assert list(output_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_untrusted_story_fields_never_control_output_path(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(story=story_factory(asset_digests=[]))
    packet["story"]["story_id"] = "../../outside-story"
    packet["story"]["slug"] = "../../../outside-slug"
    output_dir = tmp_path / "generated"
    observed: list[Path] = []

    async def generate(_prompt: str, destination: Path) -> Path:
        observed.append(destination)
        raise RuntimeError("stop after observing safe destination")

    result = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=output_dir,
        ledger=AssetFingerprintLedger(tmp_path / "fingerprints.jsonl"),
        generate=generate,
    )

    assert result.fallback_reason == "generation_failed"
    assert observed[0].parent == output_dir.resolve()
    assert "outside-story" not in observed[0].name
    assert "outside-slug" not in observed[0].name


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
async def test_semantic_pii_is_rejected_before_cloud_generation(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(
        story=story_factory(
            title="A deadline affecting Made Wijaya at his home in Ubud",
            asset_digests=[],
        )
    )
    scanned: list[str] = []

    async def scan(_text: str, filename: str) -> DLPResult:
        scanned.append(filename)
        return DLPResult(has_pii=True, patterns=["SEMANTIC_PERSON_NAME"])

    async def generate(_prompt: str, _destination: Path) -> Path:
        raise AssertionError("semantic PII must never reach the cloud generator")

    result = await resolve_asset_manifest(
        packet,
        breaking=True,
        output_dir=tmp_path / "generated",
        ledger=AssetFingerprintLedger(tmp_path / "fingerprints.jsonl"),
        generate=generate,
        scan_dlp=scan,
    )

    assert scanned == ["magazine-editorial-prompt.txt"]
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
    assert list((tmp_path / "animated").iterdir()) == []

    async def safe_generate(_prompt: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_image_bytes(color="#2C2F38"))
        return destination

    async def describe(_data: bytes, _filename: str) -> tuple[str, dict[str, str]]:
        return "A synthetic sensitive marker is visible.", {"model": "local"}

    async def pii(_text: str, filename: str) -> DLPResult:
        if filename == "magazine-editorial-prompt.txt":
            return DLPResult(has_pii=False)
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
    assert list((tmp_path / "pii").iterdir()) == []


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
    assert list((tmp_path / "oversized").iterdir()) == []

    async def generate(_prompt: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_image_bytes(color="#2C2F38"))
        return destination

    async def describe(_data: bytes, _filename: str) -> tuple[str, dict[str, str]]:
        return "A dark abstract editorial composition.", {"model": "local"}

    async def indeterminate(_text: str, filename: str) -> DLPResult:
        if filename == "magazine-editorial-prompt.txt":
            return DLPResult(has_pii=False)
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
    assert list((tmp_path / "indeterminate").iterdir()) == []


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
async def test_flowkit_generator_uses_bounded_timeout_and_secret_free_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_args: tuple[Any, ...] = ()
    observed_kwargs: dict[str, Any] = {}

    class Process:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b'{"ok":true}', b""

    async def create(*args: Any, **kwargs: Any) -> Process:
        nonlocal observed_args, observed_kwargs
        observed_args = args
        observed_kwargs = kwargs
        return Process()

    monkeypatch.setenv("FLOWKIT_BASE_URL", "http://127.0.0.1:8787")
    monkeypatch.setenv("MAGAZINE_HMAC_SECRET", "must-not-reach-flowkit")
    monkeypatch.setenv("MAGAZINE_SIWC_BEARER_TOKEN", "must-not-reach-flowkit")
    monkeypatch.setattr("asyncio.create_subprocess_exec", create)

    generate = _flowkit_generator(tmp_path / "flowkit_cli.py")
    destination = tmp_path / "hero.png"
    assert await generate("bounded prompt", destination) == destination

    assert "--timeout" in observed_args
    timeout_index = observed_args.index("--timeout")
    assert float(observed_args[timeout_index + 1]) > 30
    assert float(observed_args[timeout_index + 1]) < 240
    child_env = observed_kwargs["env"]
    assert child_env["FLOWKIT_BASE_URL"] == "http://127.0.0.1:8787"
    assert "MAGAZINE_HMAC_SECRET" not in child_env
    assert "MAGAZINE_SIWC_BEARER_TOKEN" not in child_env


@pytest.mark.asyncio
async def test_perceptual_duplicate_is_not_silently_reused(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    packet = breaking_factory(story=story_factory(asset_digests=[]))
    ledger = AssetFingerprintLedger(tmp_path / "fingerprints.jsonl")
    generation_count = 0

    async def generate(_prompt: str, destination: Path) -> Path:
        nonlocal generation_count
        generation_count += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(
            _image_bytes(color="#000000", compress_level=0 if generation_count == 1 else 9)
        )
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
    assert list((tmp_path / "second").iterdir()) == []


@pytest.mark.asyncio
async def test_perceptual_hashes_outside_threshold_are_both_reserved(
    tmp_path: Path,
) -> None:
    ledger = AssetFingerprintLedger(tmp_path / "fingerprints.jsonl")

    first = await ledger.reserve(
        RasterFingerprint(sha256="a" * 64, dhash="0000000000000000"), "hero-first"
    )
    second = await ledger.reserve(
        RasterFingerprint(sha256="b" * 64, dhash="ffffffffffffffff"), "hero-second"
    )

    assert first is not None
    assert second is not None


@pytest.mark.asyncio
async def test_dead_pending_reservation_is_reconciled_and_can_retry(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "fingerprints.jsonl"
    orphan = tmp_path / "generated" / "hero-orphan.png"
    orphan.parent.mkdir()
    orphan.write_bytes(_image_bytes(color="#123456"))
    fingerprint = RasterFingerprint(sha256="a" * 64, dhash="0000000000000000")
    ledger_path.write_text(
        json.dumps(
            {
                "asset_id": "hero-orphan",
                "dhash": fingerprint.dhash,
                "event": "reserved",
                "manifest_path": str(tmp_path / "missing-assets.json"),
                "owner_pid": 99999999,
                "reservation_id": "reservation-orphan",
                "sha256": fingerprint.sha256,
                "source_path": str(orphan),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ledger = AssetFingerprintLedger(ledger_path, asset_root=orphan.parent)

    reservation = await ledger.reserve(
        fingerprint,
        "hero-retry",
        manifest_path=tmp_path / "retry-assets.json",
        source_path=tmp_path / "generated" / "hero-retry.png",
    )

    assert reservation is not None
    assert not orphan.exists()


@pytest.mark.asyncio
async def test_dead_pending_reservation_with_published_manifest_stays_committed(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "fingerprints.jsonl"
    generated = tmp_path / "generated" / "hero-published.png"
    generated.parent.mkdir()
    generated.write_bytes(_image_bytes(color="#654321"))
    manifest_path = tmp_path / "assets.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "asset-intents.v1",
                "intents": [
                    {
                        "asset_id": "hero-published",
                        "source_path": str(generated),
                        "story_ids": ["story-1"],
                        "captured_at": "2026-07-22T00:00:00Z",
                        "alt_text": "Generated editorial hero",
                        "source": "Bali Zero editorial generator",
                        "source_url": None,
                        "rights_basis": "generated",
                        "rights_status": "approved",
                        "usage_status": "approved",
                        "dlp_status": "passed",
                        "sanitization_status": "passed",
                        "perceptual_dedup_status": "unique",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    fingerprint = RasterFingerprint(sha256="c" * 64, dhash="1111111111111111")
    ledger_path.write_text(
        json.dumps(
            {
                "asset_id": "hero-published",
                "dhash": fingerprint.dhash,
                "event": "reserved",
                "manifest_path": str(manifest_path),
                "owner_pid": 99999999,
                "reservation_id": "reservation-published",
                "sha256": fingerprint.sha256,
                "source_path": str(generated),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ledger = AssetFingerprintLedger(ledger_path, asset_root=generated.parent)

    duplicate = await ledger.reserve(fingerprint, "hero-duplicate")

    assert duplicate is None
    assert generated.exists()
    records = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    assert records[-1]["event"] == "committed"
