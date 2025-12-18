#!/usr/bin/env python3
"""
Ingest Training Conversations into Qdrant
------------------------------------------
Scans conv/ folder for .md conversation files and ingests them.
Chunks by Q&A pairs for optimal RAG retrieval.
"""

import asyncio
import logging
import os
import re
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.embeddings import EmbeddingsGenerator
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Try to import settings, fallback to env vars
try:
    from app.core.config import settings

    QDRANT_URL = settings.qdrant_url
except ImportError:
    QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directories to scan for conversations
CONV_DIRS = [
    Path("/Users/antonellosiano/Desktop/nuzantara/conv"),
    Path("/Users/antonellosiano/Desktop/nuzantara/conv/generated"),
]

# Collection name for conversations
COLLECTION_NAME = "training_conversations"


def extract_metadata_from_filename(filename: str) -> dict:
    """Extract topic category from filename"""
    filename_lower = filename.lower()

    # Visa types
    if any(x in filename_lower for x in ["e33g", "digital_nomad", "digital-nomad"]):
        return {"category": "visa", "visa_type": "E33G", "topic": "Digital Nomad KITAS"}
    elif any(x in filename_lower for x in ["e28a", "investor"]):
        return {"category": "visa", "visa_type": "E28A", "topic": "Investor KITAS"}
    elif any(
        x in filename_lower
        for x in ["e31a", "spouse", "mixed_marriage", "mixed-marriage"]
    ):
        return {
            "category": "visa",
            "visa_type": "E31A",
            "topic": "Spouse KITAS / Mixed Marriage",
        }
    elif any(x in filename_lower for x in ["e26", "spouse_kitas"]):
        return {"category": "visa", "visa_type": "E26", "topic": "Spouse KITAS"}
    elif "d1" in filename_lower or "tourism" in filename_lower:
        return {
            "category": "visa",
            "visa_type": "D1",
            "topic": "Tourism Multiple Entry",
        }
    elif "d2" in filename_lower:
        return {
            "category": "visa",
            "visa_type": "D2",
            "topic": "Business Multiple Entry",
        }
    elif "c1" in filename_lower:
        return {"category": "visa", "visa_type": "C1", "topic": "Tourism Single Entry"}
    elif "c2" in filename_lower:
        return {"category": "visa", "visa_type": "C2", "topic": "Business Visit"}
    elif "c7" in filename_lower:
        return {"category": "visa", "visa_type": "C7", "topic": "Performing Visa"}
    elif "c10" in filename_lower:
        return {"category": "visa", "visa_type": "C10", "topic": "Event Participant"}
    elif "c11" in filename_lower:
        return {"category": "visa", "visa_type": "C11", "topic": "Exhibitor Visa"}
    elif "b1" in filename_lower:
        return {"category": "visa", "visa_type": "B1", "topic": "Business Visit"}
    elif "golden_visa" in filename_lower or "golden-visa" in filename_lower:
        return {"category": "visa", "visa_type": "Golden Visa", "topic": "Golden Visa"}
    elif "freelance" in filename_lower:
        return {
            "category": "visa",
            "visa_type": "Freelance KITAS",
            "topic": "Freelance KITAS",
        }
    elif "working" in filename_lower and "kitas" in filename_lower:
        return {
            "category": "visa",
            "visa_type": "Working KITAS",
            "topic": "Working KITAS",
        }
    elif "dependent" in filename_lower:
        return {
            "category": "visa",
            "visa_type": "Dependent KITAS",
            "topic": "Dependent KITAS",
        }
    elif "kitap" in filename_lower:
        return {
            "category": "visa",
            "visa_type": "KITAP",
            "topic": "Permanent Stay Permit",
        }

    # Business types
    elif "kbli" in filename_lower:
        if "restaurant" in filename_lower:
            return {"category": "business", "topic": "KBLI Restaurant"}
        elif "villa" in filename_lower:
            return {"category": "business", "topic": "KBLI Villa"}
        elif "it" in filename_lower or "consulting" in filename_lower:
            return {"category": "business", "topic": "KBLI IT Consulting"}
        return {"category": "business", "topic": "KBLI Codes"}
    elif (
        "pt_pma" in filename_lower
        or "pt-pma" in filename_lower
        or "pma" in filename_lower
    ):
        return {"category": "business", "topic": "PT PMA Setup"}
    elif "pt_lokal" in filename_lower or "lokal_vs_pma" in filename_lower:
        return {"category": "business", "topic": "PT Lokal vs PT PMA"}
    elif "oss" in filename_lower or "nib" in filename_lower:
        return {"category": "business", "topic": "OSS NIB Registration"}

    # Tax types
    elif "pph" in filename_lower or "ppn" in filename_lower:
        return {"category": "tax", "topic": "PPh/PPN Tax"}
    elif "corporate" in filename_lower and "tax" in filename_lower:
        return {"category": "tax", "topic": "Corporate Income Tax"}
    elif "expat" in filename_lower or "expatriate" in filename_lower:
        return {"category": "tax", "topic": "Expatriate Tax Obligations"}
    elif "transfer_pricing" in filename_lower or "transfer-pricing" in filename_lower:
        return {"category": "tax", "topic": "Transfer Pricing"}

    # Property
    elif "property" in filename_lower or "buying" in filename_lower:
        return {"category": "realestate", "topic": "Property Purchase"}

    # Default
    return {"category": "general", "topic": "General Consultation"}


