import asyncio
import logging

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)


async def main():
    from backend.core.qdrant_db import QdrantClient

    client = QdrantClient(collection_name="legal_unified")

    # Scroll to find points with document_id BALI_UNKNOWN_UNKNOWN
    url = "/collections/legal_unified/points/scroll"
    payload = {
        "filter": {
            "must": [{"key": "metadata.document_id", "match": {"value": "BALI_UNKNOWN_UNKNOWN"}}]
        },
        "limit": 100,
        "with_payload": True,
    }

    qclient = await client._get_client()
    response = await qclient.post(url, json=payload)
    data = response.json()
    points = data.get("result", {}).get("points", [])

    print("Found " + str(len(points)) + " bad points.")

    if points:
        # Delete them
        ids = [p["id"] for p in points]
        await client.delete(ids=ids)
        print("Deleted " + str(len(ids)) + " bad points.")


if __name__ == "__main__":
    asyncio.run(main())
