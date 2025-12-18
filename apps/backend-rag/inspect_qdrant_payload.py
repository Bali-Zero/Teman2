import json
import ssl
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_URL = "https://nuzantara-qdrant.fly.dev"
COLLECTIONS = ["legal_unified", "knowledge_base"]

print(f"🔌 Connecting to {BASE_URL}...")

for collection in COLLECTIONS:
    print(f"\n🔍 Inspecting collection: {collection}")

    url = f"{BASE_URL}/collections/{collection}/points/scroll"
    payload = {"limit": 1, "with_payload": True, "with_vector": False}
    data_json = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data_json, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            resp_data = json.loads(response.read().decode())
            points = resp_data.get("result", {}).get("points", [])

            if points:
                print("   ✅ First point payload:")
                print(json.dumps(points[0].get("payload"), indent=2))
            else:
                print("   ⚠️ No points found.")
    except Exception as e:
        print(f"   ❌ Error: {e}")
