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


def get_collection_info():
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    try:
        response = requests.get(
            f"{QDRANT_URL}/collections/legal_unified", headers=headers, verify=False
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    print("🔍 Checking Qdrant 'legal_unified' count...")
    info = get_collection_info()

    if info and "result" in info:
        points_count = info["result"].get("points_count", 0)
        vectors_count = info["result"].get("vectors_count", 0)
        status = info["result"].get("status", "Unknown")

        print("\n✅ Collection Found: 'legal_unified'")
        print(f"📊 Total Points (Chunks): {points_count}")
        print(f"🔢 Total Vectors: {vectors_count}")
        print(f"Bz Status: {status}")
    else:
        print("❌ Could not retrieve collection info.")
