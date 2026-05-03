"""
KG Performance Benchmark

Measures latency for core KG operations:
- Entity resolution (exact + fuzzy)
- BFS traversal (1-3 hops)
- Stats queries
- Full pipeline (resolve → traverse → reason)

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python -m backend.scripts.benchmark_kg_performance
"""

import asyncio
import os
import statistics
import time

import asyncpg


async def get_pool() -> asyncpg.Pool:
    """Create a connection pool."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise ValueError("DATABASE_URL not set")
    return await asyncpg.create_pool(dsn, min_size=2, max_size=5)


async def benchmark_exact_resolution(pool: asyncpg.Pool, n: int = 50) -> dict:
    """Benchmark exact entity_id lookup."""
    async with pool.acquire() as conn:
        # Get some real entity_ids to test with
        rows = await conn.fetch("SELECT entity_id FROM kg_nodes ORDER BY RANDOM() LIMIT $1", n)
        entity_ids = [r["entity_id"] for r in rows]

    timings = []
    async with pool.acquire() as conn:
        for eid in entity_ids:
            t0 = time.perf_counter()
            await conn.fetchrow(
                """
                SELECT entity_id, name, confidence, entity_type
                FROM kg_nodes
                WHERE entity_id = $1 OR LOWER(name) = LOWER($2)
                LIMIT 1
                """,
                eid,
                eid,
            )
            timings.append((time.perf_counter() - t0) * 1000)

    return _summarize("Exact Resolution", timings)


async def benchmark_fuzzy_resolution(pool: asyncpg.Pool, n: int = 20) -> dict:
    """Benchmark similarity() fuzzy search."""
    test_terms = [
        "KITAS",
        "NPWP",
        "PT PMA",
        "Hak Pakai",
        "restoran",
        "visa kerja",
        "pajak",
        "izin",
        "notaris",
        "akta",
        "perizinan",
        "pendaftaran",
        "sertifikat",
        "impor",
        "ekspor",
        "tenaga kerja",
        "investasi",
        "perusahaan",
        "lahan",
        "bangunan",
    ]

    timings = []
    async with pool.acquire() as conn:
        for term in test_terms[:n]:
            t0 = time.perf_counter()
            await conn.fetch(
                """
                SELECT entity_id, name, confidence, entity_type,
                       similarity(name, $1) as sim_score
                FROM kg_nodes
                WHERE similarity(name, $1) > 0.7
                ORDER BY sim_score DESC
                LIMIT 3
                """,
                term,
            )
            timings.append((time.perf_counter() - t0) * 1000)

    return _summarize("Fuzzy Resolution (similarity)", timings)


async def benchmark_bfs_traversal(pool: asyncpg.Pool, n: int = 10) -> dict:
    """Benchmark BFS traversal from random starting entities."""
    async with pool.acquire() as conn:
        # Find entities that have outgoing edges (non-orphan)
        rows = await conn.fetch(
            """
            SELECT DISTINCT e.source_entity_id
            FROM kg_edges e
            WHERE e.relationship_type IN ('REQUIRES', 'ENABLES', 'PART_OF')
            ORDER BY RANDOM()
            LIMIT $1
            """,
            n,
        )
        start_ids = [r["source_entity_id"] for r in rows]

    timings = []
    chains_counts = []
    for eid in start_ids:
        async with pool.acquire() as conn:
            t0 = time.perf_counter()
            total_chains = 0
            frontier = [eid]
            visited: set[str] = set()

            for _depth in range(3):
                unvisited = [e for e in frontier if e not in visited]
                if not unvisited:
                    break
                visited.update(unvisited)

                edges = await conn.fetch(
                    """
                    SELECT e.source_entity_id, e.target_entity_id,
                           e.relationship_type, t.confidence
                    FROM kg_edges e
                    JOIN kg_nodes t ON e.target_entity_id = t.entity_id
                    WHERE e.source_entity_id = ANY($1::text[])
                      AND e.relationship_type IN ('REQUIRES', 'ENABLES', 'PART_OF')
                      AND t.confidence > 0.7
                    """,
                    unvisited,
                )
                total_chains += len(edges)
                frontier = [
                    e["target_entity_id"] for e in edges if e["target_entity_id"] not in visited
                ]

            elapsed = (time.perf_counter() - t0) * 1000
            timings.append(elapsed)
            chains_counts.append(total_chains)

    result = _summarize("BFS Traversal (3 hops)", timings)
    result["avg_chains"] = round(statistics.mean(chains_counts), 1) if chains_counts else 0
    return result


async def benchmark_stats_queries(pool: asyncpg.Pool, n: int = 10) -> dict:
    """Benchmark the stats endpoint queries."""
    timings = []
    async with pool.acquire() as conn:
        for _ in range(n):
            t0 = time.perf_counter()
            await conn.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM kg_nodes) as total_nodes,
                    (SELECT COUNT(*) FROM kg_edges) as total_edges
                """,
            )
            await conn.fetch(
                """
                SELECT entity_type, COUNT(*) as count
                FROM kg_nodes
                GROUP BY entity_type
                ORDER BY count DESC
                """,
            )
            await conn.fetch(
                """
                SELECT relationship_type, COUNT(*) as count
                FROM kg_edges
                GROUP BY relationship_type
                ORDER BY count DESC
                """,
            )
            timings.append((time.perf_counter() - t0) * 1000)

    return _summarize("Stats Queries (3 queries)", timings)


