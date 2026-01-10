#!/usr/bin/env python3
"""Verifica collezione e punti salvati"""
import os
import httpx

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "balizero_news_history"

headers = {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else {}

with httpx.Client(timeout=30.0, headers=headers) as client:
    # Info collezione
    r = client.get(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
    data = r.json().get("result", {})
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Points: {data.get('points_count', 0)}")
    print(f"Status: {data.get('status', 'unknown')}")
    
    # Scroll punti
    r = client.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
        json={"limit": 5, "with_payload": True}
    )
    points = r.json().get("result", {}).get("points", [])
    print(f"\nFound {len(points)} points:")
    for p in points[:3]:
        payload = p.get("payload", {})
        print(f"  - {payload.get('title', 'No title')[:60]}...")
        print(f"    Published: {payload.get('published_at', 'N/A')}")
