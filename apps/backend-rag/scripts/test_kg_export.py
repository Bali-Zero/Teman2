"""
Test Knowledge Graph Export functionality
"""

import os
import sys

# Add parent directory to path to import backend modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from backend.services.autonomous_agents.knowledge_graph_builder import (
    Entity,
    KnowledgeGraphBuilder,
    Relationship,
)


def test_export():
    print("🏗️  Initializing Knowledge Graph Builder...")
    kg = KnowledgeGraphBuilder()

    # Create mock entities
    print("➕ Adding mock entities...")
    e1 = Entity(
        entity_id="kbli_56101",
        entity_type="kbli_code",
        name="Restaurant KBLI",
        description="Restaurants and mobile food service activities",
        confidence=0.9,
        properties={"risk_level": "medium", "min_capital": 1000000000},
    )
    kg.add_entity(e1)

    e2 = Entity(
        entity_id="permit_nib",
        entity_type="permit",
        name="NIB",
        description="Nomor Induk Berusaha (Business ID Number)",
        confidence=0.95,
    )
    kg.add_entity(e2)

    # Create mock relationship
    print("🔗 Adding mock relationship...")
    r1 = Relationship(
        relationship_id="rel_1",
        source_entity_id="kbli_56101",
        target_entity_id="permit_nib",
        relationship_type="requires",
        confidence=0.8,
        properties={"mandatory": True},
    )
    kg.add_relationship(r1)

    # Test Exports
    print("\n📦 Testing Exports:")

    # 1. JSON
    json_out = kg.export_graph("json")
    print(f"\n✅ JSON Export ({len(json_out)} chars):")
    print(json_out[:200] + "...")

    # 2. Cypher
    cypher_out = kg.export_graph("cypher")
    print(f"\n✅ Cypher Export ({len(cypher_out)} chars):")
    print("-" * 40)
    print(cypher_out)
    print("-" * 40)

    # 3. GraphML
    graphml_out = kg.export_graph("graphml")
    print(f"\n✅ GraphML Export ({len(graphml_out)} chars):")
    print("-" * 40)
    print(graphml_out)
    print("-" * 40)


if __name__ == "__main__":
    test_export()
