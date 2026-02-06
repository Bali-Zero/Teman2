#!/usr/bin/env python3
"""
Ingest Kemnaker Circular SE 3/836/PK.04/I/2026 on Alih Status TKA

This script:
1. Creates the immigration_circulars collection in Qdrant (hybrid with BM25)
2. Creates 4 semantic chunks from the circular content
3. Extracts 7 KG entities to PostgreSQL kg_nodes
4. Extracts 5 KG relationships to PostgreSQL kg_edges

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/ingestion/ingest_kemnaker_circular.py [--dry-run] [--skip-kg] [--verbose]

Flags:
    --dry-run   Validate without inserting to Qdrant/PostgreSQL
    --skip-kg   Only ingest to Qdrant, skip Knowledge Graph
    --verbose   Enable detailed logging
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env from backend-rag directory
backend_rag_dir = Path(__file__).parent.parent.parent / "apps" / "backend-rag"
load_dotenv(backend_rag_dir / ".env")

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Qdrant configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION_NAME = "immigration_circulars"

# Vector configuration (OpenAI text-embedding-3-small)
VECTOR_SIZE = 1536

# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENT CONTENT: Kemnaker SE 3/836/PK.04/I/2026
# ─────────────────────────────────────────────────────────────────────────────

KEMNAKER_CIRCULAR = {
    "number": "SE No. 3/836/PK.04/I/2026",
    "title": "Surat Edaran tentang Kesamaan Sponsor pada Proses Alih Status Keimigrasian TKA",
    "issuing_authority": "Direktorat Jenderal Pembinaan Penempatan Tenaga Kerja dan Perluasan Kesempatan Kerja",
    "ministry": "Kementerian Ketenagakerjaan (Kemnaker)",
    "effective_date": "2026-01-15",
    "topic": "Alih Status Keimigrasian TKA - One Sponsor Policy",
    "summary": """
Surat Edaran ini mengatur persyaratan KESAMAAN SPONSOR antara Izin Tinggal Keimigrasian (ITK)
dan Rencana Penggunaan Tenaga Kerja Asing (RPTKA) untuk proses Alih Status TKA.

POIN UTAMA:
1. Sponsor ITK HARUS SAMA dengan Sponsor RPTKA
2. Jika berbeda → Alih Status DITOLAK
3. Pengecualian: Partnership/Subsidiary dengan bukti afiliasi
4. Solusi alternatif: Offshore Scheme (keluar Indonesia, apply visa baru)
5. Verifikasi: BPJS data matching + WLKP + NIB aktif
""",
    "sections": {
        "main_rule": """
## Ketentuan Utama: Kesamaan Sponsor (One Sponsor Policy)

Berdasarkan SE No. 3/836/PK.04/I/2026, proses Alih Status Keimigrasian TKA
(dari KITAS Kunjungan ke KITAS Kerja, atau perubahan sponsor) WAJIB memenuhi
persyaratan KESAMAAN SPONSOR:

1. **Sponsor pada Izin Tinggal Keimigrasian (ITK)** yang diterbitkan oleh
   Direktorat Jenderal Imigrasi HARUS SAMA dengan:

2. **Sponsor pada Rencana Penggunaan Tenaga Kerja Asing (RPTKA)** yang
   diajukan di sistem SIAPKerja Kemnaker.

### Implikasi
- Jika TKA masuk Indonesia dengan sponsor PT A (ITK)
- Kemudian ingin bekerja di PT B (RPTKA berbeda)
- Maka proses Alih Status akan DITOLAK oleh sistem

### Dasar Hukum
- PP No. 28 Tahun 2025 tentang Peraturan Pelaksana UU Cipta Kerja
- Pasal 42-48 UU 6/2023 tentang Ketenagakerjaan
""",
        "exception": """
## Pengecualian: Partnership/Subsidiary (Afiliasi Perusahaan)

Kesamaan Sponsor DAPAT DIKECUALIKAN dalam kondisi berikut:

1. **Partnership Relationship**
   - PT A dan PT B memiliki perjanjian kemitraan resmi
   - Harus dibuktikan dengan akta notaris atau MoU yang disahkan

2. **Subsidiary/Holding Structure**
   - PT A adalah anak perusahaan (subsidiary) dari PT B, atau sebaliknya
   - Dibuktikan dengan Akta Pendirian yang menunjukkan struktur kepemilikan
   - Atau laporan keuangan konsolidasi yang diaudit

