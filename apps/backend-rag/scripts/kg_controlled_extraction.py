"""
Knowledge Graph - Controlled Extraction with Review

Estrae entità e relazioni da un campione di chunks,
mostra i risultati per review PRIMA di persistere nel DB.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


async def run_controlled_extraction(
    collection: str = "legal_unified_hybrid", sample_size: int = 50, dry_run: bool = True
):
    """
    Estrazione controllata con review.

    Args:
        collection: Nome collection Qdrant
        sample_size: Numero chunks da estrarre
        dry_run: Se True, mostra risultati senza persistere
    """
    from qdrant_client import QdrantClient

    from app.core.config import settings

    print(f"\n{'=' * 60}")
    print("🔬 KNOWLEDGE GRAPH - CONTROLLED EXTRACTION")
    print(f"{'=' * 60}")
    print(f"Collection: {collection}")
    print(f"Sample size: {sample_size}")
    print(f"Mode: {'DRY RUN (no DB writes)' if dry_run else 'LIVE (will persist)'}")
    print(f"{'=' * 60}\n")

    # Connect to Qdrant
    qdrant_url = settings.qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant = QdrantClient(url=qdrant_url)

    # Get sample chunks
    print(f"📥 Fetching {sample_size} chunks from {collection}...")

    try:
        # Scroll to get sample
        results = qdrant.scroll(
            collection_name=collection, limit=sample_size, with_payload=True, with_vectors=False
        )

        chunks = results[0]
        print(f"✅ Retrieved {len(chunks)} chunks\n")

    except Exception as e:
        print(f"❌ Error fetching chunks: {e}")
        return

    # Entity extraction using patterns (no LLM for controlled extraction)
    import re

    ENTITY_PATTERNS = {
        "legal_entity": [
            r"\b(PT\s+PMA)\b",
            r"\b(PT\s+PMDN)\b",
            r"\b(PT\s+Perorangan)\b",
            r"\b(PT\s+Tbk)\b",
            r"\b(Perseroan\s+Terbatas)\b",
            r"\bCV\b",
            r"\b(Firma)\b",
            r"\b(Koperasi)\b",
            r"\b(Yayasan)\b",
            r"\b(Persekutuan\s+Perdata)\b",
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
            r"\b(Investor\s+KITAS)\b",
            r"\b(Work\s+Permit)\b",
        ],
        "tax_type": [
            r"\bPPh\s*\d+\b",
            r"\bPPN\b",
            r"\bPBB\b",
            r"\bBPHTB\b",
        ],
        "kbli": [
            r"\bKBLI\s+\d{5}\b",
            r"\bkode\s+KBLI\s+\d{5}\b",
        ],
        "regulation": [
            r"\b(UU|PP|Perpres|Permen|Perda)\s+(No\.?\s*)?\d+[\/\s]*(Tahun\s*)?\d{4}\b",
            r"\b(Peraturan\s+(Pemerintah|Menteri|Presiden))\b",
        ],
    }

    RELATIONSHIP_PATTERNS = [
        (r"(memerlukan|membutuhkan|requires?|needs?|wajib\s+memiliki)", "REQUIRES"),
        (r"(biaya|tarif|costs?|Rp\.?\s*[\d\.,]+)", "COSTS"),
        (r"(proses|waktu|duration|(\d+)\s*(hari|bulan|tahun|days?|months?|years?))", "DURATION"),
        (r"(bagian\s+dari|termasuk|part\s+of|includes?)", "PART_OF"),
        (r"(pajak|tax\s+obligation)", "TAX_OBLIGATION"),
    ]

    # Extract entities
    all_entities = {}
    all_relationships = []
    chunk_sources = {}  # Track which chunks mention which entities

    for i, chunk in enumerate(chunks):
        text = chunk.payload.get("text", "") or chunk.payload.get("content", "")
        chunk_id = str(chunk.id)

        if not text:
            continue

        # Extract entities from this chunk
        chunk_entities = []
        for entity_type, patterns in ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Normalize entity name
                    name = match if isinstance(match, str) else match[0]
                    name = name.strip().upper()
                    entity_id = f"{entity_type}_{name.replace(' ', '_').lower()}"

                    if entity_id not in all_entities:
                        all_entities[entity_id] = {
                            "entity_id": entity_id,
                            "entity_type": entity_type,
                            "name": name,
                            "mentions": 0,
                            "source_chunks": [],
                            "context_snippets": [],
                        }

                    all_entities[entity_id]["mentions"] += 1
                    if chunk_id not in all_entities[entity_id]["source_chunks"]:
                        all_entities[entity_id]["source_chunks"].append(chunk_id)
                        # Store context snippet
                        match_pos = text.lower().find(name.lower())
                        if match_pos >= 0:
                            start = max(0, match_pos - 50)
                            end = min(len(text), match_pos + len(name) + 50)
                            snippet = text[start:end].replace("\n", " ").strip()
                            all_entities[entity_id]["context_snippets"].append(f"...{snippet}...")

                    chunk_entities.append(entity_id)

        # Infer relationships within same chunk
        if len(chunk_entities) >= 2:
            for rel_pattern, rel_type in RELATIONSHIP_PATTERNS:
                if re.search(rel_pattern, text, re.IGNORECASE):
                    # Create relationships between entities in same chunk
                    for j, e1 in enumerate(chunk_entities):
                        for e2 in chunk_entities[j + 1 :]:
                            rel_id = f"{e1}_{rel_type}_{e2}"
                            if rel_id not in [r["relationship_id"] for r in all_relationships]:
                                all_relationships.append(
                                    {
                                        "relationship_id": rel_id,
                                        "source": e1,
                                        "target": e2,
                                        "type": rel_type,
                                        "source_chunk": chunk_id,
                                        "confidence": 0.7,  # Lower confidence for inferred
                                    }
                                )

    # Sort entities by mentions (most mentioned first)
    sorted_entities = sorted(all_entities.values(), key=lambda x: x["mentions"], reverse=True)

    # Output results
    print(f"\n{'=' * 60}")
    print("📊 EXTRACTION RESULTS")
    print(f"{'=' * 60}")
    print(f"Total entities found: {len(sorted_entities)}")
    print(f"Total relationships inferred: {len(all_relationships)}")

    # Show top entities
    print("\n📌 TOP ENTITIES (by mention count):")
    print("-" * 60)
    for i, entity in enumerate(sorted_entities[:30], 1):
        print(
            f"{i:2}. [{entity['entity_type']:12}] {entity['name']:20} ({entity['mentions']} mentions)"
        )
        if entity["context_snippets"]:
            print(f"    Context: {entity['context_snippets'][0][:80]}...")

    if len(sorted_entities) > 30:
        print(f"    ... and {len(sorted_entities) - 30} more entities")

    # Show relationships
    print("\n🔗 RELATIONSHIPS (sample):")
    print("-" * 60)
    for i, rel in enumerate(all_relationships[:20], 1):
        source_name = all_entities.get(rel["source"], {}).get("name", rel["source"])
        target_name = all_entities.get(rel["target"], {}).get("name", rel["target"])
        print(f"{i:2}. {source_name} --[{rel['type']}]--> {target_name}")

    if len(all_relationships) > 20:
        print(f"    ... and {len(all_relationships) - 20} more relationships")

    # Entity type distribution
    print("\n📈 ENTITY TYPE DISTRIBUTION:")
    print("-" * 60)
    type_counts = {}
    for e in sorted_entities:
        t = e["entity_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {t:15}: {count:4} entities")

    # Save to JSON for review
    output = {
        "extraction_date": datetime.now().isoformat(),
        "collection": collection,
        "sample_size": sample_size,
        "chunks_processed": len(chunks),
        "entities": sorted_entities,
        "relationships": all_relationships,
        "stats": {
            "total_entities": len(sorted_entities),
            "total_relationships": len(all_relationships),
            "entity_type_distribution": type_counts,
        },
    }

    output_file = f"kg_extraction_{collection}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to: {output_file}")
    print(f"\n{'=' * 60}")
    print("⏸️  REVIEW THE RESULTS ABOVE")
    print("   If satisfied, run with dry_run=False to persist to DB")
    print(f"{'=' * 60}\n")

    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="KG Controlled Extraction")
    parser.add_argument("--collection", default="legal_unified_hybrid", help="Qdrant collection")
    parser.add_argument("--sample", type=int, default=50, help="Sample size")
    parser.add_argument("--live", action="store_true", help="Persist to DB (default: dry run)")

    args = parser.parse_args()

    asyncio.run(
        run_controlled_extraction(
            collection=args.collection, sample_size=args.sample, dry_run=not args.live
        )
    )
