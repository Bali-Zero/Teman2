"""Propose (do NOT apply) skill-merge pairs based on embedding cosine.

Philosophy (SYMBIOSIS Legge 5): auto-merge is never automatic. We compute
cosine distance between every pair of active skills' procedures; pairs
under the threshold (default 0.15) are written to a jsonl proposal file.
Zero reads the file, decides, and (optionally) invokes the merge via a
dedicated endpoint — never this script.

Embedding model: ``text-embedding-3-small`` (1536 dims, FROZEN per
CLAUDE.md §6). We do NOT change it here — doing so would invalidate the
93k production vectors.

Usage:

    # Dry-run (default): writes proposals to the default path.
    PYTHONPATH=. python backend/scripts/skill_merge_proposals.py

    # Explicit paths (used in tests and one-off invocations).
    PYTHONPATH=. python backend/scripts/skill_merge_proposals.py \\
        --db-path /tmp/skills.db --out /tmp/proposals.jsonl --threshold 0.12

Safety:
- Read-only on the Genome; all writes go to the proposals file.
- Skips the live OpenAI client when the stub path is taken by tests.
- Handles zero-length vectors (returns infinite distance, never suggests).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from typing import Any, Iterable, Protocol

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """Minimal contract for embedding clients (real and stub)."""

    def embed(self, text: str, skill_id: str | None = None) -> list[float]: ...


# ─── Cosine ──────────────────────────────────────────────────────


def cosine_distance(v1: list[float], v2: list[float]) -> float:
    """Cosine distance in [0, 2]. Identical -> 0, orthogonal -> 1, opposite -> 2.

    Returns +inf for degenerate inputs (zero-length vector) so the caller
    never suggests a merge based on garbage vectors.
    """
    if len(v1) != len(v2):
        raise ValueError(f"vector dim mismatch: {len(v1)} vs {len(v2)}")
    dot = 0.0
    n1 = 0.0
    n2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        n1 += a * a
        n2 += b * b
    if n1 <= 0.0 or n2 <= 0.0:
        return math.inf
    cos_sim = dot / (math.sqrt(n1) * math.sqrt(n2))
    # Clamp because float round-off occasionally yields 1.0000001
    cos_sim = max(-1.0, min(1.0, cos_sim))
    return 1.0 - cos_sim


# ─── Candidate discovery ─────────────────────────────────────────


def find_merge_candidates(
    skills: list[dict[str, Any]],
    embedder: Embedder,
    threshold: float = 0.15,
) -> list[dict[str, Any]]:
    """Return all skill pairs whose cosine distance is < threshold.

    Each candidate dict has:
        pair: [skill_id_a, skill_id_b]
        cosine: float (the distance, not similarity)
        rationale: short human-readable text
        procedures: {a: proc_a, b: proc_b}  # to aid human review
    """
    if len(skills) < 2:
        return []

    # Embed once per skill, keyed by id so the stub can look up by id.
    #
    # DeepSeek review (2026-04-16): embed the FULL (precondition, procedure,
    # success_criterion) triple — not just procedure. Two skills that share
    # a procedure body but apply to different contexts (e.g. tourist vs
    # business visa submission) must stay separate, and the context lives in
    # precondition + success_criterion. The " | " separator is non-semantic
    # but keeps each field legible for a human reading the jsonl.
    vectors: dict[str, list[float]] = {}
    for s in skills:
        sid = s["id"]
        procedure = (s.get("procedure") or "").strip()
        if not procedure:
            continue
        precondition = (s.get("precondition") or "").strip()
        success = (s.get("success_criterion") or "").strip()
        text = f"{precondition} | {procedure} | {success}"
        try:
            vectors[sid] = embedder.embed(text, skill_id=sid)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("embed failed for %s: %s", sid, exc)

    ids = sorted(vectors.keys())
    candidates: list[dict[str, Any]] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = cosine_distance(vectors[a], vectors[b])
            if d >= threshold:
                continue
            proc_a = next((s["procedure"] for s in skills if s["id"] == a), "")
            proc_b = next((s["procedure"] for s in skills if s["id"] == b), "")
            candidates.append({
                "pair": [a, b],
                "cosine": round(d, 6),
                "rationale": (
                    f"cosine distance {d:.4f} < threshold {threshold:.2f}"
                ),
                "procedures": {a: proc_a, b: proc_b},
            })
    return candidates


# ─── Embedder wiring ─────────────────────────────────────────────


def _default_embedder() -> Embedder:
    """Build a real embedder backed by ``EmbeddingsGenerator``.

    Lazy import so tests that monkeypatch this symbol don't pay the OpenAI
    client setup cost.
    """
    from backend.core.embeddings import EmbeddingsGenerator  # pragma: no cover

    gen = EmbeddingsGenerator()

    class _RealEmbedder:
        def embed(self, text: str, skill_id: str | None = None) -> list[float]:
            import asyncio
            return asyncio.run(gen.generate_single_embedding(text))

    return _RealEmbedder()


# ─── Genome scan ─────────────────────────────────────────────────


def _fetch_active_skills(db_path: str) -> list[dict[str, Any]]:
    """Return all active skills (type='skill', not silenced) as plain dicts."""
    import sqlite3
    from datetime import datetime, timezone
    if not os.path.exists(db_path):
        return []
    today = datetime.now(timezone.utc).date().isoformat()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT id, cell_origin, type, procedure, precondition,
                      success_criterion, confidence, valid_to
               FROM genome
               WHERE type='skill' AND (valid_to IS NULL OR valid_to > ?)""",
            (today,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ─── main ───────────────────────────────────────────────────────


def _default_out_path() -> str:
    return os.environ.get(
        "SKILL_MERGE_PROPOSALS_PATH",
        os.path.expanduser("~/.nuzantara/skill_merge_proposals.jsonl"),
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
    parser.add_argument(
        "--threshold", type=float, default=0.15,
        help="Cosine distance below which a pair is proposed (default 0.15).",
    )
    args = parser.parse_args(argv)

    skills = _fetch_active_skills(args.db_path)
    if len(skills) < 2:
        logger.info("fewer than 2 active skills; nothing to propose.")
        # Truncate the output file so consumers see a fresh empty state.
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        open(args.out, "w").close()
        return 0

    embedder = _default_embedder()
    candidates = find_merge_candidates(skills, embedder=embedder, threshold=args.threshold)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for c in candidates:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    logger.info(
        "proposals written: %d pairs (threshold=%.3f) -> %s",
        len(candidates), args.threshold, args.out,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
