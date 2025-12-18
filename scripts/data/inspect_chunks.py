import requests
import os
from dotenv import load_dotenv
from pathlib import Path

# Load env
load_dotenv(Path(__file__).parent.parent / "apps/backend-rag/.env")

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv(
    "QDRANT_API_KEY", "QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
)

COLLECTIONS = ["visa_oracle", "tax_genius", "legal_unified"]


def inspect_chunks():
    print("🔍 INSPECTING LATEST CHUNKS IN QDRANT")
    print("=====================================")

    headers = {"api-key": QDRANT_API_KEY}

    COLLECTIONS = ["legal_unified", "visa_oracle", "tax_genius"]

    for col in COLLECTIONS:
        print(f"\n📂 COLLECTION: {col}")
        print("-" * 40)

        try:
            # Scroll points (get first 3)
            resp = requests.post(
                f"{QDRANT_URL}/collections/{col}/points/scroll",
                headers=headers,
                json={"limit": 3, "with_payload": True, "with_vector": True},
            )

            if resp.status_code != 200:
                print(
                    f"   ⚠️ Collection not ready or empty (Status: {resp.status_code})"
                )
                continue

            data = resp.json().get("result", {}).get("points", [])

            if not data:
                print("   (No chunks found yet)")
                continue

            for point in data:
                payload = point.get("payload", {})
                vector = point.get("vector")
                vector_len = len(vector) if vector else 0

                print(f"   🆔 Chunk ID: {point['id']}")
                print(f"   📄 Source: {payload.get('source_file', 'N/A')}")
                print(f"   🏷️  Title: {payload.get('title', 'N/A')}")
                print(f"   📏 Vector Dim: {vector_len} (Should be 1536)")

                text = payload.get("text", "")
                snippet = text[:200].replace("\n", " ") + "..."
                print(f"   📝 Text: {snippet}")
                print("-" * 20)

        except Exception as e:
            print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    inspect_chunks()
