import urllib.request
import json
import ssl

# Bypass SSL verification if needed (though curl worked)
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
            status = data.get("result", {}).get("status")
            points_count = data.get("result", {}).get("points_count")
            print(f"   - Status: {status}")
            print(f"   - Points: {points_count}")
            
            if not points_count:
                print("   - Empty collection.")
                continue
    except Exception as e:
        print(f"   ❌ Error getting stats: {e}")
        continue

    # Scroll points
    print("   - Scanning documents...")
    filenames = set()
    next_page_offset = None
    
    # We'll fetch up to 1000 points to get a good sample
    # To get ALL, we'd need a loop. Let's do a loop but limit to 5000 points to be safe on time.
    total_fetched = 0
    
    while total_fetched < 5000:
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
                    # Try various keys
                    fname = p.get("filename") or p.get("source") or p.get("title") or p.get("file_path")
                    if fname:
                        # Clean up
                        if "/" in fname:
                            fname = fname.split("/")[-1]
                        filenames.add(fname)
                
                total_fetched += len(points)
                if not next_page_offset:
                    break
        except Exception as e:
            print(f"   ❌ Error scrolling: {e}")
            break
            
    print(f"   ✅ Found {len(filenames)} unique documents (sampled from {total_fetched} points):")
    for f in sorted(list(filenames)):
        print(f"      - {f}")

