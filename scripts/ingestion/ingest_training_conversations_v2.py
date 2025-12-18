#!/usr/bin/env python3
"""
Training Conversations Ingestion v2 - Full Architecture Compliance
------------------------------------------------------------------
Features:
- LegalChunker semantic chunking with context injection
- Parent document registration via API (PostgreSQL)
- OpenAI text-embedding-3-small embeddings
- Qdrant vector storage

Architecture compliance:
- [x] Context Injection: [CONTEXT: TRAINING - CATEGORY X - TOPIC Y...]
- [x] Embeddings: text-embedding-3-small (1536 dims)
- [x] Vector DB: Qdrant
- [x] Parent Docs: PostgreSQL via API endpoint
- [x] Semantic Chunking: SemanticSplitter from LegalChunker
"""

import hashlib
import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent / "apps" / "backend-rag" / "backend"
sys.path.insert(0, str(backend_dir))

# Load .env from backend-rag
load_dotenv(backend_dir.parent / ".env")

from core.embeddings import EmbeddingsGenerator
from core.legal.chunker import SemanticSplitter

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
BACKEND_URL = os.getenv("BACKEND_URL", "https://nuzantara-rag.fly.dev")
API_KEY = os.getenv("API_KEYS", "").split(",")[0] if os.getenv("API_KEYS") else ""
COLLECTION_NAME = "training_conversations"

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directories to scan for conversations
CONV_DIRS = [
    Path("/Users/antonellosiano/Desktop/nuzantara/conv"),
    Path("/Users/antonellosiano/Desktop/nuzantara/conv/generated"),
    Path("/Users/antonellosiano/Desktop/nuzantara/apps/backend-rag/training-data"),
    Path("/Users/antonellosiano/Desktop/nuzantara/apps/backend-rag/training-data/visa"),
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


def register_parent_doc_via_api(
    parent_id: str,
    document_id: str,
    title: str,
    full_text: str,
    metadata: dict,
    chunk_count: int,
) -> bool:
    """Register parent document via backend API"""
    url = f"{BACKEND_URL}/api/legal/parent-documents"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    }

    payload = {
        "id": parent_id,
        "document_id": document_id,
        "doc_type": "training_conversation",
        "title": title,
        "full_text": full_text[:50000],  # Limit size
        "char_count": len(full_text),
        "chunk_count": chunk_count,
        "metadata": metadata,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in [200, 201]:
            logger.info(f"  ✅ Registered parent doc: {parent_id}")
            return True
        else:
            logger.warning(f"  ⚠️ Failed to register parent doc: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        logger.warning(f"  ⚠️ Could not register parent doc (API unavailable): {e}")
        return False


def extract_metadata_from_filename(filename: str) -> dict:
    """Extract topic category from filename"""
    filename_lower = filename.lower()

    # Visa types
    if any(x in filename_lower for x in ["e33g", "digital_nomad", "digital-nomad"]):
        return {"category": "visa", "visa_type": "E33G", "topic": "Digital Nomad KITAS"}
    elif any(x in filename_lower for x in ["e28a", "investor"]):
        return {"category": "visa", "visa_type": "E28A", "topic": "Investor KITAS"}
    elif any(x in filename_lower for x in ["e31a", "spouse", "mixed_marriage", "mixed-marriage"]):
        return {"category": "visa", "visa_type": "E31A", "topic": "Spouse KITAS / Mixed Marriage"}
    elif any(x in filename_lower for x in ["e26", "spouse_kitas"]):
        return {"category": "visa", "visa_type": "E26", "topic": "Spouse KITAS"}
    elif "d1" in filename_lower or "tourism" in filename_lower:
        return {"category": "visa", "visa_type": "D1", "topic": "Tourism Multiple Entry"}
    elif "d2" in filename_lower:
        return {"category": "visa", "visa_type": "D2", "topic": "Business Multiple Entry"}
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
        return {"category": "visa", "visa_type": "Freelance KITAS", "topic": "Freelance KITAS"}
    elif "working" in filename_lower and "kitas" in filename_lower:
        return {"category": "visa", "visa_type": "Working KITAS", "topic": "Working KITAS"}
    elif "dependent" in filename_lower:
        return {"category": "visa", "visa_type": "Dependent KITAS", "topic": "Dependent KITAS"}
    elif "kitap" in filename_lower:
        return {"category": "visa", "visa_type": "KITAP", "topic": "Permanent Stay Permit"}
    # Business types
    elif "kbli" in filename_lower:
        if "restaurant" in filename_lower:
            return {"category": "business", "topic": "KBLI Restaurant"}
        elif "villa" in filename_lower:
            return {"category": "business", "topic": "KBLI Villa"}
        elif "it" in filename_lower or "consulting" in filename_lower:
            return {"category": "business", "topic": "KBLI IT Consulting"}
        return {"category": "business", "topic": "KBLI Codes"}
    elif "pt_pma" in filename_lower or "pt-pma" in filename_lower or "pma" in filename_lower:
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
    if any(x in text_lower for x in ["nggih", "panjenengan", "kuwi", "kanggo", "sak", "nek ", "wae", "piro"]):
        return "jv"  # Javanese
    # Balinese markers
    elif any(x in text_lower for x in ["titiang", "punapi", "dados", "nggih", "punika", "ring "]):
        return "ban"  # Balinese
    # Indonesian markers
    elif any(x in text_lower for x in ["apa", "bisa", "untuk", "yang", "ini", "dengan", "tidak"]):
        return "id"  # Indonesian
    # English
    elif any(x in text_lower for x in ["what", "how", "can", "the", "is", "for", "this"]):
        return "en"  # English

    return "id"  # Default to Indonesian


def build_context_injection(metadata: dict, lang: str = "id") -> str:
    """
    Build context injection string following system standard.
    Format: [CONTEXT: TRAINING - CATEGORY X - VISA Y - TOPIC Z - LANG W]
    """
    category = metadata.get("category", "general").upper()
    topic = metadata.get("topic", "Unknown")
    visa_type = metadata.get("visa_type", "")

    parts = ["TRAINING", f"CATEGORY {category}"]
    if visa_type:
        parts.append(f"VISA {visa_type}")
    parts.append(f"TOPIC {topic}")
    parts.append(f"LANG {lang.upper()}")

    return f"[CONTEXT: {' - '.join(parts)}]"


def generate_parent_id(file_path: str) -> str:
    """Generate deterministic parent ID from file path"""
    return hashlib.md5(file_path.encode()).hexdigest()[:16]


def chunk_conversation_semantic(
    text: str, metadata: dict, embedder: EmbeddingsGenerator, max_tokens: int = 1000
) -> list[dict]:
    """
    Chunk conversation using semantic splitting with context injection.
    Uses SemanticSplitter for intelligent grouping of related content.
    """
    chunks = []

    # Initialize semantic splitter
    semantic_splitter = SemanticSplitter(embedder, similarity_threshold=0.7)

    # Split by conversation sections (language versions)
    sections = re.split(r"(?=##\s+|---\s*\n)", text)

    for section in sections:
        if not section.strip() or len(section.strip()) < 100:
            continue

        # Detect language of this section
        lang = detect_language(section)

        # Build context injection for this section
        context = build_context_injection(metadata, lang)

        # Use semantic splitting for intelligent chunking
        semantic_chunks = semantic_splitter.split_text(section, max_tokens)

        for chunk_content in semantic_chunks:
            if len(chunk_content) < 50:  # Skip tiny chunks
                continue

            # Inject context at the beginning of each chunk
            chunk_with_context = f"{context}\n\n{chunk_content}"

            chunk_meta = {
                **metadata,
                "language": lang,
                "chunk_type": "semantic",
                "source": "training_conversation",
                "has_context": True,
            }

            chunks.append({"text": chunk_with_context, "metadata": chunk_meta})

    # Fallback: if semantic splitting failed, use simple Q&A splitting with context
    if not chunks:
        logger.warning("Semantic chunking failed, falling back to Q&A splitting")
        chunks = chunk_conversation_by_qa_with_context(text, metadata)

    return chunks


def chunk_conversation_by_qa_with_context(text: str, metadata: dict) -> list[dict]:
    """
    Fallback: Chunk conversation into Q&A pairs with context injection.
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

        # Build context injection
        context = build_context_injection(metadata, lang)

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
                    # Inject context at the beginning
                    chunk_with_context = f"{context}\n\n{chunk_content}"

                    chunk_meta = {
                        **metadata,
                        "language": lang,
                        "chunk_type": "qa_exchange",
                        "source": "training_conversation",
                        "has_context": True,
                    }

                    chunks.append({"text": chunk_with_context, "metadata": chunk_meta})

                current_chunk_text = []
                exchange_count = 0

    # If no Q&A pattern found, chunk by paragraphs
    if not chunks:
        lang = detect_language(text)
        context = build_context_injection(metadata, lang)
        paragraphs = text.split("\n\n")
        chunk_size = 3  # paragraphs per chunk

        for i in range(0, len(paragraphs), chunk_size):
            chunk_text = "\n\n".join(paragraphs[i : i + chunk_size])
            if len(chunk_text) > 100:
                chunk_with_context = f"{context}\n\n{chunk_text}"
                chunks.append({
                    "text": chunk_with_context,
                    "metadata": {
                        **metadata,
                        "language": detect_language(chunk_text),
                        "chunk_type": "paragraph",
                        "source": "training_conversation",
                        "has_context": True,
                    },
                })

    return chunks


def create_collection(vector_size: int):
    """Create or recreate collection via REST"""
    logger.info(f"Creating collection: {COLLECTION_NAME}")

    # Delete if exists
    try:
        qdrant_request("DELETE", f"/collections/{COLLECTION_NAME}")
        logger.info(f"Deleted existing collection: {COLLECTION_NAME}")
    except:
        pass

    # Create new collection
    config = {"vectors": {"size": vector_size, "distance": "Cosine"}}

    result = qdrant_request("PUT", f"/collections/{COLLECTION_NAME}", config)
    logger.info(f"Collection created: {result}")


def upsert_points(points: list[dict]):
    """Upsert points via REST API"""
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
            logger.info(f"  Batch {batch_num}/{total_batches}: {len(batch)} points upserted")
        except Exception as e:
            logger.error(f"  Batch {batch_num} failed: {e}")


def main():
    """Main ingestion function"""
    logger.info("=" * 60)
    logger.info("TRAINING CONVERSATIONS INGESTION v2")
    logger.info("Full Architecture Compliance")
    logger.info("=" * 60)

    logger.info(f"Qdrant URL: {QDRANT_URL}")
    logger.info(f"Backend URL: {BACKEND_URL}")
    logger.info(f"API Key: {'SET' if API_KEY else 'NOT SET'}")

    # Initialize embeddings - FORCE OpenAI for consistency with rest of system
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set! Required for embeddings.")
        return

    embedder = EmbeddingsGenerator(api_key=openai_key, provider="openai")
    vector_size = embedder.dimensions  # Should be 1536

    logger.info(f"Embedding dimensions: {vector_size}")

    # Create collection
    create_collection(vector_size)

    # Collect all .md files
    all_files = []
    for conv_dir in CONV_DIRS:
        if conv_dir.exists():
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
    parent_docs_registered = 0

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

            # Generate parent ID
            parent_id = generate_parent_id(str(file_path))
            metadata["parent_id"] = parent_id

            # Chunk the conversation with semantic splitting + context injection
            chunks = chunk_conversation_semantic(content, metadata, embedder)

            logger.info(f"  Created {len(chunks)} chunks")

            # Register parent document via API
            if register_parent_doc_via_api(
                parent_id=parent_id,
                document_id=f"training_{file_path.stem}",
                title=file_path.name,
                full_text=content,
                metadata=metadata,
                chunk_count=len(chunks),
            ):
                parent_docs_registered += 1

            # Generate embeddings and create points
            for i, chunk in enumerate(chunks):
                try:
                    vector = embedder.generate_single_embedding(chunk["text"][:8000])

                    point = {
                        "id": str(uuid.uuid4()),
                        "vector": vector,
                        "payload": {
                            "text": chunk["text"][:10000],
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            **chunk["metadata"],
                        },
                    }
                    points.append(point)
                    total_chunks += 1

                except Exception as e:
                    logger.error(f"  Error embedding chunk: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            continue

    # Upsert all points
    logger.info(f"Upserting {len(points)} points to Qdrant...")
    upsert_points(points)

    # Verify collection
    try:
        info = qdrant_request("GET", f"/collections/{COLLECTION_NAME}")
        points_count = info.get("result", {}).get("points_count", 0)
        logger.info(f"Collection {COLLECTION_NAME} now has {points_count} points")
    except Exception as e:
        logger.warning(f"Could not verify collection: {e}")

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info(f"Total files processed: {len(all_files)}")
    logger.info(f"Total chunks created: {total_chunks}")
    logger.info(f"Parent docs registered: {parent_docs_registered}")
    logger.info(f"Collection: {COLLECTION_NAME}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
