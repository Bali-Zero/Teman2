"""Pro-local editorial asset selection and resolution."""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import io
import json
import logging
import os
import re
import sys
import warnings
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from zantara_media.indexer.handlers.image_handler import extract_image
from zantara_media.magazine.assets import AssetIntentManifestV1, AssetIntentV1
from zantara_media.security.dlp import DLPResult, INDONESIAN_PII_PATTERNS, dlp_check

logger = logging.getLogger(__name__)

GenerateAsset = Callable[[str, Path], Awaitable[Path]]
DescribeAsset = Callable[[bytes, str], Awaitable[tuple[str, dict[str, Any]]]]
ScanDlp = Callable[[str, str], Awaitable[DLPResult]]

_MAX_BYTES = 12 * 1024 * 1024
_MAX_DIMENSION = 8192
_MAX_PIXELS = 40_000_000
_DUPLICATE_DISTANCE = 4
_GENERATION_TIMEOUT_S = 240.0


@dataclass(frozen=True)
class AssetTarget:
    story_id: str
    slug: str
    captured_at: str
    alt_text: str
    prompt: str


@dataclass(frozen=True)
class AssetResolutionResult:
    manifest: AssetIntentManifestV1
    fallback_reason: str | None


@dataclass(frozen=True)
class RasterFingerprint:
    sha256: str
    dhash: str


class AssetFingerprintLedger:
    """Append-only exact and perceptual fingerprint registry."""

    def __init__(self, path: Path) -> None:
        self.path = path

    async def reserve(self, fingerprint: RasterFingerprint, asset_id: str) -> bool:
        """Atomically reserve a unique fingerprint across concurrent publishers."""

        return await asyncio.to_thread(self._reserve_sync, fingerprint, asset_id)

    def _reserve_sync(self, fingerprint: RasterFingerprint, asset_id: str) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                stream.seek(0)
                for line in stream:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        known_sha = str(record["sha256"])
                        known_dhash = str(record["dhash"])
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                        raise ValueError("fingerprint ledger is invalid") from exc
                    if (
                        known_sha == fingerprint.sha256
                        or _hamming_distance(known_dhash, fingerprint.dhash) <= _DUPLICATE_DISTANCE
                    ):
                        return False
                record = {
                    "asset_id": asset_id,
                    "dhash": fingerprint.dhash,
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "sha256": fingerprint.sha256,
                }
                stream.seek(0, os.SEEK_END)
                stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                return True
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


async def resolve_asset_manifest(
    packet: dict[str, Any],
    *,
    breaking: bool,
    output_dir: Path,
    ledger: AssetFingerprintLedger,
    generate: GenerateAsset | None = None,
    describe: DescribeAsset | None = None,
    scan_dlp: ScanDlp | None = None,
    flowkit_cli: Path | None = None,
) -> AssetResolutionResult:
    """Create one fail-closed hero intent or preserve the typographic fallback."""

    target = select_asset_target(packet, breaking=breaking)
    if target is None:
        return _fallback(None)
    if any(re.search(pattern, target.prompt) for pattern in INDONESIAN_PII_PATTERNS.values()):
        return _fallback("prompt_rejected")

    output_dir = output_dir.resolve()
    await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)
    destination = output_dir / f"{target.slug[:80]}-{target.story_id[:24]}.png"
    generator = generate or _flowkit_generator(flowkit_cli)
    try:
        source_path = (await generator(target.prompt, destination)).resolve()
    except Exception:
        logger.warning("Magazine asset generation failed", extra={"reason": "generation_failed"})
        return _fallback("generation_failed")
    if source_path.parent != output_dir or not source_path.is_file():
        await _discard(source_path, output_dir)
        return _fallback("generation_failed")

    try:
        file_data = await asyncio.to_thread(source_path.read_bytes)
        fingerprint = await asyncio.to_thread(_inspect_raster, file_data)
    except (
        EOFError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        Image.UnidentifiedImageError,
    ):
        await _discard(source_path, output_dir)
        return _fallback("invalid_raster")

    describer = describe or extract_image
    try:
        description, metadata = await describer(file_data, source_path.name)
    except Exception:
        await _discard(source_path, output_dir)
        return _fallback("vision_unavailable")
    if not description.strip() or metadata.get("error"):
        await _discard(source_path, output_dir)
        return _fallback("vision_unavailable")

    scanner = scan_dlp or dlp_check
    try:
        dlp_result = await scanner(description, source_path.name)
    except Exception:
        await _discard(source_path, output_dir)
        return _fallback("dlp_rejected")
    if dlp_result.has_pii or dlp_result.indeterminate:
        await _discard(source_path, output_dir)
        return _fallback("dlp_rejected")

    packet_id = str(packet.get("packet_id", ""))
    asset_id = (
        "hero-"
        + hashlib.sha256(
            f"{packet_id}:{target.story_id}:{fingerprint.sha256}".encode()
        ).hexdigest()[:24]
    )
    try:
        unique = await ledger.reserve(fingerprint, asset_id)
    except (OSError, ValueError):
        await _discard(source_path, output_dir)
        return _fallback("duplicate_check_failed")
    if not unique:
        await _discard(source_path, output_dir)
        return _fallback("duplicate_asset")

    intent = AssetIntentV1(
        asset_id=asset_id,
        source_path=source_path,
        story_ids=(target.story_id,),
        captured_at=target.captured_at,
        alt_text=target.alt_text,
        source="Bali Zero editorial generator",
        source_url=None,
        rights_basis="generated",
        rights_status="approved",
        usage_status="approved",
        dlp_status="passed",
        sanitization_status="passed",
        perceptual_dedup_status="unique",
    )
    return AssetResolutionResult(
        manifest=AssetIntentManifestV1(schema_version="asset-intents.v1", intents=(intent,)),
        fallback_reason=None,
    )


