#!/usr/bin/env python3
"""
Visa Oracle Incremental Ingestion with Knowledge Graph Extraction

This script:
1. Parses the official Imigrasi Indonesia visa dump
2. Identifies missing visas (not in Qdrant)
3. Creates semantic chunks with rich metadata
4. Extracts entities and relationships for Knowledge Graph
5. Ingests into Qdrant (visa_oracle) and PostgreSQL (kg_nodes/kg_edges)

Usage:
    python scripts/ingestion/ingest_visa_kg.py --file PATH_TO_VISA_FILE [--dry-run]

Example:
    python scripts/ingestion/ingest_visa_kg.py \
        --file "/Users/antonellosiano/Desktop/tutti_visti_indonesia_2026-01-13 (1).txt" \
        --dry-run
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Any

import httpx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Qdrant configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION_NAME = "visa_oracle"

# API configuration
API_URL = os.getenv("RAG_API_URL", "https://nuzantara-rag.fly.dev")

# Entity types for Knowledge Graph
VISA_ENTITY_TYPES = {
    "A": "bebas_visa",          # Visa Free
    "B": "voa",                 # Visa on Arrival
    "C": "visa_kunjungan",      # Visit Visa (single entry)
    "D": "visa_kunjungan_me",   # Visit Visa (multiple entry)
    "E": "visa_tinggal",        # Stay Visa (ITAS/ITAP)
    "F": "visa_diplomatik",     # Diplomatic Visa
}

# Relationship types for KG
RELATIONSHIP_TYPES = {
    "REQUIRES_DOCUMENT": "Requires document",
    "HAS_DURATION": "Has duration",
    "HAS_FEE": "Has fee/cost",
    "EXTENDS_TO": "Can be extended to",
    "CONVERTS_TO": "Can convert to",
    "REQUIRES_SPONSOR": "Requires sponsor",
    "APPLICABLE_FOR": "Applicable for activity",
    "LINKED_KBLI": "Linked to KBLI code",
    "REQUIRES_TAX": "Requires tax registration",
    "ISSUED_BY": "Issued by",
}

# KBLI categories that relate to work visas
WORK_VISA_KBLI_PATTERNS = {
    "E23": ["62", "63", "70", "71", "72", "73", "74"],  # Tech, consulting, professional
    "E25": ["64", "65", "66", "68", "70"],  # Finance, real estate, holding
    "E27": ["94"],  # Religious activities
    "E28": ["64", "65", "66", "68", "70"],  # Investment
    "E30": ["85"],  # Education
}


class VisaKGIngestion:
    """Handles visa ingestion with Knowledge Graph extraction."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            "visas_parsed": 0,
            "visas_missing": 0,
            "chunks_created": 0,
            "entities_extracted": 0,
            "relationships_extracted": 0,
            "errors": [],
        }

    def _qdrant_request(self, method: str, endpoint: str, json_data: dict = None) -> dict:
        """Make HTTP request to Qdrant API."""
        url = f"{QDRANT_URL}{endpoint}"
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

        with httpx.Client(timeout=60) as client:
            if method == "GET":
                resp = client.get(url, headers=headers)
            elif method == "POST":
                resp = client.post(url, headers=headers, json=json_data)
            resp.raise_for_status()
            return resp.json()

    def get_existing_visa_codes(self) -> set:
        """Get visa codes already in Qdrant."""
        result = self._qdrant_request(
            "POST",
            f"/collections/{COLLECTION_NAME}/points/scroll",
            {"limit": 200, "with_payload": True, "with_vector": False}
        )

        codes = set()
        for point in result.get("result", {}).get("points", []):
            payload = point.get("payload", {})

            # Try multiple locations for visa code
            code = payload.get("visa_code")
            if not code and "metadata" in payload:
                code = payload["metadata"].get("code")
            if code:
                codes.add(code)

        return codes

    def parse_visa_file(self, file_path: str) -> list[dict]:
        """Parse the Imigrasi dump file into visa records."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Convert literal \n to actual newlines
        content = content.replace("\\n", "\n")

        # Split by separator
        sections = content.split("=" * 80)

        visas = []
        for section in sections:
            lines = section.strip().split("\n")
            if not lines:
                continue

            # Find visa code (pattern: "A1 A1" or "E23Y E23Y")
            code = None
            name = None
            for i, line in enumerate(lines[:5]):
                line = line.strip()
                match = re.match(r"^([A-Z][0-9]+[A-Z]?)\s+\1\s*$", line)
                if match:
                    code = match.group(1)
                    # Get name from next non-empty line
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and not next_line.startswith("=") and not next_line.startswith("("):
                            name = next_line
                            break
                    break

            if not code:
                continue

            # Extract full content (skip header lines)
            content_lines = []
            in_content = False
            for line in lines:
                if "(titolo)" in line:
                    in_content = True
                    continue
                if in_content:
                    content_lines.append(line)

            full_content = "\n".join(content_lines).strip()
            if not full_content:
                full_content = "\n".join(lines[3:]).strip()  # Fallback

            # Extract structured data
            visa_data = {
                "code": code,
                "name": name or f"Visa {code}",
                "full_content": full_content,
                "category": self._determine_category(code),
                "sections": self._extract_sections(full_content),
            }

            visas.append(visa_data)
            self.stats["visas_parsed"] += 1

        return visas

    def _determine_category(self, code: str) -> str:
        """Determine visa category from code prefix."""
        prefix = code[0] if code else "?"
        return VISA_ENTITY_TYPES.get(prefix, "visa_other")

    def _extract_sections(self, content: str) -> dict:
        """Extract structured sections from visa content."""
        sections = {}

        # Common section headers in Indonesian
        section_patterns = {
            "jenis_visa": r"Jenis [Vv]isa\s*\n(.*?)(?=\n\n|\n[A-Z]|\Z)",
            "masa_tinggal": r"Masa [Tt]inggal\s*\n(.*?)(?=\n\n|\n[A-Z]|\Z)",
            "biaya": r"Biaya.*?\n(.*?)(?=\n\n|\n[A-Z]|\Z)",
            "penjamin": r"Penjamin.*?\n(.*?)(?=\n\n|\n[A-Z]|\Z)",
            "pengajuan": r"Pengajuan [Vv]isa\s*\n(.*?)(?=\n\n|\n[A-Z]|\Z)",
            "persyaratan": r"Persyaratan.*?\n(.*?)(?=\n\n|\n[A-Z]|\Z)",
            "ketentuan": r"Ketentuan [Ll]ain\s*\n(.*?)(?=\n\n|\n[A-Z]|\Z)",
            "dasar_hukum": r"Dasar [Hh]ukum\s*\n(.*?)(?=\n\n|\n[A-Z]|\Z)",
        }

        for key, pattern in section_patterns.items():
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                sections[key] = match.group(1).strip()[:2000]  # Limit length

        return sections

    def create_chunks(self, visa: dict) -> list[dict]:
        """Create semantic chunks from visa data."""
        chunks = []
        code = visa["code"]
        name = visa["name"]

        # Chunk 1: Overview
        overview_chunk = {
            "content": f"""[CONTEXT: Immigration 2026 - Visa {code} - {visa['category'].replace('_', ' ').title()}]

