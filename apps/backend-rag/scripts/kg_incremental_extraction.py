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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


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


import asyncpg
import httpx

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
        self, db_pool: asyncpg.Pool, qdrant_url: str, qdrant_api_key: str, gemini_client=None
    ):
        self.db_pool = db_pool
        self.qdrant_url = qdrant_url.rstrip("/")
        self.qdrant_api_key = qdrant_api_key
        self.gemini = gemini_client
        self.stats = {
            "chunks_processed": 0,
            "entities_extracted": 0,
            "relationships_extracted": 0,
            "errors": 0,
            "start_time": None,
        }

    def _qdrant_request(self, method: str, endpoint: str, json_data: dict = None) -> dict:
        """Make HTTP request to Qdrant API with retries."""
        url = f"{self.qdrant_url}{endpoint}"
        headers = {"api-key": self.qdrant_api_key, "Content-Type": "application/json"}

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
        return set(r["chunk_id"] for r in rows if r["chunk_id"])

    def get_qdrant_collections(self) -> list:
        """Get list of Qdrant collections."""
        result = self._qdrant_request("GET", "/collections")
        return [c["name"] for c in result.get("result", {}).get("collections", [])]

    def get_collection_chunks(
        self, collection_name: str, limit: int = None, offset: int = 0
    ) -> list:
        """Get chunks from a Qdrant collection using scroll API with pagination."""
        chunks = []
        batch_size = 100  # Qdrant scroll batch size
        next_offset = None

        while True:
            # Build scroll request
            scroll_data = {"limit": batch_size, "with_payload": True, "with_vector": False}
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

    async def extract_with_gemini(self, text: str) -> dict:
        """Extract entities using Gemini."""
        if not self.gemini:
            return {"entities": [], "relationships": []}

        prompt = EXTRACTION_PROMPT.format(text=text[:8000])

        try:
            # Use the new google-genai API
            response = self.gemini.models.generate_content(
                model="gemini-2.0-flash",  # 2.0 Flash - try without -exp suffix
                contents=prompt,
            )
            response_text = response.text.strip()

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
        self, rel: dict, chunk_id: str, collection: str, new_entity_ids: set = None
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

        # Extract with Gemini
        result = await self.extract_with_gemini(text)

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

        if not self.gemini:
            logger.error("Gemini client not available - cannot proceed")
            return self.stats

        # Process chunks in parallel batches
        logger.info("\nStarting extraction (parallel workers: 2, Free Tier: 15 RPM)...")

        batch_size = 2  # Process 2 chunks in parallel (Free Tier: 15 RPM limit)

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

                # Rate limit: 2 chunk ogni 8s = 15 RPM (Google AI Studio Free Tier limit)
                await asyncio.sleep(8.0)

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

    # Gemini client (optional for dry-run)
    gemini = None
    if not args.dry_run:
        try:
            import tempfile

            from google import genai

            # Get credentials from env var (JSON string)
            creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
            project_id = os.environ.get("GOOGLE_PROJECT_ID", "gen-lang-client-0498009027")
            location = os.environ.get("GOOGLE_LOCATION", "us-central1")

            if creds_json:
                # Write to temp file for auth
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                    f.write(creds_json)
                    creds_path = f.name

                # Set for ADC
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
                logger.info("Set GOOGLE_APPLICATION_CREDENTIALS from secret")

            client = genai.Client(vertexai=True, project=project_id, location=location)
            gemini = client
            logger.info(f"Gemini client initialized (project: {project_id})")
        except Exception as e:
            logger.warning(f"Could not initialize Gemini: {e}")

    # Run extraction - pass URL/key instead of client to allow fresh connections
    extractor = KGIncrementalExtractor(db_pool, qdrant_url, qdrant_api_key, gemini)

    collections = [args.collection] if args.collection else None

    await extractor.run(collections=collections, limit=args.limit, dry_run=args.dry_run)

    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
