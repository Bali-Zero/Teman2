import asyncio
import json
import logging
import sys
import os
from pathlib import Path

# Load environment variables FIRST
from dotenv import load_dotenv

env_path = Path(os.getcwd()) / "apps/backend-rag/.env"
load_dotenv(dotenv_path=env_path, override=True)

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "apps/backend-rag/backend"))

from core.qdrant_db import QdrantClient
from core.embeddings import EmbeddingsGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def ingest_synthetic_data(file_path: str):
    """
    Ingest synthetic QA pairs into Qdrant 'conversation_examples' collection.
    """
    try:
        # Initialize clients
        qdrant = QdrantClient(collection_name="conversation_examples")
        embedder = EmbeddingsGenerator()

        # Check if collection exists, create if not
        stats = qdrant.get_collection_stats()
        if "error" in stats:
            logger.info("⚠️ Collection not found, creating 'conversation_examples'...")
            if not qdrant.create_collection(vector_size=1536, distance="Cosine"):
                logger.error("❌ Failed to create collection")
                sys.exit(1)
            logger.info("✅ Collection created successfully")

        # Load data
        with open(file_path, "r") as f:
            data = json.load(f)

        logger.info(f"📚 Loaded {len(data)} examples from {file_path}")

        # Prepare for ingestion
        texts = []
        metadatas = []

        for item in data:
            # Create a rich text representation for embedding
            # We want to find examples based on the QUESTION primarily
            text_to_embed = f"Question: {item['question']}\nAnswer: {item['answer']}"
            texts.append(text_to_embed)

            # Store full data in metadata
            metadatas.append(
                {
                    "question": item["question"],
                    "answer": item["answer"],
                    "context_used": item.get("context_used", ""),
                    "persona": item.get("persona", "general"),
                    "source": "synthetic_gold_laws",
                }
            )

        # Generate embeddings
        logger.info("🧠 Generating embeddings...")
        embeddings = embedder.generate_embeddings(texts)

        # Upsert to Qdrant
        logger.info("💾 Upserting to Qdrant...")
        qdrant.upsert_documents(
            chunks=texts, embeddings=embeddings, metadatas=metadatas
        )

        logger.info("✅ Successfully ingested synthetic examples!")

    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_synthetic_data.py <path_to_json>")
        sys.exit(1)

    file_path = sys.argv[1]
    asyncio.run(ingest_synthetic_data(file_path))