def detect_language(text: str) -> str:
    """Simple language detection based on keywords"""
    text_lower = text[:1000].lower()

    # Javanese markers
    if any(
        x in text_lower
        for x in [
            "nggih",
            "panjenengan",
            "kuwi",
            "kanggo",
            "sak",
            "nek ",
            "wae",
            "piro",
        ]
    ):
        return "jv"  # Javanese
    # Balinese markers
    elif any(
        x in text_lower
        for x in ["titiang", "punapi", "dados", "nggih", "punika", "ring "]
    ):
        return "ban"  # Balinese
    # Indonesian markers (more common)
    elif any(
        x in text_lower
        for x in ["apa", "bisa", "untuk", "yang", "ini", "dengan", "tidak"]
    ):
        return "id"  # Indonesian
    # English
    elif any(
        x in text_lower for x in ["what", "how", "can", "the", "is", "for", "this"]
    ):
        return "en"  # English

    return "id"  # Default to Indonesian


def chunk_conversation_by_qa(text: str, metadata: dict) -> list[dict]:
    """
    Chunk conversation into Q&A pairs for optimal retrieval.
    Groups 2-3 exchanges together for context.
    """
    chunks = []

    # Split by conversation sections (language versions)
    sections = re.split(r"(?=##\s+|---\s*\n)", text)

    for section in sections:
        if not section.strip():
            continue

        # Detect language of this section
        lang = detect_language(section)

        # Find Q&A pairs using various patterns
        # Pattern: **N — Client:** or **Client:** followed by **Consultant:**
        qa_pattern = r"(?:\*\*\d+\s*[—-]\s*)?(?:\*\*)?(?:Client|Customer|Klien)(?:\*\*)?[:\s]*\n?(.*?)(?=(?:\*\*\d+\s*[—-]\s*)?(?:\*\*)?(?:Consultant|Konsultan|You|Anda)(?:\*\*)?[:\s])"

        # Simpler approach: split by Client/Consultant markers
        exchanges = re.split(
            r"\*\*(?:\d+\s*[—-]\s*)?(?:Client|Customer|Klien)\*\*",
            section,
            flags=re.IGNORECASE,
        )

        current_chunk_text = []
        exchange_count = 0

        for i, exchange in enumerate(exchanges):
            if not exchange.strip():
                continue

            # Clean up the exchange
            exchange = exchange.strip()

            # Add to current chunk
            current_chunk_text.append(exchange)
            exchange_count += 1

            # Create chunk every 2-3 exchanges or at section end
            if exchange_count >= 2 or i == len(exchanges) - 1:
                chunk_content = "\n\n".join(current_chunk_text)

                if len(chunk_content) > 100:  # Min chunk size
                    chunk_meta = {
                        **metadata,
                        "language": lang,
                        "chunk_type": "qa_exchange",
                        "source": "training_conversation",
                    }

                    chunks.append({"text": chunk_content, "metadata": chunk_meta})

                current_chunk_text = []
                exchange_count = 0

    # If no Q&A pattern found, chunk by paragraphs
    if not chunks:
        paragraphs = text.split("\n\n")
        chunk_size = 3  # paragraphs per chunk

        for i in range(0, len(paragraphs), chunk_size):
            chunk_text = "\n\n".join(paragraphs[i : i + chunk_size])
            if len(chunk_text) > 100:
                chunks.append(
                    {
                        "text": chunk_text,
                        "metadata": {
                            **metadata,
                            "language": detect_language(chunk_text),
                            "chunk_type": "paragraph",
                            "source": "training_conversation",
                        },
                    }
                )

    return chunks


