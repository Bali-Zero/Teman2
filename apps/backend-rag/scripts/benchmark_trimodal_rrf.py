"""Benchmark Trimodal RRF: weight=0 (bimodal baseline) vs 0.3 vs 0.5.

We do not have a labelled gold-standard query set for legal_unified. Instead
we evaluate proxy metrics that correlate with RAG downstream quality:

    - coverage@10: fraction of top-10 results that have at least one
      kg_entity_mention (high coverage = well-grounded results)
    - kg_mentions_per_result@10: avg # of linked entities per top-10 doc
    - shift@10: Jaccard distance vs bimodal baseline (signals how much
      adding graph weight changes the ranking)

Procedure for each of N benchmark queries:
    1. Call HybridSearchService.search_hybrid (bimodal → dense_results +
       sparse_results, reconstructed via alpha=1.0 and alpha=0.0 probes).
    2. Build graph_results from kg_entity_mentions: point_ids with the
       most mentions linked to entities matching the query's detected
       entity types (matches the query-time strategy documented in
       kg_enhanced_retrieval.py).
    3. Run reciprocal_rank_fusion_trimodal with 3 weight configs.
    4. Compute proxy metrics and emit a JSON report.

Usage:
    PYTHONPATH=. python scripts/benchmark_trimodal_rrf.py \
        --collection legal_unified_hybrid_hybrid --queries-file queries.txt \
        --output docs/graphrag-rrf-weight-decision.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import asyncpg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from qdrant_client import AsyncQdrantClient  # noqa: E402

def _require_env(name: str) -> str:
    import os as _os
    val = _os.environ.get(name)
    if not val:
        raise SystemExit(f"{name} env var is required (no hardcoded fallback for security)")
    return val



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("benchmark_trimodal")


DB_URL = _require_env("ENTITY_LINKER_DB_URL")
QDRANT_URL = _require_env("QDRANT_URL")
QDRANT_API_KEY = _require_env("QDRANT_API_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

RRF_K = 60
TOP_K = 10
DEFAULT_QUERIES = [
    "persyaratan KITAS untuk investor asing",
    "UU Cipta Kerja ketenagakerjaan",
    "NIB untuk PT PMA di Bali",
    "KBLI konsultasi manajemen",
    "PPh 21 karyawan expat",
    "izin usaha restoran di Bali",
    "Permen perlindungan data pribadi",
    "BPJS Kesehatan pekerja asing",
    "visa tinggal terbatas investor",
    "persyaratan modal PMA minimum",
    "Peraturan Pemerintah tentang OSS",
    "imigrasi izin tinggal KITAP",
]


def _rrf_bimodal(
    dense: list[dict[str, Any]],
    sparse: list[dict[str, Any]],
    alpha: float = 0.5,
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    ranks: dict[str, dict[str, Any]] = {}
    for rank, r in enumerate(dense, 1):
        did = str(r.get("id") or r.get("_id") or "")
        if not did:
            continue
        ranks.setdefault(did, {"result": r})["dense_rank"] = rank
    for rank, r in enumerate(sparse, 1):
        did = str(r.get("id") or r.get("_id") or "")
        if not did:
            continue
        ranks.setdefault(did, {"result": r})["sparse_rank"] = rank
    fused: list[dict[str, Any]] = []
    for did, data in ranks.items():
        score = 0.0
        if data.get("dense_rank") is not None:
            score += alpha / (k + data["dense_rank"])
        if data.get("sparse_rank") is not None:
            score += (1 - alpha) / (k + data["sparse_rank"])
        fused.append({"id": did, "fusion_score": score, "result": data["result"]})
    fused.sort(key=lambda x: x["fusion_score"], reverse=True)
    return fused


def _rrf_trimodal(
    dense: list[dict[str, Any]],
    sparse: list[dict[str, Any]],
    graph: list[dict[str, Any]],
    weights: tuple[float, float, float],
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    w_dense, w_sparse, w_graph = weights
    ranks: dict[str, dict[str, Any]] = {}
    for rank, r in enumerate(dense, 1):
        did = str(r.get("id") or r.get("_id") or "")
        if not did:
            continue
        ranks.setdefault(did, {"result": r})["dense_rank"] = rank
    for rank, r in enumerate(sparse, 1):
        did = str(r.get("id") or r.get("_id") or "")
        if not did:
            continue
        ranks.setdefault(did, {"result": r})["sparse_rank"] = rank
    for rank, r in enumerate(graph, 1):
        did = str(r.get("id") or r.get("_id") or "")
        if not did:
            continue
        ranks.setdefault(did, {"result": r})["graph_rank"] = rank

    fused: list[dict[str, Any]] = []
    for did, data in ranks.items():
        score = 0.0
        if data.get("dense_rank") is not None:
            score += w_dense / (k + data["dense_rank"])
        if data.get("sparse_rank") is not None:
            score += w_sparse / (k + data["sparse_rank"])
        if data.get("graph_rank") is not None:
            score += w_graph / (k + data["graph_rank"])
        fused.append({"id": did, "fusion_score": score, "result": data["result"]})
    fused.sort(key=lambda x: x["fusion_score"], reverse=True)
    return fused


_QUERY_ENTITY_RE = [
    re.compile(r"KBLI\s*(\d{4,5})", re.IGNORECASE),
    re.compile(r"\b(KITAS|KITAP|VITAS|KUNJUNGAN|B211A?|C312|VOA)\b", re.IGNORECASE),
    re.compile(r"\b(NIB|SIUP|TDP|NPWP|IMB|AMDAL|OSS|RPTKA|IMTA)\b", re.IGNORECASE),
    re.compile(r"\b(PT\s*PMA|PT\s*PMDN|CV)\b", re.IGNORECASE),
    re.compile(r"\b(PPh\s*\d{1,2}|PPN|PBB|BPHTB|SPT)\b", re.IGNORECASE),
    re.compile(r"\b(BKPM|DJP|Kemenkumham|Kemenaker|Imigrasi|BPN)\b", re.IGNORECASE),
    re.compile(r"\b(BPJS)\b", re.IGNORECASE),
]


def extract_query_entities(query: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pat in _QUERY_ENTITY_RE:
        for m in pat.finditer(query):
            term = m.group(0).strip().lower()
            if term and term not in seen:
                seen.add(term)
                found.append(term)
    return found


async def _embed_query(query: str) -> list[float]:
    """Use OpenAI text-embedding-3-small via REST to stay decoupled from app deps."""
    import httpx

    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": "text-embedding-3-small", "input": query},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


async def _dense_search(
    qdrant: AsyncQdrantClient,
    collection: str,
    query_vec: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    """Dense vector search via query_points (qdrant-client ≥ 2.x).

    legal_unified_hybrid_hybrid uses named vectors (`dense` + `bm25`).
    """
    try:
        response = await qdrant.query_points(
            collection_name=collection,
            query=query_vec,
            using="dense",
            limit=limit,
            with_payload=True,
        )
    except Exception as exc:
        logger.debug("Named vector 'dense' failed: %s — retrying default", exc)
        response = await qdrant.query_points(
            collection_name=collection,
            query=query_vec,
            limit=limit,
            with_payload=True,
        )
    return [{"id": str(h.id), "score": float(h.score), "payload": h.payload} for h in response.points]


async def _bm25_search(
    qdrant: AsyncQdrantClient,
    collection: str,
    query_text: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Fallback BM25-like search via Qdrant payload text scroll + simple TF.

    Production bm25 uses ingested sparse vectors; for benchmark we proxy with
    payload keyword scroll (adequate for relative comparison).
    """
    # Use query_points with a sparse vector if BM25 index exists; for this benchmark
    # we emulate BM25 by scrolling payloads matching any query token.
    tokens = [t for t in re.split(r"\W+", query_text.lower()) if len(t) >= 3]
    if not tokens:
        return []
    # Use Qdrant filter full-text match on `text` field.
    from qdrant_client.http.models import FieldCondition, Filter, MatchText

    results: dict[str, dict[str, Any]] = {}
    for token in tokens[:6]:  # cap to 6 tokens to keep it bounded
        try:
            hits, _ = await qdrant.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    should=[FieldCondition(key="text", match=MatchText(text=token))],
                ),
                limit=limit * 3,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            logger.debug("BM25 scroll token=%s failed: %s", token, exc)
            continue
        for h in hits:
            pid = str(h.id)
            results.setdefault(pid, {"id": pid, "payload": h.payload, "score": 0.0})
            results[pid]["score"] += 1.0  # simple TF across tokens
    ranked = sorted(results.values(), key=lambda x: x["score"], reverse=True)[:limit]
    return ranked


