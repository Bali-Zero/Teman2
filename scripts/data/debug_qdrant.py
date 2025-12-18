import os
import requests
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

env_path = Path(os.getcwd()) / "apps/backend-rag/.env"
load_dotenv(dotenv_path=env_path, override=True)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "legal_unified"


def check_stats():
    url = f"{QDRANT_URL}/collections/{COLLECTION}"
    print(f"Checking {url}...")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print("✅ Collection found!")
            print(json.dumps(data, indent=2))
        else:
            print(f"❌ Collection check failed: {response.status_code}")
            print(response.text)

        # Check points count
        url_points = f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll"
        response = requests.post(url_points, json={"limit": 5, "with_payload": True})
        if response.status_code == 200:
            points = response.json().get("result", {}).get("points", [])
            print(f"\n✅ Found {len(points)} points in scroll (limit 5)")
            for p in points:
                print(f" - ID: {p['id']}")
                print(
                    f"   Payload: {p.get('payload', {}).get('question', 'No question')}"
                )
        else:
            print(f"❌ Scroll failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    import json

    check_stats()
