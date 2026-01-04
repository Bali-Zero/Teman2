#!/usr/bin/env python3
"""Extract KG entities from 500 chunks - runs on Fly.io"""

import json
import os
import re

from qdrant_client import QdrantClient

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

print("=" * 60)
print("KG EXTRACTION - 500 CHUNKS")
print("=" * 60)

qdrant_url = os.environ.get("QDRANT_URL", "http://nuzantara-qdrant.flycast:6333")
print(f"Connecting to: {qdrant_url}")
qdrant = QdrantClient(url=qdrant_url, timeout=120)

print("Fetching 500 chunks from legal_unified_hybrid...")
chunks = qdrant.scroll(
    collection_name="legal_unified_hybrid", limit=500, with_payload=True, with_vectors=False
)[0]
print(f"Retrieved {len(chunks)} chunks\n")

all_entities = {}
all_relationships = []

for chunk in chunks:
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
print(f"FOUND {len(sorted_e)} UNIQUE ENTITIES")
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
    for e in entities[:8]:
        print(f"  {e['name']:30} ({e['mentions']:3} mentions, {len(e['source_chunks']):3} chunks)")
    if len(entities) > 8:
        print(f"  ... and {len(entities) - 8} more")

# Relationship sample
print("\n[RELATIONSHIPS SAMPLE]")
for r in all_relationships[:15]:
    src = all_entities.get(r["source"], {}).get("name", r["source"])
    tgt = all_entities.get(r["target"], {}).get("name", r["target"])
    print(f"  {src} --[{r['type']}]--> {tgt}")
if len(all_relationships) > 15:
    print(f"  ... and {len(all_relationships) - 15} more")

# Summary
print(f"\n{'=' * 60}")
print("SUMMARY")
print("=" * 60)
for t, entities in sorted(by_type.items()):
    total_mentions = sum(e["mentions"] for e in entities)
    print(f"  {t:15}: {len(entities):4} entities, {total_mentions:6} total mentions")
print(f"\n  TOTAL: {len(sorted_e)} entities, {len(all_relationships)} relationships")

# Save to JSON
output = {
    "entities": sorted_e,
    "relationships": all_relationships,
    "stats": {
        "total_entities": len(sorted_e),
        "total_relationships": len(all_relationships),
        "by_type": {t: len(e) for t, e in by_type.items()},
    },
}
with open("/tmp/kg_extraction_500.json", "w") as f:
    json.dump(output, f, indent=2)
print("\nSaved to /tmp/kg_extraction_500.json")