async def check_indexes(pool: asyncpg.Pool) -> dict:
    """Check which KG indexes exist."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename IN ('kg_nodes', 'kg_edges')
            ORDER BY tablename, indexname
            """,
        )
    return {r["indexname"]: r["indexdef"] for r in rows}


def _summarize(name: str, timings: list[float]) -> dict:
    """Summarize timing results."""
    if not timings:
        return {"name": name, "n": 0}
    return {
        "name": name,
        "n": len(timings),
        "p50_ms": round(statistics.median(timings), 2),
        "p95_ms": round(sorted(timings)[int(len(timings) * 0.95)], 2)
        if len(timings) >= 2
        else round(timings[0], 2),
        "avg_ms": round(statistics.mean(timings), 2),
        "min_ms": round(min(timings), 2),
        "max_ms": round(max(timings), 2),
    }


async def main() -> None:
    print("=" * 60)
    print("Knowledge Graph Performance Benchmark")
    print("=" * 60)

    pool = await get_pool()

    # Check DB size
    async with pool.acquire() as conn:
        nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
        edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
    print(f"\nKG Size: {nodes:,} nodes, {edges:,} edges")

    # Check indexes
    print("\n--- Indexes ---")
    indexes = await check_indexes(pool)
    for name, defn in indexes.items():
        has_trgm = "trgm" in defn.lower()
        marker = " *** NEW" if has_trgm else ""
        print(f"  {name}{marker}")

    has_trgm_index = any("trgm" in d.lower() for d in indexes.values())
    print(f"\n  Trigram index: {'YES' if has_trgm_index else 'NO (run migration 055)'}")

    # Run benchmarks
    print("\n--- Benchmarks ---\n")

    results = []
    for bench_fn in [
        benchmark_exact_resolution,
        benchmark_fuzzy_resolution,
        benchmark_bfs_traversal,
        benchmark_stats_queries,
    ]:
        try:
            result = await bench_fn(pool)
            results.append(result)
            print(
                f"  {result['name']:35s}  "
                f"p50={result.get('p50_ms', 0):7.2f}ms  "
                f"p95={result.get('p95_ms', 0):7.2f}ms  "
                f"avg={result.get('avg_ms', 0):7.2f}ms  "
                f"n={result.get('n', 0)}",
            )
            if "avg_chains" in result:
                print(f"  {'':35s}  avg_chains={result['avg_chains']}")
        except Exception as e:
            print(f"  {bench_fn.__name__}: ERROR - {e}")

    print("\n" + "=" * 60)
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
