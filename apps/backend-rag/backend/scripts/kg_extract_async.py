#!/usr/bin/env python3
"""Extract KG entities from 500 chunks using backend's async QdrantClient"""

import asyncio
import json
import re
import sys

# Add backend to path
sys.path.insert(0, "/app")

ENTITY_PATTERNS = {
    "legal_entity": [
        r"\b(PT\s+PMA)\b",
        r"\b(PT\s+PMDN)\b",
        r"\b(PT\s+Perorangan)\b",
        r"\bCV\b",
        r"\b(Firma)\b",
        r"\b(Koperasi)\b",
        r"\b(Yayasan)\b",
    ],
    "permit": [
        r"\bNIB\b",
        r"\bSIUP\b",
        r"\bTDP\b",
        r"\bNPWP\b",
        r"\bIUJK\b",
        r"\bIMTA\b",
        r"\bRPTKA\b",
    ],
    "visa_type": [
        r"\bKITAS\b",
        r"\bKITAP\b",
        r"\b(Visa\s+On\s+Arrival)\b",
        r"\b(VOA)\b",
        r"\b(E-Visa)\b",
    ],
    "tax_type": [
        r"\bPPh\s*\d+\b",
        r"\bPPN\b",
        r"\bPBB\b",
        r"\bBPHTB\b",
    ],
    "kbli": [
        r"\bKBLI\s+\d{5}\b",
    ],
    "regulation": [
        r"\b(UU|PP|Perpres|Permen)\s+(No\.?\s*)?\d+[\/\s]*(Tahun\s*)?\d{4}\b",
    ],
}

RELATIONSHIP_PATTERNS = [
    (r"(memerlukan|membutuhkan|requires?|needs?|wajib\s+memiliki)", "REQUIRES"),
    (r"(biaya|tarif|costs?|Rp\.?\s*[\d\.,]+)", "COSTS"),
    (r"(proses|waktu|duration|(\d+)\s*(hari|bulan|tahun|days?|months?|years?))", "DURATION"),
    (r"(bagian\s+dari|termasuk|part\s+of|includes?)", "PART_OF"),
    (r"(pajak|tax\s+obligation)", "TAX_OBLIGATION"),
]


async def main():
    from backend.core.qdrant_db import QdrantClient

    print("=" * 60)
    print("KG EXTRACTION - 500 CHUNKS (ASYNC)")
    print("=" * 60)

    client = QdrantClient(collection_name="legal_unified_hybrid")

    # Get collection stats
    stats = await client.get_collection_stats()
    print(f"Collection: {stats['collection_name']}, Total docs: {stats['total_documents']}")

    # Fetch 500 chunks in batches
    all_chunks = []
    batch_size = 100
    for batch_num in range(5):
        print(f"Fetching batch {batch_num + 1}/5...")
        # Use peek with offset simulation via scroll
        result = await client._client.scroll(
            collection_name="legal_unified_hybrid",
            limit=batch_size,
            offset=batch_num * batch_size if batch_num > 0 else None,
            with_payload=True,
            with_vectors=False,
        )
        points = result[0] if isinstance(result, tuple) else result
        all_chunks.extend(points)
        print(f"  Got {len(points)} chunks")

    print(f"\nTotal chunks retrieved: {len(all_chunks)}")

    # Extract entities
    all_entities = {}
    all_relationships = []

    for chunk in all_chunks:
        text = chunk.payload.get("text", "") or chunk.payload.get("content", "")
        chunk_id = str(chunk.id)
        if not text:
            continue

        chunk_entities = []
        for entity_type, patterns in ENTITY_PATTERNS.items():
            for pattern in patterns:
                for match in re.findall(pattern, text, re.IGNORECASE):
                    name = match if isinstance(match, str) else match[0]
                    name = name.strip().upper()
                    eid = f"{entity_type}_{name.replace(' ', '_').lower()}"

                    if eid not in all_entities:
                        all_entities[eid] = {
                            "entity_id": eid,
                            "type": entity_type,
                            "name": name,
                            "mentions": 0,
                            "source_chunks": [],
                        }
                    all_entities[eid]["mentions"] += 1
                    if chunk_id not in all_entities[eid]["source_chunks"]:
                        all_entities[eid]["source_chunks"].append(chunk_id)
                    chunk_entities.append(eid)

        # Infer relationships
        if len(chunk_entities) >= 2:
            for rel_pattern, rel_type in RELATIONSHIP_PATTERNS:
                if re.search(rel_pattern, text, re.IGNORECASE):
                    for i, e1 in enumerate(chunk_entities):
                        for e2 in chunk_entities[i + 1 :]:
                            rel_id = f"{e1}_{rel_type}_{e2}"
                            if rel_id not in [r["id"] for r in all_relationships]:
                                all_relationships.append(
                                    {
                                        "id": rel_id,
                                        "source": e1,
                                        "target": e2,
                                        "type": rel_type,
                                        "chunk": chunk_id,
                                    }
                                )

    # Results
    sorted_e = sorted(all_entities.values(), key=lambda x: x["mentions"], reverse=True)
    print(f"\nFOUND {len(sorted_e)} UNIQUE ENTITIES")
    print(f"FOUND {len(all_relationships)} RELATIONSHIPS\n")

    # Group by type
    by_type = {}
    for e in sorted_e:
        t = e["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(e)

    for t, entities in sorted(by_type.items()):
        print(f"\n[{t.upper()}] ({len(entities)} entities)")
        for e in entities[:5]:
            print(f"  {e['name']:25} ({e['mentions']:3} mentions)")
        if len(entities) > 5:
            print(f"  ... and {len(entities) - 5} more")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)
    for t, entities in sorted(by_type.items()):
        total_mentions = sum(e["mentions"] for e in entities)
        print(f"  {t:15}: {len(entities):4} entities, {total_mentions:6} mentions")
    print(f"\n  TOTAL: {len(sorted_e)} entities, {len(all_relationships)} relationships")

    # Save to JSON
    output = {
        "entities": sorted_e,
        "relationships": all_relationships,
        "stats": {
            "total_entities": len(sorted_e),
            "total_relationships": len(all_relationships),
            "by_type": {t: len(e) for t, e in by_type.items()},
            "chunks_processed": len(all_chunks),
        },
    }
    with open("/tmp/kg_extraction_500.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nSaved to /tmp/kg_extraction_500.json")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
