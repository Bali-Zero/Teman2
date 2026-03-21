import asyncio
import logging

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)


async def main():
    from backend.core.embeddings import create_embeddings_generator
    from backend.core.qdrant_db import QdrantClient

    client = QdrantClient(collection_name="legal_unified")
    embedder = create_embeddings_generator()

    query = "Penutupan PMA di virtual office Bali"
    embeddings = await embedder.generate_embeddings([query])

    results = await client.search(query_embedding=embeddings[0], limit=3, vector_name="dense")

    print("\n--- TOP SEARCH RESULTS ---")
    for i, doc in enumerate(results.get("documents", [])):
        print(f"RESULT: {doc[:200]}...")
        print(f"METADATA: {results.get('metadatas', [])[i]}")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())
