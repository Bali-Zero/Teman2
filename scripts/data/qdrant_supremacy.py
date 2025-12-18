import os
import requests
from dotenv import load_dotenv

# Carica environment specifico del backend
load_dotenv("apps/backend-rag/.env")

# Configurazione (Priorità: Env > Docker Local)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
API_KEY = os.getenv("QDRANT_API_KEY")

print(f"🔌 Connecting to Vector Brain at: {QDRANT_URL}")

try:
    headers = {}
    if API_KEY:
        headers["api-key"] = API_KEY

    # 1. List Collections
    resp = requests.get(f"{QDRANT_URL}/collections", headers=headers, timeout=5)

    if resp.status_code == 200:
        collections = resp.json().get("result", {}).get("collections", [])
        print(f"\n🧠 ACTIVE MEMORY ZONES ({len(collections)}):")
        print("-" * 40)

        total_vectors = 0
        for col in collections:
            name = col["name"]
            # 2. Deep Dive per collection
            det_resp = requests.get(
                f"{QDRANT_URL}/collections/{name}", headers=headers, timeout=5
            )
            if det_resp.status_code == 200:
                stats = det_resp.json().get("result", {})
                count = stats.get("points_count", 0)
                status = stats.get("status", "unknown")
                print(f"  • {name:<25} : {count:>5} vectors [{status.upper()}]")
                total_vectors += count
            else:
                print(f"  • {name:<25} :   ??? vectors")

        print("-" * 40)
        print(f"🔥 TOTAL KNOWLEDGE POINTS: {total_vectors}")
    else:
        print(f"❌ Connection Failed: {resp.status_code} - {resp.text}")

except Exception as e:
    print(f"💀 CRITICAL ERROR: {str(e)}")