async def _graph_search(
    pool: asyncpg.Pool,
    collection: str,
    query_entities: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    """Return point_ids ranked by number of query-entity mentions.

    Uses kg_entity_mentions + kg_nodes. Selects mentions whose LOWER(mention_text)
    matches any query entity (substring match).
    """
    if not query_entities:
        return []
    rows = await pool.fetch(
        """
        SELECT m.point_id, COUNT(*) AS cnt
        FROM kg_entity_mentions m
        WHERE m.collection_name = $1
          AND LOWER(m.mention_text) = ANY($2::text[])
        GROUP BY m.point_id
        ORDER BY cnt DESC
        LIMIT $3
        """,
        collection,
        query_entities,
        limit,
    )
    return [{"id": r["point_id"], "score": float(r["cnt"])} for r in rows]


async def _mention_coverage(
    pool: asyncpg.Pool,
    collection: str,
    point_ids: list[str],
) -> tuple[int, int]:
    """Return (points_with_mentions, total_mentions_across_all_points)."""
    if not point_ids:
        return 0, 0
    rows = await pool.fetch(
        """
        SELECT m.point_id, COUNT(*) AS cnt
        FROM kg_entity_mentions m
        WHERE m.collection_name = $1 AND m.point_id = ANY($2::text[])
        GROUP BY m.point_id
        """,
        collection,
        point_ids,
    )
    covered = len(rows)
    total = sum(int(r["cnt"]) for r in rows)
    return covered, total


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


async def run_benchmark(
    queries: list[str],
    collection: str,
    weights_configs: list[tuple[float, float, float]],
    top_k: int = TOP_K,
) -> dict[str, Any]:
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=4)
    qdrant = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)

    per_query: list[dict[str, Any]] = []
    try:
        for qi, query in enumerate(queries, 1):
            logger.info("[%d/%d] %s", qi, len(queries), query)
            t0 = time.time()

            # Get embedding + run dense + sparse + graph candidate lists
            try:
                qvec = await _embed_query(query)
            except Exception as exc:
                logger.warning("embed failed: %s — skipping query", exc)
                continue

            dense = await _dense_search(qdrant, collection, qvec, limit=top_k * 4)
            sparse = await _bm25_search(qdrant, collection, query, limit=top_k * 4)
            qents = extract_query_entities(query)
            graph = await _graph_search(pool, collection, qents, limit=top_k * 4)

            logger.info(
                "  dense=%d sparse=%d graph=%d (qents=%s)",
                len(dense),
                len(sparse),
                len(graph),
                qents,
            )

            variants: dict[str, list[dict[str, Any]]] = {}
            for weights in weights_configs:
                name = f"w={weights}"
                if weights[2] == 0.0:
                    fused = _rrf_bimodal(
                        dense,
                        sparse,
                        alpha=weights[0] / (weights[0] + weights[1]) if (weights[0] + weights[1]) else 0.5,
                    )
                else:
                    fused = _rrf_trimodal(dense, sparse, graph, weights=weights)
                variants[name] = fused[:top_k]

            # Coverage on top-k for each variant
            per_variant: dict[str, dict[str, Any]] = {}
            baseline_ids = [r["id"] for r in variants[f"w={weights_configs[0]}"]]
            for name, ranked in variants.items():
                ids = [r["id"] for r in ranked]
                covered, total = await _mention_coverage(pool, collection, ids)
                per_variant[name] = {
                    "top_ids": ids,
                    "coverage_at_k": round(covered / max(1, len(ids)), 3),
                    "mentions_per_result": round(total / max(1, len(ids)), 2),
                    "jaccard_vs_baseline": round(_jaccard(baseline_ids, ids), 3),
                }

            per_query.append(
                {
                    "query": query,
                    "query_entities": qents,
                    "variants": per_variant,
                    "elapsed_s": round(time.time() - t0, 2),
                },
            )
    finally:
        await qdrant.close()
        await pool.close()

    # Aggregate
    aggregates: dict[str, dict[str, float]] = {}
    for weights in weights_configs:
        name = f"w={weights}"
        covs = [q["variants"][name]["coverage_at_k"] for q in per_query if name in q["variants"]]
        mpr = [q["variants"][name]["mentions_per_result"] for q in per_query if name in q["variants"]]
        jac = [q["variants"][name]["jaccard_vs_baseline"] for q in per_query if name in q["variants"]]
        aggregates[name] = {
            "mean_coverage_at_k": round(statistics.mean(covs) if covs else 0.0, 3),
            "mean_mentions_per_result": round(statistics.mean(mpr) if mpr else 0.0, 2),
            "mean_jaccard_vs_baseline": round(statistics.mean(jac) if jac else 1.0, 3),
            "n_queries": len(covs),
        }

    return {"per_query": per_query, "aggregates": aggregates}


