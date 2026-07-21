"""Pro-local editorial asset selection and resolution."""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import hmac
import io
import json
import logging
import os
import re
import sys
import uuid
import warnings
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from PIL import Image

from zantara_media.indexer.handlers.image_handler import extract_image
from zantara_media.magazine.assets import (
    AssetIntentManifestV1,
    AssetIntentV1,
    validate_asset_intent_targets,
)
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
_FLOWKIT_REQUEST_TIMEOUT_S = 210.0
_FLOWKIT_ENV_ALLOWLIST = frozenset(
    {
        "CURL_CA_BUNDLE",
        "FLOWKIT_BASE_URL",
        "FLOWKIT_PAYGATE_TIER",
        "FLOWKIT_TIMEOUT_S",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONPATH",
        "REQUESTS_CA_BUNDLE",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TMPDIR",
    }
)


@dataclass(frozen=True)
class AssetTarget:
    story_id: str
    story_version: int
    target_role: Literal["morning-lead", "breaking-story"]
    slug: str
    captured_at: str
    alt_text: str
    prompt: str


@dataclass(frozen=True)
class AssetResolutionResult:
    manifest: AssetIntentManifestV1
    fallback_reason: str | None
    reservation_id: str | None = None


@dataclass(frozen=True)
class RasterFingerprint:
    sha256: str
    dhash: str


