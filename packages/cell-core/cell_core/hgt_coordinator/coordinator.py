"""Coordinator — observe Redis Stream ``cell:skills`` and emit proposals.

Sits OUTSIDE the cell-core HGT layer. The in-cell-core HGT publisher /
consumer is automatic (≥0.7 + matching domain) and runs in real time.
This coordinator runs on a heartbeat (default 7d window via OpenClaw),
aggregates per-skill statistics across cells, and writes propose-only
rows into a SQLite audit log. **No auto-merge.** Operators (or the
Kimi K2.6 OpenClaw agent) review pending rows via the CLI.

Threshold (per `__init__.py` doc): ≥10 uses + average confidence > 0.7.
``recommended_action``:

    confidence_std < 0.15  → "propose"   (stable pattern)
    0.15 ≤ std < 0.25      → "defer"     (keep observing)
    confidence_std ≥ 0.25  → "reject"    (too noisy)

Graceful degradation:
    - Redis client may be ``None`` → return ``[]`` + warning, never raise.
    - Redis errors (``RedisError``) caught → return ``[]`` + warning.
    - Malformed stream entries (missing ``name``/``confidence``/``cell``)
      → log warning + skip.

Idempotency: persistence happens via :func:`audit_log.record_proposal`
which already de-dupes on
``(skill_name, observation_window_days, status='pending', last 24h)``.
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cell_core.hgt.domains import CANONICAL_DOMAINS, validate_domain
from cell_core.hgt_coordinator.audit_log import record_proposal
from cell_core.hgt_coordinator.proposal import Proposal, RecommendedAction

logger = logging.getLogger("cell_core.hgt_coordinator.coordinator")

# Streams names (kept in sync with cell_core.hgt.publisher.STREAM_SKILLS).
STREAM_SKILLS = "cell:skills"
STREAM_SKILLS_CONSUMED = "cell:skills:consumed"

# Eligibility thresholds (frozen — bump only via brainstorm).
MIN_TOTAL_USES = 10
MIN_AVG_CONFIDENCE = 0.7

# Variance bands for ``recommended_action`` selection.
_STD_PROPOSE_MAX = 0.15
_STD_DEFER_MAX = 0.25


def _decode_field(value: Any) -> str:
    """Decode a stream-entry field to ``str`` (fakeredis returns bytes)."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:  # pragma: no cover — defensive
            return value.decode("utf-8", errors="replace")
    return str(value)


def _normalize_entry(fields: dict[Any, Any]) -> dict[str, str]:
    """Normalise a stream entry: bytes→str on both keys and values."""
    out: dict[str, str] = {}
    for k, v in fields.items():
        out[_decode_field(k)] = _decode_field(v)
    return out


def _classify(confidence_std: float) -> RecommendedAction:
    """Translate variance to recommended action; see module docstring."""
    if confidence_std < _STD_PROPOSE_MAX:
        return "propose"
    if confidence_std < _STD_DEFER_MAX:
        return "defer"
    return "reject"


