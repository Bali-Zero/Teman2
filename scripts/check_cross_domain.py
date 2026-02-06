#!/usr/bin/env python3
"""Check cross-domain relationships in KG (Visa, TKA, Tax, KBLI)."""

import os
import asyncio
import asyncpg


async def check_cross_domain():
    print("=" * 70)
    print("🔍 VERIFICA RELAZIONI CROSS-DOMAIN NEL KG")
    print("=" * 70)

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    # 1. All entity types
    print("\n[1] TUTTI I TIPI DI ENTITÀ")
    print("-" * 50)
    types = await conn.fetch("""
        SELECT entity_type, COUNT(*) as cnt
        FROM kg_nodes GROUP BY entity_type ORDER BY cnt DESC
    """)
    for t in types:
        print(f"  {t['entity_type']}: {t['cnt']}")

    # 2. Visa-related nodes
    print("\n[2] NODI VISA")
    print("-" * 50)
    visas = await conn.fetch("""
        SELECT entity_id, name, entity_type FROM kg_nodes
        WHERE entity_type IN ('visa_type', 'visa', 'immigration_doc')
        OR name ILIKE '%visa%' OR name ILIKE '%kitas%' OR name ILIKE '%kitap%'
        LIMIT 15
    """)
    print(f"Found {len(visas)} visa-related nodes:")
    for v in visas:
        print(f"  [{v['entity_type']}] {v['name'][:50]}")

    # 3. TKA/work permit nodes
    print("\n[3] NODI TKA / WORK PERMIT")
    print("-" * 50)
    tka = await conn.fetch("""
        SELECT entity_id, name, entity_type FROM kg_nodes
        WHERE name ILIKE '%TKA%' OR name ILIKE '%tenaga kerja asing%'
        OR name ILIKE '%work permit%' OR name ILIKE '%RPTKA%' OR name ILIKE '%IMTA%'
        LIMIT 15
    """)
    print(f"Found {len(tka)} TKA-related nodes:")
    for t in tka:
        print(f"  [{t['entity_type']}] {t['name'][:50]}")

    # 4. Tax-related nodes
    print("\n[4] NODI TAX / PAJAK")
    print("-" * 50)
    tax = await conn.fetch("""
        SELECT entity_id, name, entity_type FROM kg_nodes
        WHERE entity_type = 'tax' OR name ILIKE '%pajak%' OR name ILIKE '%tax%'
        OR name ILIKE '%NPWP%' OR name ILIKE '%PPh%' OR name ILIKE '%PPN%'
        LIMIT 15
    """)
    print(f"Found {len(tax)} tax-related nodes:")
    for t in tax:
        print(f"  [{t['entity_type']}] {t['name'][:50]}")

    # 5. Company type nodes
    print("\n[5] NODI COMPANY TYPE")
    print("-" * 50)
    company = await conn.fetch("""
        SELECT entity_id, name, entity_type FROM kg_nodes
        WHERE entity_type = 'company_type'
        OR name ILIKE '%PT PMA%' OR name ILIKE '%PT PMDN%'
        LIMIT 15
    """)
    print(f"Found {len(company)} company-related nodes:")
    for c in company:
        print(f"  [{c['entity_type']}] {c['name'][:50]}")

    # 6. Cross-domain relationships
    print("\n[6] RELAZIONI CROSS-DOMAIN")
    print("-" * 50)

    # KBLI → Company
    kbli_company = await conn.fetch("""
        SELECT e.relationship_type, COUNT(*) as cnt
        FROM kg_edges e
        JOIN kg_nodes s ON e.source_entity_id = s.entity_id
        JOIN kg_nodes t ON e.target_entity_id = t.entity_id
        WHERE s.entity_type = 'kbli' AND t.entity_type = 'company_type'
        GROUP BY e.relationship_type
    """)
    print("\nKBLI → Company Type:")
    for r in kbli_company:
        print(f"  {r['relationship_type']}: {r['cnt']}")

    # Visa → anything
    visa_rels = await conn.fetch("""
        SELECT e.relationship_type, t.entity_type as target_type, COUNT(*) as cnt
        FROM kg_edges e
        JOIN kg_nodes s ON e.source_entity_id = s.entity_id
        JOIN kg_nodes t ON e.target_entity_id = t.entity_id
        WHERE s.entity_type IN ('visa_type', 'visa')
        GROUP BY e.relationship_type, t.entity_type
    """)
    print("\nVisa → (target types):")
    for r in visa_rels:
        print(f"  --[{r['relationship_type']}]--> {r['target_type']}: {r['cnt']}")

    # 7. Source collections for cross-domain data
    print("\n[7] SORGENTI DATI")
    print("-" * 50)
    sources = await conn.fetch("""
        SELECT entity_type, source_collection, COUNT(*) as cnt
        FROM kg_nodes
        WHERE entity_type IN ('visa_type', 'visa', 'tax', 'company_type', 'immigration_doc', 'permit_type', 'kbli')
        GROUP BY entity_type, source_collection ORDER BY entity_type, cnt DESC
    """)
    current_type = None
    for s in sources:
        if s["entity_type"] != current_type:
            current_type = s["entity_type"]
            print(f"\n  {current_type}:")
        coll = s["source_collection"] or "null"
        print(f"    - {coll}: {s['cnt']}")

    # 8. Check Qdrant collections for visa/tax data
    print("\n[8] SUMMARY")
    print("-" * 50)
    summary = await conn.fetch("""
        SELECT
            SUM(CASE WHEN entity_type = 'kbli' THEN 1 ELSE 0 END) as kbli,
            SUM(CASE WHEN entity_type IN ('visa_type', 'visa') THEN 1 ELSE 0 END) as visa,
            SUM(CASE WHEN entity_type = 'company_type' THEN 1 ELSE 0 END) as company,
            SUM(CASE WHEN entity_type = 'tax' THEN 1 ELSE 0 END) as tax,
            SUM(CASE WHEN entity_type = 'immigration_doc' THEN 1 ELSE 0 END) as immigration
        FROM kg_nodes
    """)
    s = summary[0]
    print(f"  KBLI nodes: {s['kbli']}")
    print(f"  Visa nodes: {s['visa']}")
    print(f"  Company nodes: {s['company']}")
    print(f"  Tax nodes: {s['tax']}")
    print(f"  Immigration docs: {s['immigration']}")

    await conn.close()
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(check_cross_domain())
