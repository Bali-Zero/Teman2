import logging
import re
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class GraphPathfinder:
    """
    Nuzantara Nexus Pathfinder Service.
    Navigates the Knowledge Graph to reconstruct deterministic workflows.
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    async def get_workflow_by_id(self, workflow_id: str) -> dict[str, Any] | None:
        """
        Reconstructs a full workflow from the graph starting from a Workflow node.
        """
        logger.info(f"🔍 Nexus: Reconstructing workflow {workflow_id}")
        async with self.db_pool.acquire() as conn:
            # 1. Get Workflow Header
            workflow = await conn.fetchrow(
                """
                SELECT entity_id, name, description
                FROM kg_nodes
                WHERE entity_id = $1 AND entity_type = 'workflow'
            """,
                workflow_id,
            )

            if not workflow:
                logger.warning(f"⚠️ Nexus: Workflow node {workflow_id} not found in DB")
                return None

            logger.info(f"✅ Nexus: Found workflow header: {workflow['name']}")

            # 2. Find Start Node
            start_edge = await conn.fetchrow(
                """
                SELECT target_entity_id
                FROM kg_edges
                WHERE source_entity_id = $1 AND relationship_type = 'STARTS_WITH'
            """,
                workflow_id,
            )

            if not start_edge:
                return dict(workflow)

            # 3. Traverse the chain (Iterative traversal)
            current_step_id = start_edge["target_entity_id"]
            steps = []

            while current_step_id:
                # Fetch step details
                step_node = await conn.fetchrow(
                    """
                    SELECT entity_id, name, description, entity_type
                    FROM kg_nodes
                    WHERE entity_id = $1
                """,
                    current_step_id,
                )

                if not step_node:
                    break

                # Fetch requirements/outputs for this step
                related = await conn.fetch(
                    """
                    SELECT e.relationship_type, n.name, n.entity_type
                    FROM kg_edges e
                    JOIN kg_nodes n ON e.target_entity_id = n.entity_id
                    WHERE e.source_entity_id = $1
                      AND e.relationship_type IN ('REQUIRES', 'PRODUCES', 'USES', 'CONSULTS')
                """,
                    current_step_id,
                )

                step_data = dict(step_node)
                step_data["requirements"] = [
                    dict(r) for r in related if r["relationship_type"] in ("REQUIRES", "CONSULTS")
                ]
                step_data["outputs"] = [
                    dict(r) for r in related if r["relationship_type"] == "PRODUCES"
                ]
                step_data["tools"] = [dict(r) for r in related if r["relationship_type"] == "USES"]

                steps.append(step_data)

                # Find next step
                next_edge = await conn.fetchrow(
                    """
                    SELECT target_entity_id
                    FROM kg_edges
                    WHERE source_entity_id = $1 AND relationship_type = 'NEXT_STEP'
                """,
                    current_step_id,
                )

                current_step_id = next_edge["target_entity_id"] if next_edge else None

            return {
                "id": workflow["entity_id"],
                "name": workflow["name"],
                "description": workflow["description"],
                "steps": steps,
            }

    async def find_workflow_for_query(
        self, query: str, user_context: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """
        Semantic search for the right workflow based on user query AND context.
        Implements Dual-Core Logic (Foreign vs Domestic).
        """
        query_lower = query.lower()
        user_context = user_context or {}
        citizenship = user_context.get("citizenship", "foreign").lower()

        # COMPANY SETUP INTENT PATTERNS
        company_patterns = [
            r"open.*company",
            r"setup.*company",
            r"buat.*pt",
            r"bikin.*pt",
            r"register.*company",
            r"establish.*company",
        ]

        is_company_intent = any(re.search(pattern, query_lower) for pattern in company_patterns)

        if is_company_intent:
            logger.info(f"🎯 Nexus: Detected Company Setup intent for {citizenship} market")

            # 🇮🇩 DOMESTIC PATH (Indonesian Citizen)
            if citizenship in ["id", "indonesia", "indonesian", "wni"]:
                return await self.get_workflow_by_id("nexus:wf:pt_perorangan")

            # 🌏 INTERNATIONAL PATH (Foreigner)
            else:
                return await self.get_workflow_by_id("nexus:wf:pt_pma")

        return None
