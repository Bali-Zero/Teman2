#!/usr/bin/env python3
"""Test upsert in Qdrant"""
import httpx
import os
import uuid
import hashlib

url = os.getenv('QDRANT_URL')
key = os.getenv('QDRANT_API_KEY')
headers = {'api-key': key}

# Test upsert
doc_id = str(uuid.UUID(hashlib.md5(b'test-url').hexdigest()))
vector = [0.1] * 1536
payload = {
    'title': 'Test Article',
    'summary': 'Test summary',
    'source_url': 'https://test.example.com',
    'published_at': '2025-01-10T12:00:00Z'
}

upsert_data = {
    'points': [{
        'id': doc_id,
        'vector': vector,
        'payload': payload
    }]
}

with httpx.Client(timeout=30, headers=headers) as client:
    r = client.put(f'{url}/collections/balizero_news_history/points', json=upsert_data)
    print(f'Upsert Status: {r.status_code}')
    print(f'Response: {r.text[:200]}')
    
    # Verify
    r2 = client.get(f'{url}/collections/balizero_news_history')
    print(f'Points after upsert: {r2.json().get("result", {}).get("points_count", 0)}')