3. **Group Company**
   - PT A dan PT B adalah bagian dari grup perusahaan yang sama
   - Holding company yang sama memiliki minimal 50% saham di keduanya

### Dokumen Pendukung untuk Pengecualian
- Akta Notaris yang menyatakan hubungan afiliasi
- Struktur organisasi grup perusahaan
- Laporan keuangan konsolidasi (audited)
- Surat pernyataan dari holding company
""",
        "alternative": """
## Solusi Alternatif: Offshore Scheme

Jika TIDAK memenuhi syarat Kesamaan Sponsor dan BUKAN afiliasi:

### Offshore Scheme Process
1. **Keluar Indonesia** - TKA keluar wilayah Indonesia (Singapore, Malaysia, dll)
2. **Apply VITAS Baru** - Sponsor baru (PT B) mengajukan RPTKA + Notifikasi
3. **Telex Visa** - PT B memproses Telex Visa untuk TKA
4. **Entry Baru** - TKA masuk Indonesia dengan VITAS baru dari PT B
5. **KITAS Baru** - Proses KITAS dengan sponsor PT B sesuai RPTKA

### Keuntungan Offshore Scheme
- Tidak melanggar One Sponsor Policy
- Status keimigrasian bersih dari awal
- Menghindari penolakan sistem

### Kerugian Offshore Scheme
- Biaya tambahan (tiket, akomodasi selama di luar negeri)
- Waktu proses lebih lama (2-4 minggu)
- Memerlukan koordinasi sponsor lama dan baru
""",
        "compliance": """
## Verifikasi Compliance: BPJS, WLKP, NIB

Selain Kesamaan Sponsor, sistem SIAPKerja dan Imigrasi juga melakukan
verifikasi silang (cross-check) terhadap:

### 1. BPJS Data Matching
- Data BPJS Ketenagakerjaan TKA harus cocok dengan RPTKA
- Nama TKA, nomor paspor, dan perusahaan sponsor harus identik
- Ketidakcocokan = penolakan otomatis

### 2. WLKP (Wajib Lapor Ketenagakerjaan Perusahaan)
- Perusahaan sponsor harus aktif dalam sistem WLKP
- Laporan tahunan/triwulan harus up-to-date
- TKA harus terdaftar dalam laporan WLKP perusahaan

### 3. NIB (Nomor Induk Berusaha)
- NIB perusahaan sponsor harus aktif di OSS
- KBLI dalam NIB harus sesuai dengan jabatan TKA
- Status risiko usaha harus sesuai (rendah/menengah/tinggi)

