"""MetabolicCollector — reads data sources and computes 4 metabolic metrics.

Each metric collector is independent and handles its own errors gracefully.
If a data source is unavailable, the metric returns value=None with error metadata.

# Organo: cell-core (L0) metabolic module
# Produce: MetabolicSnapshot (4 metrics)
# Consuma: cell_pulse_log (PG), kg_nodes/kg_edges (PG), cron JSONL logs,
#          MOS SQLite, escalations JSONL
"""
from __future__ import annotations

import glob
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

from cell_core.metabolic.definitions import (
    METRIC_AUTONOMY_INDEX,
    METRIC_ESCALATION_FREQ,
    METRIC_ONTOLOGY_DENSITY,
    METRIC_TTR,
    MetabolicSnapshot,
    MetricValue,
)

logger = logging.getLogger("cell_core.metabolic.collector")


class MetabolicCollector:
    """Reads all data sources and computes the 4 SYMBIOSIS metabolic metrics.

    Constructor injection for all paths. PG connection is optional — if pg_dsn
    is None, PG-dependent metrics (TTR, DO) return None gracefully.
    """

    def __init__(
        self,
        cron_log_dir: str = "~/logs/cron",
        escalation_path: str = "shared/escalations_pro.jsonl",
        mos_db_path: str = "~/.claude/memory.db",
        pg_dsn: str | None = None,
        window_hours: int = 24,
    ) -> None:
        self._cron_log_dir = os.path.expanduser(cron_log_dir)
        self._escalation_path = os.path.expanduser(escalation_path)
        self._mos_db_path = os.path.expanduser(mos_db_path)
        self._pg_dsn = pg_dsn
        self._window_hours = window_hours

    def collect(self) -> MetabolicSnapshot:
        """Compute all 4 metrics. Each is independent — failures are isolated."""
        now = datetime.now(timezone.utc).isoformat()

        ttr = self._collect_ttr(now)
        do = self._collect_do(now)
        ia_result = self._collect_ia(now)
        fe = self._collect_fe(now, ia_result.metadata.get("total_actions", 0))

        return MetabolicSnapshot(
            ttr=ttr,
            ontology_density=do,
            autonomy_index=ia_result,
            escalation_freq=fe,
            calculated_at=now,
        )

    # ── M1: Time-to-Resolution ─────────────────────────────────────────────

    def _collect_ttr(self, now: str) -> MetricValue:
        """Count contiguous non-green pulse episodes from cell_pulse_log.

        An 'episode' is a consecutive run of pulses with health_status != 'green'.
        TTR = mean(episode_lengths). Lower is better.
        """
        if not self._pg_dsn:
            return MetricValue(
                metric_type=METRIC_TTR, value=None, calculated_at=now,
                metadata={"error": "pg_dsn_not_configured"},
            )
        try:
            import asyncio
            return asyncio.get_event_loop().run_until_complete(self._collect_ttr_async(now))
        except RuntimeError:
            # No event loop — create one
            import asyncio
            return asyncio.run(self._collect_ttr_async(now))
        except Exception as e:
            logger.error(f"[metabolic] TTR collection failed: {e}")
            return MetricValue(
                metric_type=METRIC_TTR, value=None, calculated_at=now,
                metadata={"error": str(e)},
            )

    async def _collect_ttr_async(self, now: str) -> MetricValue:
        """Async PG query for TTR."""
        try:
            import asyncpg
        except ImportError:
            return MetricValue(
                metric_type=METRIC_TTR, value=None, calculated_at=now,
                metadata={"error": "asyncpg_not_installed"},
            )
        try:
            conn = await asyncpg.connect(self._pg_dsn, timeout=10)
            try:
                cutoff = datetime.now(timezone.utc).timestamp() - self._window_hours * 3600
                cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
                rows = await conn.fetch(
                    """SELECT health_status FROM cell_pulse_log
                       WHERE created_at >= $1
                       ORDER BY pulse_number ASC""",
                    cutoff_dt,
                )
                episodes = _extract_episodes([r["health_status"] for r in rows])
                if not episodes:
                    return MetricValue(
                        metric_type=METRIC_TTR, value=0.0, calculated_at=now,
                        metadata={"episodes_count": 0, "total_pulses": len(rows)},
                    )
                mean_len = sum(episodes) / len(episodes)
                return MetricValue(
                    metric_type=METRIC_TTR, value=round(mean_len, 2), calculated_at=now,
                    metadata={
                        "episodes_count": len(episodes),
                        "total_pulses_degraded": sum(episodes),
                        "max_episode_length": max(episodes),
                        "total_pulses": len(rows),
                    },
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"[metabolic] TTR PG query failed: {e}")
            return MetricValue(
                metric_type=METRIC_TTR, value=None, calculated_at=now,
                metadata={"error": str(e)},
            )

    # ── M2: Ontological Density ────────────────────────────────────────────

    def _collect_do(self, now: str) -> MetricValue:
        """Query KG node/edge counts from PostgreSQL kg_nodes/kg_edges."""
        if not self._pg_dsn:
            return MetricValue(
                metric_type=METRIC_ONTOLOGY_DENSITY, value=None, calculated_at=now,
                metadata={"error": "pg_dsn_not_configured"},
            )
        try:
            import asyncio
            try:
                return asyncio.get_event_loop().run_until_complete(self._collect_do_async(now))
            except RuntimeError:
                return asyncio.run(self._collect_do_async(now))
        except Exception as e:
            logger.error(f"[metabolic] DO collection failed: {e}")
            return MetricValue(
                metric_type=METRIC_ONTOLOGY_DENSITY, value=None, calculated_at=now,
                metadata={"error": str(e)},
            )

    async def _collect_do_async(self, now: str) -> MetricValue:
        """Async PG query for DO."""
        try:
            import asyncpg
        except ImportError:
            return MetricValue(
                metric_type=METRIC_ONTOLOGY_DENSITY, value=None, calculated_at=now,
                metadata={"error": "asyncpg_not_installed"},
            )
        try:
            conn = await asyncpg.connect(self._pg_dsn, timeout=10)
            try:
                nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
                edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
                if not nodes or nodes == 0:
                    return MetricValue(
                        metric_type=METRIC_ONTOLOGY_DENSITY, value=0.0, calculated_at=now,
                        metadata={"nodes": nodes or 0, "edges": edges or 0},
                    )
                do_value = round(edges / nodes, 4)
                return MetricValue(
                    metric_type=METRIC_ONTOLOGY_DENSITY, value=do_value, calculated_at=now,
                    metadata={"nodes": nodes, "edges": edges},
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"[metabolic] DO PG query failed: {e}")
            return MetricValue(
                metric_type=METRIC_ONTOLOGY_DENSITY, value=None, calculated_at=now,
                metadata={"error": str(e)},
            )

    # ── M3: Autonomy Index ─────────────────────────────────────────────────

    def _collect_ia(self, now: str) -> MetricValue:
        """Compute endogenous/total action ratio from local data sources.

        Endogenous: cron JSONL (status=ok) + cell pulse actions (if PG available)
        Exogenous: MOS sessions started in window
        """
        try:
            endogenous = self._count_cron_executions()
            exogenous = self._count_mos_sessions()

            # Try to add cell pulse actions if PG available
            pulse_actions = 0
            if self._pg_dsn:
                try:
                    import asyncio
                    try:
                        pulse_actions = asyncio.get_event_loop().run_until_complete(
                            self._count_pulse_actions()
                        )
                    except RuntimeError:
                        pulse_actions = asyncio.run(self._count_pulse_actions())
                except Exception:
                    pass  # graceful — pulse actions are bonus, not required

            endogenous_total = endogenous + pulse_actions
            total = endogenous_total + exogenous
            if total == 0:
                ia = 0.0
            else:
                ia = round(endogenous_total / total, 4)

            return MetricValue(
                metric_type=METRIC_AUTONOMY_INDEX, value=ia, calculated_at=now,
                metadata={
                    "endogenous": {"cron": endogenous, "pulse_actions": pulse_actions},
                    "exogenous": {"sessions": exogenous},
                    "total_actions": total,
                },
            )
        except Exception as e:
            logger.error(f"[metabolic] IA collection failed: {e}")
            return MetricValue(
                metric_type=METRIC_AUTONOMY_INDEX, value=None, calculated_at=now,
                metadata={"error": str(e)},
            )

    def _count_cron_executions(self) -> int:
        """Count cron JSONL entries with status=ok in the last window_hours."""
        cutoff = time.time() - self._window_hours * 3600
        count = 0
        if not os.path.isdir(self._cron_log_dir):
            return 0
        for fpath in glob.glob(os.path.join(self._cron_log_dir, "*.jsonl")):
            try:
                with open(fpath) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        ts = entry.get("ts", "")
                        status = entry.get("status", "")
                        if status != "ok":
                            continue
                        # Parse ISO timestamp or unix
                        entry_time = _parse_timestamp(ts)
                        if entry_time and entry_time >= cutoff:
                            count += 1
            except (OSError, IOError):
                continue
        return count

    def _count_mos_sessions(self) -> int:
        """Count MOS sessions started in the last window_hours."""
        if not os.path.isfile(self._mos_db_path):
            return 0
        try:
            conn = sqlite3.connect(self._mos_db_path, timeout=3.0)
            conn.row_factory = sqlite3.Row
            cutoff_dt = datetime.fromtimestamp(
                time.time() - self._window_hours * 3600, tz=timezone.utc
            )
            # MOS stores started_at as ISO string
            cutoff_str = cutoff_dt.isoformat()
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM sessions WHERE started_at >= ?",
                (cutoff_str,),
            ).fetchone()
            conn.close()
            return row["cnt"] if row else 0
        except Exception as e:
            logger.debug(f"[metabolic] MOS session count failed: {e}")
            return 0

    async def _count_pulse_actions(self) -> int:
        """Count cell pulse actions (action_taken IS NOT NULL) in window."""
        try:
            import asyncpg
            conn = await asyncpg.connect(self._pg_dsn, timeout=10)
            try:
                cutoff = datetime.fromtimestamp(
                    time.time() - self._window_hours * 3600, tz=timezone.utc
                )
                count = await conn.fetchval(
                    """SELECT COUNT(*) FROM cell_pulse_log
                       WHERE created_at >= $1 AND action_taken IS NOT NULL
                       AND action_taken != ''""",
                    cutoff,
                )
                return count or 0
            finally:
                await conn.close()
        except Exception:
            return 0

    # ── M4: Escalation Frequency ───────────────────────────────────────────

    def _collect_fe(self, now: str, total_actions: int) -> MetricValue:
        """Count escalations in window, normalize by total actions from IA.

        Reads shared/escalations_pro.jsonl line by line, filtering by timestamp.
        """
        try:
            raw_count = self._count_escalations()
            if total_actions == 0:
                fe = 0.0 if raw_count == 0 else 1.0
            else:
                fe = round(raw_count / total_actions, 4)

            return MetricValue(
                metric_type=METRIC_ESCALATION_FREQ, value=fe, calculated_at=now,
                metadata={
                    "raw_count": raw_count,
                    "total_actions": total_actions,
                },
            )
        except Exception as e:
            logger.error(f"[metabolic] FE collection failed: {e}")
            return MetricValue(
                metric_type=METRIC_ESCALATION_FREQ, value=None, calculated_at=now,
                metadata={"error": str(e)},
            )

    def _count_escalations(self) -> int:
        """Count escalation entries in the last window_hours."""
        if not os.path.isfile(self._escalation_path):
            return 0
        cutoff = time.time() - self._window_hours * 3600
        count = 0
        try:
            with open(self._escalation_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("ts", "")
                    entry_time = _parse_timestamp(ts)
                    if entry_time and entry_time >= cutoff:
                        count += 1
        except (OSError, IOError) as e:
            logger.debug(f"[metabolic] Escalation file read failed: {e}")
        return count


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_episodes(statuses: list[str]) -> list[int]:
    """Extract contiguous runs of non-green statuses and return their lengths.

    Example: [green, yellow, red, green, red, green] -> [2, 1]
    """
    episodes: list[int] = []
    current_length = 0
    for s in statuses:
        if s != "green":
            current_length += 1
        else:
            if current_length > 0:
                episodes.append(current_length)
                current_length = 0
    # If we end on a non-green run, count it as an open episode
    if current_length > 0:
        episodes.append(current_length)
    return episodes


def _parse_timestamp(ts: Any) -> float | None:
    """Parse a timestamp (ISO string or unix float/int) to unix float."""
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        ts = ts.strip()
        if not ts:
            return None
        # Try ISO 8601
        try:
            dt = datetime.fromisoformat(ts)
            return dt.timestamp()
        except ValueError:
            pass
        # Try unix as string
        try:
            return float(ts)
        except ValueError:
            pass
    return None