class AssetFingerprintLedger:
    """Crash-recoverable exact and perceptual fingerprint registry."""

    def __init__(self, path: Path, *, asset_root: Path | None = None) -> None:
        self.path = path
        self.asset_root = asset_root.resolve() if asset_root is not None else None

    async def reconcile(self) -> None:
        """Recover reservations whose owner exited before final commit."""

        await asyncio.to_thread(self._reconcile_sync)

    async def reserve(
        self,
        fingerprint: RasterFingerprint,
        asset_id: str,
        *,
        manifest_path: Path | None = None,
        source_path: Path | None = None,
    ) -> str | None:
        """Atomically reserve a unique fingerprint across concurrent publishers."""

        return await asyncio.to_thread(
            self._reserve_sync,
            fingerprint,
            asset_id,
            manifest_path,
            source_path,
        )

    async def commit(self, reservation_id: str) -> None:
        """Mark a reservation durable after its manifest has been replaced."""

        await asyncio.to_thread(self._transition_sync, reservation_id, "committed")

    async def release(self, reservation_id: str) -> None:
        """Release a reservation after a handled manifest-write failure."""

        await asyncio.to_thread(self._transition_sync, reservation_id, "released")

    def _reserve_sync(
        self,
        fingerprint: RasterFingerprint,
        asset_id: str,
        manifest_path: Path | None,
        source_path: Path | None,
    ) -> str | None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                active = self._active_records(stream, reconcile=True)
                for record in active:
                    known_sha = str(record["sha256"])
                    known_dhash = str(record["dhash"])
                    if (
                        known_sha == fingerprint.sha256
                        or _hamming_distance(known_dhash, fingerprint.dhash) <= _DUPLICATE_DISTANCE
                    ):
                        return None
                reservation_id = uuid.uuid4().hex
                record = {
                    "asset_id": asset_id,
                    "dhash": fingerprint.dhash,
                    "event": "reserved" if manifest_path is not None else "committed",
                    "manifest_path": str(manifest_path.resolve()) if manifest_path else None,
                    "owner_pid": os.getpid(),
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "reservation_id": reservation_id,
                    "sha256": fingerprint.sha256,
                    "source_path": str(source_path.resolve()) if source_path else None,
                }
                self._append(stream, record)
                return reservation_id
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _reconcile_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                self._active_records(stream, reconcile=True)
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _transition_sync(self, reservation_id: str, event: str) -> None:
        if event not in {"committed", "released"}:
            raise ValueError("invalid fingerprint ledger transition")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                records = self._records(stream)
                record = records.get(reservation_id)
                if record is None or record["event"] == "released":
                    raise ValueError("fingerprint reservation is not active")
                if record["event"] == event:
                    return
                transitioned = dict(record)
                transitioned["event"] = event
                transitioned["recorded_at"] = datetime.now(UTC).isoformat()
                self._append(stream, transitioned)
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _active_records(
        self,
        stream: Any,
        *,
        reconcile: bool,
    ) -> list[dict[str, Any]]:
        records = self._records(stream)
        for reservation_id, record in tuple(records.items()):
            if record["event"] != "reserved" or not reconcile:
                continue
            owner_pid = int(record["owner_pid"])
            if _process_is_alive(owner_pid):
                continue
            manifest_path = Path(str(record["manifest_path"]))
            if _manifest_contains_asset(manifest_path, str(record["asset_id"])):
                event = "committed"
            else:
                event = "released"
                self._remove_orphan(record)
            transitioned = dict(record)
            transitioned["event"] = event
            transitioned["recorded_at"] = datetime.now(UTC).isoformat()
            self._append(stream, transitioned)
            records[reservation_id] = transitioned
        return [
            record
            for record in records.values()
            if record["event"] in {"reserved", "committed"}
        ]

    def _records(self, stream: Any) -> dict[str, dict[str, Any]]:
        stream.seek(0)
        records: dict[str, dict[str, Any]] = {}
        legacy_index = 0
        while True:
            record_start = stream.tell()
            line = stream.readline()
            if not line:
                break
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                if not line.endswith("\n"):
                    stream.seek(record_start)
                    stream.truncate()
                    stream.flush()
                    os.fsync(stream.fileno())
                    break
                raise ValueError("fingerprint ledger is invalid") from exc
            try:
                if not isinstance(raw, dict):
                    raise TypeError
                record = dict(raw)
                str(record["asset_id"])
                str(record["sha256"])
                str(record["dhash"])
                event = str(record.get("event", "committed"))
                if event not in {"reserved", "committed", "released"}:
                    raise ValueError
                if event == "reserved":
                    int(record["owner_pid"])
                    if not record.get("manifest_path"):
                        raise ValueError
                reservation_id = str(
                    record.get("reservation_id", f"legacy-{legacy_index}")
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("fingerprint ledger is invalid") from exc
            record["event"] = event
            record["reservation_id"] = reservation_id
            records[reservation_id] = record
            legacy_index += 1
        return records

    @staticmethod
    def _append(stream: Any, record: dict[str, Any]) -> None:
        stream.seek(0, os.SEEK_END)
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())

    def _remove_orphan(self, record: dict[str, Any]) -> None:
        raw_path = record.get("source_path")
        if self.asset_root is None or not raw_path:
            return
        source_path = Path(str(raw_path)).resolve()
        if source_path.parent != self.asset_root or not source_path.name.startswith("hero-"):
            return
        source_path.unlink(missing_ok=True)


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
    manifest_path: Path | None = None,
) -> AssetResolutionResult:
    """Create one fail-closed hero intent or preserve the typographic fallback."""

    target = select_asset_target(packet, breaking=breaking)
    if target is None:
        return _fallback(None)
    if any(re.search(pattern, target.prompt) for pattern in INDONESIAN_PII_PATTERNS.values()):
        return _fallback("prompt_rejected")
    scanner = scan_dlp or dlp_check
    try:
        prompt_dlp = await scanner(target.prompt, "magazine-editorial-prompt.txt")
    except Exception:
        return _fallback("prompt_rejected")
    if prompt_dlp.has_pii or prompt_dlp.indeterminate:
        return _fallback("prompt_rejected")

    output_dir = output_dir.resolve()
    await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)
    packet_id = str(packet.get("packet_id", ""))
    target_key = hashlib.sha256(f"{packet_id}:{target.story_id}".encode()).hexdigest()[:24]
    attempt_id = uuid.uuid4().hex
    destination = (output_dir / f".pending-hero-{target_key}-{attempt_id}.png").resolve()
    if destination.parent != output_dir:
        return _fallback("generation_failed")
    generator = generate or _flowkit_generator(flowkit_cli)
    try:
        source_path = (await generator(target.prompt, destination)).resolve()
    except Exception:
        await _discard(destination, output_dir)
        logger.warning("Magazine asset generation failed", extra={"reason": "generation_failed"})
        return _fallback("generation_failed")
    if source_path != destination or not source_path.is_file():
        await _discard(source_path, output_dir)
        await _discard(destination, output_dir)
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

    try:
        dlp_result = await scanner(description, source_path.name)
    except Exception:
        await _discard(source_path, output_dir)
        return _fallback("dlp_rejected")
    if dlp_result.has_pii or dlp_result.indeterminate:
        await _discard(source_path, output_dir)
        return _fallback("dlp_rejected")

    prompt_sha256 = hashlib.sha256(target.prompt.encode()).hexdigest()
    asset_id = _generated_asset_id(
        packet_id=packet_id,
        story_id=target.story_id,
        story_version=target.story_version,
        target_role=target.target_role,
        prompt_sha256=prompt_sha256,
        content_sha256=fingerprint.sha256,
    )
    approved_path = (output_dir / f"hero-{fingerprint.sha256}-{attempt_id}.png").resolve()
    if approved_path.parent != output_dir:
        await _discard(source_path, output_dir)
        return _fallback("generation_failed")
    try:
        reservation_id = await ledger.reserve(
            fingerprint,
            asset_id,
            manifest_path=manifest_path,
            source_path=approved_path,
        )
    except (OSError, ValueError):
        await _discard(source_path, output_dir)
        return _fallback("duplicate_check_failed")
    if reservation_id is None:
        await _discard(source_path, output_dir)
        return _fallback("duplicate_asset")
    try:
        await asyncio.to_thread(source_path.replace, approved_path)
    except OSError:
        try:
            await ledger.release(reservation_id)
        except (OSError, ValueError):
            logger.exception("Magazine fingerprint reservation release failed")
        await _discard(source_path, output_dir)
        await _discard(approved_path, output_dir)
        return _fallback("generation_failed")

    intent = AssetIntentV1(
        asset_id=asset_id,
        source_path=approved_path,
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
        approved_for_packet_id=packet_id,
        source_sha256=fingerprint.sha256,
        generated_for_packet_id=packet_id,
        generated_for_story_version=target.story_version,
        generated_for_target_role=target.target_role,
        prompt_sha256=prompt_sha256,
    )
    return AssetResolutionResult(
        manifest=AssetIntentManifestV1(schema_version="asset-intents.v1", intents=(intent,)),
        fallback_reason=None,
        reservation_id=reservation_id,
    )


