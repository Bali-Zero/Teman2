#!/usr/bin/env python3
"""
Ingest Surat Edaran (Circolari) into Qdrant visa_oracle collection
------------------------------------------------------------------
Uses direct REST API calls to bypass qdrant-client SSL issues.
Ingests into visa_oracle collection for visa-related queries.
"""

import logging
import os
import sys
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.embeddings import EmbeddingsGenerator

# Qdrant config
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Collection name - visa_oracle for visa-related regulations
COLLECTION_NAME = "visa_oracle"

# Files to ingest
SURAT_EDARAN_FILES = [
    Path(
        "/Users/antonellosiano/Desktop/nuzantara/apps/kb/data/immigration/SE_IMI-941_GR_01_01_2024_peneraan_cap.txt"
    ),
    Path(
        "/Users/antonellosiano/Desktop/nuzantara/apps/kb/data/immigration/SE_IMI-417_GR_01_01_2025_penyesuaian_pelayanan.txt"
    ),
]


def qdrant_request(method: str, endpoint: str, json_data: dict = None) -> dict:
    """Make REST request to Qdrant"""
    url = f"{QDRANT_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=60)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, json=json_data, timeout=60)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=json_data, timeout=60)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=60)
        else:
            raise ValueError(f"Unknown method: {method}")

        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Qdrant request failed: {e}")
        raise


def chunk_document(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """
    Chunk document by sections (## headers) or by size.
    Optimized for legal documents with clear section markers.
    """
    chunks = []

    # Try to split by major sections first
    sections = text.split("\n## ")

    if len(sections) > 1:
        # Document has clear sections
        current_chunk = sections[0]  # First part (header/intro)

        for section in sections[1:]:
            section_text = "## " + section

            if len(current_chunk) + len(section_text) < chunk_size:
                current_chunk += "\n" + section_text
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = section_text

        if current_chunk.strip():
            chunks.append(current_chunk.strip())
    else:
        # No clear sections, chunk by size with overlap
        words = text.split()
        current_chunk = []
        current_size = 0

        for word in words:
            current_chunk.append(word)
            current_size += len(word) + 1

            if current_size >= chunk_size:
                chunks.append(" ".join(current_chunk))
                # Keep last N words for overlap
                overlap_words = int(overlap / 5)  # ~5 chars per word avg
                current_chunk = current_chunk[-overlap_words:]
                current_size = sum(len(w) + 1 for w in current_chunk)

        if current_chunk:
            chunks.append(" ".join(current_chunk))

    return chunks


def extract_metadata(file_path: Path, content: str) -> dict:
    """Extract metadata from file content and name"""
    metadata = {
        "source": "surat_edaran",
        "file_name": file_path.name,
        "category": "visa_procedure",
        "document_type": "circular_letter",
    }

    # Extract from filename
    filename_lower = file_path.name.lower()

    if "imi-941" in filename_lower or "941" in filename_lower:
        metadata.update(
            {
                "regulation_number": "IMI-941.GR.01.01",
                "regulation_year": "2024",
                "topic": "Peneraan Cap Izin Tinggal - No More Passport Stamps",
                "effective_date": "2024-10-07",
                "issuing_authority": "Direktur Jenderal Imigrasi",
                "keywords": [
                    "cap",
                    "stamp",
                    "paspor",
                    "passport",
                    "molina",
                    "evisa",
                    "online",
                    "paperless",
                    "SIMKIM",
                ],
            }
        )
    elif "imi-417" in filename_lower or "417" in filename_lower:
        metadata.update(
            {
                "regulation_number": "IMI-417.GR.01.01",
                "regulation_year": "2025",
                "topic": "Penyesuaian Pelayanan - Mandatory Photo & Interview",
                "effective_date": "2025-05-29",
                "issuing_authority": "Plt. Direktur Jenderal Imigrasi",
                "keywords": [
                    "foto",
                    "wawancara",
                    "photo",
                    "interview",
                    "kantor imigrasi",
                    "walk-in",
                    "lanjut usia",
                    "elderly",
                    "disabilitas",
                    "ibu hamil",
                    "pregnant",
                ],
            }
        )

    # Extract title from content
    for line in content.split("\n")[:5]:
        if line.startswith("TITLE:"):
            metadata["title"] = line.replace("TITLE:", "").strip()
            break

    return metadata


def upsert_points(points: list[dict]):
    """Upsert points to Qdrant via REST API"""
    batch_size = 20
    total_batches = (len(points) + batch_size - 1) // batch_size

    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        batch_num = i // batch_size + 1

        payload = {"points": batch}

        try:
            result = qdrant_request(
                "PUT", f"/collections/{COLLECTION_NAME}/points", payload
            )
            logger.info(
                f"  Batch {batch_num}/{total_batches}: {len(batch)} points upserted"
            )
        except Exception as e:
            logger.error(f"  Batch {batch_num} failed: {e}")


def main():
    """Main ingestion function"""
    logger.info("=" * 60)
    logger.info("SURAT EDARAN INGESTION TO VISA_ORACLE")
    logger.info("=" * 60)

    logger.info(f"Qdrant URL: {QDRANT_URL}")
    logger.info(f"Collection: {COLLECTION_NAME}")

    # Initialize embeddings - FORCE OpenAI for consistency
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set! Required for embeddings.")
        return

    embedder = EmbeddingsGenerator(api_key=openai_key, provider="openai")
    vector_size = embedder.dimensions  # Should be 1536

    logger.info(f"Embedding dimensions: {vector_size}")

    # Verify collection exists
    try:
        info = qdrant_request("GET", f"/collections/{COLLECTION_NAME}")
        points_count = info.get("result", {}).get("points_count", 0)
        logger.info(f"Collection {COLLECTION_NAME} exists with {points_count} points")
    except Exception as e:
        logger.error(f"Collection {COLLECTION_NAME} not found: {e}")
        logger.error(
            "Please create the collection first or use a different collection name"
        )
        return

    # Process each file
    total_chunks = 0
    points = []

    for file_path in SURAT_EDARAN_FILES:
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            continue

        logger.info(f"Processing: {file_path.name}")

        try:
            # Read file
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if len(content) < 100:
                logger.warning(f"  Skipping (too short): {file_path.name}")
                continue

            # Extract metadata
            metadata = extract_metadata(file_path, content)

            # Chunk the document
            chunks = chunk_document(content)

            logger.info(f"  Created {len(chunks)} chunks")

            # Generate embeddings and create points
            for i, chunk_text in enumerate(chunks):
                try:
                    vector = embedder.generate_single_embedding(chunk_text[:8000])

                    point = {
                        "id": str(uuid.uuid4()),
                        "vector": vector,
                        "payload": {
                            "text": chunk_text[:10000],
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            **metadata,
                        },
                    }
                    points.append(point)
                    total_chunks += 1

                except Exception as e:
                    logger.error(f"  Error embedding chunk {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            continue

    # Upsert all points
    if points:
        logger.info(f"Upserting {len(points)} points to Qdrant...")
        upsert_points(points)

    # Verify final count
    try:
        info = qdrant_request("GET", f"/collections/{COLLECTION_NAME}")
        points_count = info.get("result", {}).get("points_count", 0)
        logger.info(f"Collection {COLLECTION_NAME} now has {points_count} points")
    except Exception as e:
        logger.warning(f"Could not verify collection: {e}")

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info(f"Total files processed: {len(SURAT_EDARAN_FILES)}")
    logger.info(f"Total chunks created: {total_chunks}")
    logger.info(f"Collection: {COLLECTION_NAME}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
