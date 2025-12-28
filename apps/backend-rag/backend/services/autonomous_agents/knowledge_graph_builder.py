"""
Knowledge Graph Builder - Phase 4 (Advanced Agent)

Builds and maintains a knowledge graph of relationships between entities
discovered in Qdrant collections.

Example Knowledge Graph:
```
KBLI 56101 (Restaurant)
  ├─→ requires → NIB
  ├─→ requires → NPWP
  ├─→ tax_obligation → PPh 23 (2%)
  ├─→ tax_obligation → PPn (11%)
  ├─→ legal_structure → PT vs CV
  ├─→ location_restriction → Zoning rules
  └─→ staff_visa → IMTA requirements

PT PMA
  ├─→ requires → Min Investment (Rp 10B)
  ├─→ requires → Foreign Director (min 1)
  ├─→ process_time → 60-90 days
  ├─→ registration_at → BKPM
  └─→ related_to → KBLI codes

KITAS (Limited Stay Permit)
  ├─→ requires → Sponsor Company
  ├─→ requires → IMTA
  ├─→ validity → 1 year (renewable)
  ├─→ cost → Rp 5-15 million
  └─→ related_to → Work Permit
```

The graph is stored in JSON/dict format (could be migrated to Neo4j later).
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class EntityType(str):
    """Types of entities in knowledge graph"""

    KBLI_CODE = "kbli_code"
    LEGAL_ENTITY = "legal_entity"
    VISA_TYPE = "visa_type"
    TAX_TYPE = "tax_type"
    PERMIT = "permit"
    DOCUMENT = "document"
    PROCESS = "process"
    REGULATION = "regulation"
    LOCATION = "location"
    SERVICE = "service"


class RelationType(str):
    """Types of relationships between entities"""

    REQUIRES = "requires"
    RELATED_TO = "related_to"
    PART_OF = "part_of"
    PROVIDES = "provides"
    COSTS = "costs"
    DURATION = "duration"
    PREREQUISITE = "prerequisite"
    TAX_OBLIGATION = "tax_obligation"
    LEGAL_REQUIREMENT = "legal_requirement"
    LOCATION_RESTRICTION = "location_restriction"


@dataclass
class Entity:
    """Node in knowledge graph"""

    entity_id: str
    entity_type: str
    name: str
    description: str
    properties: dict[str, Any] = field(default_factory=dict)
    source_collection: str | None = None
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Relationship:
    """Edge in knowledge graph"""

    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source_collection: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class KnowledgeGraphBuilder:
    """
    Builds and maintains knowledge graph from Qdrant collections.

    Process:
    1. Extract entities from collection texts
    2. Identify relationships between entities
    3. Store graph structure
    4. Provide query capabilities
    """

    # Entity extraction patterns
    ENTITY_PATTERNS = {
        EntityType.KBLI_CODE: [
            r"KBLI\s+(\d{5})",
            r"kode\s+KBLI\s+(\d{5})",
            r"business\s+classification\s+(\d{5})",
        ],
        EntityType.VISA_TYPE: [
            # Generic visa/permit patterns - no specific codes (codes are in database)
            r"([A-Z]\d+[A-Z]?)\s+visa",  # Generic visa code pattern
            r"(work permit|stay permit|residence permit|long-stay permit)",
            r"([A-Z]+)\s+permit",  # Generic permit pattern
        ],
        EntityType.TAX_TYPE: [
            # Generic tax patterns - no specific codes (codes are in database)
            r"([A-Z]+\s+\d+)",  # Generic tax code pattern
            r"([A-Z]{2,10})",  # Generic tax acronym pattern
            r"(tax\s+ID|VAT\s+number|tax\s+registration)",
        ],
        EntityType.LEGAL_ENTITY: [
            # Generic legal entity patterns - no specific codes (codes are in database)
            r"([A-Z]{2,10}\s+[A-Z]+)",  # Generic company type pattern
            r"(limited\s+liability|partnership|foundation|company\s+type)",
        ],
        EntityType.PERMIT: [
            # Generic permit patterns - no specific codes (codes are in database)
            r"([A-Z]{2,10}(-[A-Z]+)?)",  # Generic permit acronym pattern
            r"(business\s+license|operational\s+permit|permit\s+code)",
        ],
    }

    # Relationship inference patterns
    RELATIONSHIP_PATTERNS = {
        RelationType.REQUIRES: [
            r"requires?",
            r"needs?",
            r"must\s+have",
            r"prerequisite",
            r"diperlukan",
            r"membutuhkan",
        ],
        RelationType.COSTS: [r"costs?", r"Rp\s+[\d,]+", r"biaya", r"tarif", r"harga"],
        RelationType.DURATION: [
            r"(\d+)\s+(days?|months?|years?)",
            r"(\d+)\s+(hari|bulan|tahun)",
            r"process\s+time",
            r"duration",
        ],
    }

    def __init__(self, search_service=None):
        """
        Initialize Knowledge Graph Builder.

        Args:
            search_service: SearchService for querying collections
        """
        self.search = search_service

        # Graph storage (in production, use graph database like Neo4j)
        self.entities: dict[str, Entity] = {}
        self.relationships: dict[str, Relationship] = {}

        # Indexes for fast lookup
        self.entity_by_type: dict[str, list[str]] = {}
        self.relationships_by_source: dict[str, list[str]] = {}
        self.relationships_by_target: dict[str, list[str]] = {}

        self.graph_stats = {
            "total_entities": 0,
            "total_relationships": 0,
            "entity_type_distribution": {},
            "relationship_type_distribution": {},
            "collections_analyzed": [],
        }

        logger.info("✅ KnowledgeGraphBuilder initialized")

    def extract_entities_from_text(
        self, text: str, source_collection: str | None = None
    ) -> list[Entity]:
        """
        Extract entities from text using pattern matching.

        Args:
            text: Text to analyze
            source_collection: Source collection name

        Returns:
            List of extracted entities
        """
        entities = []

        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)

                for match in matches:
                    # Extract entity name
                    entity_name = match.group(1) if match.groups() else match.group(0)
                    entity_name = entity_name.strip()

                    # Generate entity ID
                    entity_id = f"{entity_type}_{entity_name.replace(' ', '_').lower()}"

                    # Skip if already exists
                    if entity_id in self.entities:
                        continue

                    # Extract context (surrounding text)
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end].strip()

                    # Create entity
                    entity = Entity(
                        entity_id=entity_id,
                        entity_type=entity_type,
                        name=entity_name,
                        description=context,
                        source_collection=source_collection,
                        confidence=0.8,  # Pattern-based extraction
                    )

                    entities.append(entity)

        return entities

    def infer_relationships_from_text(
        self, text: str, entities: list[Entity], source_collection: str | None = None
    ) -> list[Relationship]:
        """
        Infer relationships between entities from text.

        Args:
            text: Text to analyze
            entities: Entities found in text
            source_collection: Source collection name

        Returns:
            List of inferred relationships
        """
        relationships = []

        # For each pair of entities
        for i, source_entity in enumerate(entities):
            for target_entity in entities[i + 1 :]:
                # Check if both entities appear in text
                if source_entity.name not in text or target_entity.name not in text:
                    continue

                # Find text between entities
                source_pos = text.find(source_entity.name)
                target_pos = text.find(target_entity.name)

                if source_pos == -1 or target_pos == -1:
                    continue

                # Extract text between
                start_pos = min(source_pos, target_pos)
                end_pos = max(source_pos, target_pos)
                between_text = text[start_pos:end_pos]

                # Check for relationship patterns
                for rel_type, patterns in self.RELATIONSHIP_PATTERNS.items():
                    if any(re.search(p, between_text, re.IGNORECASE) for p in patterns):
                        # Found relationship
                        rel_id = f"{source_entity.entity_id}_{rel_type}_{target_entity.entity_id}"

                        relationship = Relationship(
                            relationship_id=rel_id,
                            source_entity_id=source_entity.entity_id,
                            target_entity_id=target_entity.entity_id,
                            relationship_type=rel_type,
                            source_collection=source_collection,
                            confidence=0.7,  # Inferred relationship
                        )

                        relationships.append(relationship)
                        break  # One relationship per entity pair

        return relationships

    async def build_graph_from_collection(self, collection_name: str, limit: int = 100) -> int:
        """
        Build knowledge graph from a single collection.

        Args:
            collection_name: Collection to analyze
            limit: Max documents to analyze

        Returns:
            Number of entities/relationships added
        """
        if not self.search:
            logger.warning("SearchService not available")
            return 0

        logger.info(f"🔨 Building knowledge graph from: {collection_name}")

        # Query collection (broad query to get many results)
        try:
            results = await self.search.search(
                query="business setup visa tax legal",  # Broad query
                user_level=3,
                limit=limit,
                collection_override=collection_name,
            )
        except Exception as e:
            logger.error(f"Error querying {collection_name}: {e}")
            return 0

        documents = results.get("results", [])
        logger.info(f"   Analyzing {len(documents)} documents...")

        total_added = 0

        for doc in documents:
            text = doc.get("text", "")

            # Extract entities
            entities = self.extract_entities_from_text(text, collection_name)

            # Add entities to graph
            for entity in entities:
                if entity.entity_id not in self.entities:
                    self.add_entity(entity)
                    total_added += 1

            # Infer relationships
            relationships = self.infer_relationships_from_text(text, entities, collection_name)

            # Add relationships to graph
            for rel in relationships:
                if rel.relationship_id not in self.relationships:
                    self.add_relationship(rel)
                    total_added += 1

        # Update stats
        if collection_name not in self.graph_stats["collections_analyzed"]:
            self.graph_stats["collections_analyzed"].append(collection_name)

        logger.info(f"✅ Added {total_added} entities/relationships from {collection_name}")

        return total_added

    def add_entity(self, entity: Entity):
        """Add entity to graph"""
        self.entities[entity.entity_id] = entity

        # Update indexes
        if entity.entity_type not in self.entity_by_type:
            self.entity_by_type[entity.entity_type] = []
        self.entity_by_type[entity.entity_type].append(entity.entity_id)

        # Update stats
        self.graph_stats["total_entities"] += 1
        self.graph_stats["entity_type_distribution"][entity.entity_type] = (
            self.graph_stats["entity_type_distribution"].get(entity.entity_type, 0) + 1
        )

    def add_relationship(self, relationship: Relationship):
        """Add relationship to graph"""
        self.relationships[relationship.relationship_id] = relationship

        # Update indexes
        if relationship.source_entity_id not in self.relationships_by_source:
            self.relationships_by_source[relationship.source_entity_id] = []
        self.relationships_by_source[relationship.source_entity_id].append(
            relationship.relationship_id
        )

        if relationship.target_entity_id not in self.relationships_by_target:
            self.relationships_by_target[relationship.target_entity_id] = []
        self.relationships_by_target[relationship.target_entity_id].append(
            relationship.relationship_id
        )

        # Update stats
        self.graph_stats["total_relationships"] += 1
        self.graph_stats["relationship_type_distribution"][relationship.relationship_type] = (
            self.graph_stats["relationship_type_distribution"].get(
                relationship.relationship_type, 0
            )
            + 1
        )

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID"""
        return self.entities.get(entity_id)

    def get_entities_by_type(self, entity_type: str) -> list[Entity]:
        """Get all entities of a specific type"""
        entity_ids = self.entity_by_type.get(entity_type, [])
        return [self.entities[eid] for eid in entity_ids]

    def get_relationships_for_entity(
        self, entity_id: str, direction: str = "outgoing"
    ) -> list[Relationship]:
        """
        Get relationships for an entity.

        Args:
            entity_id: Entity identifier
            direction: "outgoing", "incoming", or "both"

        Returns:
            List of relationships
        """
        relationships = []

        if direction in ["outgoing", "both"]:
            rel_ids = self.relationships_by_source.get(entity_id, [])
            relationships.extend([self.relationships[rid] for rid in rel_ids])

        if direction in ["incoming", "both"]:
            rel_ids = self.relationships_by_target.get(entity_id, [])
            relationships.extend([self.relationships[rid] for rid in rel_ids])

        return relationships

    def query_graph(self, entity_name: str, max_depth: int = 2) -> dict[str, Any]:
        """
        Query knowledge graph starting from an entity.

        Args:
            entity_name: Entity name to start from
            max_depth: Maximum relationship depth to traverse

        Returns:
            Subgraph dictionary
        """
        # Find entity
        matching_entities = [
            e for e in self.entities.values() if entity_name.lower() in e.name.lower()
        ]

        if not matching_entities:
            return {"query": entity_name, "found": False, "entities": [], "relationships": []}

        start_entity = matching_entities[0]

        # Traverse graph (BFS)
        visited_entities = {start_entity.entity_id}
        visited_relationships = set()
        queue = [(start_entity.entity_id, 0)]  # (entity_id, depth)

        entities_result = [start_entity]
        relationships_result = []

        while queue:
            current_entity_id, depth = queue.pop(0)

            if depth >= max_depth:
                continue

            # Get outgoing relationships
            for rel in self.get_relationships_for_entity(current_entity_id, "outgoing"):
                if rel.relationship_id in visited_relationships:
                    continue

                visited_relationships.add(rel.relationship_id)
                relationships_result.append(rel)

                # Add target entity
                target_id = rel.target_entity_id
                if target_id not in visited_entities:
                    visited_entities.add(target_id)
                    target_entity = self.get_entity(target_id)
                    if target_entity:
                        entities_result.append(target_entity)
                        queue.append((target_id, depth + 1))

        return {
            "query": entity_name,
            "found": True,
            "start_entity": asdict(start_entity),
            "entities": [asdict(e) for e in entities_result],
            "relationships": [asdict(r) for r in relationships_result],
            "total_entities": len(entities_result),
            "total_relationships": len(relationships_result),
        }

    def export_graph(self, format: str = "json") -> str:
        """
        Export knowledge graph.

        Args:
            format: Export format ("json", "cypher", "graphml")

        Returns:
            Exported graph string
        """
        if format == "json":
            return json.dumps(
                {
                    "entities": [asdict(e) for e in self.entities.values()],
                    "relationships": [asdict(r) for r in self.relationships.values()],
                    "stats": self.graph_stats,
                },
                indent=2,
            )
        elif format == "cypher":
            return self._export_cypher()
        elif format == "graphml":
            return self._export_graphml()
        else:
            logger.warning("Export format %s not supported", format)
            raise NotImplementedError(f"Format {format} not implemented")

    def _export_cypher(self) -> str:
        """Generate Cypher queries for Neo4j import"""
        lines = ["// Knowledge Graph Export for Neo4j"]
        lines.append("// Generated by Zantara Knowledge Graph Builder")
        lines.append("")

        # Create constraints (optional but recommended)
        lines.append("// Constraints")
        lines.append("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;")
        lines.append("")

        # Create Entities
        lines.append("// Entities")
        for entity in self.entities.values():
            # Escape strings
            name = entity.name.replace('"', '\\"')
            desc = entity.description.replace('"', '\\"')
            
            # Build node properties
            props = [
                f'id: "{entity.entity_id}"',
                f'name: "{name}"',
                f'type: "{entity.entity_type}"',
                f'description: "{desc}"',
                f'confidence: {entity.confidence}',
                f'source: "{entity.source_collection or ""}"'
            ]
            
            # Add dynamic properties
            for k, v in entity.properties.items():
                if isinstance(v, (int, float, bool)):
                    props.append(f'{k}: {v}')
                else:
                    v_str = str(v).replace('"', '\\"')
                    props.append(f'{k}: "{v_str}"')

            # MERGE query to avoid duplicates
            query = f'MERGE (e:Entity {{id: "{entity.entity_id}"}}) SET e += {{{", ".join(props)}}}, e:{entity.entity_type};'
            lines.append(query)

        lines.append("")
        
        # Create Relationships
        lines.append("// Relationships")
        for rel in self.relationships.values():
            # Escape strings
            rel_type = rel.relationship_type.upper().replace(" ", "_")
            
            # Build edge properties
            props = [
                f'id: "{rel.relationship_id}"',
                f'confidence: {rel.confidence}',
                f'source_collection: "{rel.source_collection or ""}"'
            ]
            
             # Add dynamic properties
            for k, v in rel.properties.items():
                if isinstance(v, (int, float, bool)):
                    props.append(f'{k}: {v}')
                else:
                    v_str = str(v).replace('"', '\\"')
                    props.append(f'{k}: "{v_str}"')
            
            query = (
                f'MATCH (source:Entity {{id: "{rel.source_entity_id}"}})\n'
                f'MATCH (target:Entity {{id: "{rel.target_entity_id}"}})\n'
                f'MERGE (source)-[r:{rel_type}]->(target)\n'
                f'SET r += {{{", ".join(props)}}};'
            )
            lines.append(query)

        return "\n".join(lines)

    def _export_graphml(self) -> str:
        """Generate GraphML XML for Gephi/Cytoscape"""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
            '    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns',
            '     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
        ]
        
        # Define keys (attributes)
        lines.extend([
            '  <key id="d0" for="node" attr.name="name" attr.type="string"/>',
            '  <key id="d1" for="node" attr.name="type" attr.type="string"/>',
            '  <key id="d2" for="node" attr.name="description" attr.type="string"/>',
            '  <key id="d3" for="node" attr.name="confidence" attr.type="double"/>',
            '  <key id="d4" for="edge" attr.name="type" attr.type="string"/>',
            '  <key id="d5" for="edge" attr.name="confidence" attr.type="double"/>'
        ])
        
        lines.append('  <graph id="G" edgedefault="directed">')

        # Nodes
        for entity in self.entities.values():
            # Escape XML special chars
            name = entity.name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            desc = entity.description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            lines.append(f'    <node id="{entity.entity_id}">')
            lines.append(f'      <data key="d0">{name}</data>')
            lines.append(f'      <data key="d1">{entity.entity_type}</data>')
            lines.append(f'      <data key="d2">{desc}</data>')
            lines.append(f'      <data key="d3">{entity.confidence}</data>')
            lines.append('    </node>')

        # Edges
        for rel in self.relationships.values():
            lines.append(f'    <edge source="{rel.source_entity_id}" target="{rel.target_entity_id}">')
            lines.append(f'      <data key="d4">{rel.relationship_type}</data>')
            lines.append(f'      <data key="d5">{rel.confidence}</data>')
            lines.append('    </edge>')

        lines.append('  </graph>')
        lines.append('</graphml>')
        
        return "\n".join(lines)

    def get_graph_stats(self) -> dict:
        """Get knowledge graph statistics"""
        return {
            **self.graph_stats,
            "avg_relationships_per_entity": (
                self.graph_stats["total_relationships"] / max(self.graph_stats["total_entities"], 1)
            ),
        }
