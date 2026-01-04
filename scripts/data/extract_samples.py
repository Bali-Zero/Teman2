import os
import requests
import json

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


def get_samples(collection, limit):
    headers = {"api-key": QDRANT_API_KEY}
    scroll_resp = requests.post(
        f"{QDRANT_URL}/collections/{collection}/points/scroll",
        json={"limit": limit, "with_payload": True},
        headers=headers,
    )
    if scroll_resp.status_code != 200:
        print(f"Error scrolling {collection}: {scroll_resp.text}")
        return []
    return scroll_resp.json().get("result", {}).get("points", [])


collections_to_extract = {
    "kbli_unified": 4,
    "training_conversations": 5,
    "visa_oracle": 5,
}

results = {}

for col, limit in collections_to_extract.items():
    print(f"Extracting {limit} samples from {col}...")
    samples = get_samples(col, limit)
    results[col] = [s.get("payload", {}) for s in samples]

print("\n--- RESULTS ---\n")
print(json.dumps(results, indent=2))
