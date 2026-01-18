import os
import json
import subprocess
import sys
from dotenv import load_dotenv

# Load env from the standard location
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "apps", "backend-rag", ".env")
load_dotenv(ENV_PATH)

QDRANT_URL = os.getenv("QDRANT_URL")
API_KEY = os.getenv("QDRANT_API_KEY")


def run_curl(path, method="GET", data=None):
    url = f"{QDRANT_URL}{path}"
    cmd = [
        "curl",
        "-s",
        "-X",
        method,
        url,
        "-H",
        f"api-key: {API_KEY}",
        "-H",
        "Content-Type: application/json",
    ]
    if data:
        cmd.extend(["-d", json.dumps(data)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}


def list_collections():
    res = run_curl("/collections")
    collections = [c["name"] for c in res.get("result", {}).get("collections", [])]
    print("\n--- Qdrant Collections ---")
    for i, name in enumerate(collections, 1):
        print(f"{i}. {name}")
    return collections


def inspect_collection(name):
    print(f"\n--- Inspecting: {name} ---")
    res = run_curl(f"/collections/{name}")
    info = res.get("result", {})
    print(f"Status: {info.get('status')}")
    print(f"Vectors: {info.get('vectors_count')}")
    print(f"Points: {info.get('points_count')}")

    # Peek at first 2 points
    peek = run_curl(
        f"/collections/{name}/points/scroll",
        method="POST",
        data={"limit": 2, "with_payload": True},
    )
    points = peek.get("result", {}).get("points", [])
    print(f"\nSample Data (First {len(points)} points):")
    for p in points:
        print(f"  ID: {p['id']}")
        print(f"  Payload: {json.dumps(p.get('payload'))[:200]}...")


def main():
    if not QDRANT_URL or not API_KEY:
        print("Error: QDRANT_URL or QDRANT_API_KEY not found in .env")
        return

    print(f"Connected to: {QDRANT_URL}")

    if len(sys.argv) > 1:
        col_name = sys.argv[1]
        inspect_collection(col_name)
    else:
        cols = list_collections()
        print("\nUsage: python3 scripts/qdrant_explorer.py [collection_name]")


if __name__ == "__main__":
    main()
