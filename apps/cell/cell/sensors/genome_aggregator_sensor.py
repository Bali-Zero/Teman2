"""GenomeAggregatorSensor — aggregate "chi è vivo?" across all organi.

Reads three inputs and merges them into one SensorReading:

1. **Genoma** (`apps/organism/organism/organs_registry.yaml`) — source of
   truth for "what organi exist + expected heartbeat". Static;
   checksum-validated. (File renamed from `genome.yaml` 2026-05-08 IG-3;
   filesystem symlink `genome.yaml → organs_registry.yaml` retained until
   2026-06-08 for backward compat.)
2. **last_seen.db** (`~/.organism/last_seen.db`, SQLite, per-machine) — written
   by the Supervisor consume loop in Wave 2 with `organ_id → last_seen`
   (unix epoch). For W0 the table may be absent: all organi without a
   bridge_source are treated as `stale`.
3. **bridge sources** — for organi with a `bridge_source: state_file` entry
   in organs_registry.yaml, the timestamp comes from
   `BridgeStateReader.read_all()` (see
   `apps/cell/cell/sensors/bridge_state_reader.py`). Bridge timestamps
   override last_seen.db lookups for that organ.

Classification per organ (07_innervation_protocol.md §1.1):

- `expected_hb_seconds == 0` (infra) → bridge presence only:
  - bridge ok → alive
  - bridge missing/error → dead
- `expected_hb_seconds > 0`:
  - last_seen < 1.5 × expected → alive
  - last_seen < 3.0 × expected → stale
  - last_seen ≥ 3.0 × expected (or no last_seen at all) → dead

Aggregate `status`:

- any organ dead → `red`
- any organ stale → `yellow`
- all alive → `green`

W0 scope: this sensor is NOT yet wired into `apps/cell/cell/main.py`
PulseEngine. Wire-up is deferred to W0-A.bis.bis (PulseEngine already has
26 ctor args; +1 + plumbing through fixtures is a cross-cutting change
not contained in W0-A scope). See 99c_w0a_bis_kickoff.md §3.1 deferred-block.

Authoritative spec: 07_innervation_protocol.md §3.1, 99c_w0a_bis_kickoff.md §3.1.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cell.sensors.bridge_state_reader import (
    BridgeReading,
    BridgeSource,
    BridgeStateReader,
)

logger = logging.getLogger("cell.sensors.genome_aggregator_sensor")


# ---------- data classes ----------------------------------------------------


@dataclass
class SensorReading:
    """Mirrors the per-sensor pattern (e.g. database_sensor.py)."""

    status: str  # "green" | "yellow" | "red"
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------- sensor ----------------------------------------------------------


_DEFAULT_GENOME = (
    Path(__file__).resolve().parents[3]
    / "organism"
    / "organism"
    / "organs_registry.yaml"
)
_DEFAULT_LAST_SEEN_DB = Path("~/.organism/last_seen.db").expanduser()


class GenomeAggregatorSensor:
    """Aggregate liveness of all organi for one Cell pulse cycle.

    Sync `read()` (not async): all I/O is local file/SQLite, no network.
    Returning sync keeps the test surface simple and matches the
    BridgeStateReader contract (also sync). The `async def` in the
    spec preamble is honored with a thin async wrapper at the bottom
    of this module so future PulseEngine wiring (which awaits sensors)
    works with the same instance.
    """

    def __init__(
        self,
        genome_path: Path | str | None = None,
        last_seen_db_path: Path | str | None = None,
    ) -> None:
        self._genome_path = Path(genome_path) if genome_path else _DEFAULT_GENOME
        self._last_seen_db_path = (
            Path(last_seen_db_path) if last_seen_db_path else _DEFAULT_LAST_SEEN_DB
        )

    # ----- public API -------------------------------------------------------

    async def read(self) -> SensorReading:
        """Async wrapper around `read_sync` for PulseEngine compatibility."""
        return self.read_sync()

    def read_sync(self) -> SensorReading:
        now = time.time()

        # 1. Load genome.
        try:
            organs = self._load_genome()
        except FileNotFoundError as exc:
            return SensorReading(
                status="red",
                metadata={
                    "error": "genome_missing",
                    "detail": str(exc),
                    "genome_path": str(self._genome_path),
                },
            )
        except Exception as exc:  # malformed YAML / unreadable
            return SensorReading(
                status="red",
                metadata={
                    "error": "genome_unreadable",
                    "detail": str(exc),
                    "genome_path": str(self._genome_path),
                },
            )

        # 2. Read last_seen.db (best-effort).
        last_seen, last_seen_error = self._read_last_seen()

        # 3. Read bridge sources.
        bridge_readings = self._read_bridges(organs)

        # 4. Classify each organ.
        per_organ = []
        for organ in organs:
            state = self._classify_organ(
                organ=organ,
                now=now,
                last_seen=last_seen,
                bridge_readings=bridge_readings,
            )
            per_organ.append(state)

        # 5. Aggregate.
        alive = [o for o in per_organ if o["state"] == "alive"]
        stale = [o for o in per_organ if o["state"] == "stale"]
        dead = [o for o in per_organ if o["state"] == "dead"]

        if dead:
            agg = "red"
        elif stale:
            agg = "yellow"
        else:
            agg = "green"

        metadata: dict[str, Any] = {
            "total_organs": len(per_organ),
            "alive": len(alive),
            "stale": len(stale),
            "dead": len(dead),
            "dead_organs": [o["organ_id"] for o in dead],
        }
        if last_seen_error:
            metadata["last_seen_db_status"] = last_seen_error
        if stale:
            metadata["stale_organs"] = [o["organ_id"] for o in stale]

        return SensorReading(status=agg, metadata=metadata)

    # ----- internals --------------------------------------------------------

    def _load_genome(self) -> list[dict[str, Any]]:
        """Return the `organs` list from organs_registry.yaml (raw dicts)."""
        if not self._genome_path.exists():
            raise FileNotFoundError(self._genome_path)
        text = self._genome_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError(
                f"organs_registry.yaml must be a mapping, got {type(data).__name__}"
            )
        organs = data.get("organs")
        if not isinstance(organs, list):
            raise ValueError("organs_registry.yaml missing `organs` list")
        return organs

    def _read_last_seen(self) -> tuple[dict[str, float], str]:
        """Return (organ_id → last_seen_epoch, status_string).

        Status is "" on success, otherwise a short human-readable reason
        ("missing" / "schema_unknown" / "read_error").
        """
        if not self._last_seen_db_path.exists():
            return {}, "missing"
        try:
            conn = sqlite3.connect(
                f"file:{self._last_seen_db_path}?mode=ro",
                uri=True,
                timeout=2.0,
            )
        except sqlite3.Error as exc:
            return {}, f"read_error: {exc}"

        result: dict[str, float] = {}
        try:
            cur = conn.execute(
                "SELECT organ_id, last_seen FROM organ_last_seen"
            )
            for organ_id, ts in cur.fetchall():
                if isinstance(ts, (int, float)) and isinstance(organ_id, str):
                    result[organ_id] = float(ts)
            return result, ""
        except sqlite3.OperationalError:
            # Table doesn't exist yet (Wave 2 hasn't created it).
            return {}, "schema_unknown"
        except sqlite3.Error as exc:
            return {}, f"read_error: {exc}"
        finally:
            conn.close()

    def _read_bridges(
        self, organs: list[dict[str, Any]]
    ) -> dict[str, BridgeReading]:
        sources: list[BridgeSource] = []
        for organ in organs:
            decl = organ.get("bridge_source")
            if not isinstance(decl, dict):
                continue
            organ_id = organ.get("id")
            if not isinstance(organ_id, str):
                continue
            kwargs: dict[str, Any] = {
                "organ_id": organ_id,
                "type": str(decl.get("type", "")),
                "path": str(decl.get("path", "")),
            }
            if "timestamp_field" in decl:
                kwargs["timestamp_field"] = str(decl["timestamp_field"])
            if "status_field" in decl:
                kwargs["status_field"] = str(decl["status_field"])
            sources.append(BridgeSource(**kwargs))

        if not sources:
            return {}
        readings = BridgeStateReader(sources).read_all()
        return {r.organ_id: r for r in readings}

    def _classify_organ(
        self,
        *,
        organ: dict[str, Any],
        now: float,
        last_seen: dict[str, float],
        bridge_readings: dict[str, BridgeReading],
    ) -> dict[str, Any]:
        organ_id = str(organ.get("id", ""))
        expected = organ.get("expected_hb_seconds", 0)
        try:
            expected_seconds = float(expected)
        except (TypeError, ValueError):
            expected_seconds = 0.0

        bridge = bridge_readings.get(organ_id)

        # Resolve the most recent timestamp known for this organ.
        # Bridge takes precedence over last_seen.db (per spec §3.1 case 6).
        ts: float | None = None
        source: str = ""
        bridge_error = ""
        if bridge is not None:
            if bridge.error:
                bridge_error = bridge.error
            elif bridge.timestamp is not None:
                ts = bridge.timestamp
                source = "bridge"
        if ts is None:
            db_ts = last_seen.get(organ_id)
            if db_ts is not None:
                ts = db_ts
                source = "last_seen_db"

        # Infra rule: expected_hb_seconds == 0 → bridge presence only.
        if expected_seconds == 0:
            if bridge is not None and not bridge.error and bridge.timestamp is not None:
                return {"organ_id": organ_id, "state": "alive", "source": "bridge"}
            return {
                "organ_id": organ_id,
                "state": "dead",
                "source": "bridge_missing" if bridge is None else "bridge_error",
                "error": bridge_error,
            }

        # Time-based classification for non-infra organi.
        if ts is None:
            return {
                "organ_id": organ_id,
                "state": "dead",
                "source": "no_signal",
                "error": bridge_error,
            }

        age = now - ts
        if age < 1.5 * expected_seconds:
            state = "alive"
        elif age < 3.0 * expected_seconds:
            state = "stale"
        else:
            state = "dead"
        return {
            "organ_id": organ_id,
            "state": state,
            "source": source,
            "age_seconds": age,
        }


__all__ = ["GenomeAggregatorSensor", "SensorReading"]
