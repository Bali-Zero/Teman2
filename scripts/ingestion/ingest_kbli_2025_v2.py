#!/usr/bin/env python3
"""
KBLI 2025 Ingestion Script v2 - Full Architecture Compliance
-------------------------------------------------------------
Ingests 1,945 KBLI codes into Qdrant as individual documents.
Each code becomes one document with rich metadata and context injection.

Architecture compliance:
- [x] Context Injection: [CONTEXT: KBLI 2025 - PP 28/2025 - SEKTOR X...]
- [x] Embeddings: text-embedding-3-small (1536 dims)
- [x] Vector DB: Qdrant
- [x] Parent Docs: PostgreSQL via API endpoint (dataset-level tracking)

Usage:
    python scripts/ingestion/ingest_kbli_2025_v2.py [--dry-run] [--limit N] [--recreate]
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv

# Add backend path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'backend-rag'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'backend-rag', '.env'))

import openai

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "https://nuzantara-rag.fly.dev")
API_KEY = os.getenv("API_KEYS", "").split(",")[0] if os.getenv("API_KEYS") else ""

COLLECTION_NAME = "kbli_2025"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Source file
KBLI_JSON_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..',
    'apps', 'kb', 'data', '04_aziende', 'kbli',
    'KBLI_2025_ULTIMATE_COMPLETE.json'
)


def get_embedding(text: str) -> list[float]:
    """Generate embedding using OpenAI."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text[:8000]  # Limit input length
    )
    return response.data[0].embedding


def build_context_injection(code: str, info: dict) -> str:
    """Build context injection string following system standard."""
    sektor = info.get('sektor', 'Unknown')
    risiko = info.get('tingkat_risiko', 'Unknown')

    # Format: [CONTEXT: KBLI 2025 - PP 28/2025 - SEKTOR X - KODE XXXXX - RISIKO Y]
    return f"[CONTEXT: KBLI 2025 - PP 28/2025 - SEKTOR {sektor} - KODE {code} - RISIKO {risiko}]"


def format_kbli_content(code: str, info: dict) -> str:
    """Format KBLI code info into searchable text content with context injection."""
    lines = []

    # Context Injection (REQUIRED)
    context = build_context_injection(code, info)
    lines.append(context)
    lines.append("")

    # Header
    lines.append(f"# KBLI {code} - {info.get('judul', 'N/A')}")
    lines.append("")

    # Basic info
    lines.append(f"**Kode:** {code}")
    lines.append(f"**Sektor:** {info.get('sektor', 'N/A')}")
    lines.append(f"**Tingkat Risiko:** {info.get('tingkat_risiko', 'N/A')}")
    lines.append("")

    # Foreign ownership
    pma = info.get('kepemilikan_asing', {})
    if pma:
        pma_status = "Diizinkan" if pma.get('pma_diizinkan') else "Tidak Diizinkan"
        lines.append(f"**Kepemilikan Asing (PMA):** {pma_status}")
        if pma.get('maksimum'):
            lines.append(f"**Maksimum Kepemilikan:** {pma.get('maksimum')}")
        if pma.get('catatan'):
            lines.append(f"**Catatan PMA:** {pma.get('catatan')}")
        lines.append("")

    # Investment requirements
    invest = info.get('persyaratan_investasi', {})
    if invest:
        lines.append("**Persyaratan Investasi:**")
        if invest.get('modal_minimum_pma'):
            lines.append(f"- Modal Minimum PMA: {invest.get('modal_minimum_pma')}")
        if invest.get('modal_disetor_minimum'):
            lines.append(f"- Modal Disetor Minimum: {invest.get('modal_disetor_minimum')}")
        lines.append("")

    # Licensing
    perizinan = info.get('perizinan_berusaha', {})
    if perizinan:
        lines.append("**Perizinan Berusaha:**")
        docs = perizinan.get('dokumen_wajib', [])
        if docs:
            for doc in docs[:5]:  # Limit to avoid too long content
                lines.append(f"- {doc}")
        if perizinan.get('waktu_proses'):
            lines.append(f"- Waktu Proses: {perizinan.get('waktu_proses')}")
        if perizinan.get('kewenangan'):
            lines.append(f"- Kewenangan: {perizinan.get('kewenangan')}")
        lines.append("")

    # Scale
    scales = info.get('skala_usaha', [])
    if scales:
        lines.append(f"**Skala Usaha:** {', '.join(scales)}")

    return "\n".join(lines)


