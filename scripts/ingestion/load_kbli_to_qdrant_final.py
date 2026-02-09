#!/usr/bin/env python3
"""
KBLI 2025 Final Ingestion Script
-------------------------------------------------------------
Ingests KBLI 2025 codes into Qdrant from the CLEAN final dataset.
Each code becomes one document with rich metadata and context injection.

Architecture compliance:
- [x] Context Injection: [CONTEXT: KBLI 2025 - PP 28/2025 - SEKTOR X...]
- [x] Embeddings: text-embedding-3-small (1536 dims)
- [x] Vector DB: Qdrant
- [x] Source: source_documents/KBLI_2025_FINAL_CLEAN.json
"""

import argparse
import hashlib
import json
import os
import sys
import logging
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Add backend path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag", ".env"))

import openai

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

COLLECTION_NAME = "kbli_2025_final"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Source file path
KBLI_JSON_PATH = "source_documents/KBLI_2025_FINAL_CLEAN.json"

def get_embedding(text: str) -> list[float]:
    """Generate embedding using OpenAI."""
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not found!")
        raise ValueError("OPENAI_API_KEY not found")
        
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text[:8000],  # Limit input length
    )
    return response.data[0].embedding

def format_kbli_content(code_data: dict) -> str:
    """Format KBLI code info into searchable text content."""
    code = code_data.get("kode_kbli_2025", "")
    title = code_data.get("judul", "")
    desc = code_data.get("uraian", "")
    
    # Context Injection
    context = f"[CONTEXT: KBLI 2025 - KODE {code}]"
    
    lines = [context, "", f"# KBLI {code} - {title}", "", desc, ""]
    
    # Add scales if available
    scales = code_data.get("per_skala", [])
    if scales:
        lines.append("**Skala Usaha & Risiko:**")
        for s in scales:
            lines.append(f"- {s.get('skala', 'Unknown')}: {s.get('risiko', 'Unknown')}")
            
    return "\n".join(lines)

def qdrant_request(method: str, endpoint: str, json_data: dict = None) -> dict:
    """Make authenticated request to Qdrant REST API."""
    url = f"{QDRANT_URL}{endpoint}"
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    if method == "GET":
        r = requests.get(url, headers=headers, timeout=60)
    elif method == "PUT":
        r = requests.put(url, headers=headers, json=json_data, timeout=60)
    elif method == "POST":
        r = requests.post(url, headers=headers, json=json_data, timeout=60)
    elif method == "DELETE":
        r = requests.delete(url, headers=headers, timeout=60)
    else:
        raise ValueError(f"Unknown method: {method}")

    r.raise_for_status()
    return r.json()

def create_collection(recreate: bool = False):
    """Create or recreate the KBLI collection."""
    try:
        result = qdrant_request("GET", "/collections")
        collections = [c["name"] for c in result.get("result", {}).get("collections", [])]

        if COLLECTION_NAME in collections:
            if recreate:
                logger.info(f"Deleting existing collection: {COLLECTION_NAME}")
                qdrant_request("DELETE", f"/collections/{COLLECTION_NAME}")
            else:
                logger.info(f"Collection {COLLECTION_NAME} already exists.")
                return True

        logger.info(f"Creating collection: {COLLECTION_NAME}")
        qdrant_request(
            "PUT",
            f"/collections/{COLLECTION_NAME}",
            {"vectors": {"size": EMBEDDING_DIM, "distance": "Cosine"}},
        )
        return True
    except Exception as e:
        logger.error(f"Failed to create/check collection: {e}")
        return False

def ingest_kbli(limit: Optional[int] = None, recreate: bool = False):
    """Main ingestion function."""
    
    if not os.path.exists(KBLI_JSON_PATH):
        logger.error(f"Source file not found: {KBLI_JSON_PATH}")
        return

    logger.info(f"Loading KBLI data from: {KBLI_JSON_PATH}")
    with open(KBLI_JSON_PATH, "r") as f:
        data = json.load(f)

    kbli_list = data.get("data", [])
    logger.info(f"Total codes found: {len(kbli_list)}")

    if limit:
        kbli_list = kbli_list[:limit]
        logger.info(f"Limited to: {len(kbli_list)} codes")

    # Create collection
    if not create_collection(recreate):
        return

    points = []
    errors = []

    logger.info("Generating embeddings and preparing points...")
    
    for i, item in enumerate(kbli_list):
        try:
            content = format_kbli_content(item)
            code = item.get("kode_kbli_2025")
            
            # Simple metadata
            payload = {
                "content": content,
                "kode_kbli": code,
                "judul": item.get("judul"),
                "source": "KBLI 2025 Final Clean",
                "document_type": "kbli_code"
            }
            
            # Generate embedding
            embedding = get_embedding(content)

            # Create point
            # Use hash of code as ID for consistency
            point_id = int(hashlib.md5(code.encode()).hexdigest(), 16) % (2**63 - 1)
            
            points.append({
                "id": point_id,
                "vector": embedding,
                "payload": payload
            })

            if (i + 1) % 50 == 0:
                logger.info(f"  Prepared: {i + 1}/{len(kbli_list)}")

        except Exception as e:
            code = item.get("kode_kbli_2025", "unknown")
            logger.error(f"Error processing {code}: {e}")
            errors.append((code, str(e)))

    # Upload in batches
    logger.info(f"Uploading {len(points)} points to Qdrant...")
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        try:
            qdrant_request(
                "PUT", f"/collections/{COLLECTION_NAME}/points", {"points": batch}
            )
            logger.info(f"  Uploaded: {min(i + batch_size, len(points))}/{len(points)}")
        except Exception as e:
            logger.error(f"  Upload error at batch {i}: {e}")
            errors.append((f"batch_{i}", str(e)))

    logger.info("INGESTION COMPLETE")
    logger.info(f"Errors: {len(errors)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest KBLI 2025 Final")
    parser.add_argument("--limit", type=int, help="Limit number of codes")
    parser.add_argument("--recreate", action="store_true", help="Recreate collection")
    args = parser.parse_args()

    ingest_kbli(limit=args.limit, recreate=args.recreate)
