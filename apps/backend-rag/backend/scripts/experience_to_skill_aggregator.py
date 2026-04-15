"""Aggregate successful trajectories into proposed Skill Registry entries.

Philosophy: when the same (cell, tags) combination shows up N times in a
rolling window with outcome='success', there's a distillable skill hiding
underneath. We propose, never auto-create (SYMBIOSIS Legge 5). Zero reads
the proposals file, picks which ones to record manually — or uses a future
approval endpoint.

Cluster key: (cell_origin, sorted_tags_tuple). We only look at tags the
trajectories already share — no semantic matching, no embeddings. This is
the "safe" aggregation; embedding-based clustering is the Day 5 job
(skill_merge_proposals) applied to *already-recorded* skills.

Usage:

    # Dry-run (proposals only, never writes the skill).
    PYTHONPATH=. python backend/scripts/experience_to_skill_aggregator.py

    # Tighten the cluster size for focused domains:
    PYTHONPATH=. python backend/scripts/experience_to_skill_aggregator.py \\
        --min-cluster-size 15 --window-days 14

Output: SKILL_CREATION_PROPOSALS_PATH (default
~/.nuzantara/skill_creation_proposals.jsonl), one JSON object per line.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Aggregated proposals deliberately get a lower confidence than curated
# seed skills: a distilled procedure inferred from episodes is less solid
# than a hand-written runbook entry. If Zero approves it can be bumped.
_DEFAULT_PROPOSED_CONFIDENCE = 0.45


# ─── Clustering ──────────────────────────────────────────────────


def _parse_tags(tags_field: Any) -> list[str]:
    if isinstance(tags_field, list):
        return [str(t) for t in tags_field]
    if isinstance(tags_field, str) and tags_field:
        try:
            parsed = json.loads(tags_field)
            if isinstance(parsed, list):
                return [str(t) for t in parsed]
        except json.JSONDecodeError:
            pass
    return []


def cluster_trajectories(
    trajectories: list[dict[str, Any]],
    window_days: int = 7,
) -> dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]]:
    """Group success-outcome trajectories by (cell, sorted_tags_tuple).

    Excludes:
    - non-success outcomes (failure / partial stay in the Experience layer only)
    - untagged trajectories (no safe cluster key)
    - trajectories older than *window_days* relative to today
    """
    today = datetime.now(timezone.utc).date()
    clusters: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for t in trajectories:
        if t.get("outcome") != "success":
            continue
        tags = _parse_tags(t.get("tags"))
        if not tags:
            continue
        try:
            vf = datetime.fromisoformat(t["valid_from"]).date()
        except (KeyError, ValueError):
            continue
        # window_days=7 keeps days_ago in [0, 6] — one calendar week ending today.
        if (today - vf).days >= window_days:
            continue
        key = (t.get("cell_origin", ""), tuple(sorted(set(tags))))
        clusters[key].append(t)
    return dict(clusters)


# ─── Proposal synthesis ─────────────────────────────────────────


def _synthesise_procedure(episodes: list[dict[str, Any]]) -> str:
    """Cheap procedure aggregate: take the most common procedure + count.

    We do NOT paraphrase with an LLM here — that's human review territory.
    The human sees the raw sample and decides the real skill body.
    """
    from collections import Counter
    procs = [e.get("procedure", "").strip() for e in episodes if e.get("procedure")]
    if not procs:
        return "aggregated from successful trajectories"
    most = Counter(procs).most_common(1)[0][0]
    return (
        f"Proposed from {len(episodes)} successful trajectories. "
        f"Most common body: {most[:400]}"
    )


def propose_skills_from_clusters(
    clusters: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]],
    min_cluster_size: int = 10,
) -> list[dict[str, Any]]:
    """Emit one proposal per cluster that meets the size threshold."""
    proposals: list[dict[str, Any]] = []
    for (cell, tags_tuple), episodes in clusters.items():
        if len(episodes) < min_cluster_size:
            continue
        tag_slug = "-".join(tags_tuple) or "untagged"
        proposal = {
            "cell": cell,
            "skill_id": f"{cell}:agg_{tag_slug}",
            "tags": list(tags_tuple),
            "n_trajectories": len(episodes),
            "window_start": min(e.get("valid_from", "") for e in episodes),
            "window_end": max(e.get("valid_from", "") for e in episodes),
            "procedure": _synthesise_procedure(episodes),
            "precondition": f"Cell '{cell}' running with tags {list(tags_tuple)}.",
            "success_criterion": (
                f"Outcome reaches 'success' for ≥{min_cluster_size} episodes "
                f"in a 7-day window."
            ),
            "confidence": _DEFAULT_PROPOSED_CONFIDENCE,
            "example_trajectory_ids": [e["id"] for e in episodes[:5]],
        }
        proposals.append(proposal)
    return proposals


# ─── Genome scan ─────────────────────────────────────────────────


def _fetch_active_trajectories(db_path: str) -> list[dict[str, Any]]:
    import sqlite3
    if not os.path.exists(db_path):
        return []
    today = datetime.now(timezone.utc).date().isoformat()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT id, cell_origin, type, outcome, procedure, tags,
                      valid_from, valid_to, confidence
               FROM genome
               WHERE type='trajectory' AND (valid_to IS NULL OR valid_to > ?)""",
            (today,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ─── main ───────────────────────────────────────────────────────


def _default_out_path() -> str:
    return os.environ.get(
        "SKILL_CREATION_PROPOSALS_PATH",
        os.path.expanduser("~/.nuzantara/skill_creation_proposals.jsonl"),
    )


def _default_db_path() -> str:
    return os.environ.get(
        "EXPERIENCE_DB_PATH",
        os.path.expanduser("~/.nuzantara/experience.db"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-path", default=_default_db_path())
    parser.add_argument("--out", default=_default_out_path())
    parser.add_argument("--min-cluster-size", type=int, default=10)
    parser.add_argument("--window-days", type=int, default=7)
    args = parser.parse_args(argv)

    trajectories = _fetch_active_trajectories(args.db_path)
    clusters = cluster_trajectories(trajectories, window_days=args.window_days)
    proposals = propose_skills_from_clusters(
        clusters, min_cluster_size=args.min_cluster_size,
    )

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for p in proposals:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")

    logger.info(
        "proposals written: %d clusters (min_size=%d, window=%dd) -> %s",
        len(proposals), args.min_cluster_size, args.window_days, args.out,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