def extract_metadata(code: str, info: dict, parent_id: str) -> dict:
    """Extract rich metadata for filtering."""
    pma = info.get('kepemilikan_asing', {})
    perizinan = info.get('perizinan_berusaha', {})

    return {
        # Identifiers
        "kbli_code": code,
        "kbli_code_prefix": code[:2] if len(code) >= 2 else code,  # For category filtering
        "title": info.get('judul', ''),

        # Classification
        "sector": info.get('sektor', 'Unknown'),
        "risk_level": info.get('tingkat_risiko', 'Unknown'),

        # Foreign ownership
        "pma_allowed": pma.get('pma_diizinkan', False) if pma else False,
        "pma_max_percentage": pma.get('maksimum', '') if pma else '',

        # Business scale
        "scales": info.get('skala_usaha', []),
        "allows_mikro": 'Mikro' in info.get('skala_usaha', []),
        "allows_besar": 'Besar' in info.get('skala_usaha', []),

        # Licensing
        "licensing_authority": perizinan.get('kewenangan', '') if perizinan else '',
        "processing_time": perizinan.get('waktu_proses', '') if perizinan else '',

        # Source tracking
        "source": "PP 28/2025 + KBLI 2020",
        "ingestion_date": datetime.now().isoformat(),
        "document_type": "kbli_code",
        "has_context": True,  # Context injection applied

        # Parent document reference
        "parent_id": parent_id,

        # For collection filtering in multi-collection search
        "collection": "kbli_2025",
        "tier": "A"  # High-value reference data
    }


def qdrant_request(method: str, endpoint: str, json_data: dict = None) -> dict:
    """Make authenticated request to Qdrant REST API."""
    url = f"{QDRANT_URL}{endpoint}"
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    if method == "GET":
        r = requests.get(url, headers=headers, timeout=60)
    elif method == "PUT":
        r = requests.put(url, headers=headers, json=json_data, timeout=60)
    elif method == "POST":
        r = requests.post(url, headers=headers, json=json_data, timeout=60)
    elif method == "DELETE":
        r = requests.delete(url, headers=headers, timeout=60)
    else:
        raise ValueError(f"Unknown method: {method}")

    r.raise_for_status()
    return r.json()


