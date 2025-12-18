"""
ZANTARA RAG - Ricerca Folder Ingestion Script

Ingest curated knowledge from ~/Desktop/ricerca into specific Qdrant collections.
Based on the KB Index plan - skips duplicate folders and maps to correct collections.

Usage:
    python scripts/ingest_ricerca.py --dry-run     # Preview only
    python scripts/ingest_ricerca.py               # Full ingestion
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import requests
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load env from parent directory
load_dotenv(Path(__file__).parent.parent / ".env")

# Add paths for imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "backend"))

# Import SemanticChunker for quality chunks like originals
from backend.services.rag.chunking import SemanticChunker

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True
)
logger = logging.getLogger(__name__)

# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# Configuration
DB_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
if not QDRANT_API_KEY:
    logger.warning("⚠️ QDRANT_API_KEY not found in env. Qdrant operations may fail.")

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- FOLDER TO COLLECTION MAPPING ---
FOLDER_TO_COLLECTION = {
    "TAX GENIUS": "tax_genius",
    "VISA ORACLE": "visa_oracle",
    "Eye KBLI2": "kbli_unified",
    "LEGAL ARCHITECT": "legal_unified",
    "kbli": "kbli_unified",  # Case studies
}

# Folders to skip (duplicates or obsolete)
SKIP_FOLDERS = [
    "tax",  # Duplicate of TAX GENIUS
    "visa",  # Duplicate of VISA ORACLE
    "legal",  # Duplicate of LEGAL ARCHITECT
    "Eye KBLI",  # Obsolete (< Eye KBLI2)
    "Eye KBLI1",  # Obsolete (< Eye KBLI2)
    "tools",  # Scripts, not knowledge
    "templates",  # Consider separately
    "templates_id",  # Consider separately
    "pricing",  # Goes to bali_zero_pricing (separate handling)
    "KBLI_RAG_UPLOAD",  # Pre-chunked, needs special handling
]

# File extensions to process
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".json", ".txt", ".jsonl"}

# Maximum chunks per file (avoid over-chunking correspondence tables)
MAX_CHUNKS_PER_FILE = 300

# Files containing pricing data (special routing)
PRICING_FILE_PATTERNS = ["pricelist", "pricing", "PRICING"]

# Initialize SemanticChunker (same config as ingest_intelligent.py)
logger.info(
    "🧠 Initializing SemanticChunker (paraphrase-multilingual-MiniLM-L12-v2)..."
)
chunker = SemanticChunker(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    min_chunk_size=200,
    max_chunk_size=1500,
    similarity_threshold=0.75,
)
logger.info("✅ SemanticChunker ready")


def chunk_text_semantic(text: str, metadata: dict = None) -> list[str]:
    """
    Semantic chunking using SemanticChunker - same quality as original 16k docs.
    Uses hybrid mode: combines sentence-based + structure-aware splitting.
    Returns list of chunk texts (200-1500 chars each).
    """
    try:
        semantic_chunks = chunker.chunk_document(
            text, method="hybrid", metadata=metadata
        )
        return [c.text for c in semantic_chunks]
    except Exception as e:
        logger.warning(f"Semantic chunking failed: {e}. Fallback to simple chunking.")
        # Fallback to simple overlap
        chunks = []
        chunk_size = 1000
        for i in range(0, len(text), chunk_size - 100):
            chunk = text[i : i + chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        return chunks


def read_file_content(file_path: Path) -> tuple[str, dict]:
    """
    Read file content based on extension.
    Returns (text_content, metadata_dict)
    """
    ext = file_path.suffix.lower()
    metadata = {"file_name": file_path.name, "file_type": ext}

    try:
        if ext == ".pdf":
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text, metadata

        elif ext == ".json":
            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            # If it's a dict, convert to readable text
            if isinstance(data, dict):
                # Extract common fields for metadata
                if "title" in data:
                    metadata["doc_title"] = data["title"]
                if "type" in data:
                    metadata["doc_type"] = data["type"]
                # Convert dict to formatted text
                text = json.dumps(data, indent=2, ensure_ascii=False)
            elif isinstance(data, list):
                text = json.dumps(data, indent=2, ensure_ascii=False)
            else:
                text = str(data)
            return text, metadata

        elif ext == ".jsonl":
            lines = file_path.read_text(encoding="utf-8").strip().split("\n")
            texts = []
            for line in lines:
                try:
                    obj = json.loads(line)
                    texts.append(json.dumps(obj, indent=2, ensure_ascii=False))
                except:
                    texts.append(line)
            return "\n---\n".join(texts), metadata

        else:  # .md, .txt, etc.
            return file_path.read_text(encoding="utf-8"), metadata

    except UnicodeDecodeError:
        return file_path.read_text(encoding="latin-1", errors="replace"), metadata
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return "", metadata


async def ensure_collection_exists(collection_name: str) -> bool:
    """Ensure Qdrant collection exists with correct schema."""
    headers = {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else {}

    try:
        resp = requests.get(
            f"{QDRANT_URL}/collections/{collection_name}", headers=headers, timeout=10
        )
        if resp.status_code == 200:
            return True

        # Create collection
        logger.info(f"🆕 Creating collection: {collection_name}")
        resp = requests.put(
            f"{QDRANT_URL}/collections/{collection_name}",
            headers=headers,
            json={
                "vectors": {
                    "size": 1536,  # OpenAI text-embedding-3-small
                    "distance": "Cosine",
                }
            },
            timeout=30,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Collection check failed: {e}")
        return False


async def ingest_file(
    file_path: Path,
    collection_name: str,
    conn: asyncpg.Connection,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Ingest a single file into the specified Qdrant collection.
    """
    result = {
        "file": file_path.name,
        "collection": collection_name,
        "chunks": 0,
        "status": "pending",
    }

    # Check if already ingested (PostgreSQL deduplication)
    doc_id = file_path.stem[:64]
    exists = await conn.fetchval("SELECT 1 FROM parent_documents WHERE id = $1", doc_id)
    if exists:
        result["status"] = "skipped (already exists)"
        logger.info(f"⏭️  Skipping {file_path.name} (already in DB)")
        return result

    # Read content
    text, file_metadata = read_file_content(file_path)
    if not text or len(text.strip()) < 50:
        result["status"] = "skipped (empty/too short)"
        logger.warning(f"⚠️  Skipping {file_path.name} (empty or too short)")
        return result

    # Check for pricing files - special routing
    file_lower = file_path.name.lower()
    if any(pattern.lower() in file_lower for pattern in PRICING_FILE_PATTERNS):
        collection_name = "bali_zero_pricing"
        logger.info(f"💰 Pricing file detected: routing to {collection_name}")

    # Chunk text using SemanticChunker (same quality as original 16k docs)
    chunks = chunk_text_semantic(text, metadata=file_metadata)

    # Limit chunks to avoid over-indexing large reference files
    if len(chunks) > MAX_CHUNKS_PER_FILE:
        logger.warning(
            f"⚠️  {file_path.name} has {len(chunks)} chunks, limiting to {MAX_CHUNKS_PER_FILE}"
        )
        chunks = chunks[:MAX_CHUNKS_PER_FILE]

    result["chunks"] = len(chunks)
    logger.info(f"📄 {file_path.name} → {len(chunks)} chunks → {collection_name}")

    if dry_run:
        result["status"] = "dry-run (would ingest)"
        return result

    # Ensure collection exists
    if not await ensure_collection_exists(collection_name):
        result["status"] = "error (collection creation failed)"
        return result

    # Generate embeddings and upsert
    points = []
    headers = {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else {}

    for i, chunk in enumerate(chunks):
        try:
            # Generate embedding
            embedding_resp = await openai_client.embeddings.create(
                input=chunk, model="text-embedding-3-small"
            )
            vector = embedding_resp.data[0].embedding

            # Prepare payload
            payload = {
                "text": chunk,
                "parent_id": doc_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source_file": file_path.name,
                "source_folder": file_path.parent.name,
                "book_title": file_metadata.get("doc_title", file_path.stem),
                "tier": "C",  # Default tier for business content
                "min_level": 2,
                "language": "id",  # Indonesian content
                "ingestion_date": "2025-12-09",
                "source": "ricerca",
            }

            points.append(
                {"id": str(uuid.uuid4()), "vector": vector, "payload": payload}
            )

        except Exception as e:
            logger.error(f"Embedding failed for chunk {i} of {file_path.name}: {e}")
            continue

    # Batch upsert to Qdrant
    if points:
        try:
            # Upsert in batches of 100
            batch_size = 100
            for batch_start in range(0, len(points), batch_size):
                batch = points[batch_start : batch_start + batch_size]
                resp = requests.put(
                    f"{QDRANT_URL}/collections/{collection_name}/points",
                    headers=headers,
                    json={"points": batch},
                    timeout=60,
                )
                if resp.status_code != 200:
                    logger.error(f"Qdrant upsert failed: {resp.text}")
                    result["status"] = f"error (qdrant: {resp.status_code})"
                    return result

            logger.info(f"   ✅ Indexed {len(points)} chunks to {collection_name}")

            # Save to PostgreSQL for tracking
            await conn.execute(
                """
                INSERT INTO parent_documents (id, document_id, title, full_text, summary, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET metadata = EXCLUDED.metadata
                """,
                doc_id,
                doc_id,
                file_metadata.get("doc_title", file_path.stem),
                text[:10000],  # First 10k chars
                f"Ingested from ricerca/{file_path.parent.name}",
                json.dumps(
                    {
                        "collection": collection_name,
                        "chunks": len(points),
                        "source": "ricerca",
                        "folder": file_path.parent.name,
                    }
                ),
            )

            result["status"] = "success"

        except Exception as e:
            logger.error(f"Upsert failed for {file_path.name}: {e}")
            result["status"] = f"error ({str(e)[:50]})"
    else:
        result["status"] = "error (no valid embeddings)"

    return result


async def scan_ricerca_folder(ricerca_path: Path) -> dict[str, list[Path]]:
    """
    Scan ricerca folder and group files by target collection.
    """
    files_by_collection: dict[str, list[Path]] = {}
    skipped_folders = []

    for folder in ricerca_path.iterdir():
        if not folder.is_dir():
            continue

        folder_name = folder.name

        # Check if should skip
        if folder_name in SKIP_FOLDERS:
            skipped_folders.append(folder_name)
            continue

        # Get target collection
        collection = FOLDER_TO_COLLECTION.get(folder_name)
        if not collection:
            logger.warning(f"⚠️  Unknown folder: {folder_name} (not in mapping)")
            continue

        # Collect files
        if collection not in files_by_collection:
            files_by_collection[collection] = []

        for f in folder.rglob("*"):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                files_by_collection[collection].append(f)

    logger.info(f"📂 Skipped folders: {skipped_folders}")
    return files_by_collection


async def main(dry_run: bool = False):
    """Main ingestion routine."""
    ricerca_path = Path.home() / "Desktop" / "ricerca"

    if not ricerca_path.exists():
        logger.error(f"❌ Ricerca folder not found: {ricerca_path}")
        return

    logger.info(f"🔍 Scanning: {ricerca_path}")

    # Scan and group files
    files_by_collection = await scan_ricerca_folder(ricerca_path)

    # Summary
    total_files = sum(len(files) for files in files_by_collection.values())
    logger.info("\n📊 SCAN SUMMARY:")
    for collection, files in files_by_collection.items():
        logger.info(f"   {collection}: {len(files)} files")
    logger.info(f"   TOTAL: {total_files} files to process")

    if dry_run:
        logger.info("\n🏃 DRY RUN MODE - No changes will be made")

    # Connect to PostgreSQL
    conn = await asyncpg.connect(DB_URL)

    try:
        results = {"success": 0, "skipped": 0, "errors": 0, "dry_run": 0}

        for collection, files in files_by_collection.items():
            logger.info(f"\n{'=' * 60}")
            logger.info(f"📦 Processing {len(files)} files → {collection}")
            logger.info(f"{'=' * 60}")

            for file_path in files:
                result = await ingest_file(file_path, collection, conn, dry_run)

                if "success" in result["status"]:
                    results["success"] += 1
                elif "skipped" in result["status"]:
                    results["skipped"] += 1
                elif "dry-run" in result["status"]:
                    results["dry_run"] += 1
                else:
                    results["errors"] += 1
                    logger.error(f"   ❌ {result['file']}: {result['status']}")

        # Final summary
        logger.info(f"\n{'=' * 60}")
        logger.info("🏁 INGESTION COMPLETE")
        logger.info(f"{'=' * 60}")
        logger.info(f"   ✅ Success: {results['success']}")
        logger.info(f"   ⏭️  Skipped: {results['skipped']}")
        logger.info(f"   ❌ Errors: {results['errors']}")
        if dry_run:
            logger.info(f"   🏃 Dry-run: {results['dry_run']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest ricerca folder into Qdrant")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview only, no changes"
    )
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run))
