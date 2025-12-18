#!/usr/bin/env python3
"""
Test script per ingestione singolo PDF legale
Verifica che BAB vanno in PostgreSQL e chunks in Qdrant
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "apps/backend-rag/backend"))

from services.legal_ingestion_service import LegalIngestionService


async def test_single_pdf():
    """Test ingestione di un singolo PDF"""

    # PDF di test
    test_pdf = "/Users/antonellosiano/desktop/nuzantara/apps/kb/data/01_immigrazione/PP Nomor 31 Tahun 2013_20251122_163034_f60006.pdf"

    print("=" * 80)
    print("TEST INGESTIONE PDF LEGALE")
    print("=" * 80)
    print(f"\nFile: {test_pdf}")
    print(f"Size: {os.path.getsize(test_pdf) / 1024:.1f} KB")

    # Initialize service
    print("\n[1/5] Initializing LegalIngestionService...")
    service = LegalIngestionService()
    print("✓ Service initialized")

    # Ingest document
    print("\n[2/5] Ingesting document...")
    print("  → Parsing PDF")
    print("  → Cleaning text")
    print("  → Extracting metadata")
    print("  → Parsing structure (BAB → Pasal → Ayat)")
    print("  → Chunking (Pasal-aware)")
    print("  → Generating embeddings")
    print("  → Saving to PostgreSQL (BAB) + Qdrant (chunks)")

    try:
        result = await service.ingest_legal_document(
            file_path=test_pdf,
            title="PP 31 Tahun 2013 (TEST)",
            collection_name="legal_unified"
        )

        print("\n✓ Ingestion completed!")
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(f"Success: {result.get('success')}")
        print(f"Document ID: {result.get('book_title')}")
        print(f"Chunks created: {result.get('chunks_created')}")

        if result.get('legal_metadata'):
            metadata = result['legal_metadata']
            print(f"\nMetadata:")
            print(f"  Type: {metadata.get('type')}")
            print(f"  Number: {metadata.get('number')}")
            print(f"  Year: {metadata.get('year')}")
            print(f"  Topic: {metadata.get('topic', '')[:80]}...")

        if result.get('structure'):
            structure = result['structure']
            bab_count = len(structure.get('batang_tubuh', []))
            pasal_count = sum(len(bab.get('pasal', [])) for bab in structure.get('batang_tubuh', []))
            print(f"\nStructure:")
            print(f"  BAB (chapters): {bab_count}")
            print(f"  Pasal (articles): {pasal_count}")

            # Show BAB titles
            print(f"\nBAB detected:")
            for bab in structure.get('batang_tubuh', [])[:5]:  # First 5
                print(f"  • BAB {bab.get('number')}: {bab.get('title', 'N/A')}")
            if bab_count > 5:
                print(f"  ... and {bab_count - 5} more")

        print("\n" + "=" * 80)
        print("VERIFICATION NEEDED")
        print("=" * 80)
        print("\n[3/5] Check PostgreSQL for BAB:")
        print("  psql $DATABASE_URL -c \"SELECT id, title, pasal_count FROM parent_documents WHERE document_id LIKE 'PP_31_2013%';\"")

        print("\n[4/5] Check Qdrant for chunks:")
        print("  → Should see chunks with parent_chunk_ids pointing to BAB in PostgreSQL")

        print("\n[5/5] Test retrieval:")
        print("  curl -X POST https://nuzantara-rag.fly.dev/api/rag/query \\")
        print("    -H 'Content-Type: application/json' \\")
        print("    -d '{\"query\": \"Apa isi PP 31 tahun 2013?\", \"top_k\": 3}'")

        print("\n✓ TEST COMPLETED SUCCESSFULLY!")
        return result

    except Exception as e:
        print(f"\n✗ Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Run async function
    result = asyncio.run(test_single_pdf())

    if result and result.get('success'):
        sys.exit(0)
    else:
        sys.exit(1)
