"""Community Detection for Knowledge Graph — GraphRAG 2.0

Pure Python Louvain community detection on the PostgreSQL-backed KG.
The graph (~87K nodes, ~210K edges) fits comfortably in memory (~50MB).

Communities enable:
1. Topic discovery (automatic clustering of visa/tax/property/company domains)
2. Community summaries as RAG context ("this query relates to the KITAS processing community")
3. Inter-community bridging for multi-hop reasoning

Usage:
    from backend.services.knowledge_graph.community_detection import CommunityDetector

    detector = CommunityDetector(db_pool)
    communities = await detector.detect()
    await detector.persist(communities)
    await detector.generate_summaries(llm_gateway, embedder)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Community:
    """A detected community cluster."""

    community_id: str
    level: int = 0
    parent_id: str | None = None
    name: str = ""
    summary: str = ""
    members: list[str] = field(default_factory=list)
    member_count: int = 0
    top_entities: list[str] = field(default_factory=list)
    top_relations: list[str] = field(default_factory=list)
    modularity_contribution: float = 0.0


class CommunityDetector:
    """Louvain community detection on the KG graph.

    Algorithm:
    1. Load adjacency list from kg_edges
    2. Initialize each node in its own community
    3. Iterate: for each node, try moving to neighbor's community if modularity gain > 0
    4. Repeat until no improvement (convergence)
    5. Optionally: merge communities into super-communities (hierarchical level 1)
    """

    def __init__(self, db_pool: Any) -> None:
        self._pool = db_pool

    async def load_graph(
        self,
    ) -> tuple[dict[str, set[str]], dict[tuple[str, str], float], dict[tuple[str, str], str]]:
        """Load adjacency list, edge weights, and relationship types from PostgreSQL.

        Returns:
            (adjacency_dict, edge_weights, edge_types) where:
              adjacency_dict[node] = set of neighbor nodes
              edge_weights[(node_a, node_b)] = confidence weight
              edge_types[(node_a, node_b)] = relationship_type string
        """
        adj: dict[str, set[str]] = defaultdict(set)
        weights: dict[tuple[str, str], float] = {}
        edge_types: dict[tuple[str, str], str] = {}

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT source_entity_id, target_entity_id, confidence, relationship_type "
                "FROM kg_edges",
            )

        for row in rows:
            src, tgt, conf = row["source_entity_id"], row["target_entity_id"], row["confidence"]
            rel_type = row["relationship_type"] or "RELATED"
            adj[src].add(tgt)
            adj[tgt].add(src)  # undirected
            w = float(conf or 1.0)
            weights[(src, tgt)] = w
            weights[(tgt, src)] = w
            edge_types[(src, tgt)] = rel_type
            edge_types[(tgt, src)] = rel_type

        # Ensure isolated nodes are included
        async with self._pool.acquire() as conn:
            node_rows = await conn.fetch("SELECT entity_id FROM kg_nodes")
        for row in node_rows:
            nid = row["entity_id"]
            if nid not in adj:
                adj[nid] = set()

        logger.info(
            "Loaded graph: %d nodes, %d edges",
            len(adj),
            len(weights) // 2,
        )
        return dict(adj), weights, edge_types

    def _louvain(
        self,
        adj: dict[str, set[str]],
        weights: dict[tuple[str, str], float],
        resolution: float = 1.0,
    ) -> dict[str, int]:
        """Run one pass of Louvain community detection.

        Returns:
            node_to_community: mapping of node_id → community_int_id
        """
        nodes = list(adj.keys())
        # Initialize: each node in its own community
        node2comm: dict[str, int] = {n: i for i, n in enumerate(nodes)}

        # Precompute total edge weight (m) and per-node degree (k_i)
        m = sum(weights.values()) / 2.0  # each edge counted twice
        if m == 0:
            return node2comm

        degree: dict[str, float] = defaultdict(float)
        for (src, _tgt), w in weights.items():
            degree[src] += w

        # Community totals
        comm_total: dict[int, float] = defaultdict(float)
        for n in nodes:
            comm_total[node2comm[n]] += degree[n]

        # Community internal weight
        comm_internal: dict[int, float] = defaultdict(float)
        for (src, tgt), w in weights.items():
            if node2comm[src] == node2comm[tgt]:
                comm_internal[node2comm[src]] += w / 2.0  # avoid double count

        improved = True
        iteration = 0
        max_iterations = 20

        while improved and iteration < max_iterations:
            improved = False
            iteration += 1

            for node in nodes:
                current_comm = node2comm[node]
                k_i = degree[node]

                # Remove node from its community
                comm_total[current_comm] -= k_i
                for nb in adj[node]:
                    if node2comm[nb] == current_comm:
                        comm_internal[current_comm] -= weights.get((node, nb), 0)

                # Evaluate moving to each neighbor's community
                best_comm = current_comm
                best_gain = 0.0

                # Compute neighbor community weights
                neighbor_comms: dict[int, float] = defaultdict(float)
                for nb in adj[node]:
                    c = node2comm[nb]
                    neighbor_comms[c] += weights.get((node, nb), 0)

                for c, k_in in neighbor_comms.items():
                    # Modularity gain of moving node to community c
                    sigma_tot = comm_total[c]
                    gain = (k_in - resolution * sigma_tot * k_i / (2.0 * m))
                    if gain > best_gain:
                        best_gain = gain
                        best_comm = c

                # Move node to best community
                node2comm[node] = best_comm
                comm_total[best_comm] += k_i
                for nb in adj[node]:
                    if node2comm[nb] == best_comm:
                        comm_internal[best_comm] += weights.get((node, nb), 0)

                if best_comm != current_comm:
                    improved = True

        logger.info("Louvain converged after %d iterations", iteration)
        return node2comm

    async def detect(
        self,
        resolution: float = 1.0,
        min_community_size: int = 3,
    ) -> list[Community]:
        """Run full community detection pipeline.

        Args:
            resolution: Louvain resolution (higher = more communities)
            min_community_size: Minimum members to keep a community

        Returns:
            List of detected communities
        """
        start = time.time()
        adj, weights, edge_types = await self.load_graph()

        if not adj:
            logger.warning("Empty graph, no communities to detect")
            return []

        # Run Louvain in thread executor to avoid blocking the event loop
        # (87K nodes × 20 iterations = CPU-bound, ~5-15s)
        loop = asyncio.get_event_loop()
        node2comm = await loop.run_in_executor(
            ThreadPoolExecutor(max_workers=1),
            self._louvain,
            adj,
            weights,
            resolution,
        )

        # Group nodes by community
        comm_members: dict[int, list[str]] = defaultdict(list)
        for node, comm_id in node2comm.items():
            comm_members[comm_id].append(node)

        # Filter small communities and build Community objects
        communities: list[Community] = []
        for comm_int_id, members in comm_members.items():
            if len(members) < min_community_size:
                continue

            # Generate stable community ID
            members_sorted = sorted(members)
            cid_hash = hashlib.md5(
                ",".join(members_sorted[:10]).encode(),
            ).hexdigest()[:12]
            cid = f"comm_L0_{cid_hash}"

            # Find top entities by degree (hub nodes)
            member_degrees = [
                (m, len(adj.get(m, set()))) for m in members
            ]
            member_degrees.sort(key=lambda x: x[1], reverse=True)
            top_ents = [m for m, _d in member_degrees[:5]]

            # Find top relationship types within community (using actual edge types)
            rel_type_counts: dict[str, int] = defaultdict(int)
            for m in members:
                for nb in adj.get(m, set()):
                    if node2comm.get(nb) == comm_int_id:
                        rt = edge_types.get((m, nb), "RELATED")
                        rel_type_counts[rt] += 1
            top_rels = sorted(
                rel_type_counts.keys(),
                key=lambda r: rel_type_counts[r],
                reverse=True,
            )[:5]

            communities.append(Community(
                community_id=cid,
                level=0,
                members=members,
                member_count=len(members),
                top_entities=top_ents,
                top_relations=top_rels,
            ))

        elapsed = time.time() - start
        logger.info(
            "Community detection complete: %d communities from %d nodes in %.1fs",
            len(communities),
            len(adj),
            elapsed,
        )
        return communities

    async def persist(self, communities: list[Community], batch_size: int = 500) -> int:
        """Save detected communities to PostgreSQL using batch inserts.

        Args:
            communities: List of communities to persist
            batch_size: Rows per batch for membership inserts (default 500)

        Returns number of communities persisted.
        """
        if not communities:
            return 0

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Clear old communities at same level
                levels = {c.level for c in communities}
                for level in levels:
                    await conn.execute(
                        "DELETE FROM kg_node_community WHERE community_id IN "
                        "(SELECT community_id FROM kg_communities WHERE level = $1)",
                        level,
                    )
                    await conn.execute(
                        "DELETE FROM kg_communities WHERE level = $1",
                        level,
                    )

                # Batch insert communities
                comm_rows = [
                    (c.community_id, c.level, c.parent_id, c.name, c.summary,
                     c.member_count, c.top_entities, c.top_relations)
                    for c in communities
                ]
                await conn.executemany(
                    "INSERT INTO kg_communities "
                    "(community_id, level, parent_id, name, summary, member_count, "
                    "top_entities, top_relations) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                    comm_rows,
                )

                # Batch insert memberships
                membership_rows: list[tuple[str, str, float]] = []
                for c in communities:
                    for member in c.members:
                        membership_rows.append((member, c.community_id, 1.0))

                # Insert in batches to avoid memory spike on huge lists
                for i in range(0, len(membership_rows), batch_size):
                    batch = membership_rows[i : i + batch_size]
                    await conn.executemany(
                        "INSERT INTO kg_node_community (entity_id, community_id, membership_score) "
                        "VALUES ($1, $2, $3) "
                        "ON CONFLICT (entity_id, community_id) DO UPDATE SET membership_score = $3",
                        batch,
                    )

        logger.info(
            "Persisted %d communities, %d memberships",
            len(communities),
            len(membership_rows),
        )
        return len(communities)

    async def generate_summaries(
        self,
        llm_gateway: Any,
        db_pool: Any | None = None,
        llm_model: str = "gemini-2.0-flash",
    ) -> int:
        """Generate natural language summaries for communities using LLM.

        Args:
            llm_gateway: LLMGateway with generate() method
            db_pool: Optional separate pool (uses self._pool if None)
            llm_model: Model to use for summary generation (default: gemini-2.0-flash)

        Returns:
            Number of summaries generated
        """
        pool = db_pool or self._pool
        count = 0

        async with pool.acquire() as conn:
            communities = await conn.fetch(
                "SELECT community_id, top_entities, top_relations, member_count "
                "FROM kg_communities WHERE summary IS NULL OR summary = ''",
            )

        for comm in communities:
            cid = comm["community_id"]
            top_ents = comm["top_entities"] or []
            member_count = comm["member_count"]

            # Batch load entity details (fix N+1 query)
            entity_details = []
            rel_details = []
            async with pool.acquire() as conn:
                if top_ents:
                    ent_rows = await conn.fetch(
                        "SELECT entity_id, name, entity_type, description "
                        "FROM kg_nodes WHERE entity_id = ANY($1)",
                        top_ents[:5],
                    )
                    for row in ent_rows:
                        entity_details.append(
                            f"- {row['name']} ({row['entity_type']}): {(row['description'] or '')[:100]}",
                        )

                    # Batch load relationships for top entities
                    rel_rows = await conn.fetch(
                        "SELECT e.source_entity_id, e.relationship_type, n2.name as target_name "
                        "FROM kg_edges e "
                        "JOIN kg_nodes n2 ON e.target_entity_id = n2.entity_id "
                        "WHERE e.source_entity_id = ANY($1) "
                        "LIMIT 15",
                        top_ents[:3],
                    )
                    for r in rel_rows:
                        rel_details.append(f"- {r['relationship_type']} → {r['target_name']}")

            prompt = (
                f"Summarize this knowledge cluster ({member_count} entities) in 2-3 sentences. "
                f"Focus on the domain, key topics, and common relationships.\n\n"
                f"Top entities:\n{''.join(entity_details[:5]) or 'None'}\n\n"
                f"Key relationships:\n{''.join(rel_details[:5]) or 'None'}"
            )

            try:
                summary = await llm_gateway.generate(
                    messages=[{"role": "user", "content": prompt}],
                    model_override=llm_model,
                    max_tokens=200,
                )
                summary = summary.strip()

                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE kg_communities SET summary = $1, name = $2, updated_at = NOW() "
                        "WHERE community_id = $3",
                        summary,
                        summary[:80],
                        cid,
                    )
                count += 1
            except Exception as e:
                logger.warning("Failed to generate summary for %s: %s", cid, e)

        logger.info("Generated %d community summaries", count)
        return count
