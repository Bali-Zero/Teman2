#!/usr/bin/env python3
"""Test Qdrant connection and initialize collection"""
import os
from qdrant_client import QdrantClient, models

QDRANT_URL = os.getenv('QDRANT_URL', 'https://nuzantara-qdrant.fly.dev')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = 'balizero_news_history'
VECTOR_SIZE = 1536

print('=' * 60)
print(f'INITIALIZING COLLECTION: {COLLECTION_NAME}')
print(f'URL: {QDRANT_URL}')
print('=' * 60)

try:
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=30,
        prefer_grpc=False
    )
    
    print('\nChecking existing collections...')
    cols = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in cols.collections)
    
    if exists:
        print(f'⚠️ Collection {COLLECTION_NAME} already exists.')
        print('Keeping existing collection.')
    else:
        print('\nCreating hybrid collection...')
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={'default': models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE)},
            sparse_vectors_config={'bm25': models.SparseVectorParams(modifier=models.Modifier.IDF)},
            optimizers_config=models.OptimizersConfigDiff(default_segment_number=2, indexing_threshold=1000),
            hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100, full_scan_threshold=10000)
        )
        print('✅ Collection created!')
        
        print('\nCreating payload indices...')
        client.create_payload_index(COLLECTION_NAME, 'published_at', models.PayloadSchemaType.DATETIME)
        client.create_payload_index(COLLECTION_NAME, 'source_url', models.PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION_NAME, 'category', models.PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION_NAME, 'tier', models.PayloadSchemaType.KEYWORD)
        print('✅ Indices created!')
    
    print('\n✅ SETUP COMPLETED')
except Exception as e:
    print(f'\n❌ Error: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
