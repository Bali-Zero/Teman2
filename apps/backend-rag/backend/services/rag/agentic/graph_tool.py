"""
Graph Traversal Tool - Agentic Interface for Knowledge Graph
============================================================

Allows the Agent to explore the Knowledge Graph to find relationships
and structured data that might be missed by vector search.
"""

import logging
import json
from services.tools.definitions import BaseTool
from services.graph_service import GraphService

logger = logging.getLogger(__name__)

class GraphTraversalTool(BaseTool):
    """Tool for exploring the Knowledge Graph"""

    def __init__(self, graph_service: GraphService):
        self.graph = graph_service

    @property
    def name(self) -> str:
        return "graph_traversal"

    @property
    def description(self) -> str:
        return (
            "Explore the legal Knowledge Graph. Use this to find precise relationships like "
            "prerequisites, costs, or dependencies between entities (e.g., 'What does KITAS require?'). "
            "Input an entity name (e.g., 'investor kitas', 'tax reporting')."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "The name of the entity to explore (e.g. 'PT PMA', 'Investor Visa')"
                },
                "depth": {
                    "type": "integer",
                    "description": "Traversal depth (default: 1, max: 3)"
                }
            },
            "required": ["entity_name"]
        }

    async def execute(self, entity_name: str, depth: int = 1, **kwargs) -> str:
        try:
            # 1. Find the node ID
            candidates = await self.graph.find_entity_by_name(entity_name, limit=1)
            if not candidates:
                return f"No entity found in Knowledge Graph matching '{entity_name}'. Try a broader term."
            
            start_node = candidates[0]
            
            # 2. Traverse
            subgraph = await self.graph.traverse(start_node.id, max_depth=min(depth, 3))
            
            # 3. Format output for LLM
            nodes = subgraph["nodes"]
            edges = subgraph["edges"]
            
            summary = f"Found Entity: {start_node.name} ({start_node.type})\n"
            summary += f"Relationships ({len(edges)}):\n"
            
            node_map = {n['id']: n['name'] for n in nodes}
            
            for edge in edges:
                target_name = node_map.get(edge['target'], edge['target'])
                summary += f"- [{edge['type']}] -> {target_name}\n"
                
            return summary

        except Exception as e:
            logger.error(f"Graph traversal failed: {e}", exc_info=True)
            return f"Graph traversal error: {str(e)}"
