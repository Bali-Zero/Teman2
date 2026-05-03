#!/usr/bin/env python3
"""
CLI entry point for politics KB hierarchical ingest + eval.

Usage:
    cd apps/backend-rag
    PYTHONPATH=. python scripts/ingest_kb_politics_hier.py [--eval] [--qdrant-url URL]

Options:
    --eval          Run evaluation after ingest
    --qdrant-url    Qdrant URL (default: http://localhost:6333)
    --kb-root       KB root directory (default: backend/kb/politics/id)
    --dry-run       Chunk only, don't upsert to Qdrant
"""

from __future__ import annotations

import argparse
import json
import logging
import resource
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.kb.politics.hierarchical.chunker import HierarchicalChunker
from backend.kb.politics.hierarchical.embedder import LocalEmbedder
from backend.kb.politics.hierarchical.ingest import HierarchicalIngestor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest_kb_politics_hier")


def get_peak_ram_mb() -> float:
    """Get peak RSS in MB (macOS/Linux)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS reports in bytes, Linux in KB
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest politics KB with hierarchical chunking")
    parser.add_argument("--qdrant-url", default="http://localhost:6333", help="Qdrant URL")
    parser.add_argument("--kb-root", default=None, help="KB root directory")
    parser.add_argument("--eval", action="store_true", help="Run evaluation after ingest")
    parser.add_argument("--dry-run", action="store_true", help="Chunk only, don't upsert")
    parser.add_argument("--model", default=None, help="Embedding model override")
    args = parser.parse_args()

    # Resolve KB root
    script_dir = Path(__file__).resolve().parent.parent
    kb_root = Path(args.kb_root) if args.kb_root else script_dir / "backend" / "kb" / "politics" / "id"

    if not kb_root.is_dir():
        logger.error(f"KB root not found: {kb_root}")
        sys.exit(1)

    logger.info(f"KB root: {kb_root}")
    logger.info(f"Qdrant: {args.qdrant_url}")

    start = time.perf_counter()

    if args.dry_run:
        # Dry run: chunk only
        chunker = HierarchicalChunker()
        chunks = chunker.chunk_directory(kb_root)
        parents = sum(1 for c in chunks if c.chunk_type == "parent")
        children = sum(1 for c in chunks if c.chunk_type == "child")
        logger.info(f"Dry run: {len(chunks)} chunks ({parents} parents, {children} children)")
        for chunk in chunks[:5]:
            logger.info(f"  [{chunk.chunk_type}] {chunk.id[:12]}... {chunk.text[:80]}")
    else:
        # Full ingest
        embedder = LocalEmbedder(model_name=args.model)
        ingestor = HierarchicalIngestor(
            qdrant_url=args.qdrant_url,
            embedder=embedder,
        )
        try:
            stats = ingestor.ingest_directory(kb_root)
            stats["peak_ram_mb"] = round(get_peak_ram_mb(), 1)
            logger.info(f"\n{'='*60}")
            logger.info("INGEST STATS:")
            for k, v in stats.items():
                logger.info(f"  {k}: {v}")
            logger.info(f"{'='*60}")
        finally:
            ingestor.close()

    elapsed = time.perf_counter() - start
    logger.info(f"Total runtime: {elapsed:.2f}s | Peak RAM: {get_peak_ram_mb():.1f} MB")

    # Optional eval
    if args.eval and not args.dry_run:
        logger.info("\n--- Running evaluation ---")
        eval_path = script_dir / "backend" / "kb" / "politics" / "eval" / "seed_queries.jsonl"
        if not eval_path.exists():
            logger.error(f"Eval file not found: {eval_path}")
            sys.exit(1)

        from backend.kb.politics.hierarchical.eval import evaluate, load_eval_queries
        from backend.kb.politics.hierarchical.retriever import HierarchicalRetriever

        retriever = HierarchicalRetriever(
            qdrant_url=args.qdrant_url,
            embedder=embedder,
        )
        try:
            queries = load_eval_queries(eval_path)
            summary = evaluate(retriever, queries)

            logger.info(f"\n{'='*60}")
            logger.info("EVAL RESULTS:")
            logger.info(f"  Total queries: {summary.total_queries}")
            logger.info(f"  Hard labels: {summary.hard_label_queries}")
            logger.info(f"  Weak labels: {summary.weak_label_queries}")
            logger.info(f"  Mean nDCG@5 (all): {summary.mean_ndcg_at_5}")
            logger.info(f"  Mean Recall@5 (all): {summary.mean_recall_at_5}")
            logger.info(f"  Mean nDCG@5 (hard): {summary.mean_ndcg_hard_labels}")
            logger.info(f"  Mean Recall@5 (hard): {summary.mean_recall_hard_labels}")
            logger.info(f"\nPer-query breakdown:")
            for r in summary.per_query:
                weak = " [WEAK]" if r.weak_label else ""
                logger.info(
                    f"  nDCG={r.ndcg_at_5:.3f} Recall={r.recall_at_5:.3f}{weak} | "
                    f"{r.query[:60]}"
                )
            logger.info(f"{'='*60}")
        finally:
            retriever.close()


if __name__ == "__main__":
    main()
