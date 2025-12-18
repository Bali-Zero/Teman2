import os
import requests
import urllib3
from dotenv import load_dotenv

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not QDRANT_URL or not QDRANT_API_KEY:
    print("❌ Error: Missing environment variables.")
    exit(1)

HEADERS = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}


def get_collections():
    try:
        response = requests.get(
            f"{QDRANT_URL}/collections", headers=HEADERS, verify=False
        )
        response.raise_for_status()
        return response.json()["result"]["collections"]
    except Exception as e:
        print(f"❌ Error listing collections: {e}")
        return []


def analyze_collection(name):
    print(f"\n🔍 ANALYZING: '{name}'")
    print("=" * 40)

    # 1. Get Info (Count & Specs)
    try:
        res = requests.get(
            f"{QDRANT_URL}/collections/{name}", headers=HEADERS, verify=False
        )
        info = res.json()["result"]
        count = info.get("points_count", 0)
        config = info.get("config", {}).get("params", {})
        vector_size = (
            info.get("config", {})
            .get("params", {})
            .get("vectors", {})
            .get("size", "Unknown")
        )
        distance = (
            info.get("config", {})
            .get("params", {})
            .get("vectors", {})
            .get("distance", "Unknown")
        )

        print(f"📊 Docs (Points): {count}")
        print(f"⚙️  Specs: Size={vector_size}, Metric={distance}")
    except Exception as e:
        print(f"❌ Error getting info: {e}")
        return

    # 2. Sample Data (Topics & Quality)
    if count > 0:
        try:
            payload = {"limit": 3, "with_payload": True}
            res = requests.post(
                f"{QDRANT_URL}/collections/{name}/points/scroll",
                headers=HEADERS,
                json=payload,
                verify=False,
            )
            points = res.json()["result"]["points"]

            print(f"📝 Content Analysis (Sample of {len(points)}):")
            for i, p in enumerate(points):
                payload_data = p.get("payload", {})
                text = (
                    payload_data.get("text", "")
                    or payload_data.get("content", "")
                    or str(payload_data)
                )
                metadata = payload_data.get("metadata", {})

                # Guess Topic
                snippet = text[:100].replace("\n", " ")
                print(f"   [{i + 1}] Metadata: {list(metadata.keys())}")
                print(f"       Snippet: {snippet}...")
        except Exception as e:
            print(f"❌ Error sampling data: {e}")
    else:
        print("   (Collection is empty)")


if __name__ == "__main__":
    colls = get_collections()
    print(f"Found {len(colls)} collections.")

    for c in colls:
        analyze_collection(c["name"])
