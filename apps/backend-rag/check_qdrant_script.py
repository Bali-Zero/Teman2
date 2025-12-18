import os
import sys
from typing import List, Set
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Add parent directory to path to import app modules if needed
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

def load_env_file(filepath: str):
    """Simple .env loader to avoid external dependencies if possible"""
    if not os.path.exists(filepath):
        return
    
    print(f"Loading environment from {filepath}...")
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes if present
                value = value.strip()
                if (value.startswith('"') and value.endswith('"')) or                    (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                
                if key not in os.environ:
                    os.environ[key] = value

def check_qdrant_content():
    # Load .env from current directory
    backend_root = os.path.abspath(os.path.dirname(__file__))
    load_env_file(os.path.join(backend_root, ".env"))
    
    qdrant_url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    
    if not qdrant_api_key:
        print("⚠️  WARNING: QDRANT_API_KEY not found in environment.")
    
    print(f"🔌 Connecting to Qdrant at {qdrant_url}...")
    
    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=60)
        
        # List collections
        collections_response = client.get_collections()
        collections = [c.name for c in collections_response.collections]
        
        print(f"📦 Found {len(collections)} collections: {', '.join(collections)}")
        
        target_collections = ["legal_unified", "knowledge_base"]
        
        for collection_name in target_collections:
            if collection_name not in collections:
                print(f"❌ Collection '{collection_name}' NOT found.")
                continue
                
            print(f"\n🔍 Analyzing collection: {collection_name}")
            
            # Get collection info
            info = client.get_collection(collection_name)
            print(f"   - Points count: {info.points_count}")
            print(f"   - Status: {info.status}")
            
            if info.points_count == 0:
                print("   - Collection is empty.")
                continue
                
            # Scroll through points to extract filenames
            print("   - Scanning for documents (this might take a moment)...")
            
            filenames: Set[str] = set()
            next_offset = None
            total_scanned = 0
            
            while True:
                points, next_offset = client.scroll(
                    collection_name=collection_name,
                    limit=100,
                    offset=next_offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                for point in points:
                    payload = point.payload or {}
                    # Check common metadata fields for filename
                    filename = payload.get("filename") or                                payload.get("source") or                                payload.get("file_path") or                                payload.get("title")
                               
                    if filename:
                        # Clean up path if it's a full path
                        filename = os.path.basename(filename)
                        filenames.add(filename)
                
                total_scanned += len(points)
                if total_scanned % 1000 == 0:
                    print(f"     Scanned {total_scanned} points...")
                
                if next_offset is None:
                    break
            
            print(f"   ✅ Found {len(filenames)} unique documents:")
            sorted_files = sorted(list(filenames))
            for f in sorted_files:
                print(f"      - {f}")
                
    except Exception as e:
        print(f"❌ Error connecting to Qdrant: {e}")
        if "Connection refused" in str(e) or "Connect call failed" in str(e):
            print("   (Check if you are connected to the internet and if the Qdrant URL is reachable)")

if __name__ == "__main__":
    check_qdrant_content()
