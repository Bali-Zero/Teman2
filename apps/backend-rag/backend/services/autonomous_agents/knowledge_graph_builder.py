"""
Knowledge Graph Builder - Phase 4 (Advanced Agent)

Builds and maintains a knowledge graph of relationships between entities
discovered in Qdrant collections.

Example Knowledge Graph:
```
KBLI 56101 (Restaurant)
  ☙→ requires → NIB
  ☙→ requires → NPWP
  ☙→ tax_obligation → PPh 23 (2%)
  ☙→ tax_obligation → PPn (11%)
  ☙→ legal_structure → PT vs CV
  ☙→ location_restriction → Zoning rules
  ☙→ staff_visa → IMTA requirements
```

The graph is stored in PostgreSQL (kg_nodes, kg_edges) for persistence.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import asyncpg

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
    source_chunk_ids: list[str] = field(default_factory=list)
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
    source_chunk_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class KnowledgeGraphBuilder:
    """
    Builds and maintains knowledge graph from Qdrant collections.
    Uses PostgreSQL for persistence.
    """

    # Entity extraction patterns
    ENTITY_PATTERNS = {
        EntityType.KBLI_CODE: [
            r"KBLI\s+(\d{5})",
            r"kode\s+KBLI\s+(\d{5})",
            r"business\s+classification\s+(\d{5})",
        ],
        EntityType.VISA_TYPE: [
            r"([A-Z]\d+[A-Z]?)\s+visa",
            r"(work permit|stay permit|residence permit|long-stay permit)",
            r"([A-Z]+)\s+permit",
        ],
        EntityType.TAX_TYPE: [
            r"([A-Z]+\s+\d+)",
            r"([A-Z]{2,10})",
            r"(tax\s+ID|VAT\s+number|tax\s+registration)",
        ],
        EntityType.LEGAL_ENTITY: [
            r"([A-Z]{2,10}\s+[A-Z]+)",
            r"(limited\s+liability|partnership|foundation|company\s+type)",
        ],
        EntityType.PERMIT: [
            r"([A-Z]{2,10}(-[A-Z]+)?)",
            r"(business\s+license|operational\s+permit|permit\s+code)",
        ],
    }

    # Relationship inference patterns
    RELATIONSHIP_PATTERNS = {
        RelationType.REQUIRES: [
            r"requires?", r"needs?", r"must\s+have", r"prerequisite", r"diperlukan", r"membutuhkan",
        ],
        RelationType.COSTS: [r"costs?", r"Rp\s+[\d,]+", r"biaya", r"tarif", r"harga"],
        RelationType.DURATION: [
            r"(\d+)\s+(days?|months?|years?)", r"(\d+)\s+(hari|bulan|tahun)",
            r"process\s+time", r"duration",
        ],
    }

    def __init__(self, search_service=None, db_pool: asyncpg.Pool = None, llm_gateway=None):
        """
        Initialize Knowledge Graph Builder.

        Args:
            search_service: SearchService for querying collections
            db_pool: Database connection pool for persistence
            llm_gateway: LLMGateway for semantic extraction
        """
        self.search = search_service
        self.db_pool = db_pool
        self.llm_gateway = llm_gateway

        # In-memory cache (synchronized with DB on export/load)
        self.entities: dict[str, Entity] = {}
        self.relationships: dict[str, Relationship] = {}

        self.graph_stats = {
            "total_entities": 0,
            "total_relationships": 0,
            "entity_type_distribution": {},
            "relationship_type_distribution": {},
            "collections_analyzed": [],
        }

        logger.info(f"✅ KnowledgeGraphBuilder initialized (Persistence: {'Enabled' if db_pool else 'Disabled'}, LLM: {'Enabled' if llm_gateway else 'Disabled'})")

    async def add_entity(self, entity: Entity):
        """Add entity to graph (Persistent)"""
        # 1. Update In-Memory
        self.entities[entity.entity_id] = entity

        # 2. Persist to DB
        if self.db_pool:
            try:
                # Ensure chunk_ids is a list for SQL array
                chunks = entity.source_chunk_ids or []

                query = """
                    INSERT INTO kg_nodes (
                        entity_id, entity_type, name, description, properties, 
                        confidence, source_collection, source_chunk_ids, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    ON CONFLICT (entity_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        properties = kg_nodes.properties || EXCLUDED.properties,
                        confidence = GREATEST(kg_nodes.confidence, EXCLUDED.confidence),
                        source_chunk_ids = array_cat(kg_nodes.source_chunk_ids, EXCLUDED.source_chunk_ids),
                        updated_at = NOW();
                """
                await self.db_pool.execute(
                    query,
                    entity.entity_id,
                    entity.entity_type,
                    entity.name,
                    entity.description,
                    json.dumps(entity.properties),
                    entity.confidence,
                    entity.source_collection,
                    chunks
                )
            except Exception as e:
                logger.error(f"Failed to persist entity {entity.entity_id}: {e}")

    async def add_relationship(self, relationship: Relationship):
        """Add relationship to graph (Persistent)"""
        # 1. Update In-Memory
        self.relationships[relationship.relationship_id] = relationship

        # 2. Persist to DB
        if self.db_pool:
            try:
                chunks = relationship.source_chunk_ids or []

                query = """
                    INSERT INTO kg_edges (
                        relationship_id, source_entity_id, target_entity_id, 
                        relationship_type, properties, confidence, source_collection, source_chunk_ids
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (relationship_id) DO UPDATE SET
                        properties = kg_edges.properties || EXCLUDED.properties,
                        confidence = GREATEST(kg_edges.confidence, EXCLUDED.confidence),
                        source_chunk_ids = array_cat(kg_edges.source_chunk_ids, EXCLUDED.source_chunk_ids);
                """
                await self.db_pool.execute(
                    query,
                    relationship.relationship_id,
                    relationship.source_entity_id,
                    relationship.target_entity_id,
                    relationship.relationship_type,
                    json.dumps(relationship.properties),
                    relationship.confidence,
                    relationship.source_collection,
                    chunks
                )
            except Exception as e:
                logger.error(f"Failed to persist relationship {relationship.relationship_id}: {e}")

    async def extract_entities(self, text: str) -> dict:
        """
        Unified extraction method.
        Prefers LLM extraction if available, falls back to Regex.
        Returns format compatible with API response.
        """
        if self.llm_gateway:
            return await self.extract_via_llm(text, source_collection="api_request")

        # Fallback to Regex
        logger.info("⚠️ LLM not available, using Regex extraction fallback")
        entities = self.extract_entities_from_text(text, source_collection="api_request")
        relationships = self.infer_relationships_from_text(text, entities, source_collection="api_request")

        # Save to DB (async)
        for e in entities:
            await self.add_entity(e)
        for r in relationships:
            await self.add_relationship(r)

        return {
            "entities": [asdict(e) for e in entities],
            "relationships": [asdict(r) for r in relationships]
        }

    def extract_entities_from_text(self, text: str, source_collection: str | None = None) -> list[Entity]:
        """Extract entities from text (Sync helper)"""
        entities = []
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity_name = (match.group(1) if match.groups() else match.group(0)).strip()
                    entity_id = f"{entity_type}_{entity_name.replace(' ', '_').lower()}"

                    if entity_id in self.entities:
                        continue

                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end].strip()

                    entity = Entity(
                        entity_id=entity_id,
                        entity_type=entity_type,
                        name=entity_name,
                        description=context,
                        source_collection=source_collection,
                        confidence=0.8,
                    )
                    entities.append(entity)
        return entities

    def infer_relationships_from_text(self, text: str, entities: list[Entity], source_collection: str | None = None) -> list[Relationship]:
        """Infer relationships (Sync helper)"""
        relationships = []
        for i, source_entity in enumerate(entities):
            for target_entity in entities[i + 1 :]:
                if source_entity.name not in text or target_entity.name not in text:
                    continue

                source_pos = text.find(source_entity.name)
                target_pos = text.find(target_entity.name)
                if source_pos == -1 or target_pos == -1:
                    continue

                start_pos = min(source_pos, target_pos)
                end_pos = max(source_pos, target_pos)
                between_text = text[start_pos:end_pos]

                for rel_type, patterns in self.RELATIONSHIP_PATTERNS.items():
                    if any(re.search(p, between_text, re.IGNORECASE) for p in patterns):
                        rel_id = f"{source_entity.entity_id}_{rel_type}_{target_entity.entity_id}"
                        relationship = Relationship(
                            relationship_id=rel_id,
                            source_entity_id=source_entity.entity_id,
                            target_entity_id=target_entity.entity_id,
                            relationship_type=rel_type,
                            source_collection=source_collection,
                            confidence=0.7,
                        )
                        relationships.append(relationship)
                        break
        return relationships

    async def build_graph_from_collection(self, collection_name: str, limit: int = 100) -> int:
        """Build knowledge graph from a single collection."""
        if not self.search:
            logger.warning("SearchService not available")
            return 0

        logger.info(f"🔨 Building knowledge graph from: {collection_name}")
        try:
            results = await self.search.search(
                query="business setup visa tax legal",
                user_level=3,
                limit=limit,
                collection_override=collection_name,
            )
        except Exception as e:
            logger.error(f"Error querying {collection_name}: {e}")
            return 0

        documents = results.get("results", [])
        total_added = 0

        for doc in documents:
            text = doc.get("text", "")
            chunk_id = str(doc.get("id", "")) or None

            # Use LLM extraction if available (more accurate)
            if self.llm_gateway:
                await self.extract_via_llm(text, source_collection=collection_name, chunk_id=chunk_id)
                total_added += 1
            else:
                entities = self.extract_entities_from_text(text, collection_name)
                for entity in entities:
                    if chunk_id: entity.source_chunk_ids = [chunk_id]
                    if entity.entity_id not in self.entities:
                        await self.add_entity(entity)
                        total_added += 1

                relationships = self.infer_relationships_from_text(text, entities, collection_name)
                for rel in relationships:
                    if chunk_id: rel.source_chunk_ids = [chunk_id]
                    if rel.relationship_id not in self.relationships:
                        await self.add_relationship(rel)
                        total_added += 1

        if collection_name not in self.graph_stats["collections_analyzed"]:
            self.graph_stats["collections_analyzed"].append(collection_name)

        return total_added

    async def _refresh_from_db(self):
        """Fetch all nodes and edges from DB to memory for export"""
        if not self.db_pool:
            return

        try:
            # Fetch Nodes
            nodes = await self.db_pool.fetch("SELECT * FROM kg_nodes")
            self.entities = {}
            for row in nodes:
                props = json.loads(row['properties']) if isinstance(row['properties'], str) else row['properties']
                entity = Entity(
                    entity_id=row['entity_id'],
                    entity_type=row['entity_type'],
                    name=row['name'],
                    description=row['description'],
                    properties=props,
                    confidence=row['confidence'],
                    source_collection=row['source_collection'],
                    source_chunk_ids=row['source_chunk_ids'] or []
                )
                self.entities[entity.entity_id] = entity

            # Fetch Edges
            edges = await self.db_pool.fetch("SELECT * FROM kg_edges")
            self.relationships = {}
            for row in edges:
                props = json.loads(row['properties']) if isinstance(row['properties'], str) else row['properties']
                rel = Relationship(
                    relationship_id=row['relationship_id'],
                    source_entity_id=row['source_entity_id'],
                    target_entity_id=row['target_entity_id'],
                    relationship_type=row['relationship_type'],
                    properties=props,
                    confidence=row['confidence'],
                    source_collection=row['source_collection'],
                    source_chunk_ids=row['source_chunk_ids'] or []
                )
                self.relationships[rel.relationship_id] = rel

            logger.info(f"🔄 Refreshed graph from DB: {len(self.entities)} nodes, {len(self.relationships)} edges")
        except Exception as e:
            logger.error(f"Failed to refresh from DB: {e}")

    async def extract_via_llm(self, text: str, source_collection: str = None, chunk_id: str = None) -> dict:
        """
        Extract entities and relationships using LLM (Semantic Extraction).
        Uses Zantara AI (via ZantaraAIClient).
        """
        if not self.llm_gateway:
            logger.warning("LLM client not available for semantic extraction")
            return {"entities": [], "relationships": []}

        prompt = f"""
        You are a Knowledge Graph Extractor. Analyze the text and extract entities and relationships.

        TEXT:
        {text[:8000]}

        RULES:
        1. Extract key business/legal entities.
        2. Normalize names (e.g., "P.T. PMA" -> "PT PMA").
        3. Infer relationships even if not explicit.

        ENTITY TYPES:
        - KBLI_CODE, LEGAL_ENTITY, VISA_TYPE, TAX_TYPE, PERMIT
        - DOCUMENT, PROCESS, REGULATION, LOCATION, SERVICE

        RELATION TYPES:
        - REQUIRES, RELATED_TO, COSTS, DURATION, TAX_OBLIGATION

        OUTPUT JSON FORMAT:
        {{
          "entities": [
            {{ "id": "type_normalized_name", "type": "TYPE", "name": "Name", "description": "Context" }}
          ],
          "relationships": [
            {{ "source": "id_1", "target": "id_2", "type": "TYPE", "description": "Context" }}
          ]
        }}
        """
        try:
            response = await self.llm_gateway.conversational(
                message=prompt,
                user_id="kg_builder",
                conversation_history=[],
                memory_context="You are a strict JSON extractor. Output ONLY valid JSON.",
                max_tokens=8192
            )

            response_text = response.get("text", "")
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            if "{" in cleaned_text:
                cleaned_text = cleaned_text[cleaned_text.find("{"):cleaned_text.rfind("}")+1]

            data = json.loads(cleaned_text)

            extracted_entities = []
            extracted_relationships = []

            chunk_ids = [chunk_id] if chunk_id else []

            for e_data in data.get("entities", []):
                e_id = e_data.get("id") or f"{e_data.get('type')}_{e_data.get('name').replace(' ', '_')}".lower()
                e_id = re.sub(r'[^a-zA-Z0-9_]', '', e_id)

                entity = Entity(
                    entity_id=e_id,
                    entity_type=e_data.get("type", "UNKNOWN"),
                    name=e_data.get("name", "Unknown"),
                    description=e_data.get("description", ""),
                    source_collection=source_collection,
                    confidence=0.9,
                    source_chunk_ids=chunk_ids
                )
                extracted_entities.append(entity)
                await self.add_entity(entity)

            for r_data in data.get("relationships", []):
                rel_id = f"{r_data.get('source')}_{r_data.get('type')}_{r_data.get('target')}".lower()
                rel_id = re.sub(r'[^a-zA-Z0-9_]', '', rel_id)

                rel = Relationship(
                    relationship_id=rel_id,
                    source_entity_id=r_data.get("source"),
                    target_entity_id=r_data.get("target"),
                    relationship_type=r_data.get("type", "RELATED_TO"),
                    properties={"description": r_data.get("description", "")},
                    source_collection=source_collection,
                    confidence=0.85,
                    source_chunk_ids=chunk_ids
                )
                extracted_relationships.append(rel)
                await self.add_relationship(rel)

            logger.info(f"🧠 Semantic Extraction: {len(extracted_entities)} entities, {len(extracted_relationships)} relationships")
            return {"entities": extracted_entities, "relationships": extracted_relationships}

        except Exception as e:
            logger.error(f"Semantic extraction failed: {e}")
            return {"entities": [], "relationships": []}

    async def export_graph(self, format: str = "json") -> str:
        """Export knowledge graph (refreshes from DB first)."""
        if self.db_pool:
            await self._refresh_from_db()

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
            raise NotImplementedError(f"Format {format} not implemented")

    def _export_cypher(self) -> str:
        """Generate Cypher queries"""
        lines = ["// Knowledge Graph Export for Neo4j"]
        lines.append("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;\n")

        for entity in self.entities.values():
            name = entity.name.replace('"', '\"')
            desc = (entity.description or "").replace('"', '\"')

            props = [
                f'id: "{entity.entity_id}"',
                f'name: "{name}"',
                f'type: "{entity.entity_type}"',
                f'description: "{desc}"',
                f'confidence: {entity.confidence}'
            ]

            for k, v in entity.properties.items():
                if isinstance(v, (int, float, bool)):
                    props.append(f'{k}: {v}')
                else:
                    val_safe = str(v).replace('"', '\"')
                    props.append(f'{k}: "{val_safe}"')

            lines.append(f'MERGE (e:Entity {{id: "{entity.entity_id}"}}) SET e += {{{", ".join(props)}}}, e:{entity.entity_type};')

        lines.append("")
        for rel in self.relationships.values():
            rel_type = rel.relationship_type.upper().replace(" ", "_")
            props = [f'id: "{rel.relationship_id}"', f'confidence: {rel.confidence}']

            for k, v in rel.properties.items():
                if isinstance(v, (int, float, bool)):
                    props.append(f'{k}: {v}')
                else:
                    val_safe = str(v).replace('"', '\"')
                    props.append(f'{k}: "{val_safe}"')

            lines.append(f'MATCH (s:Entity {{id: "{rel.source_entity_id}"}}) MATCH (t:Entity {{id: "{rel.target_entity_id}"}}) MERGE (s)-[r:{rel_type}]->(t) SET r += {{{", ".join(props)}}};')

        return "\n".join(lines)

    def _export_graphml(self) -> str:
        """Generate GraphML"""
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">', '<graph id="G" edgedefault="directed">']
        for e in self.entities.values():
            name_safe = e.name.replace("&", "&amp;").replace("<", "&lt;")
            lines.append(f'<node id="{e.entity_id}"><data key="name">{name_safe}</data></node>')
        for r in self.relationships.values():
            lines.append(f'<edge source="{r.source_entity_id}" target="{r.target_entity_id}"><data key="type">{r.relationship_type}</data></edge>')
        lines.append('</graph></graphml>')
        return "\n".join(lines)

    def get_graph_stats(self) -> dict:
        return self.graph_stats

    async def query_graph(self, entity_name: str, max_depth: int = 1) -> dict:
        """
        Query the knowledge graph for an entity and its relationships.

        Args:
            entity_name: Name of the entity to search for
            max_depth: How many hops to traverse (1 = direct connections)

        Returns:
            Dict with found status, entities, and relationships
        """
        entity_name_lower = entity_name.lower().strip()

        # Query from PostgreSQL if available
        if self.db_pool:
            return await self._query_graph_from_db(entity_name_lower, max_depth)

        # Fallback to in-memory cache
        return self._query_graph_from_memory(entity_name_lower, max_depth)

    async def _query_graph_from_db(self, entity_name_lower: str, max_depth: int) -> dict:
        """Query knowledge graph from PostgreSQL."""
        try:
            async with self.db_pool.acquire() as conn:
                # Find matching entity
                start_node = await conn.fetchrow("""
                    SELECT entity_id, entity_type, name, description, properties, confidence, source_collection
                    FROM kg_nodes
                    WHERE LOWER(name) LIKE $1
                    LIMIT 1
                """, f"%{entity_name_lower}%")

                if not start_node:
                    return {
                        "found": False,
                        "query": entity_name_lower,
                        "total_entities": 0,
                        "total_relationships": 0,
                        "start_entity": None,
                        "entities": [],
                        "relationships": [],
                    }

                start_entity = dict(start_node)
                start_entity["properties"] = start_entity.get("properties") or {}

                # Get relationships (up to max_depth hops)
                collected_entity_ids = {start_entity["entity_id"]}
                all_relationships = []

                frontier = [start_entity["entity_id"]]
                for _ in range(max_depth):
                    if not frontier:
                        break

                    # Get edges connected to frontier nodes
                    edges = await conn.fetch("""
                        SELECT relationship_id, source_entity_id, target_entity_id,
                               relationship_type, properties, confidence, source_collection
                        FROM kg_edges
                        WHERE source_entity_id = ANY($1) OR target_entity_id = ANY($1)
                    """, frontier)

                    next_frontier = []
                    for edge in edges:
                        edge_dict = dict(edge)
                        edge_dict["properties"] = edge_dict.get("properties") or {}
                        if edge_dict["relationship_id"] not in [r["relationship_id"] for r in all_relationships]:
                            all_relationships.append(edge_dict)

                            # Add connected entities to next frontier
                            for eid in [edge_dict["source_entity_id"], edge_dict["target_entity_id"]]:
                                if eid not in collected_entity_ids:
                                    collected_entity_ids.add(eid)
                                    next_frontier.append(eid)

                    frontier = next_frontier

                # Fetch all collected entities
                all_entities = []
                if collected_entity_ids:
                    entities = await conn.fetch("""
                        SELECT entity_id, entity_type, name, description, properties, confidence, source_collection
                        FROM kg_nodes
                        WHERE entity_id = ANY($1)
                    """, list(collected_entity_ids))
                    all_entities = [dict(e) for e in entities]
                    for e in all_entities:
                        e["properties"] = e.get("properties") or {}

                return {
                    "found": True,
                    "query": entity_name_lower,
                    "total_entities": len(all_entities),
                    "total_relationships": len(all_relationships),
                    "start_entity": start_entity,
                    "entities": all_entities,
                    "relationships": all_relationships,
                }

        except Exception as e:
            logger.error(f"Error querying KG from DB: {e}")
            return self._query_graph_from_memory(entity_name_lower, max_depth)

    def _query_graph_from_memory(self, entity_name_lower: str, max_depth: int) -> dict:
        """Query knowledge graph from in-memory cache."""
        # Find matching entity (fuzzy match on name)
        start_entity = None
        for eid, entity in self.entities.items():
            if entity_name_lower in entity.name.lower():
                start_entity = entity
                break

        if not start_entity:
            return {
                "found": False,
                "query": entity_name_lower,
                "total_entities": 0,
                "total_relationships": 0,
                "start_entity": None,
                "entities": [],
                "relationships": [],
            }

        # Collect entities and relationships within depth
        collected_entity_ids = {start_entity.entity_id}
        collected_relationships = []

        # BFS traversal
        frontier = [start_entity.entity_id]
        for _ in range(max_depth):
            next_frontier = []
            for eid in frontier:
                for rid, rel in self.relationships.items():
                    if rel.source_entity_id == eid:
                        if rid not in [r["relationship_id"] for r in collected_relationships]:
                            collected_relationships.append(asdict(rel))
                            if rel.target_entity_id not in collected_entity_ids:
                                collected_entity_ids.add(rel.target_entity_id)
                                next_frontier.append(rel.target_entity_id)
                    elif rel.target_entity_id == eid:
                        if rid not in [r["relationship_id"] for r in collected_relationships]:
                            collected_relationships.append(asdict(rel))
                            if rel.source_entity_id not in collected_entity_ids:
                                collected_entity_ids.add(rel.source_entity_id)
                                next_frontier.append(rel.source_entity_id)
            frontier = next_frontier

        # Collect entity data
        collected_entities = []
        for eid in collected_entity_ids:
            if eid in self.entities:
                collected_entities.append(asdict(self.entities[eid]))

        return {
            "found": True,
            "query": entity_name_lower,
            "total_entities": len(collected_entities),
            "total_relationships": len(collected_relationships),
            "start_entity": asdict(start_entity),
            "entities": collected_entities,
            "relationships": collected_relationships,
        }
