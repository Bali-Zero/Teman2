"""
Knowledge Graph Pipeline Orchestrator
Complete end-to-end pipeline for extracting KG from Indonesian legal documents

Based on:
- KGGen (Stanford, NeurIPS 2025)
- CORE-KG/LINK-KG for legal domain
- GraphRAG best practices
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import asyncpg

from .ontology import EntityType, RelationType
from .extractor import KGExtractor, ExtractedEntity, ExtractedRelation, ExtractionResult
from .coreference import CoreferenceResolver

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for KG Pipeline"""
    # Model settings
    model: str = "claude-sonnet-4-20250514"
    api_key: str | None = None

    # Extraction settings
    two_stage_extraction: bool = False  # Faster single-stage by default
    use_coreference: bool = True
    min_confidence: float = 0.6

    # Batch settings
    batch_size: int = 10
    max_concurrent: int = 5

    # Database
    database_url: str | None = None

    # Logging
    log_every: int = 50


@dataclass
class PipelineStats:
    """Statistics from pipeline run"""
    chunks_processed: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    entities_persisted: int = 0
    relations_persisted: int = 0
    duplicates_merged: int = 0
    errors: int = 0
    start_time: datetime | None = None
    end_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunks_processed": self.chunks_processed,
            "entities_extracted": self.entities_extracted,
            "relations_extracted": self.relations_extracted,
            "entities_persisted": self.entities_persisted,
            "relations_persisted": self.relations_persisted,
            "duplicates_merged": self.duplicates_merged,
            "errors": self.errors,
            "duration_seconds": (
                (self.end_time - self.start_time).total_seconds()
                if self.start_time and self.end_time else 0
            ),
        }


