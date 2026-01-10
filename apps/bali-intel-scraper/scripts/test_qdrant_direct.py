#!/usr/bin/env python3
"""Test diretto connessione Qdrant usando qdrant-client"""
import os
import sys
from qdrant_client import QdrantClient

QDRANT_URL = os.getenv('QDRANT_URL', 'https://nuzantara-qdrant.fly.dev')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')

print('=' * 60)
print('TEST QDRANT CLIENT CONNECTION')
print('=' * 60)
print(f'URL: {QDRANT_URL}')
print(f'API_KEY present: {bool(QDRANT_API_KEY)}')

try:
    print('\n1. Creating client with prefer_grpc=False...')
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=30,
        prefer_grpc=False
    )
    print('✅ Client created')
    
    print('\n2. Testing get_collections()...')
    cols = client.get_collections()
    print(f'✅ Success! Collections: {len(cols.collections)}')
    for c in cols.collections[:5]:
        print(f'   - {c.name}')
    
except Exception as e:
    print(f'\n❌ Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n✅ TEST PASSED')
