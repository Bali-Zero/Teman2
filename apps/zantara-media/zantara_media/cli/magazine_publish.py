"""Deterministic morning/Breaking publisher; network mutation is explicit opt-in."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Sequence

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict

from zantara_media.magazine.assets import AssetIntentManifestV1, bind_canonical_assets
from zantara_media.magazine.audit_anchor import (
    AuditAnchorService,
    AuditEventRecord,
    AuditReleaseInterlock,
    DurableAnchorLedger,
)
from zantara_media.magazine.composer import ComposerConfig, compose_breaking, compose_edition
from zantara_media.magazine.loaders import load_named_projection
from zantara_media.magazine.ranking import score_candidate
from zantara_media.magazine.reconciler import DurableOutcomeJournal
from zantara_media.magazine.transport import MagazineTransport, TransportConfig

logger = logging.getLogger(__name__)


class ProjectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    system_id: str
    projection_path: Path


class MorningInputV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["magazine-morning-input.v2"]
    projection_inputs: tuple[ProjectionInput, ...]
    expected_current_revision: int
    expected_breaking_revision: int


class BreakingInputV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["magazine-breaking-input.v2"]
    projection_input: ProjectionInput
    candidate_public_id: str
    expected_breaking_revision: int


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname.lower(),
                "logger": record.name,
                "message": record.getMessage(),
            },
            separators=(",", ":"),
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magazine-publish")
    subparsers = parser.add_subparsers(dest="command", required=True)
    morning = subparsers.add_parser("morning")
    morning.add_argument("--input", type=Path, required=True)
    morning.add_argument("--output", type=Path, required=True)
    morning.add_argument("--cutoff", required=True)
    morning.add_argument("--required-system-id", action="append", default=[])
    morning.add_argument("--editor-version", default="editor.v1")
    morning.add_argument("--ruleset-version", default="rules.v1")
    _mode_flags(morning)

    breaking = subparsers.add_parser("breaking")
    breaking.add_argument("--input", type=Path, required=True)
    breaking.add_argument("--output", type=Path, required=True)
    breaking.add_argument("--ruleset-version", default="rules.v1")
    _mode_flags(breaking)
    return parser


def _mode_flags(parser: argparse.ArgumentParser) -> None:
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--publish", action="store_true")
    parser.add_argument("--asset-manifest", type=Path)
    parser.add_argument("--audit-events", type=Path)


async def _read_json(path: Path) -> dict[str, Any]:
    raw = await asyncio.to_thread(path.read_text, encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("publisher input must be a JSON object")
    return parsed


async def _write_packet(path: Path, packet: dict[str, Any]) -> None:
    body = (
        json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()

    def write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    await asyncio.to_thread(write)


def _cutoff(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("cutoff must be a UTC timestamp ending in Z")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("cutoff must be timezone-aware")
    return parsed


def _transport_config() -> TransportConfig:
    names = {
        "base_url": "MAGAZINE_BASE_URL",
        "siwc_bearer_token": "MAGAZINE_SIWC_BEARER_TOKEN",
        "hmac_key_id": "MAGAZINE_HMAC_KEY_ID",
        "hmac_secret": "MAGAZINE_HMAC_SECRET",
        "audience": "MAGAZINE_HMAC_AUDIENCE",
    }
    values: dict[str, str] = {}
    missing: list[str] = []
    for field, env_name in names.items():
        value = os.environ.get(env_name)
        if value is None:
            missing.append(env_name)
        else:
            values[field] = value
    if missing:
        raise RuntimeError(f"missing publisher environment: {', '.join(sorted(missing))}")
    return TransportConfig(**values)


async def _publish(
    packet: dict[str, Any],
    *,
    breaking: bool,
    asset_manifest_path: Path,
    audit_events_path: Path,
) -> dict[str, Any]:
    journal_path = Path(
        os.environ.get(
            "MAGAZINE_OUTCOME_JOURNAL",
            str(Path.home() / ".local/state/bali-zero-magazine/outcomes.jsonl"),
        )
    )
    state_dir = journal_path.parent
    interlock = AuditReleaseInterlock(state_dir / "audit-release.jsonl")
    transport = MagazineTransport(
        _transport_config(),
        journal=DurableOutcomeJournal(journal_path),
        release_gate=interlock,
    )
    try:
        key_raw = os.environ.get("MAGAZINE_AUDIT_PRIVATE_KEY_B64")
        if key_raw is None:
            raise RuntimeError("missing publisher environment: MAGAZINE_AUDIT_PRIVATE_KEY_B64")
        try:
            private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key_raw))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("invalid audit private key") from exc
        events_raw = json.loads(await asyncio.to_thread(audit_events_path.read_bytes))
        if not isinstance(events_raw, list):
            raise ValueError("audit event input must be an array")
        events = tuple(AuditEventRecord.model_validate(item) for item in events_raw)
        service = AuditAnchorService(
            key_id=os.environ.get("MAGAZINE_AUDIT_KEY_ID", "pro-anchor-1"),
            private_key=private_key,
            ledger=DurableAnchorLedger(state_dir / "audit-anchors.jsonl"),
            interlock=interlock,
        )
        observed_at = str(packet["verified_at"])
        if not observed_at.endswith(".000Z"):
            observed_at = observed_at.replace("Z", ".000Z")
        await service.anchor_and_submit(
            events,
            observed_at=observed_at,
            submit=transport.submit_audit_anchor,
        )

        asset_manifest = AssetIntentManifestV1.model_validate_json(
            await asyncio.to_thread(asset_manifest_path.read_bytes)
        )
        canonical: dict[str, str] = {}
        for intent in asset_manifest.intents:
            source_bytes = await asyncio.to_thread(intent.source_path.read_bytes)
            result = await transport.upload_asset_bytes(
                source_bytes, intent.provenance(str(packet["packet_id"]))
            )
            canonical[intent.asset_id] = result.canonical_sha256
        bound = bind_canonical_assets(
            packet, asset_manifest, canonical, breaking=breaking
        )
        if breaking:
            await transport.publish_breaking(bound)
        else:
            await transport.post_json("/api/machine/publications/editions", bound)
        return bound
    finally:
        await transport.aclose()


async def _morning(args: argparse.Namespace, manifest: dict[str, Any]) -> dict[str, Any]:
    parsed = MorningInputV2.model_validate(manifest)
    loaded = [
        await load_named_projection(item.system_id, item.projection_path)
        for item in parsed.projection_inputs
    ]
    candidates = [candidate for item in loaded for candidate in item.candidates]
    collector_runs = [item.collector_run for item in loaded]
    packet = compose_edition(
        candidates=tuple(candidates),
        collector_runs=tuple(collector_runs),
        cutoff=_cutoff(args.cutoff),
        expected_current_revision=parsed.expected_current_revision,
        expected_breaking_revision=parsed.expected_breaking_revision,
        config=ComposerConfig(
            required_system_ids=tuple(sorted(set(args.required_system_id))),
            editor_version=args.editor_version,
            ruleset_version=args.ruleset_version,
        ),
    )
    result = packet.model_dump(mode="json")
    logger.info(
        "morning packet composed packet_id=%s stories=%d coverage=%s",
        packet.packet_id,
        len(packet.stories),
        packet.coverage_state,
    )
    return result


async def _breaking(args: argparse.Namespace, manifest: dict[str, Any]) -> dict[str, Any]:
    parsed = BreakingInputV2.model_validate(manifest)
    projection = await load_named_projection(
        parsed.projection_input.system_id, parsed.projection_input.projection_path
    )
    candidates = [
        item for item in projection.candidates if item.public_id == parsed.candidate_public_id
    ]
    if len(candidates) != 1:
        raise ValueError("breaking input did not select exactly one public candidate")
    packet = compose_breaking(
        score_candidate(candidates[0]),
        expected_breaking_revision=parsed.expected_breaking_revision,
        ruleset_version=args.ruleset_version,
    )
    logger.info(
        "breaking packet composed packet_id=%s story_id=%s",
        packet.packet_id,
        packet.story.story_id,
    )
    return packet.model_dump(mode="json")


async def async_main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest = await _read_json(args.input)
    packet = (
        await _morning(args, manifest)
        if args.command == "morning"
        else await _breaking(args, manifest)
    )
    if args.publish:
        if args.asset_manifest is None or args.audit_events is None:
            raise ValueError("publish requires --asset-manifest and --audit-events")
        packet = await _publish(
            packet,
            breaking=args.command == "breaking",
            asset_manifest_path=args.asset_manifest,
            audit_events_path=args.audit_events,
        )
        logger.info("packet published packet_id=%s target=%s", packet["packet_id"], args.command)
    else:
        logger.info("dry run complete packet_id=%s target=%s", packet["packet_id"], args.command)
    await _write_packet(args.output, packet)
    return 0


def main() -> None:
    if not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