class KGPipeline:
    """
    Main Knowledge Graph Extraction Pipeline

    Orchestrates:
    1. Chunk retrieval from Qdrant
    2. LLM-based entity/relation extraction
    3. Coreference resolution and deduplication
    4. Persistence to PostgreSQL
    """

    def __init__(self, config: PipelineConfig | None = None):
        """
        Initialize KG Pipeline

        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()

        # Initialize components
        self.extractor = KGExtractor(
            model=self.config.model,
            api_key=self.config.api_key,
        )

        self.coreference = CoreferenceResolver(
            use_llm=self.config.use_coreference,
            model=self.config.model,
            api_key=self.config.api_key,
        )

        # Database connection
        self._db_pool: asyncpg.Pool | None = None

        # Stats
        self.stats = PipelineStats()

        # Global entity registry for cross-chunk deduplication
        self.entity_registry: dict[str, ExtractedEntity] = {}
        self.relation_registry: set[str] = set()

        logger.info(f"KGPipeline initialized with config: {self.config}")

    async def _get_db(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if self._db_pool is None:
            import os
            db_url = self.config.database_url or os.environ.get("DATABASE_URL")
            if not db_url:
                raise ValueError("DATABASE_URL not configured")
            self._db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
        return self._db_pool

    async def close(self):
        """Close resources"""
        if self._db_pool:
            await self._db_pool.close()
            self._db_pool = None

    async def process_chunk(
        self,
        chunk_id: str,
        text: str,
    ) -> ExtractionResult:
        """
        Process a single chunk through the pipeline

        Args:
            chunk_id: ID of the chunk
            text: Text content

        Returns:
            ExtractionResult with entities and relations
        """
        try:
            # Stage 1: Extract entities and relations
            result = await self.extractor.extract(
                text=text,
                chunk_id=chunk_id,
                two_stage=self.config.two_stage_extraction,
            )

            self.stats.entities_extracted += len(result.entities)
            self.stats.relations_extracted += len(result.relations)

            # Build mapping from local IDs to canonical IDs BEFORE any transformations
            # This must happen before coreference deduplication changes entity IDs
            local_to_canonical: dict[str, str] = {}
            for entity in result.entities:
                canonical_id = self._get_canonical_id(entity)
                local_to_canonical[entity.id] = canonical_id

            # Update relation IDs to use canonical entity IDs
            for relation in result.relations:
                relation.source_id = local_to_canonical.get(relation.source_id, relation.source_id)
                relation.target_id = local_to_canonical.get(relation.target_id, relation.target_id)

            # Stage 2: Coreference resolution and deduplication
            if self.config.use_coreference and result.entities:
                # Resolve references
                resolutions = await self.coreference.resolve_all_references(
                    text, result.entities
                )

                # Deduplicate entities
                original_count = len(result.entities)
                result.entities = self.coreference.deduplicate_entities(result.entities)
                self.stats.duplicates_merged += original_count - len(result.entities)

                # Update coreference cache
                clusters = self.coreference.cluster_entities(result.entities)
                self.coreference.update_cache(clusters)

            # Stage 3: Filter by confidence
            result.entities = [
                e for e in result.entities
                if e.confidence >= self.config.min_confidence
            ]
            result.relations = [
                r for r in result.relations
                if r.confidence >= self.config.min_confidence
            ]

            # Get set of valid entity canonical IDs after filtering
            valid_entity_ids = {self._get_canonical_id(e) for e in result.entities}

            # Filter out relations that reference non-existent entities
            result.relations = [
                r for r in result.relations
                if r.source_id in valid_entity_ids and r.target_id in valid_entity_ids
            ]

            # Update global registry and normalize entity IDs
            for entity in result.entities:
                canonical_id = self._get_canonical_id(entity)
                if canonical_id not in self.entity_registry:
                    self.entity_registry[canonical_id] = entity
                entity.id = canonical_id  # Normalize ID

            return result

        except Exception as e:
            logger.error(f"Error processing chunk {chunk_id}: {e}")
            self.stats.errors += 1
            return ExtractionResult(chunk_id=chunk_id, raw_text=text)

    def _get_canonical_id(self, entity: ExtractedEntity) -> str:
        """Get canonical ID for an entity"""
        name_normalized = entity.name.upper().strip().replace(" ", "_")
        return f"{entity.type.value}_{name_normalized.lower()}"

    def _get_canonical_id_by_local(
        self, local_id: str, entities: list[ExtractedEntity]
    ) -> str:
        """Map local entity ID to canonical ID"""
        for entity in entities:
            if entity.id == local_id:
                return self._get_canonical_id(entity)
        return local_id

    async def persist_results(
        self,
        results: list[ExtractionResult],
        source_collection: str = "legal_unified_hybrid",
    ):
        """
        Persist extraction results to PostgreSQL

        Args:
            results: List of extraction results
            source_collection: Source collection name
        """
        pool = await self._get_db()

        async with pool.acquire() as conn:
            # Collect all unique entities and relations
            all_entities: dict[str, tuple[ExtractedEntity, list[str]]] = {}
            all_relations: list[tuple[ExtractedRelation, str]] = []

            for result in results:
                for entity in result.entities:
                    eid = entity.id
                    if eid not in all_entities:
                        all_entities[eid] = (entity, [result.chunk_id])
                    else:
                        all_entities[eid][1].append(result.chunk_id)

                for relation in result.relations:
                    all_relations.append((relation, result.chunk_id))

            # Persist entities
            for eid, (entity, chunk_ids) in all_entities.items():
                try:
                    await conn.execute(
                        """
                        INSERT INTO kg_nodes (
                            entity_id, entity_type, name, description,
                            properties, confidence, source_collection,
                            source_chunk_ids, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                        ON CONFLICT (entity_id) DO UPDATE SET
                            properties = kg_nodes.properties || $5,
                            source_chunk_ids = (
                                SELECT array_agg(DISTINCT elem)
                                FROM unnest(
                                    COALESCE(kg_nodes.source_chunk_ids, ARRAY[]::text[]) || $8
                                ) elem
                            ),
                            confidence = GREATEST(kg_nodes.confidence, $6),
                            updated_at = NOW()
                        """,
                        entity.id,
                        entity.type.value,
                        entity.name,
                        None,  # description
                        json.dumps(entity.attributes),
                        entity.confidence,
                        source_collection,
                        chunk_ids[:50],  # Limit chunk IDs
                    )
                    self.stats.entities_persisted += 1
                except Exception as e:
                    logger.error(f"Failed to persist entity {eid}: {e}")

            # Persist relations
            seen_relations: set[str] = set()
            for relation, chunk_id in all_relations:
                rel_id = f"{relation.source_id}_{relation.type.value}_{relation.target_id}"

                if rel_id in seen_relations or rel_id in self.relation_registry:
                    continue

                seen_relations.add(rel_id)
                self.relation_registry.add(rel_id)

                try:
                    await conn.execute(
                        """
                        INSERT INTO kg_edges (
                            relationship_id, source_entity_id, target_entity_id,
                            relationship_type, properties, confidence,
                            source_collection, source_chunk_ids, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                        ON CONFLICT DO NOTHING
                        """,
                        rel_id,
                        relation.source_id,
                        relation.target_id,
                        relation.type.value,
                        json.dumps({"evidence": relation.evidence}),
                        relation.confidence,
                        source_collection,
                        [chunk_id],
                    )
                    self.stats.relations_persisted += 1
                except Exception as e:
                    logger.debug(f"Failed to persist relation {rel_id}: {e}")

    async def process_batch(
        self,
        chunks: list[tuple[str, str]],  # List of (chunk_id, text)
    ) -> list[ExtractionResult]:
        """
        Process a batch of chunks with concurrency control

        Args:
            chunks: List of (chunk_id, text) tuples

        Returns:
            List of ExtractionResults
        """
        semaphore = asyncio.Semaphore(self.config.max_concurrent)

        async def process_with_semaphore(chunk_id: str, text: str):
            async with semaphore:
                return await self.process_chunk(chunk_id, text)

        tasks = [
            process_with_semaphore(chunk_id, text)
            for chunk_id, text in chunks
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, ExtractionResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Batch processing error: {result}")
                self.stats.errors += 1

        return valid_results

    async def run(
        self,
        chunks: list[tuple[str, str]],
        source_collection: str = "legal_unified_hybrid",
        persist: bool = True,
    ) -> PipelineStats:
        """
        Run the full pipeline on a list of chunks

        Args:
            chunks: List of (chunk_id, text) tuples
            source_collection: Source collection name
            persist: Whether to persist results to database

        Returns:
            Pipeline statistics
        """
        self.stats = PipelineStats(start_time=datetime.now())

        total = len(chunks)
        logger.info(f"Starting KG Pipeline for {total} chunks")

        # Process in batches
        for i in range(0, total, self.config.batch_size):
            batch = chunks[i:i + self.config.batch_size]

            # Process batch
            results = await self.process_batch(batch)
            self.stats.chunks_processed += len(batch)

            # Persist results
            if persist and results:
                await self.persist_results(results, source_collection)

            # Log progress
            if (i + self.config.batch_size) % self.config.log_every == 0:
                logger.info(
                    f"Progress: {self.stats.chunks_processed}/{total} chunks, "
                    f"{self.stats.entities_persisted} entities, "
                    f"{self.stats.relations_persisted} relations"
                )

        self.stats.end_time = datetime.now()

        logger.info(
            f"Pipeline completed: {self.stats.chunks_processed} chunks, "
            f"{self.stats.entities_persisted} entities, "
            f"{self.stats.relations_persisted} relations, "
            f"{self.stats.errors} errors"
        )

        return self.stats

    async def run_from_qdrant(
        self,
        collection_name: str = "legal_unified_hybrid",
        limit: int | None = None,
        persist: bool = True,
    ) -> PipelineStats:
        """
        Run pipeline fetching chunks from Qdrant

        Args:
            collection_name: Qdrant collection name
            limit: Maximum chunks to process (None for all)
            persist: Whether to persist results

        Returns:
            Pipeline statistics
        """
        from core.qdrant_db import QdrantClient

        self.stats = PipelineStats(start_time=datetime.now())

        logger.info(f"Starting KG Pipeline from Qdrant collection '{collection_name}'")

        # Initialize Qdrant client
        qdrant = QdrantClient(collection_name=collection_name)
        http = await qdrant._get_client()

        try:
            # Get collection stats
            stats = await qdrant.get_collection_stats()
            total_docs = stats.get("total_documents", 0)
            logger.info(f"Collection has {total_docs} documents")

            if limit:
                total_docs = min(total_docs, limit)

            # Scroll through all documents
            offset = None
            processed = 0

            while processed < total_docs:
                # Fetch batch
                payload = {
                    "limit": min(self.config.batch_size * 10, 250),
                    "with_payload": True,
                    "with_vectors": False,
                }
                if offset:
                    payload["offset"] = offset

                resp = await http.post(
                    f"/collections/{collection_name}/points/scroll",
                    json=payload,
                )
                data = resp.json().get("result", {})
                points = data.get("points", [])
                offset = data.get("next_page_offset")

                if not points:
                    break

                # Convert to chunks
                chunks = []
                for point in points:
                    chunk_id = str(point.get("id", ""))
                    text = (
                        point.get("payload", {}).get("text", "") or
                        point.get("payload", {}).get("content", "")
                    )
                    if text and len(text.strip()) > 20:
                        chunks.append((chunk_id, text))

                    if limit and processed + len(chunks) >= limit:
                        chunks = chunks[:limit - processed]
                        break

                # Process batch
                results = await self.process_batch(chunks)
                self.stats.chunks_processed += len(chunks)

                # Persist
                if persist and results:
                    await self.persist_results(results, collection_name)

                processed += len(chunks)

                # Log progress
                if processed % self.config.log_every == 0:
                    logger.info(
                        f"Progress: {processed}/{total_docs} chunks, "
                        f"{self.stats.entities_persisted} entities, "
                        f"{self.stats.relations_persisted} relations"
                    )

                if not offset or (limit and processed >= limit):
                    break

        finally:
            await qdrant.close()

        self.stats.end_time = datetime.now()

        logger.info(
            f"Pipeline completed: {self.stats.chunks_processed} chunks, "
            f"{self.stats.entities_persisted} entities, "
            f"{self.stats.relations_persisted} relations"
        )

        return self.stats

    def get_stats(self) -> dict[str, Any]:
        """Get current pipeline statistics"""
        return self.stats.to_dict()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get coreference cache statistics"""
        return {
            "entity_registry_size": len(self.entity_registry),
            "relation_registry_size": len(self.relation_registry),
            "coreference_cache": self.coreference.get_cache_stats(),
        }
