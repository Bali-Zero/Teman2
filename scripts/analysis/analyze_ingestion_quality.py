import asyncio
import asyncpg
import json
import textwrap

DB_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"


async def analyze_quality():
    print("🔍 DEEP QUALITY ANALYSIS OF INGESTED DOCUMENTS\n" + "=" * 60)

    try:
        conn = await asyncpg.connect(DB_URL)

        # 1. Get a sample of documents from each collection
        collections = [
            "legal_unified",
            "visa_oracle",
            "tax_genius",
            "litigation_oracle",
            "kbli_unified",
        ]

        for col in collections:
            print(f"\n📂 COLLECTION: {col}")
            print("-" * 40)

            # Fetch up to 3 random docs
            rows = await conn.fetch(
                """
                SELECT id, title, full_text, metadata
                FROM parent_documents
                WHERE metadata->>'collection' = $1
                ORDER BY RANDOM() LIMIT 2
            """,
                col,
            )

            if not rows:
                print("   (No documents found)")
                continue

            for r in rows:
                meta = json.loads(r["metadata"])
                text = r["full_text"]

                print(f"   📄 Title: {r['title']}")
                print(f"      ID: {r['id']}")
                print(f"      Type: {meta.get('type', 'N/A')}")
                print(f"      Length: {len(text)} chars")

                # Quality Checks
                issues = []
                if len(text) < 100:
                    issues.append("⚠️ Very short text")
                if "Lorem ipsum" in text:
                    issues.append("⚠️ Lorem Ipsum detected")
                if text.count("") > 10:
                    issues.append("⚠️ Encoding errors detected")

                if issues:
                    print(f"      Issues: {', '.join(issues)}")
                else:
                    print("      ✅ Basic Quality Check Passed")

                # Show snippet
                snippet = textwrap.shorten(text, width=200, placeholder="...")
                print(f"      Snippet: {snippet}")
                print("")

        # 2. Check for Duplicates (Title based)
        print("\n👯 DUPLICATE CHECK (By Title)")
        print("-" * 40)
        dupes = await conn.fetch(
            """
            SELECT title, COUNT(*) as cnt
            FROM parent_documents
            GROUP BY title
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            LIMIT 5
        """
        )

        if dupes:
            for d in dupes:
                print(f"   ⚠️ '{d['title']}' appears {d['cnt']} times")
        else:
            print("   ✅ No title duplicates found in sample.")

        await conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(analyze_quality())
