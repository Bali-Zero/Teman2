#!/usr/bin/env python3
"""
KBLI 2025 Final Ingestion Script - Parent Document Retriever Pattern (v2)
==========================================================================
Ingests KBLI_2025_FINAL_CLEAN.json into:
1. Qdrant Collection: `kbli_2025_final` (ONLY child chunks with embeddings)
2. PostgreSQL: `kbli_documents` table (parent documents for retrieval)
3. Knowledge Graph (PostgreSQL): kg_nodes, kg_edges

Strategy: Parent Document Retriever (Best Practice)
- Child chunks → Qdrant (embedded for precise search)
- Parent docs → PostgreSQL (retrieved by kode_kbli for full context)
- No zero-vector storage waste

References:
- https://dzone.com/articles/parent-document-retrieval-useful-technique-in-rag
- https://dev.to/jamesli/optimizing-rag-indexing-strategy-multi-vector-indexing-and-parent-document-retrieval-49hf

Usage:
    python scripts/ingestion/ingest_kbli_2025_final.py --dry-run
    python scripts/ingestion/ingest_kbli_2025_final.py --recreate
    python scripts/ingestion/ingest_kbli_2025_final.py

Author: Zantara AI
Date: 2026-02-04
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import httpx
from dotenv import load_dotenv

# Path setup
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "backend-rag"))

# Load environment
load_dotenv(PROJECT_ROOT / "apps" / "backend-rag" / ".env")

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

COLLECTION_NAME = "kbli_2025_final"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

SOURCE_PATH = PROJECT_ROOT / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

# Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class KBLI2025Ingestion:
    """Parent Document Retriever pattern for KBLI 2025 ingestion."""

    def __init__(self, dry_run: bool = False, recreate: bool = False):
        self.dry_run = dry_run
        self.recreate = recreate
        self.stats = {
            "parent_docs": 0,
            "child_chunks": 0,
            "vectors_uploaded": 0,
            "parent_docs_saved": 0,
            "kg_nodes": 0,
            "kg_edges": 0,
            "errors": [],
        }

    # =========================================================================
    # STEP 1: CHUNKING
    # =========================================================================

    def create_parent_document(self, item: Dict) -> Dict:
        """Create a comprehensive parent document for a KBLI code."""
        code = item["kode_kbli_2025"]

        # Build full content
        content_parts = [
            f"# KBLI {code} - {item['judul']}",
            "\n## Informasi Umum",
            f"- **Kode KBLI 2025**: {code}",
            f"- **Sektor**: {item.get('sektor_id', 'N/A')}",
            f"- **Status Mapping**: {item.get('status_mapping', 'N/A')}",
            f"- **Status Perizinan**: {item.get('licensing_status', 'N/A')}",
            "\n## Deskripsi Kegiatan Usaha",
            item.get("uraian", ""),
            "\n## Investasi Asing (PMA)",
            f"- **Status PMA**: {item.get('pma_status', 'N/A')}",
            f"- **Maksimum Kepemilikan Asing**: {item.get('pma_max_asing', 'N/A')}%",
            f"- **Prioritas Investasi**: {'Ya' if item.get('pma_prioritas') else 'Tidak'}",
        ]

        if item.get("pma_kondisi"):
            content_parts.append(f"- **Kondisi PMA**: {item['pma_kondisi']}")
        if item.get("pma_nota"):
            content_parts.append(f"- **Catatan**: {item['pma_nota']}")
        if item.get("pma_verification"):
            content_parts.append(f"- **Verifikasi**: {item['pma_verification']}")
        if item.get("pma_prediksi"):
            content_parts.append(
                f"- **Prediksi PMA**: {item['pma_prediksi']} (Probabilitas: {item.get('pma_probabilitas', 'N/A')})"
            )

        # Add per_skala details
        per_skala = item.get("per_skala", [])
        if per_skala:
            content_parts.append("\n## Perizinan Per Skala Usaha")
            for idx, skala_info in enumerate(per_skala):
                skala_names = ", ".join(skala_info.get("skala_usaha", ["N/A"]))
                content_parts.append(
                    f"\n### [{skala_names}] - Risiko: {skala_info.get('kategori_risiko', 'N/A')}"
                )
                content_parts.append(
                    f"- **Perizinan**: {skala_info.get('perizinan', 'N/A')}"
                )
                content_parts.append(
                    f"- **Jangka Waktu**: {skala_info.get('jangka_waktu', 'N/A')}"
                )
                content_parts.append(
                    f"- **Kewenangan**: {skala_info.get('kewenangan', 'N/A')}"
                )
                content_parts.append(
                    f"- **Fiktif Positif**: {'Ya' if skala_info.get('fiktif_positif') else 'Tidak'}"
                )

                # Persyaratan
                persyaratan = skala_info.get("persyaratan", [])
                if persyaratan:
                    content_parts.append("- **Persyaratan Dokumen**:")
                    for req in persyaratan:
                        content_parts.append(f"  - {req}")

                # Kewajiban
                kewajiban = skala_info.get("kewajiban", [])
                if kewajiban:
                    content_parts.append("- **Kewajiban Pelaku Usaha**:")
                    for kew in kewajiban:
                        content_parts.append(f"  - {kew}")

                # PB UMKU
                pb_umku = skala_info.get("pb_umku", [])
                if pb_umku:
                    content_parts.append("- **Perizinan Berusaha UMKU**:")
                    for pb in pb_umku:
                        content_parts.append(f"  - {pb}")

                # Sanksi
                content_parts.append("- **Sanksi Administratif**:")
                content_parts.append(
                    f"  - Peringatan: {skala_info.get('sanksi_peringatan', 'N/A')}"
                )
                content_parts.append(
                    f"  - Denda: {skala_info.get('sanksi_denda', 'N/A')}"
                )
                content_parts.append(
                    f"  - Penghentian: {skala_info.get('sanksi_penghentian', 'N/A')}"
                )
                content_parts.append(
                    f"  - Pencabutan: {skala_info.get('sanksi_pencabutan', 'N/A')}"
                )

        content = "\n".join(content_parts)

        return {
            "kode_kbli": code,
            "judul": item["judul"],
            "content": content,
            "metadata": {
                "sektor_id": item.get("sektor_id"),
                "pma_status": item.get("pma_status"),
                "pma_max_asing": item.get("pma_max_asing"),
                "licensing_status": item.get("licensing_status"),
                "status_mapping": item.get("status_mapping"),
            },
        }

    def create_child_chunks(self, item: Dict) -> List[Dict]:
        """Create child chunks for each KBLI + Scala combination."""
        code = item["kode_kbli_2025"]
        judul = item["judul"]
        uraian = item.get("uraian", "")
        chunks = []
        
        # ALWAYS create uraian chunk FIRST for semantic search
        if uraian:
            uraian_content = f"""[KBLI {code}] {judul}

