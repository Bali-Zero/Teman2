#!/usr/bin/env python3
"""
Re-ingest corrected training data files into training_conversations_hybrid collection.

Uses direct HTTP requests to bypass qdrant-client SSL issues on Fly.io.

Run LOCALLY:
    cd apps/backend-rag && python scripts/reingest_training_data.py
"""

import hashlib
import logging
import os
import sys
import time
from pathlib import Path

import requests

# Load .env from backend-rag root
script_dir = Path(__file__).parent
backend_rag_root = script_dir.parent
dotenv_path = backend_rag_root / ".env"

# Add backend to path
sys.path.insert(0, str(backend_rag_root / "backend"))

from dotenv import load_dotenv

load_dotenv(dotenv_path)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Files to re-ingest (corrected with Bali Zero 2025 prices - Jan 2026 update)
FILES_TO_REINGEST = [
    # Business - PT PMA, Restaurant, Villa
    "training-data/business/business_001_pt_pma_core_setup.md",
    "training-data/business/business_002_restaurant_best_practices.md",
    "training-data/business/business_028_pt_pma_restaurant_setup.md",  # FIXED: SLHS 9M, NPBBKC 15M
    "training-data/business/business_029_pt_pma_villa_rental.md",
    "training-data/business/business_032_pt_lokal_vs_pt_pma.md",
    # Visa - All visa types with correct Bali Zero 2025 prices
    "training-data/visa/visa_001_e33g_digital_nomad_basic.md",
    "training-data/visa/visa_003_e28a_investor_kitas.md",
    "training-data/visa/visa_004_d1_tourism_multiple_entry.md",  # FIXED: D1 1Y=5M, 2Y=7M
    "training-data/visa/visa_005_d12_business_investigation.md",
    "training-data/visa/visa_006_retirement_visas_e33e_e33f.md",  # E33E/E33F 55+ verified
    "training-data/visa/visa_010_notebooklm_session1.md",  # FIXED: E33E age 55+ (not 60)
    "training-data/visa/visa_011_notebooklm_session2.md",
    "training-data/spouse_mixed_marriage_conversation.md",  # FIXED: E31A (not E26)
    # Licenses - SLHS, NPBBKC
    "training-data/licenses/licenses_001_slhs_hygiene_certificate.md",
    "training-data/licenses/licenses_002_npbbkc_alcohol_license.md",
    # Tax & Compliance
    "training-data/tax/tax_016_pph21_individual_indonesian.md",
    "training-data/tax/tax_019_ppn_vat_full_cycle.md",
    "training-data/tax/tax_020_bpjs_insurance.md",
    "training-data/tax/tax_021_npwp_registration.md",
    "training-data/tax/tax_022_spt_annual_tax.md",
    "training-data/tax/tax_023_lkpm_investment_report.md",
    "training-data/tax_pph_ppn_conversation.md",
    # Customs
    "training-data/customs/customs_040_import_duty_basics.md",
    # Legal
    "training-data/legal/legal_055_labor_dispute_resolution.md",
    "training-data/legal/legal_058_intellectual_property_basics.md",
    # Real Estate
    "training-data/realestate/realestate_046_indonesian_buying_property.md",
]

COLLECTION_NAME = "training_conversations_hybrid"
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


def upsert_point(
    point_id: int, dense_vector: list, sparse_indices: list, sparse_values: list, payload: dict
) -> bool:
    """Upsert a single point to Qdrant using direct HTTP request."""
    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points"
    headers = {"Content-Type": "application/json", "api-key": QDRANT_API_KEY}
    data = {
        "points": [
            {
                "id": point_id,
                "vector": {
                    "dense": dense_vector,
                    "bm25": {"indices": sparse_indices, "values": sparse_values},
                },
                "payload": payload,
            }
        ]
    }

    for attempt in range(3):
        try:
            resp = requests.put(url, headers=headers, json=data, timeout=30)
            if resp.status_code == 200:
                return True
            else:
                logger.warning(f"  ⚠️ Qdrant returned {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            if attempt < 2:
                wait_time = 5 * (attempt + 1)
                logger.warning(f"  ⚠️ Retry {attempt + 1}/3 (waiting {wait_time}s): {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"  ❌ Failed after 3 attempts: {e}")
                return False
    return False


def reingest_files():
    """Re-ingest corrected training data files."""
    from core.bm25_vectorizer import BM25Vectorizer
    from core.chunker import TextChunker
    from core.embeddings import create_embeddings_generator

    logger.info(f"Connecting to Qdrant: {QDRANT_URL}")

    embedder = create_embeddings_generator()
    bm25 = BM25Vectorizer()
    chunker = TextChunker(chunk_size=1500, chunk_overlap=200)

    # Get base path (apps/backend-rag)
    base_path = backend_rag_root

    total_chunks = 0
    total_upserted = 0

    for file_path in FILES_TO_REINGEST:
        full_path = base_path / file_path

        if not full_path.exists():
            logger.warning(f"File not found: {full_path}")
            continue

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing: {file_path}")

        # Read file content
        content = full_path.read_text(encoding="utf-8")

        # Extract metadata from filename
        filename = full_path.stem
        parts = filename.split("_")
        category = parts[0] if parts else "unknown"  # business, visa, licenses

        # Extract title from markdown content
        title = filename  # Default to filename
        for line in content.split("\n")[:10]:
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
                break
            if line.startswith("**TITLE:"):
                title = line.replace("**TITLE:", "").replace("**", "").strip()
                break

        # Chunk the content
        chunks = chunker.chunk_text(content)
        logger.info(f"  Created {len(chunks)} chunks")

        for idx, chunk_text in enumerate(chunks):
            # Generate embeddings
            dense_embedding = embedder.generate_query_embedding(chunk_text)

            # Generate BM25 sparse vector
            sparse_result = bm25.generate_sparse_vector(chunk_text)
            sparse_indices = sparse_result["indices"]
            sparse_values = sparse_result["values"]

            # Create unique ID based on file + chunk index
            point_id = hashlib.md5(f"{file_path}_{idx}".encode()).hexdigest()
            point_id_int = int(point_id[:16], 16)

            # Build metadata
            payload = {
                "source": file_path,
                "filename": filename,
                "title": title,
                "category": category,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "text": chunk_text,
                "data_version": "bali_zero_2025_corrected",
            }

            # Upsert to Qdrant
            success = upsert_point(
                point_id_int, dense_embedding, sparse_indices, sparse_values, payload
            )
            if success:
                total_upserted += 1
                if (idx + 1) % 10 == 0:
                    logger.info(f"  ✅ Progress: {idx + 1}/{len(chunks)} chunks")
            else:
                logger.error(f"  ❌ Failed chunk {idx}")

            total_chunks += 1
            time.sleep(0.3)  # Small delay between requests

        logger.info(f"  ✅ File complete: {total_upserted} chunks upserted")

    logger.info(f"\n{'=' * 60}")
    logger.info(f"COMPLETED: {total_upserted}/{total_chunks} chunks upserted")
    logger.info(f"Collection: {COLLECTION_NAME}")


if __name__ == "__main__":
    reingest_files()