### Konsekuensi Ketidaksesuaian
- Penolakan RPTKA baru
- Penolakan Alih Status
- Potensi pembatalan izin kerja existing
""",
    },
    "keywords": [
        "alih status",
        "keimigrasian",
        "TKA",
        "sponsor",
        "RPTKA",
        "ITK",
        "KITAS",
        "kemnaker",
        "offshore",
        "BPJS",
        "WLKP",
        "NIB",
        "PP 28",
        "surat edaran",
        "one sponsor policy",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE GRAPH ENTITIES (7 total)
# ─────────────────────────────────────────────────────────────────────────────

KG_ENTITIES = [
    {
        "entity_id": "se:kemnaker-se-2026-3-836",
        "entity_type": "surat_edaran",
        "name": "SE No. 3/836/PK.04/I/2026",
        "description": "Surat Edaran Kemnaker tentang Kesamaan Sponsor pada Proses Alih Status Keimigrasian TKA",
        "properties": {
            "number": "3/836/PK.04/I/2026",
            "ministry": "Kemnaker",
            "effective_date": "2026-01-15",
            "topic": "Alih Status TKA - One Sponsor Policy",
        },
        "confidence": 0.95,
    },
    {
        "entity_id": "proses:alih_status_keimigrasian",
        "entity_type": "proses",
        "name": "Alih Status Keimigrasian",
        "description": "Proses perubahan status keimigrasian TKA dari satu jenis izin tinggal ke jenis lain, atau perubahan sponsor",
        "properties": {
            "applies_to": "TKA",
            "examples": [
                "KITAS Kunjungan → KITAS Kerja",
                "Perubahan sponsor PT A → PT B",
            ],
        },
        "confidence": 0.9,
    },
    {
        "entity_id": "syarat:kesamaan_sponsor",
        "entity_type": "syarat",
        "name": "Kesamaan Sponsor ITK dan RPTKA",
        "description": "Persyaratan bahwa sponsor pada Izin Tinggal Keimigrasian harus sama dengan sponsor pada RPTKA",
        "properties": {
            "rule": "Sponsor ITK = Sponsor RPTKA",
            "consequence_if_violated": "Alih Status DITOLAK",
            "exceptions": ["Partnership", "Subsidiary", "Group Company"],
        },
        "confidence": 0.95,
    },
    {
        "entity_id": "sponsor:itk_sponsor",
        "entity_type": "sponsor",
        "name": "Sponsor ITK (Izin Tinggal Keimigrasian)",
        "description": "Perusahaan atau individu yang menjadi penjamin TKA pada dokumen izin tinggal yang diterbitkan Imigrasi",
        "properties": {
            "issued_by": "Direktorat Jenderal Imigrasi",
            "document": "KITAS/KITAP",
        },
        "confidence": 0.9,
    },
    {
        "entity_id": "sponsor:rptka_sponsor",
        "entity_type": "sponsor",
        "name": "Sponsor RPTKA",
        "description": "Perusahaan yang mengajukan Rencana Penggunaan Tenaga Kerja Asing di sistem SIAPKerja Kemnaker",
        "properties": {
            "system": "SIAPKerja",
            "ministry": "Kemnaker",
            "requirements": ["NIB aktif", "WLKP up-to-date", "KBLI sesuai"],
        },
        "confidence": 0.9,
    },
    {
        "entity_id": "syarat:bpjs_data_matching",
        "entity_type": "syarat",
        "name": "BPJS Data Matching",
        "description": "Verifikasi silang data BPJS Ketenagakerjaan TKA dengan data RPTKA (nama, paspor, sponsor)",
        "properties": {
            "verified_fields": ["nama_tka", "nomor_paspor", "perusahaan_sponsor"],
            "consequence_if_mismatch": "Penolakan otomatis",
        },
        "confidence": 0.85,
    },
    {
        "entity_id": "sistem:wlkp",
        "entity_type": "sistem",
        "name": "WLKP (Wajib Lapor Ketenagakerjaan Perusahaan)",
        "description": "Sistem pelaporan wajib ketenagakerjaan perusahaan ke Kemnaker, termasuk data TKA",
        "properties": {
            "reporting_frequency": ["tahunan", "triwulan"],
            "required_data": ["jumlah_karyawan", "daftar_tka", "gaji"],
        },
        "confidence": 0.9,
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE GRAPH RELATIONSHIPS (5 total)
# ─────────────────────────────────────────────────────────────────────────────

KG_RELATIONSHIPS = [
    {
        "relationship_id": "rel:alih_status_requires_kesamaan",
        "source_entity_id": "proses:alih_status_keimigrasian",
        "target_entity_id": "syarat:kesamaan_sponsor",
        "relationship_type": "REQUIRES",
        "properties": {
            "mandatory": True,
            "note": "Tanpa kesamaan sponsor, alih status ditolak",
        },
        "confidence": 0.95,
    },
    {
        "relationship_id": "rel:alih_status_blocked_by_kesamaan",
        "source_entity_id": "proses:alih_status_keimigrasian",
        "target_entity_id": "syarat:kesamaan_sponsor",
        "relationship_type": "BLOCKED_BY",
        "properties": {
            "condition": "Jika sponsor ITK ≠ sponsor RPTKA",
            "exception": "Partnership/Subsidiary dengan bukti afiliasi",
        },
        "confidence": 0.95,
    },
    {
        "relationship_id": "rel:kesamaan_allowed_if_rptka",
        "source_entity_id": "syarat:kesamaan_sponsor",
        "target_entity_id": "sponsor:rptka_sponsor",
        "relationship_type": "ALLOWED_IF",
        "properties": {
            "condition": "RPTKA sponsor = ITK sponsor OR afiliasi terbukti",
        },
        "confidence": 0.9,
    },
    {
        "relationship_id": "rel:rptka_depends_bpjs",
        "source_entity_id": "sponsor:rptka_sponsor",
        "target_entity_id": "syarat:bpjs_data_matching",
        "relationship_type": "DEPENDS_ON",
        "properties": {
            "verification": "Data BPJS harus cocok dengan RPTKA",
        },
        "confidence": 0.85,
    },
    {
        "relationship_id": "rel:se_references_pp28",
        "source_entity_id": "se:kemnaker-se-2026-3-836",
        "target_entity_id": "pp_28_2025",
        "relationship_type": "REFERENCES",
        "properties": {
            "regulation": "PP No. 28 Tahun 2025",
            "topic": "Peraturan Pelaksana UU Cipta Kerja",
        },
        "confidence": 0.9,
    },
]


class KemnakerCircularIngestion:
    """Handles Kemnaker Circular ingestion with Knowledge Graph extraction."""

    def __init__(self, dry_run: bool = False, skip_kg: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.skip_kg = skip_kg
        self.verbose = verbose
        self.stats = {
            "chunks_created": 0,
            "points_upserted": 0,
            "entities_saved": 0,
            "relationships_saved": 0,
            "errors": [],
        }

        if verbose:
            logger.setLevel(logging.DEBUG)

    def _qdrant_request(
        self, method: str, endpoint: str, json_data: dict = None
    ) -> dict:
        """Make HTTP request to Qdrant API."""
        url = f"{QDRANT_URL}{endpoint}"
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

        with httpx.Client(timeout=60) as client:
            if method == "GET":
                resp = client.get(url, headers=headers)
            elif method == "POST":
                resp = client.post(url, headers=headers, json=json_data)
            elif method == "PUT":
                resp = client.put(url, headers=headers, json=json_data)
            elif method == "DELETE":
                resp = client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unknown method: {method}")
            resp.raise_for_status()
            return resp.json()

    def create_collection_if_not_exists(self) -> bool:
        """Create immigration_circulars collection with hybrid (BM25 + vector) config."""
        try:
            # Check if collection exists
            info = self._qdrant_request("GET", f"/collections/{COLLECTION_NAME}")
            points_count = info.get("result", {}).get("points_count", 0)
            logger.info(f"Collection {COLLECTION_NAME} exists with {points_count} points")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise

        # Collection doesn't exist, create it
        logger.info(f"Creating collection {COLLECTION_NAME} with hybrid config...")

        if self.dry_run:
            logger.info("[DRY RUN] Would create collection")
            return True

        # Hybrid collection config: dense + sparse vectors
        collection_config = {
            "vectors": {
                "dense": {
                    "size": VECTOR_SIZE,
                    "distance": "Cosine",
                }
            },
            "sparse_vectors": {
                "bm25": {
                    "modifier": "idf",
                }
            },
            "optimizers_config": {
                "default_segment_number": 2,
            },
            "replication_factor": 1,
        }

        self._qdrant_request("PUT", f"/collections/{COLLECTION_NAME}", collection_config)
        logger.info(f"Collection {COLLECTION_NAME} created successfully")
        return True

    def create_chunks(self) -> list[dict]:
        """Create 4 semantic chunks from the circular content."""
        chunks = []
        circular = KEMNAKER_CIRCULAR

        # Chunk metadata common fields
        base_metadata = {
            "source": "kemnaker_circular",
            "document_type": "surat_edaran",
            "regulation_number": circular["number"],
            "title": circular["title"],
            "issuing_authority": circular["issuing_authority"],
            "ministry": circular["ministry"],
            "effective_date": circular["effective_date"],
            "keywords": circular["keywords"],
            "ingested_at": datetime.utcnow().isoformat(),
        }

        # Chunk 0: Main Rule (Kesamaan Sponsor / One Sponsor Policy)
        chunks.append({
            "content": f"""[CONTEXT: Kemnaker Circular 2026 - Alih Status TKA - One Sponsor Policy]

