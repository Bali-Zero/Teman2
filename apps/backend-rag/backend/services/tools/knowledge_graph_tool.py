"""
Knowledge Graph Tool for Agentic RAG.

Allows the AI Agent to query the persistent Knowledge Graph to find structured
relationships between business entities (e.g., "What connects PT PMA to KITAS?").
"""

from services.tools.definitions import BaseTool
from services.autonomous_agents.knowledge_graph_builder import KnowledgeGraphBuilder


class KnowledgeGraphTool(BaseTool):
    """Tool for querying the business knowledge graph."""

    def __init__(self, kg_builder: KnowledgeGraphBuilder):
        self.kg_builder = kg_builder

    @property
    def name(self) -> str:
        return "knowledge_graph_search"

    @property
    def description(self) -> str:
        return (
            "Query the knowledge graph to find structured relationships and dependencies.\n\n"
            "**USE THIS TOOL** for questions about:\n"
            "- Prerequisites: 'What is required for PT PMA?'\n"
            "- Connections: 'What links KITAS and work permit?'\n"
            "- Obligations: 'What taxes apply to restaurants?'\n"
            "- Steps/Procedures: 'What are the steps to open a company?'\n\n"
            "**TIP**: Use AFTER vector_search for deeper insights on relationships.\n"
            "vector_search finds documents → knowledge_graph finds entity connections."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "The name of the entity to search for (e.g., 'PT PMA', 'Investor KITAS', 'KBLI 56101')."
                },
                "depth": {
                    "type": "integer",
                    "description": "How many hops to traverse (1 = direct connections, 2 = extended network). Max 2.",
                },
                "relationship_type": {
                    "type": "string",
                    "description": "Optional filter for relationship type (e.g., 'requires', 'costs', 'tax_obligation').",
                },
            },
            "required": ["entity"],
        }

    async def execute(self, entity: str, depth: int = 1, relationship_type: str = None, **kwargs) -> str:
        """
        Execute the graph search.
        """
        # Limit depth for performance
        safe_depth = min(max(1, int(depth) if depth else 1), 2)

        result = await self.kg_builder.query_graph(entity_name=entity, max_depth=safe_depth)

        if not result["found"]:
            return f"No entity found in the Knowledge Graph matching '{entity}'. Try using 'vector_search' instead."

        # Format output for LLM consumption
        entities_count = result["total_entities"]
        relationships_count = result["total_relationships"]

        output = [f"Found subgraph for '{result['query']}' ({entities_count} nodes, {relationships_count} edges):"]

        # Start Entity details
        start_node = result["start_entity"]
        output.append(f"\n[FOCUS] {start_node['name']} ({start_node['entity_type']})")
        if start_node.get('description'):
            output.append(f"  Description: {start_node['description']}")

        # Relationships
        output.append("\nConnections:")
        rels = result.get("relationships", [])

        # Build lookup for node names
        node_map = {n['entity_id']: n['name'] for n in result.get("entities", [])}

        if not rels:
            output.append("  (No direct relationships found)")

        count = 0
        for rel in rels:
            # Filter by type if requested
            if relationship_type and relationship_type.lower() not in rel['relationship_type'].lower():
                continue

            source_name = node_map.get(rel['source_entity_id'], "Unknown")
            target_name = node_map.get(rel['target_entity_id'], "Unknown")
            rel_name = rel['relationship_type'].upper()

            # Formatting direction
            if rel['source_entity_id'] == start_node['entity_id']:
                line = f"  - [This] --{rel_name}--> {target_name}"
            elif rel['target_entity_id'] == start_node['entity_id']:
                line = f"  - {source_name} --{rel_name}--> [This]"
            else:
                line = f"  - {source_name} --{rel_name}--> {target_name}"

            # Add properties if relevant
            props = rel.get('properties', {})
            relevant_props = [f"{k}={v}" for k, v in props.items() if k not in ['source', 'confidence']]
            if relevant_props:
                line += f" ({', '.join(relevant_props)})"

            output.append(line)
            count += 1
            if count >= 20:  # Context window protection
                output.append(f"  ... and {len(rels) - 20} more connections.")
                break

        return "\n".join(output)