# {code} {name}

## Informasi Dasar
- **Kode Visa**: {code}
- **Kategori**: {visa['category'].replace('_', ' ').title()}
- **Nama Resmi**: {name}

{visa['sections'].get('jenis_visa', '')}

## Masa Tinggal
{visa['sections'].get('masa_tinggal', 'Lihat ketentuan resmi.')}

## Biaya (PNBP)
{visa['sections'].get('biaya', 'Lihat tarif resmi Kemenkumham.')}
""",
            "metadata": {
                "visa_code": code,
                "title": name,
                "category": visa["category"],
                "document_type": "visa_guide",
                "source_type": "imigrasi_official",
                "source_file": "tutti_visti_indonesia_2026.txt",
                "chunk_type": "overview",
                "ingested_at": datetime.utcnow().isoformat(),
            }
        }
        chunks.append(overview_chunk)

        # Chunk 2: Requirements (if substantial content)
        requirements = visa['sections'].get('persyaratan', '') or visa['sections'].get('pengajuan', '')
        if len(requirements) > 100:
            req_chunk = {
                "content": f"""[CONTEXT: Immigration 2026 - Visa {code} Requirements]

# {code} {name} - Persyaratan dan Pengajuan

## Persyaratan Dokumen
{requirements}

## Proses Pengajuan
{visa['sections'].get('pengajuan', 'Melalui evisa.imigrasi.go.id atau Kedutaan RI.')}