{uraian}

Sektor: {item.get("sektor_id", "N/A")}
Status PMA: {item.get("pma_status", "N/A")} (Max {item.get("pma_max_asing", 0)}%)
"""
            chunks.append({
                "id": f"kbli_{code}_uraian",
                "kode_kbli": code,
                "content": uraian_content,
                "metadata": {
                    "kode_kbli": code,
                    "judul": judul,
                    "sektor_id": item.get("sektor_id"),
                    "pma_status": item.get("pma_status"),
                    "pma_max_asing": item.get("pma_max_asing"),
                    "licensing_status": item.get("licensing_status"),
                    "skala_usaha": None,
                    "kategori_risiko": None,
                    "doc_type": "kbli_child",
                    "chunk_type": "uraian",
                },
            })

        per_skala = item.get("per_skala", [])

        if not per_skala:
            # For BPS_ONLY codes without per_skala, create a single child chunk
            content = f"""KBLI {code} - {judul}

Sektor: {item.get("sektor_id", "N/A")}
Status Perizinan: {item.get("licensing_status", "N/A")}

Deskripsi:
{item.get("uraian", "")}

Investasi Asing (PMA):
- Status: {item.get("pma_status", "N/A")}
- Maksimum Asing: {item.get("pma_max_asing", "N/A")}%
- Verifikasi: {item.get("pma_verification", "N/A")}
"""
            if item.get("pma_prediksi"):
                content += f"- Prediksi: {item['pma_prediksi']} ({item.get('pma_probabilitas', '')})\n"
                content += f"- Alasan: {item.get('pma_alasan_prediksi', '')}\n"

            if item.get("licensing_note"):
                content += f"\nCatatan: {item['licensing_note']}"

            chunks.append(
                {
                    "id": f"kbli_{code}_general",
                    "kode_kbli": code,
                    "content": content,
                    "metadata": {
                        "kode_kbli": code,
                        "judul": judul,
                        "sektor_id": item.get("sektor_id"),
                        "pma_status": item.get("pma_status"),
                        "pma_max_asing": item.get("pma_max_asing"),
                        "licensing_status": item.get("licensing_status"),
                        "skala_usaha": None,
                        "kategori_risiko": None,
                        "doc_type": "kbli_child",
                        "chunk_type": "general",
                    },
                }
            )
            return chunks

        # Create one chunk per scala combination
        for idx, skala_info in enumerate(per_skala):
            skala_names = skala_info.get("skala_usaha", ["Unknown"])
            skala_key = "_".join(s.lower() for s in skala_names)
            risiko = skala_info.get("kategori_risiko", "N/A")

            # Build chunk content
            content = f"""KBLI {code} - {judul}
