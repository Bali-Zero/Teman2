"""Fill deterministic summaries for small Louvain communities.

The LLM-based generator (`generate_community_summaries.py`) is rate-limited by
the local Ollama runtime (~12s/call). For the long tail of small communities
(member_count < 10) the deterministic fallback is acceptable: it still gives
downstream consumers a text field instead of NULL, which is what matters for
the GraphRAG summary-aware retrieval path.

This script writes the fallback summary for every community with
summary IS NULL AND member_count < min_members_llm.

Usage:
    PYTHONPATH=. python scripts/fill_small_community_fallbacks.py \
        --min-members-llm 10
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import asyncpg


DB_URL = os.environ.get(
    "ENTITY_LINKER_DB_URL",
    "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
)


def _fallback(community_id: str, top_entities: list[str], member_count: int) -> str:
    entities = ", ".join(top_entities[:8]) if top_entities else "voci eterogenee"
    return (
        f"Cluster KG Louvain {community_id} ({member_count} membri) centrato su: "
        f"{entities}. Raggruppamento automatico, riepilogo semantico "
        f"non disponibile."
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-members-llm", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)
    try:
        rows = await pool.fetch(
            """
            SELECT community_id, member_count, top_entities
            FROM kg_communities
            WHERE (summary IS NULL OR summary = '')
              AND member_count < $1
            """,
            args.min_members_llm,
        )
        print(f"Pending small-community fallbacks: {len(rows)}")
        if args.dry_run or not rows:
            return 0

        batch = [
            (_fallback(r["community_id"], list(r["top_entities"] or []), int(r["member_count"])), r["community_id"])
            for r in rows
        ]
        async with pool.acquire() as conn:
            await conn.executemany(
                "UPDATE kg_communities SET summary = $1, updated_at = NOW() "
                "WHERE community_id = $2 AND (summary IS NULL OR summary = '')",
                batch,
            )
        print(f"Updated {len(batch)} rows with deterministic fallback summaries")
    finally:
        await pool.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
