import urllib.request
import json
import ssl
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_URL = "https://nuzantara-qdrant.fly.dev"
COLLECTIONS = ["legal_unified", "knowledge_base"]

print(f"🔌 Connecting to {BASE_URL} via HTTP...")

for collection in COLLECTIONS:
    print(f"\n🔍 Analyzing collection: {collection}")
    
    # Get stats
    try:
        req = urllib.request.Request(f"{BASE_URL}/collections/{collection}")
        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read().decode())
            points_count = data.get("result", {}).get("points_count")
            print(f"   - Points: {points_count}")
            
            if not points_count:
                continue
    except Exception as e:
        print(f"   ❌ Error getting stats: {e}")
        continue

    # Scroll points
    print("   - Scanning documents...")
    doc_ids = set()
    next_page_offset = None
    total_fetched = 0
    
    # Fetch more points this time to be sure
    while total_fetched < 10000:
        url = f"{BASE_URL}/collections/{collection}/points/scroll"
        payload = {
            "limit": 100,
            "with_payload": True,
            "with_vector": False
        }
        if next_page_offset:
            payload["offset"] = next_page_offset
            
        data_json = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data_json, headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req, context=ctx) as response:
                resp_data = json.loads(response.read().decode())
                result = resp_data.get("result", {})
                points = result.get("points", [])
                next_page_offset = result.get("next_page_offset")
                
                for point in points:
                    p = point.get("payload", {})
                    
                    if collection == "legal_unified":
                        # Extract from law_title: "PP-55-2022 - Pasal 206" -> "PP-55-2022"
                        title = p.get("law_title", "")
                        if " - Pasal" in title:
                            doc_id = title.split(" - Pasal")[0]
                            doc_ids.add(doc_id)
                        elif title:
                            doc_ids.add(title)
                        else:
                            # Fallback to ID parsing
                            pid = str(point.get("id", ""))
                            if "_pasal_" in pid:
                                doc_ids.add(pid.split("_pasal_")[0])
                                
                    elif collection == "knowledge_base":
                        # Extract from ID: "computer_science_..._chunk_..."
                        pid = str(point.get("id", ""))
                        if "_chunk_" in pid:
                            doc_id = pid.split("_chunk_")[0]
                            doc_ids.add(doc_id)
                        else:
                            doc_ids.add(pid)
                
                total_fetched += len(points)
                if not next_page_offset:
                    break
        except Exception as e:
            print(f"   ❌ Error scrolling: {e}")
            break
            
    print(f"   ✅ Found {len(doc_ids)} unique documents:")
    for doc in sorted(list(doc_ids)):
        print(f"      - {doc}")

