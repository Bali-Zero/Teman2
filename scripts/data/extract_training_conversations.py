import os
import json
import requests
import urllib3
from dotenv import load_dotenv

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
TARGET_FILE = "/Users/antonellosiano/Desktop/training_conversations_export.json"
COLLECTION_NAME = "training_conversations"

if not QDRANT_URL or not QDRANT_API_KEY:
    print("❌ Error: Missing environment variables.")
    exit(1)

HEADERS = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}


def fetch_all_points(collection_name):
    print(f"Starting extraction from {collection_name}...")
    points = []
    next_offset = None

    while True:
        try:
            payload = {"limit": 100, "with_payload": True, "with_vector": False}
            if next_offset:
                payload["offset"] = next_offset

            response = requests.post(
                f"{QDRANT_URL}/collections/{collection_name}/points/scroll",
                headers=HEADERS,
                json=payload,
                verify=False,
            )
            response.raise_for_status()
            result = response.json()["result"]

            batch_points = result.get("points", [])
            points.extend(batch_points)
            print(f"Fetched {len(points)} total points...")

            next_offset = result.get("next_page_offset")
            if not next_offset:
                break

        except Exception as e:
            print(f"❌ Error fetching points: {e}")
            break

    return points


def save_to_desktop(points):
    try:
        data = []
        for p in points:
            item = {"id": p["id"], "payload": p.get("payload", {})}
            data.append(item)

        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✅ Successfully saved {len(data)} documents to {TARGET_FILE}")

    except Exception as e:
        print(f"❌ Error saving to file: {e}")


if __name__ == "__main__":
    all_points = fetch_all_points(COLLECTION_NAME)
    if all_points:
        save_to_desktop(all_points)
    else:
        print("No points found or extraction failed.")