class HGTCoordinator:
    """Propose-only observer over the cell:skills Redis Stream.

    Args:
        redis_client: ``redis.asyncio.Redis``-compatible instance, OR
            ``None`` for graceful degradation (every method returns ``[]``
            and logs a warning).
        audit_log_path: optional override path to the SQLite audit log
            (default resolved by :func:`audit_log_path` which honours
            ``HGT_COORDINATOR_AUDIT_LOG`` env var).

    The coordinator is intentionally tiny — heavy lifting (LLM
    re-ranking, comment generation) happens in the OpenClaw Kimi K2.6
    agent that consumes ``coordinator observe`` JSON output.
    """

    def __init__(
        self,
        redis_client: Any,
        audit_log_path: Path | None = None,
    ) -> None:
        self._redis = redis_client
        self._audit_log_path = audit_log_path

    async def propose_transfers(
        self,
        *,
        observation_window: timedelta = timedelta(days=7),
    ) -> list[Proposal]:
        """Read recent HGT publishes, aggregate, propose transfers.

        Returns the list of :class:`Proposal` objects (also persisted to
        the SQLite audit log via :func:`record_proposal`). Empty list if
        Redis is unavailable, the stream is empty, or no skill clears
        the eligibility threshold.
        """
        if self._redis is None:
            logger.warning(
                "hgt_coordinator: redis_client is None — returning empty "
                "proposal list (graceful degradation)"
            )
            return []

        try:
            entries = await self._read_window(STREAM_SKILLS, observation_window)
        except Exception as exc:  # noqa: BLE001 — RedisError + transport
            logger.warning(
                "hgt_coordinator: redis read failed (%s); returning [] — "
                "graceful degradation",
                exc.__class__.__name__,
            )
            return []

        if not entries:
            return []

        # Optional consumer-side stream — used to compute distinct
        # consumer cells when present. If the stream doesn't exist or
        # Redis errors out, the consumer set remains empty.
        try:
            consumed_entries = await self._read_window(
                STREAM_SKILLS_CONSUMED, observation_window
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "hgt_coordinator: optional consumer stream read failed "
                "(%s); proceeding without consumer cells",
                exc.__class__.__name__,
            )
            consumed_entries = []

        consumers_by_skill = self._aggregate_consumers(consumed_entries)

        proposals = self._aggregate_publishers(
            entries=entries,
            consumers_by_skill=consumers_by_skill,
            observation_window=observation_window,
        )

        # Persist (idempotent via audit_log dedup).
        persisted: list[Proposal] = []
        for proposal in proposals:
            try:
                row_id = record_proposal(proposal, path=self._audit_log_path)
                # Proposal is frozen; rebuild with audit_log_id filled.
                persisted.append(
                    Proposal(
                        skill_name=proposal.skill_name,
                        source_cells=proposal.source_cells,
                        target_cell_candidates=proposal.target_cell_candidates,
                        domain=proposal.domain,
                        total_uses=proposal.total_uses,
                        avg_confidence=proposal.avg_confidence,
                        std_confidence=proposal.std_confidence,
                        confidence=proposal.confidence,
                        transfer_rationale=proposal.transfer_rationale,
                        recommended_action=proposal.recommended_action,
                        observation_window_days=proposal.observation_window_days,
                        observed_at=proposal.observed_at,
                        audit_log_id=row_id,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "hgt_coordinator: failed to persist proposal for skill "
                    "%s (%s); dropping from output",
                    proposal.skill_name,
                    exc.__class__.__name__,
                )

        logger.info(
            "hgt_coordinator: emitted %d proposals from %d stream entries "
            "(window=%dd)",
            len(persisted),
            len(entries),
            observation_window.days,
        )
        return persisted

    # === internals =========================================================

    async def _read_window(
        self,
        stream: str,
        window: timedelta,
    ) -> list[dict[str, str]]:
        """Read entries from ``stream`` over the last ``window``.

        Returns a list of normalised (str→str) dicts. Falls back to
        ``XRANGE - +`` if the time-bounded read returns nothing — useful
        in tests where ``XADD`` uses synthetic IDs.
        """
        now = datetime.now(timezone.utc)
        start_ms = int((now - window).timestamp() * 1000)
        # Use millisecond IDs for the time window.
        try:
            raw = await self._redis.xrange(stream, min=start_ms, max="+")
        except TypeError:
            # Some clients accept positional only.
            raw = await self._redis.xrange(stream, str(start_ms), "+")

        if not raw:
            # Fall back to full-range read in case stream IDs are
            # synthetic (e.g. fakeredis test fixtures with auto-IDs
            # that may already be far in the past relative to "now").
            raw = await self._redis.xrange(stream, "-", "+")

        out: list[dict[str, str]] = []
        for _entry_id, fields in raw:
            try:
                out.append(_normalize_entry(fields))
            except Exception as exc:  # noqa: BLE001 — defensive
                logger.warning(
                    "hgt_coordinator: failed to normalise stream entry on "
                    "%s (%s); skipping",
                    stream,
                    exc.__class__.__name__,
                )
                continue
        return out

    def _aggregate_consumers(
        self, entries: list[dict[str, str]]
    ) -> dict[str, set[str]]:
        """Build ``{skill_name: set(consumer_cell_names)}`` from entries.

        Tolerates missing fields by skipping individual entries.
        """
        out: dict[str, set[str]] = {}
        for fields in entries:
            name = fields.get("skill_id") or fields.get("name")
            cell = fields.get("cell_origin") or fields.get("cell")
            if not name or not cell:
                continue
            out.setdefault(name, set()).add(cell)
        return out

    def _aggregate_publishers(
        self,
        *,
        entries: list[dict[str, str]],
        consumers_by_skill: dict[str, set[str]],
        observation_window: timedelta,
    ) -> list[Proposal]:
        """Group publish events by skill_name and build :class:`Proposal`s."""
        groups: dict[str, list[dict[str, str]]] = {}
        for fields in entries:
            # Tolerate two key shapes: HGTPublisher uses ``skill_id``;
            # we also accept ``name`` for forward compatibility.
            name = fields.get("skill_id") or fields.get("name")
            cell = fields.get("cell_origin") or fields.get("cell")
            conf_str = fields.get("confidence")
            if not name or not cell or conf_str is None:
                logger.warning(
                    "hgt_coordinator: malformed stream entry — missing one of "
                    "{skill_id|name, cell_origin|cell, confidence}: keys=%r — skipping",
                    sorted(fields.keys()),
                )
                continue
            try:
                conf = float(conf_str)
            except (TypeError, ValueError):
                logger.warning(
                    "hgt_coordinator: malformed confidence %r for skill=%s — skipping",
                    conf_str,
                    name,
                )
                continue
            groups.setdefault(name, []).append(
                {**fields, "_cell": cell, "_confidence": conf}  # type: ignore[dict-item]
            )

        proposals: list[Proposal] = []
        for skill_name, items in groups.items():
            total_uses = len(items)
            confidences = [
                # Stored as float in the synthetic ``_confidence`` we injected.
                item["_confidence"]  # type: ignore[index]
                for item in items
            ]
            confidences_f: list[float] = [float(c) for c in confidences]
            avg_conf = sum(confidences_f) / total_uses
            if total_uses >= 2:
                # ``stdev`` is sample std — fine for our use case
                # (variance signal, not statistical inference).
                std_conf = statistics.stdev(confidences_f)
            else:
                std_conf = 0.0

            if total_uses < MIN_TOTAL_USES or avg_conf <= MIN_AVG_CONFIDENCE:
                # Below threshold — not eligible for proposal emission.
                continue

            source_cells = sorted({str(item["_cell"]) for item in items})
            # Domain — pick the first declared, validate against canonical set.
            raw_domain = next(
                (
                    str(item.get("domain", "generic"))
                    for item in items
                    if item.get("domain")
                ),
                "generic",
            )
            domain = validate_domain(raw_domain)

            consumer_cells = consumers_by_skill.get(skill_name, set())
            # Targets = cells in matching domain not already source/consumer.
            # We don't have a global cell registry here (the in-cell-core
            # HGT consumer enforces domain matching at consume time); the
            # coordinator works at the *Redis-stream* level. So target
            # candidates are cells that have been seen on the same domain
            # but have NOT published this skill.
            same_domain_cells: set[str] = set()
            for fields in entries:
                if validate_domain(fields.get("domain", "generic")) != domain:
                    continue
                c = fields.get("cell_origin") or fields.get("cell")
                if c:
                    same_domain_cells.add(str(c))
            already_adopted = set(source_cells) | consumer_cells
            target_candidates = sorted(same_domain_cells - already_adopted)

            confidence_clamped = max(0.0, min(1.0, avg_conf))
            recommended = _classify(std_conf)
            rationale = (
                f"Pattern observed across {len(source_cells)} cells with "
                f"mean conf {avg_conf:.2f} ({total_uses} total uses in "
                f"{observation_window.days}d). Domain {domain}. "
                f"{len(target_candidates)} candidate consumer(s) without "
                f"prior adoption."
            )
            proposals.append(
                Proposal(
                    skill_name=str(skill_name),
                    source_cells=tuple(source_cells),
                    target_cell_candidates=tuple(target_candidates),
                    domain=domain,
                    total_uses=int(total_uses),
                    avg_confidence=float(avg_conf),
                    std_confidence=float(std_conf),
                    confidence=float(confidence_clamped),
                    transfer_rationale=rationale,
                    recommended_action=recommended,
                    observation_window_days=int(observation_window.days),
                )
            )
        return proposals


__all__ = [
    "HGTCoordinator",
    "STREAM_SKILLS",
    "STREAM_SKILLS_CONSUMED",
    "MIN_TOTAL_USES",
    "MIN_AVG_CONFIDENCE",
    "CANONICAL_DOMAINS",
]
