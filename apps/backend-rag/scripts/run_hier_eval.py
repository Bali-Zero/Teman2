#!/usr/bin/env python3
"""
Standalone ingest + eval using qdrant-client in-memory mode.

Supports dense-only and hybrid (dense + BM25 sparse) modes.
No external Qdrant server required.

Usage:
    cd apps/backend-rag
    PYTHONPATH=. python scripts/run_hier_eval.py               # hybrid (default)
    PYTHONPATH=. python scripts/run_hier_eval.py --dense-only   # dense only
"""

from __future__ import annotations

import argparse
import logging
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, PointStruct, SparseVector, VectorParams

from backend.kb.politics.hierarchical.chunker import HierarchicalChunker
from backend.kb.politics.hierarchical.embedder import BM25SparseEncoder, LocalEmbedder
from backend.kb.politics.hierarchical.eval import (
    _ndcg_at_k,
    _recall_at_k,
    load_eval_queries,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_hier_eval")

COLLECTION = "kb_politics_hier_v1"


def get_peak_ram_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


def main() -> None:
    parser = argparse.ArgumentParser(description="Run hierarchical eval")
    parser.add_argument("--dense-only", action="store_true", help="Skip BM25 sparse vectors")
    args = parser.parse_args()

    hybrid = not args.dense_only
    mode_str = "HYBRID (dense + BM25)" if hybrid else "DENSE-ONLY"

    script_dir = Path(__file__).resolve().parent.parent
    kb_root = script_dir / "backend" / "kb" / "politics" / "id"
    eval_path = script_dir / "backend" / "kb" / "politics" / "eval" / "seed_queries.jsonl"

    start = time.perf_counter()

    # 1. Chunk
    logger.info(f"Mode: {mode_str}")
    logger.info(f"Chunking from {kb_root}")
    chunker = HierarchicalChunker()
    chunks = chunker.chunk_directory(kb_root)
    parents = [c for c in chunks if c.chunk_type == "parent"]
    children = [c for c in chunks if c.chunk_type == "child"]
    texts = [c.text for c in chunks]

    # 2. Dense embed
    logger.info("Loading embedder...")
    embedder = LocalEmbedder()
    logger.info("Embedding chunks (dense)...")
    dense_vecs = embedder.embed_chunks(chunks)
    dims = embedder.dimensions

    # 3. Sparse embed (BM25)
    sparse_encoder: BM25SparseEncoder | None = None
    sparse_vecs: list[dict] | None = None
    if hybrid:
        logger.info("Building BM25 sparse vectors...")
        sparse_encoder = BM25SparseEncoder()
        sparse_encoder.fit(texts)
        sparse_vecs = sparse_encoder.encode_documents(texts)
        logger.info(f"BM25 vocab: {sparse_encoder.vocab_size} terms")

    # 4. Create in-memory Qdrant
    logger.info("Creating in-memory Qdrant collection...")
    client = QdrantClient(":memory:")

    vectors_config = {"dense": models.VectorParams(size=dims, distance=Distance.COSINE)}
    sparse_config = {}
    if hybrid:
        sparse_config = {"sparse": models.SparseVectorParams()}

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=vectors_config,
        sparse_vectors_config=sparse_config if sparse_config else None,
    )

    # 5. Upsert
    points = []
    for i, (chunk, dvec) in enumerate(zip(chunks, dense_vecs)):
        vector: dict = {"dense": dvec}
        if hybrid and sparse_vecs:
            sv = sparse_vecs[i]
            if sv["indices"]:
                vector["sparse"] = SparseVector(
                    indices=sv["indices"], values=sv["values"],
                )

        payload = {
            "text": chunk.text,
            "chunk_type": chunk.chunk_type,
            "record_id": chunk.record_id,
            "record_type": chunk.record_type,
            "source_path": chunk.source_path,
            "offset": chunk.offset,
            "language": chunk.language,
            "domain": "politics-id",
        }
        if chunk.parent_id is not None:
            payload["parent_id"] = chunk.parent_id
        for k, v in chunk.metadata.items():
            if k not in payload and v is not None:
                payload[k] = v

        points.append(PointStruct(id=chunk.id, vector=vector, payload=payload))

    client.upsert(collection_name=COLLECTION, points=points)
    logger.info(f"Upserted {len(points)} points")

    embed_time = time.perf_counter() - start

    # 6. Evaluate
    logger.info("Loading eval queries...")
    queries = load_eval_queries(eval_path)
    logger.info(f"Loaded {len(queries)} queries")

    per_query: list[dict] = []
    for eq in queries:
        qvec = embedder.embed_query(eq.query)

        # Build search depending on mode
        child_filter = models.Filter(
            must=[models.FieldCondition(key="chunk_type", match=models.MatchValue(value="child"))],
        )

        if hybrid and sparse_encoder:
            sq = sparse_encoder.encode_query(eq.query)

            # Use prefetch + RRF fusion
            search_result = client.query_points(
                collection_name=COLLECTION,
                prefetch=[
                    models.Prefetch(
                        query=qvec,
                        using="dense",
                        limit=20,
                        filter=child_filter,
                    ),
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=sq["indices"], values=sq["values"],
                        ),
                        using="sparse",
                        limit=20,
                        filter=child_filter,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=20,
                with_payload=True,
            )
        else:
            search_result = client.query_points(
                collection_name=COLLECTION,
                query=qvec,
                using="dense",
                limit=20,
                query_filter=child_filter,
                with_payload=True,
            )

        # Aggregate by parent
        parent_scores: dict[str, float] = {}
        parent_records: dict[str, str] = {}
        for hit in search_result.points:
            pid = hit.payload.get("parent_id")
            if pid:
                parent_scores[pid] = parent_scores.get(pid, 0.0) + hit.score
                parent_records[pid] = hit.payload.get("record_id", "")

        sorted_parents = sorted(parent_scores.items(), key=lambda x: x[1], reverse=True)
        retrieved_record_ids = [parent_records.get(pid, "") for pid, _ in sorted_parents[:5]]

        relevant_set = set(eq.relevant_doc_ids)
        ndcg = _ndcg_at_k(retrieved_record_ids, relevant_set, 5)
        recall = _recall_at_k(retrieved_record_ids, relevant_set, 5)

        per_query.append({
            "query": eq.query,
            "ndcg_at_5": round(ndcg, 4),
            "recall_at_5": round(recall, 4),
            "retrieved": retrieved_record_ids,
            "relevant": eq.relevant_doc_ids,
            "weak_label": eq.weak_label,
            "query_type": eq.query_type,
        })

    elapsed = time.perf_counter() - start

    # 7. Report
    all_ndcg = [r["ndcg_at_5"] for r in per_query]
    all_recall = [r["recall_at_5"] for r in per_query]
    hard = [r for r in per_query if not r["weak_label"]]
    hard_ndcg = [r["ndcg_at_5"] for r in hard]
    hard_recall = [r["recall_at_5"] for r in hard]

    print(f"\n{'=' * 70}")
    print(f"MODE: {mode_str}")
    print(f"{'=' * 70}")
    print("INGEST STATS")
    print(f"  Docs processed:    {len(parents)}")
    print(f"  Parents:           {len(parents)}")
    print(f"  Children:          {len(children)}")
    print(f"  Total vectors:     {len(chunks)}")
    print(f"  Embedding model:   {embedder.model_name}")
    print(f"  Embedding dims:    {dims}")
    if sparse_encoder:
        print(f"  BM25 vocab:        {sparse_encoder.vocab_size} terms")
    print(f"  Ingest runtime:    {embed_time:.2f}s")
    print(f"  Peak RAM:          {get_peak_ram_mb():.1f} MB")

    print(f"\n{'=' * 70}")
    print("EVAL RESULTS")
    print(f"{'=' * 70}")
    print(f"  Total queries:     {len(per_query)}")
    print(f"  Hard labels:       {len(hard)}")
    print(f"  Weak labels:       {len(per_query) - len(hard)}")
    print(f"  Mean nDCG@5 (all): {sum(all_ndcg) / len(all_ndcg):.4f}")
    print(f"  Mean Recall@5 (all): {sum(all_recall) / len(all_recall):.4f}")
    print(f"  Mean nDCG@5 (hard): {sum(hard_ndcg) / len(hard_ndcg):.4f}")
    print(f"  Mean Recall@5 (hard): {sum(hard_recall) / len(hard_recall):.4f}")

    print(f"\n{'Query':<55} {'nDCG':>6} {'Rec':>6} {'Label':>6}")
    print("-" * 78)
    for r in per_query:
        label = "WEAK" if r["weak_label"] else "HARD"
        q = r["query"][:52] + "..." if len(r["query"]) > 55 else r["query"]
        print(f"  {q:<53} {r['ndcg_at_5']:>6.3f} {r['recall_at_5']:>6.3f}  {label}")

    print(f"{'=' * 70}")
    print(f"Total runtime: {elapsed:.2f}s | Peak RAM: {get_peak_ram_mb():.1f} MB")


if __name__ == "__main__":
    main()