async def generated_manifest_is_intact(
    manifest: AssetIntentManifestV1,
    *,
    output_dir: Path,
) -> bool:
    """Verify that approved generated intents still bind to their original bytes."""

    output_dir = output_dir.resolve()
    for intent in manifest.intents:
        source_path = intent.source_path.resolve()
        if source_path.parent != output_dir or not source_path.is_file():
            return False
        try:
            file_data = await asyncio.to_thread(source_path.read_bytes)
            await asyncio.to_thread(_inspect_raster, file_data)
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
            return False
        try:
            validate_generated_asset_bytes(
                intent,
                packet_id=str(intent.generated_for_packet_id or ""),
                source_bytes=file_data,
            )
        except ValueError:
            await _discard(source_path, output_dir)
            return False
    return True


def generated_manifest_matches_packet(
    manifest: AssetIntentManifestV1,
    packet: dict[str, Any],
    *,
    breaking: bool,
) -> bool:
    """Bind an automatic manifest to one exact packet and editorial target."""

    target = select_asset_target(packet, breaking=breaking)
    if target is None or len(manifest.intents) != 1:
        return False
    intent = manifest.intents[0]
    return (
        intent.story_ids == (target.story_id,)
        and intent.captured_at == target.captured_at
        and intent.generated_for_packet_id == str(packet.get("packet_id", ""))
        and intent.generated_for_story_version == target.story_version
        and intent.generated_for_target_role == target.target_role
        and intent.prompt_sha256 == hashlib.sha256(target.prompt.encode()).hexdigest()
    )


