import os
import requests
import json

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

headers = {"api-key": QDRANT_API_KEY}
resp = requests.post(
    f"{QDRANT_URL}/collections/legal_unified_hybrid/points/scroll",
    json={"limit": 3, "with_payload": True},
    headers=headers,
)
print(json.dumps(resp.json().get("result", {}).get("points", []), indent=2))
