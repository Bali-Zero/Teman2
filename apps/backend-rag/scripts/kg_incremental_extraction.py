#!/usr/bin/env python3
"""
KG Incremental Extraction Script

Extracts Knowledge Graph entities from Qdrant chunks that haven't been processed yet.
Uses Gemini Flash for semantic extraction.

Usage:
    python scripts/kg_incremental_extraction.py [--collection COLLECTION] [--limit LIMIT] [--dry-run]

Examples:
    # Extract from all collections (dry run)
    python scripts/kg_incremental_extraction.py --dry-run

    # Extract from specific collection
    python scripts/kg_incremental_extraction.py --collection visa_oracle --limit 100

    # Full extraction
    python scripts/kg_incremental_extraction.py
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from functools import wraps

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def retry_qdrant(max_retries=3, delay=2):
    """Decorator for retrying Qdrant operations."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2**attempt)  # Exponential backoff
                        logging.warning(
                            f"Qdrant error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
            raise last_error

        return wrapper

    return decorator


import asyncpg  # noqa: E402
import httpx  # noqa: E402

from backend.llm.genai_client import get_genai_client  # noqa: E402

try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Gemini extraction prompt
EXTRACTION_PROMPT = """You are a Knowledge Graph Extractor for Indonesian business/legal documents.

TEXT:
{text}

INSTRUCTIONS:
1. Extract ALL relevant entities (laws, regulations, permits, visas, taxes, companies, costs, durations)
2. Normalize names (e.g., "U.U. No. 25" -> "UU 25", "P.T. PMA" -> "PT PMA")
3. Identify relationships between entities
4. Be thorough - extract everything relevant

ENTITY TYPES (use these exact types):
- undang_undang: Laws (UU, Undang-Undang)
- peraturan_pemerintah: Government regulations (PP)
- permen: Ministerial regulations
- perpres: Presidential regulations
- perda: Regional regulations
- pasal: Articles (Pasal X)
- kbli: Business classification codes (KBLI XXXXX)
- pt_pma: Foreign investment companies
- pt_pmdn: Domestic investment companies
- kitas: Work permits (KITAS, ITAS)
- kitap: Permanent stay permits
- vitas: Visit visas
- rptka: Foreign worker plans
- imta: Work permits
- ppn: VAT
- pph_21: Income tax article 21
- pph_23: Income tax article 23
- npwp: Tax ID
- nib: Business ID
- oss: Online Single Submission
- izin_usaha: Business permits
- biaya: Costs/fees
- jangka_waktu: Time periods/durations
- dokumen: Documents
- sanksi: Sanctions/penalties

RELATIONSHIP TYPES:
- REQUIRES: A requires B
- PART_OF: A is part of B
- REFERENCES: A references B
- APPLIES_TO: A applies to B
- HAS_DURATION: A has duration B
- HAS_FEE: A has fee B
- PENALTY_FOR: A is penalty for B
- AMENDS: A amends B
- ISSUED_BY: A is issued by B

OUTPUT (valid JSON only, no markdown):
{{
  "entities": [
    {{"id": "type_normalized_name", "type": "TYPE", "name": "Display Name", "description": "Brief context"}}
  ],
  "relationships": [
    {{"source": "entity_id_1", "target": "entity_id_2", "type": "RELATIONSHIP_TYPE"}}
  ]
}}
"""


class KGIncrementalExtractor:
    """Extracts KG entities from unprocessed Qdrant chunks."""

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        qdrant_url: str,
        qdrant_api_key: str,
        gemini_client=None,
        openai_client=None,
        provider: str = "gemini",
    ):
        self.db_pool = db_pool
        self.qdrant_url = qdrant_url.rstrip("/")
        self.qdrant_api_key = qdrant_api_key
        self.gemini = gemini_client
        self.openai = openai_client
        self.provider = provider
        self.stats = {
            "chunks_processed": 0,
            "entities_extracted": 0,
            "relationships_extracted": 0,
            "errors": 0,
            "start_time": None,
        }

    def _llm_available(self) -> bool:
        """Check if the configured LLM provider is available."""
        if self.provider == "openai":
            return self.openai is not None
        return self.gemini is not None and getattr(self.gemini, "is_available", True)

    def _qdrant_request(self, method: str, endpoint: str, json_data: dict = None) -> dict:
        """Make HTTP request to Qdrant API with retries."""
        url = f"{self.qdrant_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        if self.qdrant_api_key:
            headers["api-key"] = self.qdrant_api_key

        for attempt in range(5):
            try:
                with httpx.Client(timeout=120) as client:
                    if method == "GET":
                        resp = client.get(url, headers=headers)
                    elif method == "POST":
                        resp = client.post(url, headers=headers, json=json_data)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as e:
                if attempt < 4:
                    wait_time = 3 * (2**attempt)
                    logger.warning(
                        f"Qdrant request failed (attempt {attempt + 1}/5): {e}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    raise

    async def get_processed_chunk_ids(self) -> set:
        """Get all chunk IDs already in KG."""
        query = "SELECT DISTINCT unnest(source_chunk_ids) as chunk_id FROM kg_nodes WHERE source_chunk_ids IS NOT NULL"
        rows = await self.db_pool.fetch(query)
        return {r["chunk_id"] for r in rows if r["chunk_id"]}

    def get_qdrant_collections(self) -> list:
        """Get list of Qdrant collections."""
        result = self._qdrant_request("GET", "/collections")
        return [c["name"] for c in result.get("result", {}).get("collections", [])]

    def get_collection_chunks(
        self,
        collection_name: str,
        limit: int = None,
        offset: int = 0,  # noqa: ARG002
    ) -> list:
        """Get chunks from a Qdrant collection using scroll API with pagination."""
        chunks = []
        batch_size = 100  # Qdrant scroll batch size
        next_offset = None

        while True:
            # Build scroll request
            scroll_data = {"limit": batch_size, "with_payload": True, "with_vectors": False}
            if next_offset is not None:
                scroll_data["offset"] = next_offset

            result = self._qdrant_request(
                "POST", f"/collections/{collection_name}/points/scroll", scroll_data
            )

            points = result.get("result", {}).get("points", [])
            next_offset = result.get("result", {}).get("next_page_offset")

            if not points:
                break

            for point in points:
                chunk_id = str(point.get("id", ""))
                payload = point.get("payload", {})
                text = payload.get("text", "") or payload.get("content", "")
                if text:
                    chunks.append(
                        {
                            "id": chunk_id,
                            "text": text,
                            "collection": collection_name,
                            "metadata": payload,
                        }
                    )

                if limit and len(chunks) >= limit:
                    return chunks[:limit]

            # Stop if no more pages
            if next_offset is None:
                break

            # Progress log for large collections
            if len(chunks) % 1000 == 0:
                logger.info(f"  Scrolled {len(chunks):,} chunks from {collection_name}...")

        return chunks[:limit] if limit else chunks

    async def _fetch_chunks_from_collection(
        self, collection_name: str, document_id: str = None, limit: int = None
    ) -> list[dict]:
        """
        Fetch chunks from Qdrant collection using native filters.
        """
        chunks = []
        batch_size = 100
        next_offset = None

        # Build native filter if document_id provided
        filter_data = None
        if document_id:
            filter_data = {"must": [{"key": "document_id", "match": {"value": document_id}}]}

        while True:
            # Build scroll request
            scroll_data = {"limit": batch_size, "with_payload": True, "with_vectors": False}
            if next_offset is not None:
                scroll_data["offset"] = next_offset

            if filter_data:
                scroll_data["filter"] = filter_data

            result = self._qdrant_request(
                "POST", f"/collections/{collection_name}/points/scroll", scroll_data
            )

            points = result.get("result", {}).get("points", [])
            next_offset = result.get("result", {}).get("next_page_offset")

            if not points:
                break

            for point in points:
                chunk_id = str(point.get("id", ""))
                payload = point.get("payload", {})
                text = payload.get("text", "") or payload.get("content", "")
                if text:
                    chunks.append(
                        {
                            "id": chunk_id,
                            "text": text,
                            "collection": collection_name,
                            "metadata": payload,
                        }
                    )

                if limit and len(chunks) >= limit:
                    return chunks[:limit]

            if next_offset is None:
                break

        return chunks[:limit] if limit else chunks

    async def extract_from_collection(
        self,
        collection_name: str,
        document_id: str = None,
        limit: int = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Extract KG from chunks in a collection, optionally filtered by document_id.

        Args:
            collection_name: Qdrant collection name
            document_id: Optional document_id filter (from metadata)
            limit: Max chunks to process
            dry_run: If True, don't save to DB

        Returns:
            Dict with extraction stats
        """
        # Reset stats for this extraction
        initial_entities = self.stats["entities_extracted"]
        initial_relationships = self.stats["relationships_extracted"]
        initial_chunks = self.stats["chunks_processed"]

        # Fetch chunks from collection
        chunks = await self._fetch_chunks_from_collection(
            collection_name=collection_name, document_id=document_id, limit=limit
        )

        logger.info(f"Found {len(chunks)} chunks to process (document_id={document_id})")

        if dry_run:
            return {
                "chunks_processed": len(chunks),
                "entities_extracted": 0,
                "relationships_extracted": 0,
            }

        if not self._llm_available():
            logger.warning("LLM client not available - skipping extraction")
            return {"chunks_processed": 0, "entities_extracted": 0, "relationships_extracted": 0}

        # Process each chunk
        for chunk in chunks:
            try:
                # Extract entities/relationships
                result = await self.extract_entities(chunk["text"])

                # Save entities
                for entity in result.get("entities", []):
                    await self.save_entity(
                        entity=entity, chunk_id=chunk["id"], collection=collection_name
                    )

                # Save relationships
                for rel in result.get("relationships", []):
                    await self.save_relationship(
                        rel=rel, chunk_id=chunk["id"], collection=collection_name
                    )
            except Exception as e:
                logger.warning(f"Error processing chunk {chunk['id']}: {e}")
                self.stats["errors"] += 1

        # Calculate stats for this extraction
        entities_extracted = self.stats["entities_extracted"] - initial_entities
        relationships_extracted = self.stats["relationships_extracted"] - initial_relationships
        chunks_processed = self.stats["chunks_processed"] - initial_chunks

        return {
            "chunks_processed": chunks_processed,
            "entities_extracted": entities_extracted,
            "relationships_extracted": relationships_extracted,
        }

    async def extract_with_gemini(self, text: str) -> dict:
        """Extract entities using Gemini."""
        if not self.gemini or not getattr(self.gemini, "is_available", True):
            return {"entities": [], "relationships": []}

        prompt = EXTRACTION_PROMPT.format(text=text[:8000])

        try:
            # Use the new GenAIClient wrapper
            response = await self.gemini.generate_content(
                model="gemini-2.0-flash-001",
                contents=prompt,
                temperature=0.1,  # Low temperature for extraction
            )
            response_text = response["text"].strip()

            # Clean JSON from markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            # Parse JSON
            result = json.loads(response_text)
            return result
        except Exception as e:
            logger.warning(f"Extraction failed: {e}")
            return {"entities": [], "relationships": []}

    async def extract_with_openai(self, text: str) -> dict:
        """Extract entities using OpenAI gpt-4o-mini."""
        if not self.openai:
            return {"entities": [], "relationships": []}

        prompt = EXTRACTION_PROMPT.format(text=text[:8000])

        try:
            model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            extra = {}
            if os.environ.get("OPENAI_BASE_URL", "").startswith("http://localhost"):
                # Ollama: no response_format json_object (not supported by all models)
                # Use think:false for qwen3.5 to disable chain-of-thought
                extra = {"extra_body": {"think": False}}
            else:
                extra = {"response_format": {"type": "json_object"}}
            response = await self.openai.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                **extra,
            )
            response_text = response.choices[0].message.content.strip()

            # Clean JSON from markdown (shouldn't happen with json_object mode, but safety)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            result = json.loads(response_text)
            return result
        except Exception as e:
            logger.warning(f"OpenAI extraction failed: {e}")
            return {"entities": [], "relationships": []}

    async def extract_entities(self, text: str) -> dict:
        """Route extraction to the configured provider."""
        if self.provider == "openai":
            return await self.extract_with_openai(text)
        return await self.extract_with_gemini(text)

    async def save_entity(self, entity: dict, chunk_id: str, collection: str):
        """Save entity to PostgreSQL."""
        entity_id = entity.get("id", "").lower().replace(" ", "_")
        if not entity_id:
            return

        query = """
            INSERT INTO kg_nodes (
                entity_id, entity_type, name, description, properties,
                confidence, source_collection, source_chunk_ids, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            ON CONFLICT (entity_id) DO UPDATE SET
                description = COALESCE(NULLIF(EXCLUDED.description, ''), kg_nodes.description),
                confidence = GREATEST(kg_nodes.confidence, EXCLUDED.confidence),
                source_chunk_ids = (
                    SELECT array_agg(DISTINCT x)
                    FROM unnest(array_cat(kg_nodes.source_chunk_ids, EXCLUDED.source_chunk_ids)) x
                ),
                updated_at = NOW();
        """

        await self.db_pool.execute(
            query,
            entity_id,
            entity.get("type", "unknown").lower(),
            entity.get("name", entity_id),
            entity.get("description", ""),
            json.dumps({}),
            0.9,  # High confidence for LLM extraction
            collection,
            [chunk_id],
        )

    async def save_relationship(
        self,
        rel: dict,
        chunk_id: str,
        collection: str,
        new_entity_ids: set = None,  # noqa: ARG002
    ):
        """Save relationship to PostgreSQL."""
        source_id = rel.get("source", "").lower().replace(" ", "_")
        target_id = rel.get("target", "").lower().replace(" ", "_")
        rel_type = rel.get("type", "RELATED_TO").upper()

        if not source_id or not target_id:
            return False

        rel_id = f"{source_id}_{rel_type}_{target_id}"

        query = """
            INSERT INTO kg_edges (
                relationship_id, source_entity_id, target_entity_id,
                relationship_type, properties, confidence, source_collection, source_chunk_ids
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (relationship_id) DO UPDATE SET
                confidence = GREATEST(kg_edges.confidence, EXCLUDED.confidence),
                source_chunk_ids = (
                    SELECT array_agg(DISTINCT x)
                    FROM unnest(array_cat(kg_edges.source_chunk_ids, EXCLUDED.source_chunk_ids)) x
                );
        """

        try:
            await self.db_pool.execute(
                query,
                rel_id,
                source_id,
                target_id,
                rel_type,
                json.dumps({}),
                0.9,
                collection,
                [chunk_id],
            )
            return True
        except Exception as e:
            # FK constraint violations are expected for orphan relationships
            if "foreign key constraint" not in str(e).lower():
                logger.warning(f"Error saving relationship {rel_id}: {e}")
            return False

    async def process_chunk(self, chunk: dict) -> int:
        """Process a single chunk and extract entities."""
        text = chunk["text"]
        chunk_id = chunk["id"]
        collection = chunk["collection"]

        # Extract with configured provider
        result = await self.extract_entities(text)

        entities = result.get("entities", [])
        relationships = result.get("relationships", [])

        # Collect valid entity IDs as we save them
        valid_entity_ids = set()

        # Save entities first
        for entity in entities:
            entity_id = entity.get("id", "").lower().replace(" ", "_")
            if entity_id:
                await self.save_entity(entity, chunk_id, collection)
                valid_entity_ids.add(entity_id)
                self.stats["entities_extracted"] += 1

        # Save relationships (FK constraint will handle invalid refs)
        for rel in relationships:
            if await self.save_relationship(rel, chunk_id, collection):
                self.stats["relationships_extracted"] += 1

        self.stats["chunks_processed"] += 1
        return len(entities) + len(relationships)

    async def run(self, collections: list = None, limit: int = None, dry_run: bool = False):
        """Run incremental extraction."""
        self.stats["start_time"] = time.time()

        # Get already processed chunks
        logger.info("Fetching processed chunk IDs...")
        processed_ids = await self.get_processed_chunk_ids()
        logger.info(f"Found {len(processed_ids):,} already processed chunks")

        # Get collections to process
        if not collections:
            collections = self.get_qdrant_collections()
        logger.info(f"Processing collections: {collections}")

        total_unprocessed = 0
        chunks_to_process = []

        # Gather unprocessed chunks
        for collection in collections:
            logger.info(f"Scanning {collection}...")

            try:
                # Get all chunks from collection
                all_chunks = self.get_collection_chunks(collection, limit=limit)

                # Filter unprocessed
                unprocessed = [c for c in all_chunks if c["id"] not in processed_ids]

                logger.info(
                    f"  {collection}: {len(unprocessed):,} unprocessed / {len(all_chunks):,} total"
                )
                total_unprocessed += len(unprocessed)
                chunks_to_process.extend(unprocessed)

            except Exception as e:
                logger.error(f"Error scanning {collection}: {e}")

        logger.info(f"\nTotal unprocessed chunks: {total_unprocessed:,}")

        if dry_run:
            logger.info("DRY RUN - No extraction performed")
            return self.stats

        if not self._llm_available():
            logger.error("LLM client not available - cannot proceed")
            return self.stats

        # OpenAI has much higher RPM (500+), Gemini free tier is 15 RPM
        if self.provider == "openai":
            is_local = os.environ.get("OPENAI_BASE_URL", "").startswith("http://localhost")
            batch_size = 1 if is_local else 5
            sleep_between = 0.5 if is_local else 1.0
            logger.info(
                f"\nStarting extraction with OpenAI (parallel workers: {batch_size}, local={is_local})..."
            )
        else:
            batch_size = 2
            sleep_between = 8.0
            logger.info(
                f"\nStarting extraction with Gemini (parallel workers: {batch_size}, Free Tier: 15 RPM)..."
            )

        for i in range(0, len(chunks_to_process), batch_size):
            batch = chunks_to_process[i : i + batch_size]

            try:
                # Process batch in parallel
                tasks = [self.process_chunk(chunk) for chunk in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

                if (i + batch_size) % 10 == 0 or i + batch_size >= len(chunks_to_process):
                    elapsed = time.time() - self.stats["start_time"]
                    rate = self.stats["chunks_processed"] / elapsed * 60 if elapsed > 0 else 0
                    logger.info(
                        f"Progress: {min(i + batch_size, len(chunks_to_process))}/{len(chunks_to_process)} chunks | "
                        f"Entities: {self.stats['entities_extracted']:,} | "
                        f"Rate: {rate:.1f} chunks/min"
                    )

                # Rate limit between batches
                await asyncio.sleep(sleep_between)

            except Exception as e:
                logger.error(f"Error processing batch at {i}: {e}")
                self.stats["errors"] += 1

        # Final stats
        elapsed = time.time() - self.stats["start_time"]
        logger.info("\n=== EXTRACTION COMPLETE ===")
        logger.info(f"Chunks processed: {self.stats['chunks_processed']:,}")
        logger.info(f"Entities extracted: {self.stats['entities_extracted']:,}")
        logger.info(f"Relationships extracted: {self.stats['relationships_extracted']:,}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Time: {elapsed / 60:.1f} minutes")

        return self.stats


async def main():
    parser = argparse.ArgumentParser(description="KG Incremental Extraction")
    parser.add_argument("--collection", type=str, help="Specific collection to process")
    parser.add_argument("--limit", type=int, help="Limit chunks per collection")
    parser.add_argument("--dry-run", action="store_true", help="Just show what would be processed")
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=["gemini", "openai"],
        help="LLM provider for extraction (default: openai)",
    )
    args = parser.parse_args()

    # Database connection
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        return

    db_pool = await asyncpg.create_pool(database_url, min_size=2, max_size=5)

    # Qdrant connection - use environment variable or Qdrant Cloud
    # Flycast is unstable for long-running connections, use external URL
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")

    if not qdrant_url:
        logger.error("QDRANT_URL not set")
        return

    logger.info(f"Using Qdrant: {qdrant_url[:50]}...")

    # LLM client initialization (optional for dry-run)
    gemini = None
    openai_client = None
    provider = args.provider

    if not args.dry_run:
        if provider == "openai":
            openai_key = os.environ.get("OPENAI_API_KEY")
            openai_base_url = os.environ.get("OPENAI_BASE_URL")
            openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            if openai_key and OPENAI_AVAILABLE:
                client_kwargs = {"api_key": openai_key}
                if openai_base_url:
                    client_kwargs["base_url"] = openai_base_url
                openai_client = AsyncOpenAI(**client_kwargs)
                logger.info(
                    f"✅ OpenAI client initialized (model={openai_model}, base_url={openai_base_url or 'default'})"
                )
            else:
                logger.error(
                    "OpenAI not available (missing key or package). Install: pip install openai"
                )
                await db_pool.close()
                return
        else:
            try:
                gemini = get_genai_client()
                if getattr(gemini, "is_available", True):
                    logger.info("✅ GenAI Client initialized")
                else:
                    logger.warning("⚠️ GenAI Client initialized but not available")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini: {e}")

    # Run extraction
    extractor = KGIncrementalExtractor(
        db_pool,
        qdrant_url,
        qdrant_api_key,
        gemini_client=gemini,
        openai_client=openai_client,
        provider=provider,
    )

    collections = [args.collection] if args.collection else None

    await extractor.run(collections=collections, limit=args.limit, dry_run=args.dry_run)

    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
