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
import re
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
from backend.llm.ollama_client import ollama_chat_kg  # noqa: E402

try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ALLOWED_ENTITY_TYPES = {
    "undang_undang",
    "peraturan_pemerintah",
    "permen",
    "perpres",
    "perda",
    "pasal",
    "kbli",
    "pt_pma",
    "pt_pmdn",
    "kitas",
    "kitap",
    "vitas",
    "rptka",
    "imta",
    "ppn",
    "pph_21",
    "pph_23",
    "npwp",
    "nib",
    "oss",
    "izin_usaha",
    "biaya",
    "jangka_waktu",
    "dokumen",
    "sanksi",
}

GENERIC_ENTITY_NAMES = {
    "asas saling menguntungkan",
    "bukti permohonan",
    "data orang asing",
    "data permohonan visa",
    "histori layanan keimigrasian",
    "kantor penjamin",
    "kepentingan administrasi",
    "kewarganegaraan orang asing",
    "nama orang asing",
    "pekerjaan orang asing",
    "pemeriksaan kelengkapan persyaratan",
    "penerbitan visa",
    "tempat/tanggal lahir orang asing",
    "tugas pemerintahan",
}

LEGAL_REFERENCE_PATTERNS = {
    "undang_undang": re.compile(
        r"(?i)(?:uu|undang-?undang)\s*(?:no\.?|nomor)?\s*(\d+)\s*(?:tahun)?\s*(\d{4})"
    ),
    "peraturan_pemerintah": re.compile(
        r"(?i)(?:pp|peraturan pemerintah)\s*(?:no\.?|nomor)?\s*(\d+)\s*(?:tahun)?\s*(\d{4})"
    ),
    "permen": re.compile(
        r"(?i)(?:permen(?:kumham|keu|aker)?|peraturan menteri(?: hukum dan hak asasi manusia)?)\s*(?:no\.?|nomor)?\s*(\d+)\s*(?:tahun)?\s*(\d{4})"
    ),
    "perpres": re.compile(
        r"(?i)(?:perpres|peraturan presiden)\s*(?:no\.?|nomor)?\s*(\d+)\s*(?:tahun)?\s*(\d{4})"
    ),
    "perda": re.compile(
        r"(?i)(?:perda|peraturan daerah)\s*(?:no\.?|nomor)?\s*(\d+)\s*(?:tahun)?\s*(\d{4})"
    ),
}

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

    @staticmethod
    def _slugify(value: str) -> str:
        """Build a stable slug for entity IDs."""
        normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return re.sub(r"_+", "_", normalized)

    def _normalize_legal_reference(self, entity_type: str, name: str) -> str | None:
        """Normalize legal references into a stable canonical display name."""
        pattern = LEGAL_REFERENCE_PATTERNS.get(entity_type)
        if not pattern:
            return name.strip()

        match = pattern.search(name)
        if not match:
            return None

        number, year = match.groups()
        if len(year) != 4 or int(year) < 1945:
            return None

        prefixes = {
            "undang_undang": "UU",
            "peraturan_pemerintah": "PP",
            "permen": "Permen",
            "perpres": "Perpres",
            "perda": "Perda",
        }
        return f"{prefixes[entity_type]} No {int(number)} Tahun {year}"

    def _normalize_entity(self, entity: dict) -> dict | None:
        """Apply lightweight quality filters and canonicalization before persistence."""
        entity_type = str(entity.get("type", "")).strip().lower()
        if entity_type not in ALLOWED_ENTITY_TYPES:
            return None

        raw_name = " ".join(str(entity.get("name", "")).split()).strip(" .,:;")
        if not raw_name:
            return None

        normalized_name = raw_name
        if entity_type in LEGAL_REFERENCE_PATTERNS:
            normalized_name = self._normalize_legal_reference(entity_type, raw_name)
            if not normalized_name:
                return None

        lower_name = normalized_name.lower()
        if lower_name in GENERIC_ENTITY_NAMES:
            return None

        if entity_type == "dokumen" and len(normalized_name.split()) <= 2:
            generic_document_tokens = {"dokumen", "surat", "keterangan", "bukti", "data"}
            if lower_name in generic_document_tokens:
                return None

        description = " ".join(str(entity.get("description", "")).split())
        canonical_id = f"{entity_type}_{self._slugify(normalized_name)}"
        return {
            "id": canonical_id,
            "type": entity_type,
            "name": normalized_name,
            "description": description,
        }

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
        Fetch chunks from Qdrant collection.

        Note:
            `legal_unified_2026` runs with Qdrant strict mode enabled and does not
            expose a payload index for `document_id`, so server-side scroll filters
            on that field return HTTP 400. We therefore scroll normally and apply
            the `document_id` filter client-side.
        """
        chunks = []
        batch_size = 100
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
                metadata = payload.get("metadata", {})

                if document_id and metadata.get("document_id") != document_id:
                    continue

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

        # Process each chunk through the shared path so per-run stats stay accurate.
        for chunk in chunks:
            try:
                await self.process_chunk(chunk)
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
            if hasattr(self.gemini, "generate_content"):
                response = await self.gemini.generate_content(
                    model="gemini-2.0-flash-001",
                    contents=prompt,
                    temperature=0.1,
                )
                response_text = response["text"].strip()
            else:
                response = await asyncio.to_thread(
                    self.gemini.models.generate_content,
                    model="gemini-2.0-flash",
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

    async def extract_with_openai(self, text: str) -> dict:
        """Extract entities using OpenAI gpt-4o-mini or local Ollama (qwen3.5:27b via 2-step fix)."""
        if not self.openai:
            return {"entities": [], "relationships": []}

        prompt = EXTRACTION_PROMPT.format(text=text[:8000])

        # Local Ollama path: use ollama_chat_kg() with 2-step think fix
        # (extra_body: {"think": False} does NOT work via OpenAI-compat API — vLLM issue #37414)
        if os.environ.get("OPENAI_BASE_URL", "").startswith("http://localhost"):
            _kg_schema = {
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "type": {"type": "string"},
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["id", "type", "name"],
                        },
                    },
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "target": {"type": "string"},
                                "type": {"type": "string"},
                            },
                            "required": ["source", "target", "type"],
                        },
                    },
                },
                "required": ["entities", "relationships"],
            }
            model_name = os.environ.get("OPENAI_MODEL", "qwen3.5:27b")
            try:
                raw = await ollama_chat_kg(prompt, _kg_schema, model=model_name, timeout=120.0)
                if not raw:
                    return {"entities": [], "relationships": []}
                return json.loads(raw)
            except Exception as e:
                logger.warning(f"Ollama KG extraction failed: {e}")
                return {"entities": [], "relationships": []}

        # Cloud OpenAI path
        try:
            response = await self.openai.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            response_text = response.choices[0].message.content.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            return json.loads(response_text)
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

        entity_id_map: dict[str, str] = {}
        normalized_entities: list[dict] = []
        seen_entity_ids: set[str] = set()

        for entity in entities:
            raw_entity_id = self._slugify(str(entity.get("id", "")))
            normalized_entity = self._normalize_entity(entity)
            if not normalized_entity:
                continue

            canonical_entity_id = normalized_entity["id"]
            if raw_entity_id:
                entity_id_map[raw_entity_id] = canonical_entity_id

            if canonical_entity_id in seen_entity_ids:
                continue

            normalized_entities.append(normalized_entity)
            seen_entity_ids.add(canonical_entity_id)

        for entity in normalized_entities:
            await self.save_entity(entity, chunk_id, collection)
            self.stats["entities_extracted"] += 1

        seen_relationship_ids: set[str] = set()
        for rel in relationships:
            source_key = self._slugify(str(rel.get("source", "")))
            target_key = self._slugify(str(rel.get("target", "")))
            rel_type = str(rel.get("type", "RELATED_TO")).upper()
            source_id = entity_id_map.get(source_key)
            target_id = entity_id_map.get(target_key)

            if not source_id or not target_id or source_id == target_id:
                continue

            relationship_id = f"{source_id}_{rel_type}_{target_id}"
            if relationship_id in seen_relationship_ids:
                continue

            normalized_relationship = {
                "source": source_id,
                "target": target_id,
                "type": rel_type,
            }
            if await self.save_relationship(normalized_relationship, chunk_id, collection):
                seen_relationship_ids.add(relationship_id)
                self.stats["relationships_extracted"] += 1

        self.stats["chunks_processed"] += 1
        return len(normalized_entities) + len(seen_relationship_ids)

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