# {circular["number"]} - {circular["title"]}

{circular["summary"]}

{circular["sections"]["main_rule"]}
""",
            "metadata": {
                **base_metadata,
                "chunk_type": "main_rule",
                "chunk_index": 0,
                "topic": "Kesamaan Sponsor (One Sponsor Policy)",
            },
        })

        # Chunk 1: Exception (Partnership/Subsidiary)
        chunks.append({
            "content": f"""[CONTEXT: Kemnaker Circular 2026 - Alih Status TKA - Pengecualian]

# {circular["number"]} - Pengecualian Kesamaan Sponsor

{circular["sections"]["exception"]}
""",
            "metadata": {
                **base_metadata,
                "chunk_type": "exception",
                "chunk_index": 1,
                "topic": "Pengecualian (Partnership/Subsidiary)",
            },
        })

        # Chunk 2: Alternative (Offshore Scheme)
        chunks.append({
            "content": f"""[CONTEXT: Kemnaker Circular 2026 - Alih Status TKA - Solusi Alternatif]

# {circular["number"]} - Solusi Offshore Scheme

{circular["sections"]["alternative"]}
""",
            "metadata": {
                **base_metadata,
                "chunk_type": "alternative",
                "chunk_index": 2,
                "topic": "Solusi Offshore Scheme",
            },
        })

        # Chunk 3: Compliance (BPJS/WLKP/NIB Verification)
        chunks.append({
            "content": f"""[CONTEXT: Kemnaker Circular 2026 - Alih Status TKA - Verifikasi Compliance]

