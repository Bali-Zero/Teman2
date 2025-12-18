#!/usr/bin/env python3
"""
DEEP AUDIT OF ALL QDRANT COLLECTIONS
=====================================
Comprehensive scan for:
- Duplicates (by content hash)
- Empty/near-empty documents
- Malformed data
- Suspicious patterns
- Data quality metrics

Output: scripts/audit_reports/deep_audit_TIMESTAMP.md
"""

import asyncio
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

REPORT_DIR = "scripts/audit_reports"
os.makedirs(REPORT_DIR, exist_ok=True)


async def get_all_collections(client, headers):
    """Get list of all collections"""
    resp = await client.get(f"{QDRANT_URL}/collections", headers=headers, timeout=30)
    if resp.status_code == 200:
        return [c["name"] for c in resp.json().get("result", {}).get("collections", [])]
    return []


async def get_collection_stats(client, headers, collection):
    """Get collection statistics"""
    resp = await client.get(
        f"{QDRANT_URL}/collections/{collection}", headers=headers, timeout=30
    )
    if resp.status_code == 200:
        result = resp.json().get("result", {})
        return {
            "points_count": result.get("points_count", 0),
            "status": result.get("status", "unknown"),
            "vectors_count": result.get("vectors_count", 0),
        }
    return {"points_count": 0, "status": "error"}


async def scroll_collection(client, headers, collection, limit=100, offset=None):
    """Scroll through collection"""
    payload = {"limit": limit, "with_payload": True, "with_vector": False}
    if offset:
        payload["offset"] = offset

    resp = await client.post(
        f"{QDRANT_URL}/collections/{collection}/points/scroll",
        headers=headers,
        json=payload,
        timeout=60,
    )

    if resp.status_code == 200:
        data = resp.json().get("result", {})
        return data.get("points", []), data.get("next_page_offset")
    return [], None


async def audit_collection(client, headers, collection):
    """Deep audit a single collection"""
    print(f"  Auditing {collection}...")

    stats = await get_collection_stats(client, headers, collection)
    total_points = stats["points_count"]

    if total_points == 0:
        return {
            "collection": collection,
            "total_documents": 0,
            "status": stats["status"],
            "issues": ["Empty collection"],
            "duplicates": [],
            "empty_docs": [],
            "malformed": [],
            "quality_score": 0,
        }

    # Audit metrics
    content_hashes = defaultdict(list)  # hash -> [ids]
    empty_docs = []
    short_docs = []  # < 50 chars
    malformed_docs = []
    docs_with_no_metadata = []
    text_lengths = []

    # Suspicious patterns
    suspicious_patterns = {
        "placeholder_text": r"\[.*placeholder.*\]|TODO|FIXME|XXX",
        "encoding_issues": r"[�□■]|\\x[0-9a-f]{2}",
        "excessive_whitespace": r"\s{10,}",
        "html_tags": r"<[^>]+>",
        "json_fragments": r"^\s*[\{\[]",
    }
    pattern_matches = {k: [] for k in suspicious_patterns}

    offset = None
    scanned = 0

    while scanned < total_points:
        points, next_offset = await scroll_collection(
            client, headers, collection, limit=100, offset=offset
        )

        if not points:
            break

        for point in points:
            scanned += 1
            point_id = str(point["id"])
            payload = point.get("payload", {})
            text = payload.get("text", "")
            metadata = payload.get("metadata", {})

            # Check text length
            text_len = len(text.strip())
            text_lengths.append(text_len)

            if text_len == 0:
                empty_docs.append(point_id)
            elif text_len < 50:
                short_docs.append(
                    {"id": point_id, "len": text_len, "preview": text[:50]}
                )

            # Check for duplicates
            if text_len > 0:
                content_hash = hashlib.md5(text.encode()).hexdigest()
                content_hashes[content_hash].append(point_id)

            # Check metadata
            if not metadata:
                docs_with_no_metadata.append(point_id)

            # Check for malformed JSON in text
            try:
                if text.strip().startswith("{") or text.strip().startswith("["):
                    json.loads(text)
                    malformed_docs.append(
                        {"id": point_id, "reason": "Raw JSON as content"}
                    )
            except:
                pass

            # Check suspicious patterns
            for pattern_name, pattern in suspicious_patterns.items():
                if re.search(pattern, text, re.IGNORECASE):
                    pattern_matches[pattern_name].append(point_id)

        offset = next_offset
        if not offset:
            break

    # Find actual duplicates (more than 1 doc with same hash)
    duplicates = {h: ids for h, ids in content_hashes.items() if len(ids) > 1}
    duplicate_count = sum(len(ids) - 1 for ids in duplicates.values())

    # Calculate quality score (0-100)
    issues_count = (
        len(empty_docs) * 10
        + len(short_docs) * 2
        + duplicate_count * 5
        + len(malformed_docs) * 3
        + sum(len(v) for v in pattern_matches.values())
    )
    quality_score = max(0, 100 - (issues_count / max(1, total_points) * 100))

    # Compile issues
    issues = []
    if empty_docs:
        issues.append(f"{len(empty_docs)} empty documents")
    if short_docs:
        issues.append(f"{len(short_docs)} very short documents (<50 chars)")
    if duplicate_count:
        issues.append(f"{duplicate_count} duplicate documents")
    if malformed_docs:
        issues.append(f"{len(malformed_docs)} malformed documents")
    if docs_with_no_metadata:
        issues.append(f"{len(docs_with_no_metadata)} documents without metadata")
    for pattern_name, matches in pattern_matches.items():
        if matches:
            issues.append(f"{len(matches)} docs with {pattern_name}")

    return {
        "collection": collection,
        "total_documents": total_points,
        "scanned": scanned,
        "status": stats["status"],
        "quality_score": round(quality_score, 1),
        "avg_text_length": round(sum(text_lengths) / max(1, len(text_lengths)), 1),
        "issues": issues if issues else ["No issues found"],
        "duplicates": {h: ids for h, ids in list(duplicates.items())[:10]},  # First 10
        "duplicate_total": duplicate_count,
        "empty_docs": empty_docs[:20],
        "short_docs": short_docs[:10],
        "malformed": malformed_docs[:10],
        "no_metadata": len(docs_with_no_metadata),
        "pattern_matches": {k: len(v) for k, v in pattern_matches.items()},
    }


