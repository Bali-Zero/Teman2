#!/usr/bin/env python3
"""
Qdrant Chunk Quality Analyzer
Samples and inspects chunks in the vector database.
"""
import os
import requests
import json
import statistics
import random
from pathlib import Path
from dotenv import load_dotenv

# Env setup
script_dir = Path(__file__).parent
backend_rag_dir = script_dir.parent / "apps" / "backend-rag"
load_dotenv(backend_rag_dir / ".env")

QDRANT_URL = "https://nuzantara-qdrant.fly.dev"
API_KEY = os.getenv("QDRANT_API_KEY")

headers = {"api-key": API_KEY}

def get_collections():
    try:
        r = requests.get(f"{QDRANT_URL}/collections", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get('result', {}).get('collections', [])
        print(f"Error getting collections: {r.status_code} {r.text}")
        return []
    except Exception as e:
        print(f"Exception getting collections: {e}")
        return []

def analyze_collection(name, sample_size=100):
    print(f"\n🔍 Analyzing collection: {name}")
    
    # Get count
    r = requests.get(f"{QDRANT_URL}/collections/{name}", headers=headers)
    count = 0
    if r.status_code == 200:
        count = r.json().get('result', {}).get('points_count', 0)
    print(f"   Total points: {count:,}")
    
    if count == 0:
        return None

    # Scroll to get samples (using filter to get non-empty vectors if possible, or just scroll)
    # We use scroll API
    points = []
    next_offset = None
    
    # Try to get diverse samples by using random offsets if count is large
    # Ideally scroll gives sequential.
    # To get random, we might need to rely on scroll with random offset? No, scroll is by ID/vector.
    # We will just scroll first N and maybe some deep ones if possible using 'offset' if scroll supports it? 
    # Scroll supports 'offset' (point id). 
    # Let's just pull the first 200 and analyze.
    
    payload = {
        "limit": sample_size,
        "with_payload": True,
        "with_vector": False
    }
    
    try:
        r = requests.post(f"{QDRANT_URL}/collections/{name}/points/scroll", headers=headers, json=payload, timeout=20)
        if r.status_code == 200:
            points = r.json().get('result', {}).get('points', [])
    except Exception as e:
        print(f"   Error scrolling: {e}")
        return None

    if not points:
        print("   No points retrieved.")
        return None

    # Analysis
    lengths = []
    metadata_keys = set()
    sources = {}
    empty_content = 0
    
    sample_texts = []

    for p in points:
        pl = p.get('payload', {})
        # Detect content field
        content = pl.get('content') or pl.get('text') or pl.get('page_content') or ""
        
        if not content:
            empty_content += 1
            continue
            
        lengths.append(len(content))
        metadata_keys.update(pl.keys())
        
        src = pl.get('source') or pl.get('filename') or "unknown"
        sources[src] = sources.get(src, 0) + 1
        
        if len(sample_texts) < 3:
            sample_texts.append(content[:200] + "...")

    if not lengths:
        print("   No valid content found in samples.")
        return None

    avg_len = statistics.mean(lengths)
    med_len = statistics.median(lengths)
    max_len = max(lengths)
    min_len = min(lengths)

    print(f"   Sample size: {len(points)}")
    print(f"   Avg Length: {avg_len:.0f} chars")
    print(f"   Median Length: {med_len:.0f} chars")
    print(f"   Content Keys Found: {list(metadata_keys)}")
    print(f"   Empty Content: {empty_content}")
    print(f"   Top Sources: {sorted(sources.items(), key=lambda x: x[1], reverse=True)[:3]}")
    
    print("   📝 Content Snippets:")
    for i, s in enumerate(sample_texts):
        print(f"      {i+1}. {s.replace(chr(10), ' ')}")

    return {
        "count": count,
        "avg_len": avg_len,
        "med_len": med_len,
        "keys": list(metadata_keys)
    }

def main():
    print("🚀 Starting Main...", flush=True)
    if not API_KEY:
        print("❌ QDRANT_API_KEY missing in env", flush=True)
        # Try finding it in process env
        if os.environ.get("QDRANT_API_KEY"):
            print("Found in os.environ", flush=True)
        else:
             print("Not in os.environ either", flush=True)
        return

    print(f"🔑 API Key found (len={len(API_KEY)})", flush=True)
    
    colls = get_collections()
    if not colls:
        print("❌ No collections returned", flush=True)
        return

    print(f"Found {len(colls)} collections.", flush=True)
    
    stats = {}
    
    # Prioritize interesting collections
    priority = ['legal_unified_hybrid', 'kbli_unified', 'feature_extraction_unified', 'training_conversations_hybrid']
    
    for c in priority:
        found = next((x for x in colls if x['name'] == c), None)
        if found:
            stats[c] = analyze_collection(c)
            
    # Do others?
    # for c in colls:
    #    if c['name'] not in priority:
    #        stats[c['name']] = analyze_collection(c['name'], sample_size=20)

if __name__ == "__main__":
    main()
