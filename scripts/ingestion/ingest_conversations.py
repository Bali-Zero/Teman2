import json
import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# Load environment variables FIRST
from dotenv import load_dotenv

env_path = Path(os.getcwd()) / "apps/backend-rag/.env"
load_dotenv(dotenv_path=env_path, override=True)

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "apps/backend-rag/backend"))

# Imports from the backend
from core.qdrant_db import QdrantClient
from core.embeddings import EmbeddingsGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_conversations(file_path: str) -> List[Dict[str, Any]]:
    """Load conversations from a JSON file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_qdrant_client() -> QdrantClient:
    """Initialize and return the Qdrant client."""
    return QdrantClient()


def recreate_conversation_collection(
    client: QdrantClient, collection_name: str, vector_size: int
):
    """
    Ensure the collection exists.
    Note: The current wrapper doesn't support dropping collections easily,
    so this attempts to create it if it doesn't exist.
    """
    stats = client.get_collection_stats()
    if "error" in stats:
        logger.info(f"Collection '{collection_name}' not found. Creating...")
        success = client.create_collection(vector_size=vector_size, distance="Cosine")
        if not success:
            raise RuntimeError(f"Failed to create collection {collection_name}")
        logger.info(f"Collection '{collection_name}' created.")
    else:
        logger.info(
            f"Collection '{collection_name}' already exists. Proceeding with upsert."
        )


def build_points_from_conversations(
    conversations: List[Dict[str, Any]], embeddings_generator: EmbeddingsGenerator
) -> Dict[str, Any]:
    """
    Process conversations into text chunks, metadata, and generate embeddings.
    Returns a dict with 'chunks', 'metadatas', and 'embeddings'.
    """
    chunks = []
    metadatas = []

    logger.info(f"Processing {len(conversations)} conversations...")

    for item in conversations:
        # Heuristic: Handle different formats
        # Format 1: 'question' and 'answer' (like synthetic data)
        if "question" in item and "answer" in item:
            text = f"Question: {item['question']}\nAnswer: {item['answer']}"
            meta = {
                "question": item.get("question"),
                "answer": item.get("answer"),
                "source": item.get("source", "conversation_file"),
                "type": "qa_pair",
            }

        # Format 2: 'messages' list (user/assistant)
        elif "messages" in item and isinstance(item["messages"], list):
            # Flatten or pick the last turn? Let's flatten for context.
            # Or formatted as a transcript.
            transcript = ""
            for msg in item["messages"]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                transcript += f"{role.capitalize()}: {content}\n"

            text = transcript.strip()
            meta = {
                "source": item.get("source", "conversation_file"),
                "type": "chat_transcript",
                # Store original messages in metadata if small enough?
                # Qdrant payload has limits, safer to keep simple.
            }

        else:
            logger.warning(f"Skipping unrecognized conversation format: {item.keys()}")
            continue

        chunks.append(text)
        metadatas.append(meta)

    if not chunks:
        return {"chunks": [], "embeddings": [], "metadatas": []}

    logger.info("Generating embeddings...")
    embeddings = embeddings_generator.generate_embeddings(chunks)

    return {"chunks": chunks, "embeddings": embeddings, "metadatas": metadatas}


def upsert_points_in_batches(
    client: QdrantClient, collection_name: str, points: Dict[str, Any]
):
    """Upsert points into Qdrant."""
    chunks = points.get("chunks", [])
    embeddings = points.get("embeddings", [])
    metadatas = points.get("metadatas", [])

    if not chunks:
        logger.warning("No points to upsert.")
        return

    # Client wrapper seems to handle upserting directly (though maybe not batching logic if chunks are huge)
    # But upsert_documents takes lists.
    logger.info(f"Upserting {len(chunks)} documents...")

    # We explicitly set client.collection_name temporarily or pass it?
    # The wrapper's upsert_documents uses self.collection_name.
    # So we should probably instantiate client with the correct collection name or modify it.

    # Check if client was initialized with correct collection
    if client.collection_name != collection_name:
        logger.info(
            f"Switching client collection from '{client.collection_name}' to '{collection_name}'"
        )
        client.collection_name = collection_name

    result = client.upsert_documents(
        chunks=chunks, embeddings=embeddings, metadatas=metadatas
    )

    if result.get("success"):
        logger.info("Upsert successful.")
    else:
        logger.error(f"Upsert failed: {result.get('error')}")


def ingest_conversations(file_path: str):
    logger.info(f"Starting ingestion from {file_path}")
    try:
        conversations = load_conversations(file_path)

        # Initialize embeddings
        embeddings_generator = EmbeddingsGenerator()
        # vector_size = embeddings_generator.dimensions # Assuming this property exists or hardcode
        # The wrapper uses 1536 default for OpenAI, let's stick to that or check embedder
        vector_size = 1536

        # Initialize Qdrant and collection
        client = get_qdrant_client()
        collection_name = "conversation_examples"
        recreate_conversation_collection(client, collection_name, vector_size)

        # Build points and upsert
        points = build_points_from_conversations(conversations, embeddings_generator)
        upsert_points_in_batches(client, collection_name, points)

        logger.info("Ingestion complete.")

    except FileNotFoundError as e:
        logger.error("File error: %s", e)
    except ValueError as e:
        logger.error("Data error: %s", e)
    except Exception as e:
        logger.exception("Unexpected error during ingestion: %s", e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Default path; override with environment variable if needed
    DATA_FILE = os.getenv("CONVERSATIONS_FILE", "data/conversations.json")

    # Allow command line argument to override
    if len(sys.argv) > 1:
        DATA_FILE = sys.argv[1]

    ingest_conversations(DATA_FILE)