Skala Usaha: {", ".join(skala_names)}
Kategori Risiko: {risiko}

Sektor: {item.get("sektor_id", "N/A")}
Status PMA: {item.get("pma_status", "N/A")} (Max {item.get("pma_max_asing", "N/A")}%)

PERIZINAN:
- Jenis Izin: {skala_info.get("perizinan", "N/A")}
- Jangka Waktu Penerbitan: {skala_info.get("jangka_waktu", "N/A")}
- Kewenangan: {skala_info.get("kewenangan", "N/A")}
- Fiktif Positif: {"Ya (auto-approval berlaku)" if skala_info.get("fiktif_positif") else "Tidak"}
"""

            # Persyaratan
            persyaratan = skala_info.get("persyaratan", [])
            if persyaratan:
                content += "\nPERSYARATAN DOKUMEN:\n"
                for req in persyaratan:
                    content += f"- {req}\n"
            else:
                content += "\nPERSYARATAN DOKUMEN: Tidak ada persyaratan khusus\n"

            # Kewajiban
            kewajiban = skala_info.get("kewajiban", [])
            if kewajiban:
                content += "\nKEWAJIBAN PELAKU USAHA:\n"
                for kew in kewajiban:
                    content += f"- {kew}\n"

            # PB UMKU
            pb_umku = skala_info.get("pb_umku", [])
            if pb_umku:
                content += "\nPERIZINAN BERUSAHA UMKU:\n"
                for pb in pb_umku:
                    content += f"- {pb}\n"

            # Sanksi
            content += f"""
SANKSI ADMINISTRATIF:
1. Peringatan: {skala_info.get("sanksi_peringatan", "N/A")}
2. Denda: {skala_info.get("sanksi_denda", "N/A")}
3. Penghentian: {skala_info.get("sanksi_penghentian", "N/A")}
4. Pencabutan: {skala_info.get("sanksi_pencabutan", "N/A")}