async def ingest_conversations():
    """Main ingestion function"""
    logger.info("=" * 60)
    logger.info("TRAINING CONVERSATIONS INGESTION")
    logger.info("=" * 60)

    # Initialize Qdrant
    qdrant_url = os.getenv("QDRANT_URL", QDRANT_URL)
    qdrant_key = os.getenv("QDRANT_API_KEY", "")

    logger.info(f"Qdrant URL: {qdrant_url}")

    client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_key if qdrant_key else None,
        timeout=60,  # Increased timeout for Fly.io
    )

    # Initialize embeddings - FORCE OpenAI for consistency with rest of system
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set! Required for embeddings.")
        return

    embedder = EmbeddingsGenerator(api_key=openai_key, provider="openai")
    vector_size = embedder.dimensions  # Should be 1536

    logger.info(f"Embedding dimensions: {vector_size}")

    # Create/recreate collection
    logger.info(f"Creating collection: {COLLECTION_NAME}")
    try:
        client.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE
            ),
        )
    except Exception as e:
        logger.warning(f"Collection creation warning: {e}")

    # Collect all .md files
    all_files = []
    for conv_dir in CONV_DIRS:
        if conv_dir.exists():
            # Get files in directory (not recursive for root, recursive for generated)
            if "generated" in str(conv_dir):
                files = list(conv_dir.glob("*.md"))
            else:
                files = [f for f in conv_dir.glob("*.md") if f.is_file()]
            all_files.extend(files)
            logger.info(f"Found {len(files)} files in {conv_dir}")

    logger.info(f"Total files to process: {len(all_files)}")

    # Process each file
    total_chunks = 0
    points = []

    for file_path in all_files:
        logger.info(f"Processing: {file_path.name}")

        try:
            # Read file
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if len(content) < 100:
                logger.warning(f"  Skipping (too short): {file_path.name}")
                continue

            # Extract metadata from filename
            metadata = extract_metadata_from_filename(file_path.name)
            metadata["file_name"] = file_path.name
            metadata["file_path"] = str(file_path)

            # Chunk the conversation
            chunks = chunk_conversation_by_qa(content, metadata)

            logger.info(f"  Created {len(chunks)} chunks")

            # Generate embeddings and create points
            for chunk in chunks:
                try:
                    vector = embedder.generate_single_embedding(
                        chunk["text"][:8000]
                    )  # Limit text length

                    point = models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={
                            "text": chunk["text"][
                                :10000
                            ],  # Store truncated for payload
                            **chunk["metadata"],
                        },
                    )
                    points.append(point)
                    total_chunks += 1

                except Exception as e:
                    logger.error(f"  Error embedding chunk: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            continue

    # Batch upsert with retry
    logger.info(f"Upserting {len(points)} points to Qdrant...")

    batch_size = 20  # Smaller batches for better reliability
    max_retries = 3

    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        for attempt in range(max_retries):
            try:
                client.upsert(collection_name=COLLECTION_NAME, points=batch)
                logger.info(
                    f"  Upserted batch {i // batch_size + 1} ({len(batch)} points)"
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"  Retry {attempt + 1}/{max_retries} for batch {i // batch_size + 1}: {e}"
                    )
                    import time

                    time.sleep(2)  # Wait before retry
                else:
                    logger.error(
                        f"  Failed batch {i // batch_size + 1} after {max_retries} attempts: {e}"
                    )

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info(f"Total files processed: {len(all_files)}")
    logger.info(f"Total chunks created: {total_chunks}")
    logger.info(f"Collection: {COLLECTION_NAME}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(ingest_conversations())
