"""BridgeStateReader — read existing state files for the genome aggregator.

Many organs already write `~/.agent/decisions/state/<job>.last.json` (cron
jobs) or `~/.cron-agent-python/<job>.state.json` (Python agents) with
their last status; this reader exposes those records as `BridgeReading`
objects so the genome aggregator can compute liveness without modifying
the organi themselves.

Authoritative spec: docs/innervation-2026-04-29/07_innervation_protocol.md §1.1
+ §2.4 (Codex bridge insight). W0 supported `state_file` only. W1.2 adds
`http` for remote sources (channel.* organi running inside the Fly machine
expose their liveness via the public `/api/channels/health-public` endpoint
and a dotted `json_path` extracts the per-channel status). `sql_table`,
`redis_stream`, `logger` remain stubbed and return an explicit "unsupported"
error so the gap is visible.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("cell.sensors.bridge_state_reader")


# ---------- data classes ----------------------------------------------------


@dataclass
class BridgeSource:
    """Genoma `bridge_source` declaration translated into runtime form.

    `path` is overloaded by `type`:
      - state_file → filesystem path (may contain `~`, expanded at read time)
      - http       → URL for `httpx.Client.get(...)`

    `json_path` is dotted notation (e.g. `channels.whatsapp.status`) used by
    the http reader to pluck a single value out of the response body. Empty
    string means "use top-level `status_field`" — same semantics as
    state_file, useful when the entire body IS the status payload.
    """

    organ_id: str
    type: str  # "state_file" | "http" | "sql_table" | "redis_stream" | "logger"
    path: str
    timestamp_field: str = "ts"
    status_field: str = "status"
    json_path: str = ""

    # http-only — surfaced as kwargs to keep state_file callers untouched.
    http_timeout_s: float = 5.0


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
        if src.type == "state_file":
            return self._read_state_file(src)
        if src.type == "http":
            return self._read_http(src)
        return BridgeReading(
            organ_id=src.organ_id,
            error=f"unsupported bridge type {src.type!r} "
            f"(supported: state_file, http)",
        )

    # ----- state_file branch ------------------------------------------------

    def _read_state_file(self, src: BridgeSource) -> BridgeReading:
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

    # ----- http branch ------------------------------------------------------

    def _read_http(self, src: BridgeSource) -> BridgeReading:
        """GET `src.path`, parse JSON body, extract status via dotted json_path.

        Synchronous httpx client — the Cell pulse loop runs every ~60s, so
        a 5s timeout × N channels (~2s wallclock for 4) is invisible at the
        pulse cadence. Async / pooling would save ~50ms but complicate the
        BridgeStateReader lifecycle (currently constructed fresh each pulse).
        Pragmatic: pay the cost.
        """
        try:
            with httpx.Client(timeout=src.http_timeout_s) as client:
                resp = client.get(src.path)
        except httpx.HTTPError as exc:
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"http request failed: {type(exc).__name__}: {exc}",
            )

        if resp.status_code != 200:
            preview = resp.text[:200]
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"http {resp.status_code}: body={preview!r}",
            )

        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError) as exc:
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"http body json parse error: {exc}",
            )

        if not isinstance(data, dict):
            return BridgeReading(
                organ_id=src.organ_id,
                error=f"http body must be JSON object, got {type(data).__name__}",
            )

        if src.timestamp_field not in data:
            return BridgeReading(
                organ_id=src.organ_id,
                payload=data,
                error=f"http body missing timestamp field {src.timestamp_field!r}",
            )

        ts = self._coerce_timestamp(data[src.timestamp_field])
        if ts is None:
            return BridgeReading(
                organ_id=src.organ_id,
                payload=data,
                error=(
                    f"could not coerce http timestamp value "
                    f"{data[src.timestamp_field]!r} from field "
                    f"{src.timestamp_field!r}"
                ),
            )

        # Status: pull via dotted json_path; fallback to top-level status_field.
        if src.json_path:
            raw_status = self._extract_dotted(data, src.json_path)
            if raw_status is None:
                return BridgeReading(
                    organ_id=src.organ_id,
                    timestamp=ts,
                    payload=data,
                    error=f"http body missing json_path {src.json_path!r}",
                )
        else:
            raw_status = data.get(src.status_field, "")

        status = self._map_remote_status(str(raw_status))

        return BridgeReading(
            organ_id=src.organ_id,
            timestamp=ts,
            status=status,
            payload=data,
        )

    # ----- helpers ----------------------------------------------------------

    @staticmethod
    def _extract_dotted(data: dict, path: str) -> Any:
        """Walk a dotted json path. Returns None if any segment is missing
        or the intermediate value is not a dict."""
        cur: Any = data
        for seg in path.split("."):
            if not isinstance(cur, dict) or seg not in cur:
                return None
            cur = cur[seg]
        return cur

    @staticmethod
    def _map_remote_status(value: str) -> str:
        """Normalize a remote-vocabulary status into the sidecar vocabulary
        consumed by the genome aggregator (`ok | degraded | fail`).

        Backend vocab: up / degraded / down (channels.health-public).
        Cell vocab:    green / yellow / red (HealthStatus enum).
        Other:         healthy, ok, partial, failed → mapped conservatively.

        Unknown vocab maps to `degraded` (operator-visible) rather than `ok`
        (silent) or `fail` (alarming) — preserves visibility without
        creating a false alarm if the backend ever returns a new state.
        """
        v = value.strip().lower()
        if v in {"up", "ok", "healthy", "green"}:
            return "ok"
        if v in {"degraded", "partial", "yellow"}:
            return "degraded"
        if v in {"down", "fail", "failed", "red"}:
            return "fail"
        return "degraded"

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