Parameter Lokasi: {skala_info.get("parameter", "N/A")}
"""

            chunks.append(
                {
                    "id": f"kbli_{code}_{skala_key}_{idx}",
                    "kode_kbli": code,
                    "content": content,
                    "metadata": {
                        "kode_kbli": code,
                        "judul": judul,
                        "sektor_id": item.get("sektor_id"),
                        "pma_status": item.get("pma_status"),
                        "pma_max_asing": item.get("pma_max_asing"),
                        "licensing_status": item.get("licensing_status"),
                        "skala_usaha": skala_names,
                        "kategori_risiko": risiko,
                        "perizinan": skala_info.get("perizinan"),
                        "jangka_waktu": skala_info.get("jangka_waktu"),
                        "kewenangan": skala_info.get("kewenangan"),
                        "fiktif_positif": skala_info.get("fiktif_positif"),
                        "doc_type": "kbli_child",
                        "chunk_type": "per_skala",
                    },
                }
            )

        return chunks

    # =========================================================================
    # STEP 2: EMBEDDING
    # =========================================================================

    async def embed_batch(
        self, texts: List[str], client: httpx.AsyncClient
    ) -> List[List[float]]:
        """Embed a batch of texts using OpenAI API."""
        if self.dry_run:
            return [[0.0] * EMBEDDING_DIM for _ in texts]

        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": [t[:8000] for t in texts],  # Truncate if needed
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    # =========================================================================
    # STEP 3: QDRANT OPERATIONS
    # =========================================================================

    async def qdrant_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        endpoint: str,
        json_data: dict = None,
    ) -> dict:
        """Make a request to Qdrant API."""
        url = f"{QDRANT_URL}{endpoint}"
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

        if method == "GET":
            resp = await client.get(url, headers=headers, timeout=30.0)
        elif method == "PUT":
            resp = await client.put(url, headers=headers, json=json_data, timeout=60.0)
        elif method == "DELETE":
            resp = await client.delete(url, headers=headers, timeout=30.0)
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=json_data, timeout=60.0)

        resp.raise_for_status()
        return resp.json()

    async def setup_collection(self, client: httpx.AsyncClient):
        """Create or recreate the Qdrant collection with payload indexes."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create collection {COLLECTION_NAME}")
            return

        # Check if exists
        try:
            await self.qdrant_request(client, "GET", f"/collections/{COLLECTION_NAME}")
            exists = True
        except httpx.HTTPStatusError:
            exists = False

        if exists:
            if self.recreate:
                logger.info(f"Deleting existing collection {COLLECTION_NAME}...")
                await self.qdrant_request(
                    client, "DELETE", f"/collections/{COLLECTION_NAME}"
                )
            else:
                logger.info(f"Collection {COLLECTION_NAME} exists. Will append/update.")
                return

        # Create collection
        logger.info(f"Creating collection {COLLECTION_NAME}...")
        await self.qdrant_request(
            client,
            "PUT",
            f"/collections/{COLLECTION_NAME}",
            {
                "vectors": {"size": EMBEDDING_DIM, "distance": "Cosine"},
                "optimizers_config": {"indexing_threshold": 20000},
            },
        )

        # Create payload indexes for filtering (Best Practice: Qdrant docs)
        logger.info("Creating payload indexes...")
        indexes_to_create = [
            ("kode_kbli", "keyword"),
            ("sektor_id", "keyword"),
            ("pma_status", "keyword"),
            ("licensing_status", "keyword"),
            ("kategori_risiko", "keyword"),
            ("chunk_type", "keyword"),
        ]

        for field_name, field_type in indexes_to_create:
            try:
                await self.qdrant_request(
                    client,
                    "PUT",
                    f"/collections/{COLLECTION_NAME}/index",
                    {"field_name": field_name, "field_schema": field_type},
                )
                logger.info(f"  ✓ Index created: {field_name} ({field_type})")
            except Exception as e:
                logger.warning(f"  ⚠ Index {field_name} failed: {e}")

    async def upsert_points(self, client: httpx.AsyncClient, points: List[Dict]):
        """Upsert points to Qdrant."""
        if self.dry_run:
            return

        await self.qdrant_request(
            client, "PUT", f"/collections/{COLLECTION_NAME}/points", {"points": points}
        )

    # =========================================================================
    # STEP 4: POSTGRESQL - PARENT DOCUMENTS
    # =========================================================================

    async def setup_parent_docs_table(self, conn):
        """Create the kbli_documents table for parent document storage."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS kbli_documents (
                kode_kbli VARCHAR(10) PRIMARY KEY,
                judul TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create index for fast lookup
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_kbli_documents_kode
            ON kbli_documents(kode_kbli)
        """)

    async def save_parent_docs(self, conn, parent_docs: List[Dict]):
        """Save parent documents to PostgreSQL."""
        for doc in parent_docs:
            await conn.execute(
                """
                INSERT INTO kbli_documents (kode_kbli, judul, content, metadata, updated_at)
                VALUES ($1, $2, $3, $4::jsonb, NOW())
                ON CONFLICT (kode_kbli) DO UPDATE SET
                    judul = EXCLUDED.judul,
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """,
                doc["kode_kbli"],
                doc["judul"],
                doc["content"],
                json.dumps(doc["metadata"]),
            )

        self.stats["parent_docs_saved"] = len(parent_docs)

    # =========================================================================
    # STEP 5: KNOWLEDGE GRAPH
    # =========================================================================

    def extract_kg_elements(self, item: Dict) -> Tuple[List[Dict], List[Dict]]:
        """Extract Knowledge Graph nodes and edges from a KBLI record."""
        nodes = []
        edges = []

        code = item["kode_kbli_2025"]
        kbli_id = f"kbli_{code}"

        # 1. KBLI Node
        nodes.append(
            {
                "id": kbli_id,
                "type": "kbli_code",
                "name": f"{code} - {item['judul']}",
                "props": {
                    "code": code,
                    "judul": item["judul"],
                    "sektor_id": item.get("sektor_id"),
                    "licensing_status": item.get("licensing_status"),
                    "status_mapping": item.get("status_mapping"),
                },
            }
        )

        # 2. Sector Node & Edge
        sektor_id = item.get("sektor_id")
        if sektor_id:
            sector_node_id = f"sector_{sektor_id.replace('.', '_')}"
            nodes.append(
                {"id": sector_node_id, "type": "sector", "name": sektor_id, "props": {}}
            )
            edges.append(
                {
                    "source": kbli_id,
                    "target": sector_node_id,
                    "type": "IN_SECTOR",
                    "props": {},
                }
            )

        # 3. PMA Status Node & Edge
        pma_status = item.get("pma_status")
        if pma_status:
            pma_node_id = f"pma_{pma_status.lower()}"
            nodes.append(
                {
                    "id": pma_node_id,
                    "type": "pma_status",
                    "name": pma_status,
                    "props": {"max_asing": item.get("pma_max_asing")},
                }
            )
            edges.append(
                {
                    "source": kbli_id,
                    "target": pma_node_id,
                    "type": "HAS_PMA_STATUS",
                    "props": {
                        "max_asing": item.get("pma_max_asing"),
                        "prioritas": item.get("pma_prioritas"),
                        "kondisi": item.get("pma_kondisi"),
                    },
                }
            )

        # 4. Licensing Status Node & Edge
        licensing = item.get("licensing_status")
        if licensing:
            lic_node_id = f"licensing_{licensing.lower()}"
            nodes.append(
                {
                    "id": lic_node_id,
                    "type": "licensing_status",
                    "name": licensing,
                    "props": {},
                }
            )
            edges.append(
                {
                    "source": kbli_id,
                    "target": lic_node_id,
                    "type": "HAS_LICENSING_STATUS",
                    "props": {},
                }
            )

        # 5. Risk Level & Permit Nodes from per_skala
        per_skala = item.get("per_skala", [])
        seen_risks = set()
        seen_permits = set()

        for skala_info in per_skala:
            # Risk level
            risiko = skala_info.get("kategori_risiko")
            if risiko and risiko not in seen_risks:
                seen_risks.add(risiko)
                risk_node_id = f"risk_{risiko.lower().replace(' ', '_')}"
                nodes.append(
                    {
                        "id": risk_node_id,
                        "type": "risk_level",
                        "name": risiko,
                        "props": {},
                    }
                )
                edges.append(
                    {
                        "source": kbli_id,
                        "target": risk_node_id,
                        "type": "HAS_RISK_LEVEL",
                        "props": {"skala": skala_info.get("skala_usaha")},
                    }
                )

            # Permit type
            perizinan = skala_info.get("perizinan")
            if perizinan and perizinan not in seen_permits:
                seen_permits.add(perizinan)
                permit_node_id = (
                    f"permit_{perizinan.lower().replace(' ', '_').replace('+', '_')}"
                )
                nodes.append(
                    {
                        "id": permit_node_id,
                        "type": "permit_type",
                        "name": perizinan,
                        "props": {},
                    }
                )
                edges.append(
                    {
                        "source": kbli_id,
                        "target": permit_node_id,
                        "type": "REQUIRES_PERMIT",
                        "props": {"skala": skala_info.get("skala_usaha")},
                    }
                )

            # Authority
            kewenangan = skala_info.get("kewenangan")
            if kewenangan:
                auth_node_id = f"authority_{kewenangan.lower().replace('/', '_').replace(' ', '_')}"
                nodes.append(
                    {
                        "id": auth_node_id,
                        "type": "authority",
                        "name": kewenangan,
                        "props": {},
                    }
                )
                edges.append(
                    {
                        "source": kbli_id,
                        "target": auth_node_id,
                        "type": "REGULATED_BY",
                        "props": {},
                    }
                )

        return nodes, edges

    async def save_kg_batch(self, conn, nodes: List[Dict], edges: List[Dict]):
        """Save Knowledge Graph elements to PostgreSQL."""
        # Deduplicate nodes by ID
        unique_nodes = {n["id"]: n for n in nodes}

        # Upsert Nodes
        for n in unique_nodes.values():
            await conn.execute(
                """
                INSERT INTO kg_nodes (entity_id, entity_type, name, properties, source_collection, confidence)
                VALUES ($1, $2, $3, $4::jsonb, $5, 0.95)
                ON CONFLICT (entity_id) DO UPDATE SET
                    properties = EXCLUDED.properties,
                    updated_at = NOW()
            """,
                n["id"],
                n["type"],
                n["name"],
                json.dumps(n["props"]),
                COLLECTION_NAME,
            )

        # Upsert Edges
        for e in edges:
            rel_id = f"rel_{e['source']}_{e['type']}_{e['target']}"
            await conn.execute(
                """
                INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id,
                                      relationship_type, properties, source_collection, confidence)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, 0.95)
                ON CONFLICT (relationship_id) DO NOTHING
            """,
                rel_id,
                e["source"],
                e["target"],
                e["type"],
                json.dumps(e["props"]),
                COLLECTION_NAME,
            )

        self.stats["kg_nodes"] = len(unique_nodes)
        self.stats["kg_edges"] = len(edges)

    # =========================================================================
    # MAIN EXECUTION
    # =========================================================================

    async def run(self):
        """Main ingestion pipeline."""
        logger.info("=" * 70)
        logger.info("KBLI 2025 FINAL INGESTION v2 - Parent Document Retriever Pattern")
        logger.info("=" * 70)
        logger.info("Best Practice: Child chunks → Qdrant, Parent docs → PostgreSQL")

        # Load source data
        logger.info(f"\n[1/6] Loading source data: {SOURCE_PATH}")
        with open(SOURCE_PATH, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        items = raw_data.get("data", raw_data)
        logger.info(f"      Loaded {len(items)} KBLI codes")

        # Generate chunks
        logger.info("\n[2/6] Generating chunks...")
        parent_docs = []
        child_chunks = []
        all_kg_nodes = []
        all_kg_edges = []

        for item in items:
            # Parent document
            parent = self.create_parent_document(item)
            parent_docs.append(parent)

            # Child chunks
            children = self.create_child_chunks(item)
            child_chunks.extend(children)

            # Knowledge Graph
            nodes, edges = self.extract_kg_elements(item)
            all_kg_nodes.extend(nodes)
            all_kg_edges.extend(edges)

        self.stats["parent_docs"] = len(parent_docs)
        self.stats["child_chunks"] = len(child_chunks)

        logger.info(f"      Parent documents: {len(parent_docs)}")
        logger.info(f"      Child chunks: {len(child_chunks)}")
        logger.info(f"      KG Nodes (raw): {len(all_kg_nodes)}")
        logger.info(f"      KG Edges: {len(all_kg_edges)}")

        # Setup Qdrant
        async with httpx.AsyncClient() as http_client:
            logger.info("\n[3/6] Setting up Qdrant collection with payload indexes...")
            await self.setup_collection(http_client)

            # Embed and upload ONLY child chunks
            logger.info("\n[4/6] Embedding and uploading child chunks to Qdrant...")
            batch_size = 50

            for i in range(0, len(child_chunks), batch_size):
                batch = child_chunks[i : i + batch_size]
                texts = [c["content"] for c in batch]

                # Embed
                embeddings = await self.embed_batch(texts, http_client)

                # Create points
                points = []
                for j, chunk in enumerate(batch):
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["id"]))
                    points.append(
                        {
                            "id": point_id,
                            "vector": embeddings[j],
                            "payload": {
                                "content": chunk["content"],
                                "chunk_id": chunk["id"],
                                **chunk["metadata"],
                            },
                        }
                    )

                # Upload
                if not self.dry_run:
                    await self.upsert_points(http_client, points)
                self.stats["vectors_uploaded"] += len(points)

                if (i + batch_size) % 500 == 0 or i + batch_size >= len(child_chunks):
                    logger.info(
                        f"      Progress: {min(i + batch_size, len(child_chunks))}/{len(child_chunks)} chunks"
                    )

        # Save to PostgreSQL
        if DATABASE_URL and not self.dry_run:
            import asyncpg

            conn = await asyncpg.connect(DATABASE_URL)
            try:
                # Parent documents
                logger.info("\n[5/6] Saving parent documents to PostgreSQL...")
                await self.setup_parent_docs_table(conn)
                await self.save_parent_docs(conn, parent_docs)
                logger.info(
                    f"      Saved {len(parent_docs)} parent documents to kbli_documents table"
                )

                # Knowledge Graph
                logger.info("\n[6/6] Saving Knowledge Graph to PostgreSQL...")
                await self.save_kg_batch(conn, all_kg_nodes, all_kg_edges)

            except Exception as err:
                logger.error(f"PostgreSQL error: {err}")
                self.stats["errors"].append(str(err))
            finally:
                await conn.close()
        else:
            if self.dry_run:
                logger.info("\n[5/6] [DRY RUN] Would save parent docs to PostgreSQL")
                logger.info("\n[6/6] [DRY RUN] Would save KG to PostgreSQL")
            else:
                logger.warning("\n[5-6/6] No DATABASE_URL - skipping PostgreSQL")

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("INGESTION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"""
Statistics:
  - Parent Documents:      {self.stats["parent_docs"]}
  - Child Chunks:          {self.stats["child_chunks"]}
  - Vectors in Qdrant:     {self.stats["vectors_uploaded"]}
  - Parent Docs in PG:     {self.stats["parent_docs_saved"]}
  - KG Nodes:              {self.stats["kg_nodes"]}
  - KG Edges:              {self.stats["kg_edges"]}
  - Errors:                {len(self.stats["errors"])}

Architecture:
  - Qdrant Collection:     {COLLECTION_NAME} (child chunks only)
  - PostgreSQL Table:      kbli_documents (parent docs for retrieval)
  - PostgreSQL Tables:     kg_nodes, kg_edges (knowledge graph)
        """)

        if self.stats["errors"]:
            logger.warning(f"Errors encountered: {self.stats['errors']}")

        return self.stats


async def main():
    parser = argparse.ArgumentParser(description="KBLI 2025 Final Ingestion v2")
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without actual uploads"
    )
    parser.add_argument(
        "--recreate", action="store_true", help="Delete and recreate collection"
    )
    args = parser.parse_args()

    ingester = KBLI2025Ingestion(dry_run=args.dry_run, recreate=args.recreate)
    await ingester.run()


if __name__ == "__main__":
    asyncio.run(main())