def register_parent_doc_via_api(
    parent_id: str,
    document_id: str,
    title: str,
    description: str,
    total_codes: int,
    metadata: dict,
) -> bool:
    """Register parent document via backend API"""
    url = f"{BACKEND_URL}/api/legal/parent-documents"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
    }

    payload = {
        "id": parent_id,
        "document_id": document_id,
        "doc_type": "kbli_dataset",
        "title": title,
        "full_text": description,
        "char_count": len(description),
        "chunk_count": total_codes,  # Number of KBLI codes
        "metadata": metadata,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in [200, 201]:
            print(f"✅ Registered parent doc: {parent_id}")
            return True
        else:
            print(f"⚠️ Failed to register parent doc: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"⚠️ Could not register parent doc (API unavailable): {e}")
        return False


def create_collection(recreate: bool = False):
    """Create or recreate the KBLI collection."""
    # Get existing collections
    result = qdrant_request("GET", "/collections")
    collections = [c["name"] for c in result.get("result", {}).get("collections", [])]

    if COLLECTION_NAME in collections:
        if recreate:
            print(f"Deleting existing collection: {COLLECTION_NAME}")
            qdrant_request("DELETE", f"/collections/{COLLECTION_NAME}")
        else:
            print(f"Collection {COLLECTION_NAME} already exists. Use --recreate to overwrite.")
            return False

    print(f"Creating collection: {COLLECTION_NAME}")
    qdrant_request("PUT", f"/collections/{COLLECTION_NAME}", {
        "vectors": {
            "size": EMBEDDING_DIM,
            "distance": "Cosine"
        }
    })
    return True


def ingest_kbli(
    dry_run: bool = False,
    limit: Optional[int] = None,
    recreate: bool = False
):
    """Main ingestion function."""

    # Load KBLI data
    print(f"Loading KBLI data from: {KBLI_JSON_PATH}")
    with open(KBLI_JSON_PATH, 'r') as f:
        data = json.load(f)

    file_metadata = data.get('metadata', {})
    codes = data.get('kbli_codes', {})

    print(f"Total codes: {len(codes)}")
    print(f"Source: {file_metadata.get('peraturan', 'Unknown')}")

    if limit:
        codes = dict(list(codes.items())[:limit])
        print(f"Limited to: {len(codes)} codes")

    # Generate parent ID for the dataset
    parent_id = hashlib.md5(KBLI_JSON_PATH.encode()).hexdigest()[:16]

    if dry_run:
        print("\n=== DRY RUN MODE ===")
        # Show sample
        for i, (code, info) in enumerate(codes.items()):
            if i >= 3:
                break
            content = format_kbli_content(code, info)
            meta = extract_metadata(code, info, parent_id)
            print(f"\n--- Sample {i+1}: KBLI {code} ---")
            print(f"Content length: {len(content)} chars")
            print(f"Metadata: {json.dumps(meta, indent=2, ensure_ascii=False)[:500]}...")
        return

    # Test connection
    print(f"\nConnecting to Qdrant: {QDRANT_URL}")
    try:
        result = qdrant_request("GET", "/collections")
        print(f"Connected. Existing collections: {len(result.get('result', {}).get('collections', []))}")
    except Exception as e:
        print(f"Connection error: {e}")
        return

    # Create collection
    if not create_collection(recreate):
        if not recreate:
            print("Aborting. Use --recreate to overwrite existing collection.")
            return

    # Register parent document (the KBLI dataset)
    print(f"\nBackend URL: {BACKEND_URL}")
    print(f"API Key: {'SET' if API_KEY else 'NOT SET'}")

    dataset_description = f"""
KBLI 2025 - Klasifikasi Baku Lapangan Usaha Indonesia

Source: {file_metadata.get('peraturan', 'PP 28/2025 + KBLI 2020 (BPS)')}
Total Codes: {len(codes)}
Generated: {file_metadata.get('generated', 'Unknown')}

Berisi klasifikasi lengkap kode usaha Indonesia dengan:
- Informasi kepemilikan asing (PMA)
- Tingkat risiko usaha
- Persyaratan perizinan
- Skala usaha yang diizinkan
"""

    register_parent_doc_via_api(
        parent_id=parent_id,
        document_id="kbli_2025",
        title="KBLI 2025 - PP 28/2025 + KBLI 2020",
        description=dataset_description,
        total_codes=len(codes),
        metadata={
            "source_file": KBLI_JSON_PATH,
            "peraturan": file_metadata.get('peraturan', ''),
            "generated": file_metadata.get('generated', ''),
            "ingestion_date": datetime.now().isoformat(),
        }
    )

    # Prepare points
    points = []
    errors = []

    print(f"\nProcessing {len(codes)} KBLI codes...")
    for i, (code, info) in enumerate(codes.items()):
        try:
            content = format_kbli_content(code, info)
            meta = extract_metadata(code, info, parent_id)

            # Generate embedding
            embedding = get_embedding(content)

            point = {
                "id": i,
                "vector": embedding,
                "payload": {
                    "content": content,
                    **meta
                }
            }
            points.append(point)

            if (i + 1) % 50 == 0:
                print(f"  Processed: {i + 1}/{len(codes)}")

        except Exception as e:
            errors.append((code, str(e)))
            print(f"  Error on {code}: {e}")

    # Upload in batches
    print(f"\nUploading {len(points)} points to Qdrant...")
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        try:
            qdrant_request("PUT", f"/collections/{COLLECTION_NAME}/points", {
                "points": batch
            })
            print(f"  Uploaded: {min(i + batch_size, len(points))}/{len(points)}")
        except Exception as e:
            print(f"  Upload error at batch {i}: {e}")
            errors.append((f"batch_{i}", str(e)))

    # Summary
    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Total processed: {len(points)}")
    print(f"Parent doc registered: {parent_id}")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nErrors:")
        for code, err in errors[:10]:
            print(f"  - {code}: {err}")

    # Verify
    try:
        result = qdrant_request("GET", f"/collections/{COLLECTION_NAME}")
        points_count = result.get("result", {}).get("points_count", 0)
        print(f"\nVerification: {points_count} points in collection")
    except Exception as e:
        print(f"\nVerification error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest KBLI 2025 codes into Qdrant (v2)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    parser.add_argument("--limit", type=int, help="Limit number of codes to process")
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate collection")

    args = parser.parse_args()

    ingest_kbli(
        dry_run=args.dry_run,
        limit=args.limit,
        recreate=args.recreate
    )
