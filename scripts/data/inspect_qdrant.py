import os

import requests

# Qdrant URL from env or default
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
if not QDRANT_API_KEY:
    print("⚠️  Warning: QDRANT_API_KEY not found in environment")


def inspect_qdrant():
    try:
        headers = {"api-key": QDRANT_API_KEY}
        # 1. List Collections
        resp = requests.get(f"{QDRANT_URL}/collections", headers=headers)
        if resp.status_code != 200:
            print(f"Error listing collections: {resp.text}")
            return

        collections = resp.json().get("result", {}).get("collections", [])
        print(f"Found {len(collections)} collections in Qdrant:")

        for col in collections:
            name = col["name"]
            print(f"\n--- Collection: {name} ---")

            # Get count
            count_resp = requests.post(
                f"{QDRANT_URL}/collections/{name}/points/count",
                json={"exact": True},
                headers=headers,
            )
            count = count_resp.json().get("result", {}).get("count", "Unknown")
            print(f"  Count: {count}")

            # Get one sample point to check metadata
            scroll_resp = requests.post(
                f"{QDRANT_URL}/collections/{name}/points/scroll",
                json={"limit": 1, "with_payload": True},
                headers=headers,
            )
            points = scroll_resp.json().get("result", {}).get("points", [])

            if points:
                payload = points[0].get("payload", {})
                print("  Sample Metadata keys:", list(payload.keys()))
                if "parent_id" in payload:
                    print(f"  ✅ Has 'parent_id': {payload['parent_id']}")
                else:
                    print("  ⚠️ NO 'parent_id' found (Old format?)")
            else:
                print("  (Empty collection)")

    except Exception as e:
        print(f"Error connecting to Qdrant: {e}")


if __name__ == "__main__":
    inspect_qdrant()
