import os
import sys
import asyncio
from typing import List, Dict, Any
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "apps/backend-rag"))

from backend.core.config import settings
from backend.services.qdrant_service import QdrantService
from backend.services.embeddings import EmbeddingService
from qdrant_client.http import models
import fitz  # PyMuPDF

# Paths (Corrected with spaces)
BASE_PATH = "/Users/nuzantara/Desktop/KBLI-Navigator-2025 "
FILES = [
    {
        "path": os.path.join(BASE_PATH, "KBLI_2025_FINAL_CLEAN.backup_final_20260204_165833.txt"),
        "type": "kbli_database",
        "name": "KBLI 2025 Master Database"
    },
    {
        "path": os.path.join(BASE_PATH, "regulation/undang-undang/PP Nomor 28 Tahun 2025.pdf"),
        "type": "regulation",
        "name": "PP Nomor 28 Tahun 2025"
    },
    {
        "path": os.path.join(BASE_PATH, "regulation/peraturan-bps-2025/peraturan-bps-no-7-tahun-2025.pdf"),
        "type": "regulation",
        "name": "Peraturan BPS No 7 Tahun 2025"
    }
]

COLLECTION_NAME = "kbli_notebook_expert"

async def process_pdf(file_info: Dict) -> List[Dict]:
    """Extracts text from PDF with semantic chunking for regulations."""
    print(f"Processing PDF: {file_info['name']}")
    try:
        doc = fitz.open(file_info['path'])
    except Exception as e:
        print(f"Error opening PDF {file_info['path']}: {e}")
        return []

    chunks = []
    
    current_chunk = ""
    current_pasal = "General"
    
    for page in doc:
        text = page.get_text()
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Simple heuristic for Pasal detection
            if line.lower().startswith("pasal") and len(line) < 20:
                # Save previous chunk
                if current_chunk:
                    chunks.append({
                        "content": current_chunk,
                        "metadata": {
                            "source": file_info['name'],
                            "type": file_info['type'],
                            "section": current_pasal,
                            "page": page.number + 1
                        }
                    })
                current_pasal = line
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
                
    # Last chunk
    if current_chunk:
        chunks.append({
            "content": current_chunk,
            "metadata": {
                "source": file_info['name'],
                "type": file_info['type'],
                "section": current_pasal,
                "page": -1
            }
        })
        
    return chunks

async def process_txt(file_info: Dict) -> List[Dict]:
    """Process KBLI text database."""
    print(f"Processing TXT: {file_info['name']}")
    try:
        with open(file_info['path'], 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading TXT {file_info['path']}: {e}")
        return []
    
    # Split by double newline usually separates entries in clean dumps
    raw_entries = content.split('\n\n')
    chunks = []
    
    for entry in raw_entries:
        if len(entry) < 10: continue
        chunks.append({
            "content": entry,
            "metadata": {
                "source": file_info['name'],
                "type": file_info['type'],
                "section": "KBLI Code"
            }
        })
    return chunks

async def ingest():
    print(f"🚀 Starting Expert Ingestion for {COLLECTION_NAME}...")
    
    qdrant = QdrantService()
    embedding_service = EmbeddingService()
    
    # 1. Recreate Collection
    print("Recreating collection...")
    try:
        await qdrant.client.delete_collection(COLLECTION_NAME)
    except:
        pass
        
    await qdrant.client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=1536,  # OpenAI text-embedding-3-small
            distance=models.Distance.COSINE
        )
    )
    
    all_docs = []
    
    # 2. Process Files
    for file_info in FILES:
        if file_info['path'].endswith('.pdf'):
            docs = await process_pdf(file_info)
        else:
            docs = await process_txt(file_info)
        all_docs.extend(docs)
        print(f"  > Extracted {len(docs)} chunks from {file_info['name']}")

    if not all_docs:
        print("❌ No documents extracted. Aborting.")
        return

    # 3. Embed and Upload
    batch_size = 100
    total = len(all_docs)
    print(f"Total chunks to ingest: {total}")
    
    for i in range(0, total, batch_size):
        batch = all_docs[i:i+batch_size]
        texts = [d['content'] for d in batch]
        
        try:
            # Embed
            embeddings = await embedding_service.get_embeddings(texts)
            
            points = [
                models.PointStruct(
                    id=i + idx,
                    vector=emb,
                    payload={
                        "text": doc['content'],
                        "metadata": doc['metadata']
                    }
                )
                for idx, (doc, emb) in enumerate(zip(batch, embeddings))
            ]
            
            await qdrant.client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
            print(f"  > Uploaded batch {i}-{i+len(batch)}/{total}")
        except Exception as e:
            print(f"Error processing batch {i}: {e}")

    print("✅ Ingestion Complete!")

if __name__ == "__main__":
    asyncio.run(ingest())