## Penjamin (Sponsor)
{visa['sections'].get('penjamin', 'Lihat ketentuan sponsor untuk visa ini.')}
""",
                "metadata": {
                    "visa_code": code,
                    "title": f"{name} - Requirements",
                    "category": visa["category"],
                    "document_type": "visa_requirements",
                    "source_type": "imigrasi_official",
                    "chunk_type": "requirements",
                    "ingested_at": datetime.utcnow().isoformat(),
                }
            }
            chunks.append(req_chunk)

        # Chunk 3: Legal basis (if present)
        dasar_hukum = visa['sections'].get('dasar_hukum', '')
        if len(dasar_hukum) > 50:
            legal_chunk = {
                "content": f"""[CONTEXT: Immigration 2026 - Visa {code} Legal Basis]

# {code} {name} - Dasar Hukum

## Peraturan Terkait
{dasar_hukum}

## Ketentuan Lain
{visa['sections'].get('ketentuan', '')}
""",
                "metadata": {
                    "visa_code": code,
                    "title": f"{name} - Legal Basis",
                    "category": visa["category"],
                    "document_type": "visa_legal",
                    "source_type": "imigrasi_official",
                    "chunk_type": "legal_basis",
                    "ingested_at": datetime.utcnow().isoformat(),
                }
            }
            chunks.append(legal_chunk)

        self.stats["chunks_created"] += len(chunks)
        return chunks

    def extract_kg_entities(self, visa: dict) -> list[dict]:
        """Extract Knowledge Graph entities from visa data."""
        entities = []
        code = visa["code"]
        name = visa["name"]
        category = visa["category"]

        # Main visa entity
        visa_entity = {
            "entity_id": f"visa_{code.lower()}",
            "entity_type": category,
            "name": f"{code} - {name}",
            "description": visa["sections"].get("jenis_visa", name)[:500],
            "properties": {
                "code": code,
                "official_name": name,
                "category": category,
                "source": "imigrasi_official_2026",
            },
            "confidence": 0.95,
            "source_collection": COLLECTION_NAME,
        }
        entities.append(visa_entity)

        # Extract duration entity
        masa_tinggal = visa["sections"].get("masa_tinggal", "")
        duration_match = re.search(r"(\d+)\s*(hari|bulan|tahun)", masa_tinggal, re.IGNORECASE)
        if duration_match:
            duration = f"{duration_match.group(1)} {duration_match.group(2)}"
            entities.append({
                "entity_id": f"duration_{code.lower()}_{duration.replace(' ', '_')}",
                "entity_type": "jangka_waktu",
                "name": duration,
                "description": f"Masa tinggal untuk visa {code}",
                "properties": {"value": duration_match.group(1), "unit": duration_match.group(2)},
                "confidence": 0.9,
                "source_collection": COLLECTION_NAME,
            })

        # Extract fee entity
        biaya = visa["sections"].get("biaya", "")
        fee_match = re.search(r"Rp\s*([\d.,]+)", biaya)
        if fee_match:
            fee_amount = fee_match.group(1).replace(".", "").replace(",", "")
            entities.append({
                "entity_id": f"fee_{code.lower()}_pnbp",
                "entity_type": "biaya",
                "name": f"PNBP Visa {code}",
                "description": f"Biaya PNBP untuk visa {code}",
                "properties": {"amount": fee_amount, "currency": "IDR"},
                "confidence": 0.85,
                "source_collection": COLLECTION_NAME,
            })

        # Extract legal references
        dasar_hukum = visa["sections"].get("dasar_hukum", "")

        # Find PP references
        for match in re.finditer(r"PP\s*(?:Nomor\s*)?(\d+)\s*(?:tahun\s*)?(\d{4})?", dasar_hukum, re.IGNORECASE):
            pp_num = match.group(1)
            pp_year = match.group(2) or "2024"
            entities.append({
                "entity_id": f"pp_{pp_num}_{pp_year}",
                "entity_type": "peraturan_pemerintah",
                "name": f"PP {pp_num} Tahun {pp_year}",
                "description": f"Peraturan Pemerintah terkait visa {code}",
                "properties": {"number": pp_num, "year": pp_year},
                "confidence": 0.9,
                "source_collection": COLLECTION_NAME,
            })

        # Find Permen references
        for match in re.finditer(r"Permen\s*(?:kumham|hukum|imigrasi)?\s*(?:Nomor\s*)?(\d+)\s*(?:tahun\s*)?(\d{4})?", dasar_hukum, re.IGNORECASE):
            permen_num = match.group(1)
            permen_year = match.group(2) or "2024"
            entities.append({
                "entity_id": f"permen_{permen_num}_{permen_year}",
                "entity_type": "permen",
                "name": f"Permenkumham {permen_num} Tahun {permen_year}",
                "description": f"Peraturan Menteri terkait visa {code}",
                "properties": {"number": permen_num, "year": permen_year},
                "confidence": 0.9,
                "source_collection": COLLECTION_NAME,
            })

        self.stats["entities_extracted"] += len(entities)
        return entities

    def extract_kg_relationships(self, visa: dict, entities: list[dict]) -> list[dict]:
        """Extract Knowledge Graph relationships from visa data."""
        relationships = []
        code = visa["code"]
        visa_entity_id = f"visa_{code.lower()}"

        # Find related entities and create relationships
        for entity in entities:
            eid = entity["entity_id"]
            etype = entity["entity_type"]

            if eid == visa_entity_id:
                continue

            # Duration relationship
            if etype == "jangka_waktu":
                relationships.append({
                    "relationship_id": f"rel_{visa_entity_id}_duration_{eid}",
                    "source_entity_id": visa_entity_id,
                    "target_entity_id": eid,
                    "relationship_type": "HAS_DURATION",
                    "properties": {},
                    "confidence": 0.9,
                    "source_collection": COLLECTION_NAME,
                })

            # Fee relationship
            elif etype == "biaya":
                relationships.append({
                    "relationship_id": f"rel_{visa_entity_id}_fee_{eid}",
                    "source_entity_id": visa_entity_id,
                    "target_entity_id": eid,
                    "relationship_type": "HAS_FEE",
                    "properties": {},
                    "confidence": 0.85,
                    "source_collection": COLLECTION_NAME,
                })

            # Legal reference relationship
            elif etype in ("peraturan_pemerintah", "permen", "undang_undang"):
                relationships.append({
                    "relationship_id": f"rel_{visa_entity_id}_legal_{eid}",
                    "source_entity_id": visa_entity_id,
                    "target_entity_id": eid,
                    "relationship_type": "REFERENCES",
                    "properties": {},
                    "confidence": 0.9,
                    "source_collection": COLLECTION_NAME,
                })

        # Add KBLI relationships for work visas
        if code.startswith("E23") or code.startswith("E25"):
            kbli_prefixes = WORK_VISA_KBLI_PATTERNS.get(code[:3], [])
            for kbli_prefix in kbli_prefixes:
                relationships.append({
                    "relationship_id": f"rel_{visa_entity_id}_kbli_{kbli_prefix}",
                    "source_entity_id": visa_entity_id,
                    "target_entity_id": f"kbli_{kbli_prefix}xxx",
                    "relationship_type": "LINKED_KBLI",
                    "properties": {"kbli_prefix": kbli_prefix, "note": "Work visa applicable"},
                    "confidence": 0.7,
                    "source_collection": COLLECTION_NAME,
                })

        # Add tax relationship for work/investor visas
        if code.startswith("E"):
            relationships.append({
                "relationship_id": f"rel_{visa_entity_id}_tax_npwp",
                "source_entity_id": visa_entity_id,
                "target_entity_id": "npwp_registration",
                "relationship_type": "REQUIRES_TAX",
                "properties": {"tax_type": "NPWP", "note": "Required for stay permit holders"},
                "confidence": 0.8,
                "source_collection": COLLECTION_NAME,
            })

        self.stats["relationships_extracted"] += len(relationships)
        return relationships

    async def ingest_to_qdrant(self, chunks: list[dict]) -> bool:
        """Ingest chunks to Qdrant directly with embeddings."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would ingest {len(chunks)} chunks to Qdrant")
            return True

        try:
            import openai
            openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            # Generate embeddings for all chunks
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            texts = [c["content"][:8000] for c in chunks]  # Truncate for embedding

            # Batch embed (OpenAI limit: 2048 per request)
            all_embeddings = []
            batch_size = 100
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                response = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=batch,
                    dimensions=1536,
                )
                all_embeddings.extend([e.embedding for e in response.data])

            # Build Qdrant points with named vector "dense"
            import uuid
            points = []
            for idx, (chunk, embedding) in enumerate(zip(chunks, all_embeddings)):
                # Generate UUID v5 from visa code for deterministic but unique IDs
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"visa_oracle_{chunk['metadata']['visa_code']}_{idx}"))
                points.append({
                    "id": point_id,
                    "vector": {"dense": embedding},  # Named vector format
                    "payload": {
                        "content": chunk["content"],
                        **chunk["metadata"],
                        "ingested_at": datetime.utcnow().isoformat(),
                    }
                })

            # Upsert to Qdrant
            logger.info(f"Upserting {len(points)} points to Qdrant...")
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.put(
                    f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
                    json={"points": points},
                    headers={"api-key": QDRANT_API_KEY, "Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    logger.error(f"Qdrant response: {resp.text}")
                resp.raise_for_status()
                logger.info(f"Qdrant ingestion: {len(points)} documents upserted")
                return True

        except Exception as e:
            logger.error(f"Qdrant ingestion failed: {e}")
            self.stats["errors"].append(f"Qdrant: {e}")
            return False

    async def save_kg_to_db(self, entities: list[dict], relationships: list[dict]) -> bool:
        """Save KG entities and relationships to PostgreSQL directly."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would save {len(entities)} entities, {len(relationships)} relationships to KG")
            return True

        try:
            import asyncpg

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.warning("DATABASE_URL not set, saving to file")
                with open("/tmp/visa_kg_entities.json", "w") as f:
                    json.dump({"entities": entities, "relationships": relationships}, f, indent=2)
                return True

            conn = await asyncpg.connect(database_url)

            try:
                # Insert entities
                logger.info(f"Inserting {len(entities)} entities to kg_nodes...")
                for entity in entities:
                    await conn.execute("""
                        INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties, confidence, source_collection)
                        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                        ON CONFLICT (entity_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            properties = EXCLUDED.properties,
                            confidence = EXCLUDED.confidence
                    """,
                        entity["entity_id"],
                        entity["entity_type"],
                        entity["name"],
                        entity.get("description", ""),
                        json.dumps(entity.get("properties", {})),
                        entity.get("confidence", 1.0),
                        entity.get("source_collection", COLLECTION_NAME),
                    )

                # Insert relationships (need target entities to exist)
                logger.info(f"Inserting {len(relationships)} relationships to kg_edges...")
                inserted_rels = 0
                skipped_rels = 0
                for rel in relationships:
                    try:
                        # Check if target entity exists, create placeholder if not
                        target_exists = await conn.fetchval(
                            "SELECT 1 FROM kg_nodes WHERE entity_id = $1",
                            rel["target_entity_id"]
                        )
                        if not target_exists:
                            # Create placeholder target entity
                            target_type = "requirement" if "duration" in rel["target_entity_id"] or "fee" in rel["target_entity_id"] else "external_reference"
                            await conn.execute("""
                                INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties, confidence, source_collection)
                                VALUES ($1, $2, $3, $4, '{}'::jsonb, 0.5, $5)
                                ON CONFLICT (entity_id) DO NOTHING
                            """,
                                rel["target_entity_id"],
                                target_type,
                                rel["target_entity_id"].replace("_", " ").title(),
                                f"Auto-created for relationship from visa ingestion",
                                COLLECTION_NAME,
                            )

                        await conn.execute("""
                            INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id, relationship_type, properties, confidence, source_collection)
                            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                            ON CONFLICT (relationship_id) DO UPDATE SET
                                properties = EXCLUDED.properties,
                                confidence = EXCLUDED.confidence
                        """,
                            rel["relationship_id"],
                            rel["source_entity_id"],
                            rel["target_entity_id"],
                            rel["relationship_type"],
                            json.dumps(rel.get("properties", {})),
                            rel.get("confidence", 1.0),
                            rel.get("source_collection", COLLECTION_NAME),
                        )
                        inserted_rels += 1
                    except Exception as rel_err:
                        logger.warning(f"Skipped relationship {rel['relationship_id']}: {rel_err}")
                        skipped_rels += 1

                logger.info(f"KG save complete: {len(entities)} entities, {inserted_rels} relationships ({skipped_rels} skipped)")
                return True

            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"KG save failed: {e}")
            self.stats["errors"].append(f"KG: {e}")
            # Save to file as backup
            with open("/tmp/visa_kg_entities.json", "w") as f:
                json.dump({"entities": entities, "relationships": relationships}, f, indent=2)
            return False

    async def run(self, file_path: str) -> dict:
        """Run the full ingestion pipeline."""
        logger.info(f"Starting Visa KG Ingestion (dry_run={self.dry_run})")

        # 1. Parse visa file
        logger.info(f"Parsing visa file: {file_path}")
        visas = self.parse_visa_file(file_path)
        logger.info(f"Parsed {len(visas)} visas")

        # 2. Get existing codes
        logger.info("Checking existing visa codes in Qdrant...")
        existing_codes = self.get_existing_visa_codes()
        logger.info(f"Found {len(existing_codes)} existing codes")

        # 3. Filter to missing visas
        missing_visas = [v for v in visas if v["code"] not in existing_codes]
        self.stats["visas_missing"] = len(missing_visas)
        logger.info(f"Found {len(missing_visas)} missing visas to ingest")

        if not missing_visas:
            logger.info("No missing visas - all up to date!")
            return self.stats

        # 4. Process each missing visa
        all_chunks = []
        all_entities = []
        all_relationships = []

        for visa in missing_visas:
            logger.info(f"Processing {visa['code']}: {visa['name'][:50]}...")

            # Create chunks
            chunks = self.create_chunks(visa)
            all_chunks.extend(chunks)

            # Extract KG entities
            entities = self.extract_kg_entities(visa)
            all_entities.extend(entities)

            # Extract KG relationships
            relationships = self.extract_kg_relationships(visa, entities)
            all_relationships.extend(relationships)

        # 5. Ingest to Qdrant
        logger.info(f"Ingesting {len(all_chunks)} chunks to Qdrant...")
        await self.ingest_to_qdrant(all_chunks)

        # 6. Save KG to PostgreSQL
        logger.info(f"Saving {len(all_entities)} entities, {len(all_relationships)} relationships to KG...")
        await self.save_kg_to_db(all_entities, all_relationships)

        # 7. Summary
        logger.info("=" * 60)
        logger.info("INGESTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Visas parsed: {self.stats['visas_parsed']}")
        logger.info(f"Visas missing (ingested): {self.stats['visas_missing']}")
        logger.info(f"Chunks created: {self.stats['chunks_created']}")
        logger.info(f"KG entities: {self.stats['entities_extracted']}")
        logger.info(f"KG relationships: {self.stats['relationships_extracted']}")
        if self.stats["errors"]:
            logger.warning(f"Errors: {len(self.stats['errors'])}")
            for err in self.stats["errors"]:
                logger.warning(f"  - {err}")

        return self.stats


async def main():
    parser = argparse.ArgumentParser(description="Visa Oracle KG Ingestion")
    parser.add_argument("--file", required=True, help="Path to visa dump file")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually ingest")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    ingestion = VisaKGIngestion(dry_run=args.dry_run)
    stats = await ingestion.run(args.file)

    # Exit with error code if errors occurred
    if stats.get("errors"):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