def validate_manifest_publication_binding(
    manifest: AssetIntentManifestV1,
    packet: dict[str, Any],
    *,
    breaking: bool,
) -> None:
    """Require every approved intent to bind to the exact publication context."""

    validate_asset_intent_targets(packet, manifest, breaking=breaking)
    packet_id = str(packet.get("packet_id", ""))
    for item in manifest.intents:
        generated_rights = item.rights_basis == "generated"
        generated_source = item.source == "Bali Zero editorial generator"
        if generated_rights != generated_source:
            raise ValueError("asset has inconsistent generated provenance")
        if item.approved_for_packet_id != packet_id:
            raise ValueError("asset is not approved for packet")
        if generated_rights:
            single = AssetIntentManifestV1(
                schema_version="asset-intents.v1", intents=(item,)
            )
            if not generated_manifest_matches_packet(single, packet, breaking=breaking):
                raise ValueError(
                    "generated asset does not match the current generation context"
                )
        elif item.source_sha256 is None:
            raise ValueError("explicit asset lacks an approved source digest")


def validate_generated_asset_bytes(
    intent: AssetIntentV1,
    *,
    packet_id: str,
    source_bytes: bytes,
) -> None:
    """Reject source bytes that no longer match their immutable approval binding."""

    automatic = (
        intent.rights_basis == "generated" and intent.source == "Bali Zero editorial generator"
    )
    if not automatic:
        if intent.source_sha256 is None:
            raise ValueError("explicit asset lacks an approved source digest")
        actual_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if not hmac.compare_digest(intent.source_sha256, actual_sha256):
            raise ValueError("explicit asset bytes do not match the approved source digest")
        return
    if (
        not intent.generated_for_packet_id
        or intent.generated_for_story_version is None
        or intent.generated_for_target_role is None
        or intent.prompt_sha256 is None
        or len(intent.story_ids) != 1
        or intent.generated_for_packet_id != packet_id
    ):
        raise ValueError("generated asset bytes lack a valid publication binding")
    expected = _generated_asset_id(
        packet_id=packet_id,
        story_id=intent.story_ids[0],
        story_version=intent.generated_for_story_version,
        target_role=intent.generated_for_target_role,
        prompt_sha256=intent.prompt_sha256,
        content_sha256=hashlib.sha256(source_bytes).hexdigest(),
    )
    if intent.asset_id != expected:
        raise ValueError("generated asset bytes do not match the manifest binding")


def _generated_asset_id(
    *,
    packet_id: str,
    story_id: str,
    story_version: int,
    target_role: str,
    prompt_sha256: str,
    content_sha256: str,
) -> str:
    binding = ":".join(
        (
            packet_id,
            story_id,
            str(story_version),
            target_role,
            prompt_sha256,
            content_sha256,
        )
    )
    return f"hero-{hashlib.sha256(binding.encode()).hexdigest()}"


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
        child_env = {
            key: value for key, value in os.environ.items() if key in _FLOWKIT_ENV_ALLOWLIST
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(cli),
            "generate-image",
            "--prompt",
            prompt,
            "--timeout",
            str(_FLOWKIT_REQUEST_TIMEOUT_S),
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
            env=child_env,
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


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _manifest_contains_asset(path: Path, asset_id: str) -> bool:
    if not path.is_file():
        return False
    try:
        manifest = AssetIntentManifestV1.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError("fingerprint reservation manifest is invalid") from exc
    return any(intent.asset_id == asset_id for intent in manifest.intents)


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

    story_id = str(story.get("story_id") or "").strip()
    slug = str(story.get("slug") or "").strip()
    captured_at = str(packet.get("verified_at") or "").strip()
    title = str(story.get("title") or "").strip()[:240]
    deck = str(story.get("deck") or "").strip()[:360]
    domain = str(story.get("domain") or "general").strip()[:40]
    why = str(story.get("why_it_matters") or "").strip()[:360]
    story_version = story.get("version")
    if (
        not story_id
        or not slug
        or not captured_at
        or not title
        or not isinstance(story_version, int)
        or story_version < 0
    ):
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
        story_version=story_version,
        target_role="breaking-story" if breaking else "morning-lead",
        slug=slug,
        captured_at=captured_at,
        alt_text=f"Editorial illustration for {title}"[:500],
        prompt=prompt,
    )
