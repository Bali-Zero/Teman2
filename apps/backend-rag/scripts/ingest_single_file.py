#!/usr/bin/env python3
"""
Ingest a single training data file into training_conversations_hybrid collection.
Bypasses broken sentence_transformers by using OpenAI directly.

Usage:
    cd apps/backend-rag && python scripts/ingest_single_file.py training-data/business/business_033_kbli_foreign_ownership.md
"""

import hashlib
import logging
import os
import sys
import time
from pathlib import Path

import requests

# Load .env
script_dir = Path(__file__).parent
backend_rag_root = script_dir.parent
sys.path.insert(0, str(backend_rag_root / "backend"))

from dotenv import load_dotenv

load_dotenv(backend_rag_root / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

COLLECTION_NAME = "training_conversations_hybrid"
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def get_openai_embedding(text: str) -> list[float]:
    """Get embedding from OpenAI text-embedding-3-small (1536 dims)."""
    import openai

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
    )
    return response.data[0].embedding


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Simple text chunker using paragraph boundaries."""
    separators = ["\n\n\n", "\n\n", "\n---\n", "\n"]
    chunks = []

    def _split(text, seps):
        if not seps or len(text) <= chunk_size:
            return [text] if text.strip() else []

        sep = seps[0]
        parts = text.split(sep)
        current = ""
        result = []

        for part in parts:
            if len(current) + len(part) + len(sep) <= chunk_size:
                current = current + sep + part if current else part
            else:
                if current.strip():
                    result.append(current.strip())
                if len(part) > chunk_size:
                    result.extend(_split(part, seps[1:]))
                else:
                    current = part
        if current.strip():
            result.append(current.strip())
        return result

    raw_chunks = _split(text, separators)

    # Add overlap
    for i, chunk in enumerate(raw_chunks):
        if i > 0 and overlap > 0:
            prev_tail = raw_chunks[i - 1][-overlap:]
            chunk = prev_tail + "\n" + chunk
        chunks.append(chunk)

    return chunks


def generate_bm25_sparse(text: str) -> dict:
    """Generate BM25 sparse vector using hash-based token IDs."""
    from core.bm25_vectorizer import BM25Vectorizer

    bm25 = BM25Vectorizer()
    return bm25.generate_sparse_vector(text)


def upsert_point(point_id, dense_vector, sparse_indices, sparse_values, payload) -> bool:
    """Upsert a single point to Qdrant."""
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
            logger.warning(f"  Qdrant returned {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
                logger.warning(f"  Retry {attempt + 1}/3: {e}")
            else:
                logger.error(f"  Failed after 3 attempts: {e}")
                return False
    return False


def ingest_file(file_path: str):
    """Ingest a single file into Qdrant."""
    full_path = backend_rag_root / file_path

    if not full_path.exists():
        logger.error(f"File not found: {full_path}")
        return

    logger.info(f"Processing: {file_path}")
    content = full_path.read_text(encoding="utf-8")

    # Extract metadata
    filename = full_path.stem
    parts = filename.split("_")
    category = parts[0] if parts else "unknown"

    title = filename
    for line in content.split("\n")[:10]:
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # Chunk
    chunks = chunk_text(content)
    logger.info(f"  Created {len(chunks)} chunks")

    total_ok = 0
    for idx, chunk_text_str in enumerate(chunks):
        # Dense embedding (OpenAI)
        dense = get_openai_embedding(chunk_text_str)

        # Sparse BM25
        sparse = generate_bm25_sparse(chunk_text_str)

        # Unique ID
        point_id_hex = hashlib.md5(f"{file_path}_{idx}".encode()).hexdigest()
        point_id_int = int(point_id_hex[:16], 16)

        payload = {
            "source": file_path,
            "filename": filename,
            "title": title,
            "category": category,
            "chunk_index": idx,
            "total_chunks": len(chunks),
            "text": chunk_text_str,
            "data_version": "bali_zero_2025_corrected",
        }

        ok = upsert_point(point_id_int, dense, sparse["indices"], sparse["values"], payload)
        if ok:
            total_ok += 1
            if (idx + 1) % 5 == 0:
                logger.info(f"  Progress: {idx + 1}/{len(chunks)} chunks")
        else:
            logger.error(f"  Failed chunk {idx}")

        time.sleep(0.5)  # Rate limit

    logger.info(f"DONE: {total_ok}/{len(chunks)} chunks upserted for {file_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_single_file.py <relative-file-path>")
        print(
            "Example: python scripts/ingest_single_file.py training-data/business/business_033_kbli_foreign_ownership.md"
        )
        sys.exit(1)

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set in .env")
        sys.exit(1)
    if not QDRANT_API_KEY:
        logger.error("QDRANT_API_KEY not set in .env")
        sys.exit(1)

    ingest_file(sys.argv[1])