async def main():
    """Run deep audit on all collections"""
    print("=" * 70)
    print("🔍 DEEP AUDIT OF ALL QDRANT COLLECTIONS")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Qdrant URL: {QDRANT_URL}\n")

    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        collections = await get_all_collections(client, headers)
        print(f"Found {len(collections)} collections\n")

        results = []
        for collection in collections:
            try:
                result = await audit_collection(client, headers, collection)
                results.append(result)
                print(
                    f"    ✓ {collection}: {result['total_documents']} docs, score: {result['quality_score']}"
                )
            except Exception as e:
                print(f"    ✗ {collection}: Error - {e}")
                results.append(
                    {"collection": collection, "error": str(e), "quality_score": 0}
                )

    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{REPORT_DIR}/deep_audit_{timestamp}.md"

    with open(report_path, "w") as f:
        f.write("# 🔍 Deep Audit Report - All Qdrant Collections\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n")
        f.write(f"**Qdrant URL:** {QDRANT_URL}\n\n")

        # Summary table
        f.write("## Summary\n\n")
        f.write("| Collection | Documents | Quality Score | Issues |\n")
        f.write("|------------|-----------|---------------|--------|\n")

        for r in sorted(results, key=lambda x: x.get("quality_score", 0)):
            score = r.get("quality_score", 0)
            score_emoji = "🟢" if score >= 90 else "🟡" if score >= 70 else "🔴"
            issues = (
                len(r.get("issues", []))
                if r.get("issues", [""])[0] != "No issues found"
                else 0
            )
            f.write(
                f"| {r['collection']} | {r.get('total_documents', 0):,} | {score_emoji} {score} | {issues} |\n"
            )

        # Detailed results
        f.write("\n## Detailed Results\n\n")

        for r in results:
            f.write(f"### {r['collection']}\n\n")

            if "error" in r:
                f.write(f"**Error:** {r['error']}\n\n")
                continue

            f.write(f"- **Documents:** {r.get('total_documents', 0):,}\n")
            f.write(f"- **Quality Score:** {r.get('quality_score', 0)}/100\n")
            f.write(f"- **Avg Text Length:** {r.get('avg_text_length', 0)} chars\n")
            f.write(f"- **Status:** {r.get('status', 'unknown')}\n\n")

            f.write("**Issues:**\n")
            for issue in r.get("issues", []):
                f.write(f"- {issue}\n")

            if r.get("duplicate_total", 0) > 0:
                f.write(f"\n**Duplicates:** {r['duplicate_total']} total\n")
                f.write("```\n")
                for h, ids in list(r.get("duplicates", {}).items())[:5]:
                    f.write(f"Hash {h[:8]}...: {ids}\n")
                f.write("```\n")

            if r.get("empty_docs"):
                f.write("\n**Empty Document IDs (first 10):**\n")
                f.write(f"```\n{r['empty_docs'][:10]}\n```\n")

            if r.get("short_docs"):
                f.write("\n**Short Documents (first 5):**\n")
                for doc in r["short_docs"][:5]:
                    f.write(
                        f"- `{doc['id']}`: {doc['len']} chars - \"{doc['preview']}...\"\n"
                    )

            f.write("\n---\n\n")

        # Recommendations
        f.write("## Recommendations\n\n")

        total_duplicates = sum(r.get("duplicate_total", 0) for r in results)
        total_empty = sum(len(r.get("empty_docs", [])) for r in results)

        if total_duplicates > 0:
            f.write(
                f"1. **Remove {total_duplicates} duplicate documents** across collections\n"
            )
        if total_empty > 0:
            f.write(f"2. **Remove {total_empty} empty documents** across collections\n")

        low_quality = [r for r in results if r.get("quality_score", 100) < 70]
        if low_quality:
            f.write(
                f"3. **Review low-quality collections:** {[r['collection'] for r in low_quality]}\n"
            )

        f.write("\n---\n*Report generated by deep_audit_all_collections.py*\n")

    print(f"\n✅ Report saved to: {report_path}")
    return report_path


if __name__ == "__main__":
    asyncio.run(main())
