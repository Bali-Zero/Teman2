"""BridgeStateReader — read existing state files for the genome aggregator.

Many organs already write `~/.agent/decisions/state/<job>.last.json` (cron
jobs) or `~/.cron-agent-python/<job>.state.json` (Python agents) with
their last status; this reader exposes those records as `BridgeReading`
objects so the genome aggregator can compute liveness without modifying
the organi themselves.

Authoritative spec: docs/innervation-2026-04-29/07_innervation_protocol.md §1.1
+ §2.4 (Codex bridge insight). The reader supports `state_file` sources in
W0; `sql_table`, `redis_stream`, `logger` types are stubbed and return an
explicit "unsupported" error so the gap is visible.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("cell.sensors.bridge_state_reader")


# ---------- data classes ----------------------------------------------------


@dataclass
class BridgeSource:
    """Genoma `bridge_source` declaration translated into runtime form."""

    organ_id: str
    type: str  # "state_file" | "sql_table" | "redis_stream" | "logger"
    path: str
    timestamp_field: str = "ts"
    status_field: str = "status"


@dataclass
class BridgeReading:
    """A single read result. `error` is "" on success, populated otherwise."""

    organ_id: str
    timestamp: float | None = None
    status: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""


# ---------- reader ----------------------------------------------------------


class BridgeStateReader:
    """Reads N bridge sources in one shot. Stateless; safe for repeated calls."""

    def __init__(self, sources: list[BridgeSource]) -> None:
        self._sources = list(sources)

    def read_all(self) -> list[BridgeReading]:
        return [self._read_one(s) for s in self._sources]

    # ----- internals --------------------------------------------------------

    def _read_one(self, src: BridgeSource) -> BridgeReading:
        if src.type != "state_file":
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"unsupported bridge type {src.type!r} (only state_file in W0)",
            )

        try:
            path = Path(str(src.path)).expanduser()
        except Exception as exc:
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"path expand failed: {exc}",
            )

        if not path.exists():
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"state file not found: {path}",
            )

        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"state file read failed: {exc}",
            )

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"json parse error: {exc.msg}",
            )

        if not isinstance(data, dict):
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"state file must contain a JSON object, got {type(data).__name__}",
            )

        if src.timestamp_field not in data:
            return BridgeReading(
                organ_id=src.organ_id,
                payload=data,
                error=f"missing timestamp field {src.timestamp_field!r}",
            )

        ts = self._coerce_timestamp(data[src.timestamp_field])
        if ts is None:
            return BridgeReading(
                organ_id=src.organ_id,
                payload=data,
                error=(
                    f"could not coerce timestamp value "
                    f"{data[src.timestamp_field]!r} from field "
                    f"{src.timestamp_field!r} to unix epoch"
                ),
            )

        status = str(data.get(src.status_field, ""))

        return BridgeReading(
            organ_id=src.organ_id,
            timestamp=ts,
            status=status,
            payload=data,
        )

    @staticmethod
    def _coerce_timestamp(value: Any) -> float | None:
        """Accept a unix epoch (int|float) OR an ISO-8601 string."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).timestamp()
            except ValueError:
                return None
        return None
