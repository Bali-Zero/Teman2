#!/usr/bin/env python3
"""
Ingest C7 Arts & Culture Visa Training Data into visa_oracle collection.

Usage:
    python scripts/ingestion/ingest_c7_visas.py

This script:
1. Reads the C7 training data markdown file
2. Chunks it by sections
3. Calls the oracle ingest API to add to visa_oracle
"""

import re
import requests
import sys
from pathlib import Path

# Configuration
API_URL = "https://nuzantara-rag.fly.dev/api/oracle/ingest"
COLLECTION = "visa_oracle"
TRAINING_FILE = (
    Path(__file__).parent.parent.parent
    / "apps/backend-rag/training-data/visa/visa_015_c7_arts_culture_visas.md"
)


def chunk_markdown(content: str) -> list[dict]:
    """Split markdown into semantic chunks by ## headers."""
    chunks = []

    # Split by ## headers
    sections = re.split(r"\n(?=## )", content)

    for section in sections:
        section = section.strip()
        if not section or len(section) < 50:
            continue

        # Extract section title
        title_match = re.match(r"^##\s+(.+?)(?:\n|$)", section)
        title = title_match.group(1) if title_match else "C7 Visa Information"

        # Determine visa code from content
        visa_code = "C7"
        if "C7A" in section[:200]:
            visa_code = "C7A"
        elif "C7B" in section[:200]:
            visa_code = "C7B"
        elif "C7C" in section[:200]:
            visa_code = "C7C"

        # Create chunk with metadata
        chunk = {
            "content": section,
            "metadata": {
                "visa_code": visa_code,
                "title": title,
                "source_type": "training_data",
                "source_file": "visa_015_c7_arts_culture_visas.md",
                "category": "arts_culture",
                "document_type": "visa_guide",
            },
        }
        chunks.append(chunk)

    # Also create sub-chunks for very long sections
    final_chunks = []
    for chunk in chunks:
        content = chunk["content"]
        if len(content) > 2000:
            # Split long sections by ### headers or paragraphs
            sub_sections = re.split(r"\n(?=### |\n\n)", content)
            for i, sub in enumerate(sub_sections):
                sub = sub.strip()
                if len(sub) > 100:
                    sub_chunk = {
                        "content": sub,
                        "metadata": {**chunk["metadata"], "chunk_index": i},
                    }
                    final_chunks.append(sub_chunk)
        else:
            final_chunks.append(chunk)

    return final_chunks


def main():
    print(f"📂 Reading training file: {TRAINING_FILE}")

    if not TRAINING_FILE.exists():
        print(f"❌ File not found: {TRAINING_FILE}")
        sys.exit(1)

    # Read markdown content
    content = TRAINING_FILE.read_text(encoding="utf-8")
    print(f"   Read {len(content):,} characters")

    # Chunk the content
    chunks = chunk_markdown(content)
    print(f"📦 Created {len(chunks)} chunks")

    # Show preview
    for i, chunk in enumerate(chunks[:3]):
        preview = chunk["content"][:100].replace("\n", " ")
        print(f"   [{i + 1}] {chunk['metadata']['visa_code']}: {preview}...")

    if len(chunks) > 3:
        print(f"   ... and {len(chunks) - 3} more chunks")

    # Prepare API request
    payload = {"collection": COLLECTION, "documents": chunks, "batch_size": 100}

    print(f"\n🚀 Ingesting to {COLLECTION}...")

    try:
        response = requests.post(API_URL, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            print("✅ Success!")
            print(f"   Documents ingested: {result.get('documents_ingested', 0)}")
            print(f"   Execution time: {result.get('execution_time_ms', 0):.0f}ms")
            print(f"   Message: {result.get('message', 'OK')}")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text}")
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        sys.exit(1)

    print("\n🎉 C7 Visa training data ingested successfully!")


if __name__ == "__main__":
    main()
