
import os
import json
import subprocess
from dotenv import load_dotenv

# Explicitly load .env from apps/backend-rag
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag", ".env")
load_dotenv(env_path)

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
API_KEY = os.getenv("QDRANT_API_KEY")

def get_point(collection_name, kbli_code="62193"):
    url = f"{QDRANT_URL}/collections/{collection_name}/points/scroll"
    
    # Both collections use 'kbli_code' based on ingestion script review
    # kbli_platinum_2026: line 296 "kbli_code": code
    # kbli_2025/unified: likely "kbli_code": code
    filter_key = "kbli_code"
    
    payload = {
        "filter": {
            "must": [
                {"key": filter_key, "match": {"value": kbli_code}}
            ]
        },
        "limit": 1,
        "with_payload": True
    }
    
    # Construct curl command
    cmd = [
        "curl", "-s", "-X", "POST", url,
        "-H", f"api-key: {API_KEY}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if not result.stdout.strip():
            return "Error: Empty response from Qdrant"
            
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON response: {result.stdout[:200]}"

        if data.get("result", {}).get("points"):
            return data["result"]["points"][0]["payload"]
        
        # If no points found as is, try 'code' just in case (fallback)
        return f"No points found. Filter used: {filter_key}={kbli_code}. Response: {json.dumps(data)}"
        
    except Exception as e:
        return f"Error: {e}"

def main():
    target_code = "62193" # Blockchain / Tech
    
    print(f"--- Comparing KBLI {target_code} ---")
    
    # User suggests 'kbli_unified' might be the name
    legacy_col = "kbli_unified"
    print(f"\n[Collection: {legacy_col}] (Legacy)")
    old_payload = get_point(legacy_col, target_code)
    print(json.dumps(old_payload, indent=2) if isinstance(old_payload, dict) else old_payload)

    print(f"\n{'='*40}\n")

    platinum_col = "kbli_platinum_2026"
    print(f"[Collection: {platinum_col}] (New)")
    new_payload = get_point(platinum_col, target_code)
    print(json.dumps(new_payload, indent=2) if isinstance(new_payload, dict) else new_payload)

if __name__ == "__main__":
    main()