def _fallback(reason: str | None) -> AssetResolutionResult:
    return AssetResolutionResult(
        manifest=AssetIntentManifestV1(schema_version="asset-intents.v1", intents=()),
        fallback_reason=reason,
    )


def _flowkit_generator(flowkit_cli: Path | None) -> GenerateAsset:
    cli = flowkit_cli or Path(
        os.getenv(
            "MAGAZINE_FLOWKIT_CLI",
            str(Path(__file__).resolve().parents[4] / "scripts" / "flowkit_cli.py"),
        )
    )

    async def generate(prompt: str, destination: Path) -> Path:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(cli),
            "generate-image",
            "--prompt",
            prompt,
            "--orientation",
            "LANDSCAPE",
            "--project",
            "bali-zero-magazine",
            "--material",
            "editorial hero",
            "--language",
            "en",
            "--dest",
            str(destination),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(
                process.communicate(), timeout=_GENERATION_TIMEOUT_S
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("asset generation timed out") from None
        if process.returncode != 0:
            raise RuntimeError("asset generation failed")
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("asset generation returned invalid output") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError("asset generation returned a failure")
        return destination

    return generate


def _inspect_raster(file_data: bytes) -> RasterFingerprint:
    if not file_data or len(file_data) > _MAX_BYTES:
        raise ValueError("raster size is outside the allowed range")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(file_data)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("unsupported raster format")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("animated raster is not allowed")
            width, height = image.size
            if (
                width < 1
                or height < 1
                or width > _MAX_DIMENSION
                or height > _MAX_DIMENSION
                or width * height > _MAX_PIXELS
            ):
                raise ValueError("raster dimensions are outside the allowed range")
            image.verify()
        with Image.open(io.BytesIO(file_data)) as image:
            grayscale = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            flattened = getattr(grayscale, "get_flattened_data", None)
            pixels = list(flattened() if flattened is not None else grayscale.getdata())
    bits = [
        pixels[row * 9 + column] > pixels[row * 9 + column + 1]
        for row in range(8)
        for column in range(8)
    ]
    dhash_value = sum(int(bit) << index for index, bit in enumerate(bits))
    return RasterFingerprint(
        sha256=hashlib.sha256(file_data).hexdigest(),
        dhash=f"{dhash_value:016x}",
    )


def _hamming_distance(left: str, right: str) -> int:
    if len(left) != 16 or len(right) != 16:
        raise ValueError("invalid perceptual hash")
    return (int(left, 16) ^ int(right, 16)).bit_count()


async def _discard(path: Path, allowed_parent: Path) -> None:
    if path.parent != allowed_parent or not path.exists():
        return
    try:
        await asyncio.to_thread(path.unlink)
    except OSError:
        logger.warning("Failed to remove rejected magazine asset")


def select_asset_target(
    packet: dict[str, Any],
    *,
    breaking: bool,
) -> AssetTarget | None:
    """Select the single Phase-1 hero target from a publication packet."""

    story: dict[str, Any] | None = None
    if breaking:
        candidate = packet.get("story")
        if isinstance(candidate, dict):
            story = candidate
    else:
        if packet.get("edition_kind") == "quiet":
            return None
        placements = packet.get("placements")
        stories = packet.get("stories")
        if not isinstance(placements, list) or not isinstance(stories, list):
            return None
        lead_ids = {
            str(item.get("story_id"))
            for item in placements
            if isinstance(item, dict) and item.get("lead") is True
        }
        matches = [
            item
            for item in stories
            if isinstance(item, dict) and str(item.get("story_id")) in lead_ids
        ]
        if len(matches) == 1:
            story = matches[0]
    if story is None or story.get("asset_digests"):
        return None

    story_id = str(story.get("story_id", "")).strip()
    slug = str(story.get("slug", "")).strip()
    captured_at = str(packet.get("verified_at", "")).strip()
    title = str(story.get("title", "")).strip()[:240]
    deck = str(story.get("deck", "")).strip()[:360]
    domain = str(story.get("domain", "general")).strip()[:40]
    why = str(story.get("why_it_matters", "")).strip()[:360]
    if not story_id or not slug or not captured_at or not title:
        return None
    prompt = (
        "Create one original landscape editorial photograph for the private Bali Zero "
        "Magazine. Cinematic, restrained, credible Indonesian context, near-black and "
        "warm natural tones, strong negative space for an editorial crop. No text, logos, "
        "watermarks, passports, identity documents, personal data, or recognizable public "
        f"figures. Editorial domain: {domain}. Headline concept: {title}. Context: {deck}. "
        f"Operational meaning: {why}."
    )[:1400]
    return AssetTarget(
        story_id=story_id,
        slug=slug,
        captured_at=captured_at,
        alt_text=f"Editorial illustration for {title}"[:500],
        prompt=prompt,
    )
