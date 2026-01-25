
import os
from qdrant_client import QdrantClient

url = os.environ.get("QDRANT_URL")
api_key = os.environ.get("QDRANT_API_KEY")

print(f"Connecting to {url}...")
client = QdrantClient(url=url, api_key=api_key)

cols = ["kbli_unified", "legal_unified_hybrid"]

for name in cols:
    try:
        info = client.get_collection(name)
        print(f"\nCollection: {name}")
        # Access config.params.vectors might vary by client version, usually it's there
        print(f"Vectors Config: {info.config.params.vectors}")
    except Exception as e:
        print(f"Error checking {name}: {e}")
