#!/usr/bin/env python3
"""
Ingest Team Q&A into Qdrant.

Takes the bilingual Q&A dataset and ingests it into Qdrant with embeddings.
Creates a new collection 'team_knowledge_qa' optimized for bilingual retrieval.
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "backend-rag"))

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct


def load_bilingual_qa(file_path: Path) -> List[Dict[str, Any]]:
    """Load bilingual Q&A from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_embeddings(texts: List[str], client: OpenAI, model: str = "text-embedding-3-small") -> List[List[float]]:
    """
    Create embeddings for a list of texts using OpenAI.

    Args:
        texts: List of texts to embed
        client: OpenAI client instance
        model: Embedding model (default: text-embedding-3-small, 1536 dims)

    Returns:
        List of embedding vectors
    """
    print(f"   Creating embeddings for {len(texts)} texts...")

    # Batch embeddings (OpenAI supports up to 2048 texts per request)
    batch_size = 100
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"   Processing batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}...")

        response = client.embeddings.create(
            model=model,
            input=batch
        )

        embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(embeddings)

    return all_embeddings


def create_collection(qdrant_client: QdrantClient, collection_name: str, vector_size: int = 1536):
    """
    Create Qdrant collection for team Q&A.

    Args:
        qdrant_client: Qdrant client instance
        collection_name: Name of collection to create
        vector_size: Embedding vector size (1536 for text-embedding-3-small)
    """
    # Check if collection exists
    collections = qdrant_client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)

    if exists:
        print(f"   ⚠️  Collection '{collection_name}' already exists. Deleting...")
        qdrant_client.delete_collection(collection_name)

    # Create new collection
    print(f"   Creating collection '{collection_name}'...")
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE
        )
    )
    print(f"   ✅ Collection created")


def ingest_qa_to_qdrant(
    qa_data: List[Dict[str, Any]],
    qdrant_client: QdrantClient,
    openai_client: OpenAI,
    collection_name: str = "team_knowledge_qa"
):
    """
    Ingest bilingual Q&A into Qdrant.

    Creates embeddings for both English and Indonesian questions,
    then stores with full metadata for hybrid retrieval.

    Args:
        qa_data: List of bilingual Q&A dictionaries
        qdrant_client: Qdrant client instance
        openai_client: OpenAI client instance
        collection_name: Qdrant collection name
    """
    print(f"\n🔄 Ingesting {len(qa_data)} Q&A pairs into Qdrant...")

    # Step 1: Create collection
    create_collection(qdrant_client, collection_name)

    # Step 2: Prepare texts for embedding
    # We'll embed: "Question (EN): {question_en} Answer (EN): {answer_en}"
    # This allows semantic search in English
    texts_en = []
    texts_id = []

    for qa in qa_data:
        # English text for embedding
        text_en = f"Question: {qa['question_en']}\nAnswer: {qa['answer_en'][:500]}"  # Limit answer length
        texts_en.append(text_en)

        # Indonesian text for embedding
        text_id = f"Pertanyaan: {qa['question_id']}\nJawaban: {qa['answer_id'][:500]}"
        texts_id.append(text_id)

    # Step 3: Create embeddings
    print("\n📊 Creating embeddings...")
    print("   English embeddings...")
    embeddings_en = create_embeddings(texts_en, openai_client)

    print("   Indonesian embeddings...")
    embeddings_id = create_embeddings(texts_id, openai_client)

    # Step 4: Prepare points for Qdrant
    print("\n💾 Preparing Qdrant points...")
    points_en = []
    points_id = []

    for i, qa in enumerate(qa_data):
        # English point
        point_en = PointStruct(
            id=i * 2,  # Even IDs for English
            vector=embeddings_en[i],
            payload={
                "id": qa["id"],
                "domain": qa["domain"],
                "language": "en",
                "question": qa["question_en"],
                "answer": qa["answer_en"],
                "question_other_lang": qa["question_id"],  # For reference
                "answer_other_lang": qa["answer_id"],
                "source": qa["source"],
                "metadata": qa.get("metadata", {})
            }
        )
        points_en.append(point_en)

        # Indonesian point
        point_id = PointStruct(
            id=i * 2 + 1,  # Odd IDs for Indonesian
            vector=embeddings_id[i],
            payload={
                "id": qa["id"],
                "domain": qa["domain"],
                "language": "id",
                "question": qa["question_id"],
                "answer": qa["answer_id"],
                "question_other_lang": qa["question_en"],
                "answer_other_lang": qa["answer_en"],
                "source": qa["source"],
                "metadata": qa.get("metadata", {})
            }
        )
        points_id.append(point_id)

    # Combine all points
    all_points = points_en + points_id

    # Step 5: Upload to Qdrant
    print(f"\n⬆️  Uploading {len(all_points)} points to Qdrant...")

    # Use smaller batch size for cloud Qdrant to avoid timeouts
    batch_size = 25
    for i in range(0, len(all_points), batch_size):
        batch = all_points[i:i + batch_size]
        qdrant_client.upsert(
            collection_name=collection_name,
            points=batch
        )
        print(f"   Uploaded batch {i//batch_size + 1}/{(len(all_points)-1)//batch_size + 1}")

    print(f"\n✅ Ingestion complete!")
    print(f"   📊 Total points: {len(all_points)} ({len(points_en)} EN + {len(points_id)} ID)")
    print(f"   📁 Collection: {collection_name}")


def main():
    """Main ingestion workflow."""
    print("=" * 70)
    print("🚀 TEAM Q&A INGESTION TO QDRANT")
    print("=" * 70)

    # Paths
    data_dir = Path("/Users/antonellosiano/Projects/nuzantara/data/team_qa")
    qa_file = data_dir / "team_qa_bilingual.json"

    # Load Q&A
    print("\n📂 Loading bilingual Q&A...")
    qa_data = load_bilingual_qa(qa_file)
    print(f"   ✅ Loaded {len(qa_data)} Q&A pairs")

    # Initialize clients
    print("\n🔧 Initializing clients...")

    # OpenAI
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("❌ Error: OPENAI_API_KEY not set")
        return
    openai_client = OpenAI(api_key=openai_api_key)
    print("   ✅ OpenAI client initialized")

    # Qdrant (local or cloud)
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    print(f"   ✅ Qdrant client initialized ({qdrant_url})")

    # Ingest
    ingest_qa_to_qdrant(
        qa_data=qa_data,
        qdrant_client=qdrant_client,
        openai_client=openai_client,
        collection_name="team_knowledge_qa"
    )

    print("\n" + "=" * 70)
    print("✅ SUCCESS! Team Q&A ingested to Qdrant")
    print("=" * 70)
    print("\n📊 Next steps:")
    print("   1. Test retrieval: Query Qdrant for 'What is PPh Badan rate?'")
    print("   2. Deploy to production: Update backend to use team_knowledge_qa collection")
    print("   3. Add to SearchService: Register as new collection")
    print()


if __name__ == "__main__":
    main()
