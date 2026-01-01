"""
Tax Genius Collection Ingestion Script

Populates the tax_genius collection in Qdrant with tax-related documents.
Includes: PPh 21 (individual tax), PPN/VAT (11%), and other tax topics.

Usage:
    # Local (for testing)
    python -m scripts.ingest_tax_genius --dry-run

    # On Fly.io
    fly ssh console -a nuzantara-rag -C "cd /app && python -m scripts.ingest_tax_genius"
"""

import asyncio
import hashlib
import logging
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from core.chunker import TextChunker
from core.embeddings import create_embeddings_generator
from core.qdrant_db import QdrantClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Tax document definitions with metadata
TAX_DOCUMENTS = [
    {
        "path": "training-data/tax/tax_016_pph21_individual_indonesian.md",
        "title": "PPh 21 - Individual Employee Tax Guide",
        "category": "income_tax",
        "subcategory": "pph21",
        "topics": ["PPh 21", "employee tax", "PTKP", "tax brackets", "withholding tax", "NPWP"],
        "language": "id",
        "tier": "A",
    },
    {
        "path": "training-data/tax/tax_019_ppn_vat_full_cycle.md",
        "title": "PPN/VAT 11% - Full Cycle Guide",
        "category": "value_added_tax",
        "subcategory": "ppn",
        "topics": ["PPN", "VAT", "PKP", "e-Faktur", "SPT Masa", "input VAT", "output VAT"],
        "language": "id",
        "tier": "A",
    },
    {
        "path": "training-data/tax_pph_ppn_conversation.md",
        "title": "PPh & PPN Conversation Examples",
        "category": "general_tax",
        "subcategory": "conversations",
        "topics": ["PPh", "PPN", "tax questions", "FAQ"],
        "language": "id",
        "tier": "B",
    },
]


def generate_doc_id(text: str, source: str, chunk_index: int) -> str:
    """Generate deterministic document ID for upsert idempotency."""
    content = f"{source}:{chunk_index}:{text[:100]}"
    return hashlib.md5(content.encode()).hexdigest()


async def ingest_tax_genius(dry_run: bool = False) -> dict:
    """
    Main ingestion function for tax_genius collection.

    Args:
        dry_run: If True, only show what would be ingested without actually doing it

    Returns:
        Dictionary with ingestion results
    """
    logger.info("=" * 60)
    logger.info("TAX GENIUS COLLECTION INGESTION")
    logger.info("=" * 60)

    # Initialize services
    chunker = TextChunker()
    embedder = create_embeddings_generator()
    qdrant = QdrantClient(collection_name="tax_genius")

    # Check if collection exists, create if not
    if not dry_run:
        logger.info("Checking if tax_genius collection exists...")
        stats = await qdrant.get_collection_stats()
        if "error" in stats and "404" in str(stats.get("error", "")):
            logger.info("Creating tax_genius collection...")
            created = await qdrant.create_collection(
                vector_size=1536,  # OpenAI text-embedding-3-small
                distance="Cosine",
                enable_sparse=False,  # Keep simple for now
            )
            if created:
                logger.info("✅ Collection tax_genius created")
            else:
                logger.error("❌ Failed to create collection")
                return {"success": False, "error": "Failed to create collection"}
        else:
            logger.info(f"✅ Collection exists with {stats.get('total_documents', 0)} documents")

    # Process each document
    all_chunks = []
    all_embeddings = []
    all_metadatas = []
    all_ids = []

    base_path = Path(__file__).parent.parent

    for doc_config in TAX_DOCUMENTS:
        doc_path = base_path / doc_config["path"]
        if not doc_path.exists():
            logger.warning(f"⚠️ Document not found: {doc_path}")
            continue

        logger.info(f"\n📄 Processing: {doc_config['title']}")
        logger.info(f"   Path: {doc_path}")

        # Read document
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        logger.info(f"   Size: {len(content):,} characters")

        # Chunk document
        base_metadata = {
            "source": doc_config["path"],
            "title": doc_config["title"],
            "category": doc_config["category"],
            "subcategory": doc_config["subcategory"],
            "topics": doc_config["topics"],
            "language": doc_config["language"],
            "tier": doc_config["tier"],
        }

        chunks = chunker.semantic_chunk(content, metadata=base_metadata)
        logger.info(f"   Chunks: {len(chunks)}")

        if dry_run:
            # Show sample chunks
            for i, chunk in enumerate(chunks[:3]):
                preview = chunk["text"][:100].replace("\n", " ")
                logger.info(f"   Sample chunk {i+1}: {preview}...")
            continue

        # Generate embeddings
        chunk_texts = [chunk["text"] for chunk in chunks]
        logger.info(f"   Generating embeddings for {len(chunk_texts)} chunks...")
        embeddings = embedder.generate_embeddings(chunk_texts)

        # Build metadata and IDs
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                **base_metadata,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "text_preview": chunk["text"][:200],
            }
            all_metadatas.append(chunk_metadata)

            doc_id = generate_doc_id(chunk["text"], doc_config["path"], i)
            all_ids.append(doc_id)

        all_chunks.extend(chunk_texts)
        all_embeddings.extend(embeddings)

        logger.info(f"   ✅ Processed {len(chunks)} chunks")

    if dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("DRY RUN COMPLETE - No documents were ingested")
        logger.info(f"Would ingest: {len(TAX_DOCUMENTS)} documents")
        return {"success": True, "dry_run": True, "documents": len(TAX_DOCUMENTS)}

    # Upsert all documents
    logger.info(f"\n📤 Upserting {len(all_chunks)} chunks to tax_genius...")

    result = await qdrant.upsert_documents(
        chunks=all_chunks,
        embeddings=all_embeddings,
        metadatas=all_metadatas,
        ids=all_ids,
    )

    if result.get("success"):
        logger.info("=" * 60)
        logger.info("✅ TAX GENIUS INGESTION COMPLETE")
        logger.info(f"   Documents: {len(TAX_DOCUMENTS)}")
        logger.info(f"   Chunks: {result.get('documents_added', 0)}")
        logger.info("=" * 60)
    else:
        logger.error(f"❌ Ingestion failed: {result.get('error')}")

    # Close client
    await qdrant.close()

    return result


async def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest tax documents to tax_genius collection")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without ingesting")
    args = parser.parse_args()

    result = await ingest_tax_genius(dry_run=args.dry_run)

    if result.get("success"):
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