def _render_markdown(
    report: dict[str, Any],
    weights_configs: list[tuple[float, float, float]],
) -> str:
    lines = [
        "# Trimodal RRF Weight Decision — GraphRAG 2.0",
        "",
        "Generated: 2026-04-17 (Air-3 session)",
        "",
        "## Method",
        "",
        f"- Collection: `legal_unified_hybrid_hybrid` ({len(report['per_query'])} queries)",
        "- Proxy metrics (no gold labels available in this collection):",
        "    - **coverage@10** — fraction of top-10 docs with ≥1 `kg_entity_mentions` link",
        "    - **mentions_per_result@10** — avg linked entities per top-10 doc",
        "    - **jaccard_vs_baseline** — Jaccard similarity of top-10 id set vs w=(0.5,0.5,0.0)",
        "- dense = Qdrant named-vector `dense` search on `text-embedding-3-small`",
        "- sparse = payload full-text match proxy (BM25 index not queried directly here)",
        "- graph = mentions count for query-detected entities in `kg_entity_mentions`",
        "",
        "## Configurations",
        "",
        "| name | dense | sparse | graph |",
        "|------|-------|--------|-------|",
    ]
    for w in weights_configs:
        lines.append(f"| w={w} | {w[0]} | {w[1]} | {w[2]} |")

    lines.extend(["", "## Aggregate results", "", "| variant | coverage@10 | mentions/result | jaccard vs baseline | n |", "|---|---|---|---|---|"])
    for name, agg in report["aggregates"].items():
        lines.append(
            f"| {name} | {agg['mean_coverage_at_k']} | {agg['mean_mentions_per_result']} | {agg['mean_jaccard_vs_baseline']} | {agg['n_queries']} |",
        )

    lines.extend(["", "## Per-query detail", ""])
    for q in report["per_query"]:
        lines.append(f"### {q['query']}")
        lines.append(f"- entities detected: `{q['query_entities']}`")
        lines.append("- variants:")
        for name, v in q["variants"].items():
            lines.append(
                f"    - {name}: cov={v['coverage_at_k']} mpr={v['mentions_per_result']} "
                f"jac={v['jaccard_vs_baseline']}",
            )
        lines.append("")

    # Decision heuristic
    configs = list(report["aggregates"].items())
    # Prefer the config with highest mean_coverage_at_k that is not too far from baseline
    baseline = configs[0][1]["mean_coverage_at_k"]
    picked = configs[0][0]
    best = baseline
    for name, agg in configs[1:]:
        if agg["mean_coverage_at_k"] > best + 0.02 and agg["mean_jaccard_vs_baseline"] > 0.4:
            picked = name
            best = agg["mean_coverage_at_k"]

    lines.extend(
        [
            "## Decision",
            "",
            f"- **Picked:** `{picked}`",
            f"- Baseline coverage@10 = {baseline}, picked coverage@10 = {best}",
            "- Rationale: prefer highest coverage@10 (grounded in KG) provided the",
            "  result set is not a radical departure from bimodal (jaccard ≥ 0.4),",
            "  which would indicate graph signal is dominating rather than",
            "  augmenting.",
            "",
            "## Caveats",
            "",
            "- Proxy metrics, not human-labelled relevance. MRR/NDCG/Recall require a",
            "  gold-standard Q→relevant-doc dataset that does not yet exist for this",
            "  collection.",
            "- Sparse branch is a payload full-text proxy; native BM25 sparse vectors",
            "  would yield slightly different rankings but similar deltas across",
            "  weight configurations.",
            "- Next step: collect 50-100 gold-labelled queries (e.g. from production",
            "  Zantara logs with user-clicked citations) and rerun with MRR/NDCG/Recall.",
            "",
        ],
    )
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="legal_unified_hybrid_hybrid")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[3] / "docs" / "graphrag-rrf-weight-decision.md"),
    )
    parser.add_argument("--queries-file", default=None)
    args = parser.parse_args()

    if args.queries_file:
        queries = [q.strip() for q in Path(args.queries_file).read_text(encoding="utf-8").splitlines() if q.strip()]
    else:
        queries = DEFAULT_QUERIES

    weights_configs = [
        (0.5, 0.5, 0.0),   # baseline: bimodal, graph OFF
        (0.4, 0.3, 0.3),   # balanced: graph contributes a third
        (0.35, 0.15, 0.5), # graph-heavy
    ]

    report = await run_benchmark(queries, args.collection, weights_configs, top_k=args.top_k)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render_markdown(report, weights_configs), encoding="utf-8")
    logger.info("Wrote report -> %s", out_path)
    print("AGGREGATES:", json.dumps(report["aggregates"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
