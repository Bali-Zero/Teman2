"""Conservative backfill: LAM episodes → Experience Library trajectories.

Philosophy (from Sprint 5.2 decision 2026-04-15): quality > quantity. We only
promote a LAM episode to a trajectory when its `outcome` field maps
*unambiguously* to one of success/failure/partial. Everything else — empty
outcomes, "completed"/"done", free-text notes — is skipped. Better to backfill
50 high-signal trajectories than 1000 noisy ones that would pollute FTS search.

Usage:
    PYTHONPATH=. python backend/scripts/backfill_lam_to_experience.py --dry-run
    PYTHONPATH=. python backend/scripts/backfill_lam_to_experience.py
    PYTHONPATH=. python backend/scripts/backfill_lam_to_experience.py --limit 500

Safety:
- Idempotent: trajectory_id = "lam:{episode_id}". Re-runs update in place,
  never duplicate.
- Read-only on Qdrant. All writes go through ExperienceService.
- Honours EXPERIENCE_DB_PATH env var for the target SQLite.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Any, Iterable, Iterator, Protocol

from backend.services.experience.models import (
    TrajectoryOutcome,
    TrajectoryRecord,
)
from backend.services.experience.service import ExperienceService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ─── Outcome normalisation ────────────────────────────────────────────
#
# Explicit allowlists. Anything outside these sets → skip (conservative).

_SUCCESS_TERMS = frozenset({
    "success", "successful", "succeeded", "ok", "pass", "passed", "resolved",
})
_FAILURE_TERMS = frozenset({
    "failure", "failed", "fail", "error", "crash", "crashed", "aborted",
})
_PARTIAL_TERMS = frozenset({
    "partial", "partially_successful", "partial_success", "timeout", "retry",
})

# Explicit "known but ambiguous" set — these terms exist in real LAM episodes
# but don't carry enough signal. Documented in tests so reviewers see the
# rationale.
AMBIGUOUS_OUTCOMES = frozenset({
    "", "unknown", "completed", "done", "finished", "n/a", "?", "maybe",
})


def normalize_outcome(raw: Any) -> str | None:
    """Map a LAM episode `outcome` field to one of success|failure|partial.

    Returns None when the outcome is missing, empty, or ambiguous — caller
    must then skip the episode. This is the core quality gate.
    """
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    if not key or key in AMBIGUOUS_OUTCOMES:
        return None
    if key in _SUCCESS_TERMS:
        return "success"
    if key in _FAILURE_TERMS:
        return "failure"
    if key in _PARTIAL_TERMS:
        return "partial"
    return None  # unknown token — treat as ambiguous


# ─── Dedup key ────────────────────────────────────────────────────────


def trajectory_id_for_episode(episode_id: str) -> str:
    """Stable trajectory id built from the LAM episode id. The "lam:" prefix
    makes provenance obvious at query time and keeps the dedup window narrow
    (re-running backfill_all never duplicates)."""
    return f"lam:{episode_id}"


# ─── Record construction ─────────────────────────────────────────────


def build_trajectory_record(episode: dict[str, Any]) -> TrajectoryRecord | None:
    """Convert one LAM episode dict into a TrajectoryRecord, or None if it
    does not meet the quality gate (ambiguous outcome / empty content)."""
    content = episode.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    outcome = normalize_outcome(episode.get("outcome"))
    if outcome is None:
        return None

    episode_id = str(episode.get("id") or "").strip()
    if not episode_id:
        return None

    metadata = episode.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    tokens = metadata.get("tokens") if isinstance(metadata.get("tokens"), int) else None
    duration_ms = (
        metadata.get("duration_ms")
        if isinstance(metadata.get("duration_ms"), int)
        else None
    )

    tags_raw = episode.get("tags")
    tags: list[str] = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else []

    return TrajectoryRecord(
        trajectory_id=trajectory_id_for_episode(episode_id),
        cell=str(episode.get("agent") or "lam_legacy"),
        outcome=TrajectoryOutcome(outcome),
        procedure=content.strip()[:4000],  # match service-layer upper bound
        tokens=tokens,
        duration_ms=duration_ms,
        tags=tags[:16],  # match service-layer upper bound
    )


# ─── Source protocol + orchestration ─────────────────────────────────


class EpisodeSource(Protocol):
    """Anything iterating over LAM episode dicts. Lets us swap in a fake
    source in tests without a running Qdrant."""

    def iter_episodes(self) -> Iterator[dict[str, Any]]:
        ...


def backfill_all(
    source: EpisodeSource,
    service: ExperienceService,
    dry_run: bool = True,
) -> dict[str, int]:
    """Run the backfill over *source*.

    Returns a report with counts:
        total_seen / recorded / would_record / skipped_ambiguous /
        skipped_empty / skipped_unknown_id / errors.
    """
    report = {
        "total_seen": 0,
        "recorded": 0,
        "would_record": 0,
        "skipped_ambiguous": 0,
        "skipped_empty": 0,
        "skipped_unknown_id": 0,
        "errors": 0,
    }
    for ep in source.iter_episodes():
        report["total_seen"] += 1
        content = ep.get("content")
        if not isinstance(content, str) or not content.strip():
            report["skipped_empty"] += 1
            continue
        outcome = normalize_outcome(ep.get("outcome"))
        if outcome is None:
            report["skipped_ambiguous"] += 1
            continue
        if not str(ep.get("id") or "").strip():
            report["skipped_unknown_id"] += 1
            continue

        rec = build_trajectory_record(ep)
        if rec is None:  # pragma: no cover — defensive
            report["errors"] += 1
            continue

        if dry_run:
            report["would_record"] += 1
            logger.info(
                "[DRY] would record %s (outcome=%s, cell=%s)",
                rec.trajectory_id, rec.outcome, rec.cell,
            )
            continue

        try:
            service.record(rec)
            report["recorded"] += 1
        except Exception:  # pragma: no cover — defensive
            logger.exception("failed to record %s", rec.trajectory_id)
            report["errors"] += 1

    logger.info("backfill report: %s", report)
    return report


# ─── Qdrant scroll source (production path) ─────────────────────────


class _QdrantEpisodeSource:
    """Scrolls the lam_episodes collection lazily. Used only from __main__."""

    def __init__(self, limit: int | None = None) -> None:
        self._limit = limit

    def iter_episodes(self) -> Iterator[dict[str, Any]]:
        from backend.app.core.config import settings
        from backend.core.qdrant_db import QdrantClient

        client = QdrantClient(
            qdrant_url=settings.qdrant_url, collection_name="lam_episodes",
        )
        offset: Any = None
        seen = 0
        while True:
            batch, offset = asyncio.get_event_loop().run_until_complete(
                client.scroll(limit=100, offset=offset),
            )
            if not batch:
                return
            for point in batch:
                payload = getattr(point, "payload", None) or {}
                yield {
                    "id": str(getattr(point, "id", "")),
                    **payload,
                }
                seen += 1
                if self._limit is not None and seen >= self._limit:
                    return
            if offset is None:
                return


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be recorded without writing anywhere.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Stop after N episodes (default: scan all).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    db_path = os.environ.get("EXPERIENCE_DB_PATH")
    service = ExperienceService(db_path=db_path) if db_path else ExperienceService()
    if not service.is_available:  # pragma: no cover
        logger.error("ExperienceService unavailable (cell-core not importable)")
        return 2

    source = _QdrantEpisodeSource(limit=args.limit)
    report = backfill_all(source, service, dry_run=args.dry_run)
    logger.info("done: %s", report)
    return 0 if report["errors"] == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