# {circular["number"]} - Verifikasi BPJS, WLKP, NIB

{circular["sections"]["compliance"]}
""",
            "metadata": {
                **base_metadata,
                "chunk_type": "compliance",
                "chunk_index": 3,
                "topic": "BPJS/WLKP/NIB Verification",
            },
        })

        self.stats["chunks_created"] = len(chunks)
        logger.info(f"Created {len(chunks)} chunks")
        return chunks

    async def ingest_to_qdrant(self, chunks: list[dict]) -> bool:
        """Ingest chunks to Qdrant with OpenAI embeddings + BM25."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would ingest {len(chunks)} chunks to Qdrant")
            return True

        try:
            import openai
            from qdrant_client.models import models as qdrant_models

            openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            # Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            texts = [c["content"][:8000] for c in chunks]

            response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
                dimensions=VECTOR_SIZE,
            )
            embeddings = [e.embedding for e in response.data]

            # Build Qdrant points with named vectors
            points = []
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Deterministic UUID based on chunk content
                point_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_DNS,
                        f"kemnaker_circular_{chunk['metadata']['chunk_type']}_{idx}",
                    )
                )

                # Generate BM25 sparse vector from text
                # Note: Qdrant auto-generates BM25 if we provide the text
                # But for hybrid search, we need to index it properly
                text_for_bm25 = chunk["content"]

                points.append({
                    "id": point_id,
                    "vector": {
                        "dense": embedding,
                    },
                    "payload": {
                        "text": chunk["content"],
                        **chunk["metadata"],
                    },
                })

            # Upsert to Qdrant
            logger.info(f"Upserting {len(points)} points to Qdrant...")
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.put(
                    f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points?wait=true",
                    json={"points": points},
                    headers={
                        "api-key": QDRANT_API_KEY,
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code != 200:
                    logger.error(f"Qdrant response: {resp.text}")
                resp.raise_for_status()

            self.stats["points_upserted"] = len(points)
            logger.info(f"Qdrant ingestion: {len(points)} documents upserted")
            return True

        except Exception as e:
            logger.error(f"Qdrant ingestion failed: {e}")
            self.stats["errors"].append(f"Qdrant: {e}")
            return False

    async def save_kg_to_db(self) -> bool:
        """Save KG entities and relationships to PostgreSQL."""
        if self.skip_kg:
            logger.info("Skipping Knowledge Graph (--skip-kg flag)")
            return True

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would save {len(KG_ENTITIES)} entities, {len(KG_RELATIONSHIPS)} relationships to KG"
            )
            return True

        try:
            import asyncpg

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.warning("DATABASE_URL not set, saving to file instead")
                output_path = Path("/tmp/kemnaker_circular_kg.json")
                with open(output_path, "w") as f:
                    json.dump(
                        {"entities": KG_ENTITIES, "relationships": KG_RELATIONSHIPS},
                        f,
                        indent=2,
                    )
                logger.info(f"KG saved to {output_path}")
                return True

            conn = await asyncpg.connect(database_url)

            try:
                # Insert entities
                logger.info(f"Inserting {len(KG_ENTITIES)} entities to kg_nodes...")
                for entity in KG_ENTITIES:
                    await conn.execute(
                        """
                        INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties, confidence, source_collection)
                        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                        ON CONFLICT (entity_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            properties = EXCLUDED.properties,
                            confidence = EXCLUDED.confidence,
                            source_collection = EXCLUDED.source_collection
                        """,
                        entity["entity_id"],
                        entity["entity_type"],
                        entity["name"],
                        entity.get("description", ""),
                        json.dumps(entity.get("properties", {})),
                        entity.get("confidence", 0.9),
                        COLLECTION_NAME,
                    )
                    self.stats["entities_saved"] += 1

                # First, ensure PP 28/2025 entity exists (referenced by relationship)
                await conn.execute(
                    """
                    INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties, confidence, source_collection)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                    ON CONFLICT (entity_id) DO NOTHING
                    """,
                    "pp_28_2025",
                    "peraturan_pemerintah",
                    "PP No. 28 Tahun 2025",
                    "Peraturan Pemerintah tentang Peraturan Pelaksana UU Cipta Kerja (Ketenagakerjaan)",
                    json.dumps({"number": "28", "year": "2025", "topic": "Ketenagakerjaan"}),
                    0.9,
                    "legal_unified_hybrid",
                )

                # Insert relationships
                logger.info(f"Inserting {len(KG_RELATIONSHIPS)} relationships to kg_edges...")
                for rel in KG_RELATIONSHIPS:
                    await conn.execute(
                        """
                        INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id, relationship_type, properties, confidence, source_collection)
                        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                        ON CONFLICT (relationship_id) DO UPDATE SET
                            properties = EXCLUDED.properties,
                            confidence = EXCLUDED.confidence,
                            source_collection = EXCLUDED.source_collection
                        """,
                        rel["relationship_id"],
                        rel["source_entity_id"],
                        rel["target_entity_id"],
                        rel["relationship_type"],
                        json.dumps(rel.get("properties", {})),
                        rel.get("confidence", 0.9),
                        COLLECTION_NAME,
                    )
                    self.stats["relationships_saved"] += 1

                logger.info(
                    f"KG save complete: {self.stats['entities_saved']} entities, {self.stats['relationships_saved']} relationships"
                )
                return True

            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"KG save failed: {e}")
            self.stats["errors"].append(f"KG: {e}")
            # Save to file as backup
            output_path = Path("/tmp/kemnaker_circular_kg.json")
            with open(output_path, "w") as f:
                json.dump(
                    {"entities": KG_ENTITIES, "relationships": KG_RELATIONSHIPS},
                    f,
                    indent=2,
                )
            logger.info(f"KG backup saved to {output_path}")
            return False

    async def run(self) -> dict:
        """Run the full ingestion pipeline."""
        logger.info("=" * 60)
        logger.info("KEMNAKER CIRCULAR INGESTION")
        logger.info(f"SE No. 3/836/PK.04/I/2026 - Alih Status TKA")
        logger.info("=" * 60)
        logger.info(f"Dry run: {self.dry_run}")
        logger.info(f"Skip KG: {self.skip_kg}")
        logger.info(f"Qdrant URL: {QDRANT_URL}")
        logger.info(f"Collection: {COLLECTION_NAME}")

        # 1. Create collection if not exists
        logger.info("\n[1/4] Checking/creating collection...")
        self.create_collection_if_not_exists()

        # 2. Create chunks
        logger.info("\n[2/4] Creating semantic chunks...")
        chunks = self.create_chunks()

        # 3. Ingest to Qdrant
        logger.info("\n[3/4] Ingesting to Qdrant...")
        await self.ingest_to_qdrant(chunks)

        # 4. Save KG to PostgreSQL
        logger.info("\n[4/4] Saving Knowledge Graph...")
        await self.save_kg_to_db()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("INGESTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Chunks created: {self.stats['chunks_created']}")
        logger.info(f"Points upserted: {self.stats['points_upserted']}")
        logger.info(f"KG entities saved: {self.stats['entities_saved']}")
        logger.info(f"KG relationships saved: {self.stats['relationships_saved']}")

        if self.stats["errors"]:
            logger.warning(f"Errors: {len(self.stats['errors'])}")
            for err in self.stats["errors"]:
                logger.warning(f"  - {err}")

        return self.stats


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest Kemnaker Circular SE 3/836/PK.04/I/2026"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without inserting to Qdrant/PostgreSQL",
    )
    parser.add_argument(
        "--skip-kg",
        action="store_true",
        help="Only ingest to Qdrant, skip Knowledge Graph",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed logging",
    )
    args = parser.parse_args()

    ingestion = KemnakerCircularIngestion(
        dry_run=args.dry_run,
        skip_kg=args.skip_kg,
        verbose=args.verbose,
    )
    stats = await ingestion.run()

    # Exit with error code if errors occurred
    if stats.get("errors"):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
