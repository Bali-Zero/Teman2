"""Deterministic morning/Breaking publisher; network mutation is explicit opt-in."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from zantara_media.magazine.adapters import default_adapter_registry
from zantara_media.magazine.composer import ComposerConfig, compose_breaking, compose_edition
from zantara_media.magazine.ranking import score_candidate
from zantara_media.magazine.reconciler import DurableOutcomeJournal
from zantara_media.magazine.transport import MagazineTransport, TransportConfig

logger = logging.getLogger(__name__)


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


async def _publish(packet: dict[str, Any], *, breaking: bool) -> None:
    journal_path = Path(
        os.environ.get(
            "MAGAZINE_OUTCOME_JOURNAL",
            str(Path.home() / ".local/state/bali-zero-magazine/outcomes.jsonl"),
        )
    )
    transport = MagazineTransport(
        _transport_config(),
        journal=DurableOutcomeJournal(journal_path),
    )
    try:
        if breaking:
            await transport.publish_breaking(packet)
        else:
            await transport.post_json("/api/machine/publications/editions", packet)
    finally:
        await transport.aclose()


async def _morning(args: argparse.Namespace, manifest: dict[str, Any]) -> dict[str, Any]:
    registry = default_adapter_registry()
    rows_by_system = manifest.get("candidate_rows", {})
    if not isinstance(rows_by_system, dict):
        raise ValueError("candidate_rows must be an object keyed by registered system_id")
    candidates = []
    for system_id in sorted(rows_by_system):
        rows = rows_by_system[system_id]
        if not isinstance(rows, list):
            raise ValueError(f"candidate_rows[{system_id}] must be an array")
        candidates.extend(registry.get(system_id).candidates(rows))
    runs_raw = manifest.get("collector_runs", [])
    if not isinstance(runs_raw, list):
        raise ValueError("collector_runs must be an array")
    collector_runs = []
    for item in runs_raw:
        if not isinstance(item, dict) or not isinstance(item.get("system_id"), str):
            raise ValueError("each collector run requires a registered system_id")
        collector_runs.append(registry.get(item["system_id"]).collector_run(item))
    packet = compose_edition(
        candidates=tuple(candidates),
        collector_runs=tuple(collector_runs),
        cutoff=_cutoff(args.cutoff),
        expected_current_revision=int(manifest["expected_current_revision"]),
        expected_breaking_revision=int(manifest["expected_breaking_revision"]),
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
    system_id = manifest.get("system_id")
    row = manifest.get("candidate")
    if not isinstance(system_id, str) or not isinstance(row, dict):
        raise ValueError("breaking input requires system_id and candidate object")
    candidates = default_adapter_registry().get(system_id).candidates((row,))
    if len(candidates) != 1:
        raise ValueError("breaking input did not produce exactly one eligible candidate row")
    packet = compose_breaking(
        score_candidate(candidates[0]),
        expected_breaking_revision=int(manifest["expected_breaking_revision"]),
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
    await _write_packet(args.output, packet)
    if args.publish:
        await _publish(packet, breaking=args.command == "breaking")
        logger.info("packet published packet_id=%s target=%s", packet["packet_id"], args.command)
    else:
        logger.info("dry run complete packet_id=%s target=%s", packet["packet_id"], args.command)
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
