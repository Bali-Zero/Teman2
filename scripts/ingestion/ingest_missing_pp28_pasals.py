#!/usr/bin/env python3
"""
Ingest Missing PP 28/2025 Pasals into Qdrant

This script:
1. Parses the PP 28/2025 batang tubuh (main body) text
2. Extracts pasals with their BAB context
3. Filters only missing pasals (not in Qdrant)
4. Generates embeddings using OpenAI
5. Uploads to legal_unified_hybrid collection with proper metadata
"""

import os
import re
import uuid
import json
import requests
from typing import Optional
from openai import OpenAI

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLLECTION_NAME = "legal_unified_hybrid"

# BAB ranges based on PP 28/2025 structure
BAB_RANGES = {
    "BAB I - KETENTUAN UMUM": (1, 10),
    "BAB II - PERSYARATAN DASAR": (11, 124),
    "BAB III - PERIZINAN BERUSAHA": (125, 133),
    "BAB IV - PERIZINAN BERUSAHA UNTUK MENUNJANG KEGIATAN USAHA": (134, 137),
    "BAB V - NORMA, STANDAR, PROSEDUR, DAN KRITERIA": (138, 189),
    "BAB VI - LAYANAN SISTEM PERIZINAN BERUSAHA TERINTEGRASI SECARA ELEKTRONIK": (190, 234),
    "BAB VII - PENGAWASAN": (235, 347),
    "BAB VIII - EVALUASI DAN REFORMASI KEBIJAKAN": (348, 349),
    "BAB IX - PENDANAAN": (350, 350),
    "BAB X - PENYELESAIAN PERMASALAHAN DAN HAMBATAN": (351, 352),
    "BAB XI - SANKSI": (353, 543),
    "BAB XII - KETENTUAN LAIN-LAIN": (544, 546),
    "BAB XIII - KETENTUAN PERALIHAN": (547, 548),
    "BAB XIV - KETENTUAN PENUTUP": (549, 552),
}


def get_bab_for_pasal(pasal_num: int) -> tuple[str, str]:
    """Get BAB title and chapter_id for a pasal number."""
    for bab_title, (start, end) in BAB_RANGES.items():
        if start <= pasal_num <= end:
            # Extract BAB number (e.g., "BAB XI" -> "XI")
            bab_num = bab_title.split(" - ")[0].replace("BAB ", "")
            chapter_id = f"PP_28_2025_BAB_{bab_num}"
            return bab_title, chapter_id
    return "UNKNOWN", "PP_28_2025_UNKNOWN"


def get_existing_pasals() -> set[int]:
    """Get pasals already in Qdrant."""
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
    all_pasals = set()
    offset = None

    while True:
        body = {
            "limit": 100,
            "with_payload": True,
            "filter": {
                "must": [
                    {"key": "metadata.legal_type", "match": {"value": "PP"}},
                    {"key": "metadata.legal_number", "match": {"value": "28"}},
                    {"key": "metadata.legal_year", "match": {"value": "2025"}}
                ]
            }
        }
        if offset:
            body["offset"] = offset

        resp = requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
            json=body,
            headers=headers
        )

        if resp.status_code != 200:
            print(f"Error from Qdrant: {resp.status_code} - {resp.text[:200]}")
            break

        try:
            data = resp.json().get("result", {})
        except Exception as e:
            print(f"JSON parse error: {e}")
            break
        points = data.get("points", [])

        for p in points:
            meta = p["payload"].get("metadata", {})
            pasal = meta.get("pasal_number")
            if pasal:
                try:
                    all_pasals.add(int(pasal))
                except:
                    pass

        offset = data.get("next_page_offset")
        if not offset or len(points) == 0:
            break

    return all_pasals


def parse_pasals(text: str) -> dict[int, str]:
    """Parse pasals from text, extracting full content for each."""
    pasals = {}

    # Split by "Pasal X" pattern
    pasal_pattern = r'(Pasal\s+(\d+))'

    # Find all pasal positions
    matches = list(re.finditer(pasal_pattern, text))

    for i, match in enumerate(matches):
        pasal_num = int(match.group(2))
        start_pos = match.start()

        # End position is start of next pasal or end of text
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(text)

        # Extract content
        content = text[start_pos:end_pos].strip()

        # Clean up content
        content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
        content = content[:3000]  # Limit length

        # Store only if we have meaningful content
        if len(content) > 50:
            pasals[pasal_num] = content

    return pasals


def generate_embedding(text: str, client: OpenAI) -> list[float]:
    """Generate embedding using OpenAI."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def upload_to_qdrant(points: list[dict]) -> bool:
    """Upload points to Qdrant."""
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    # Format for named vectors
    formatted_points = []
    for p in points:
        formatted_points.append({
            "id": p["id"],
            "vector": {
                "dense": p["vector"]
            },
            "payload": p["payload"]
        })

    resp = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
        json={"points": formatted_points},
        headers=headers
    )

    return resp.status_code == 200


def main():
    # Load text
    text_file = "/tmp/PP_28_2025_text.txt"
    if not os.path.exists(text_file):
        print(f"Error: {text_file} not found. Run pdftotext first.")
        return

    with open(text_file, "r") as f:
        text = f.read()

    print(f"Loaded {len(text):,} chars from {text_file}")

    # Parse all pasals
    all_pasals = parse_pasals(text)
    print(f"Parsed {len(all_pasals)} pasals from text")

    # Get existing pasals
    existing = get_existing_pasals()
    print(f"Found {len(existing)} pasals already in Qdrant")

    # Find missing
    missing_nums = set(all_pasals.keys()) - existing
    print(f"Missing pasals to ingest: {len(missing_nums)}")

    if not missing_nums:
        print("No missing pasals to ingest!")
        return

    # Initialize OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Generate embeddings and prepare points
    points = []
    for pasal_num in sorted(missing_nums):
        content = all_pasals[pasal_num]
        bab_title, chapter_id = get_bab_for_pasal(pasal_num)

        # Generate embedding
        embedding = generate_embedding(content, client)

        # Create metadata
        metadata = {
            "book_title": "PP No 28 Tahun 2025 Tentang Penyelenggaraan Perizinan Berusaha Berbasis Risiko",
            "book_author": "Pemerintah Indonesia",
            "category": "perizinan",
            "tier": "A",
            "min_level": 1,
            "language": "id",
            "file_path": "JDIH_BP2MI/PP_28_2025.pdf",
            "doc_type": "legal",
            "legal_type": "PP",
            "legal_number": "28",
            "legal_year": "2025",
            "legal_topic": "Penyelenggaraan Perizinan Berusaha Berbasis Risiko",
            "legal_status": "berlaku",
            "type_abbrev": "PP",
            "number": "28",
            "year": "2025",
            "topic": "PBBR",
            "pasal_number": str(pasal_num),
            "document_id": "PP_28_2025",
            "chapter_id": chapter_id,
            "hierarchy_path": f"PP_28_2025/{chapter_id.split('_')[-1]}/Pasal_{pasal_num}",
            "hierarchy_level": 3,
            "bab_title": bab_title,
            "chunk_id": str(uuid.uuid4()),
            "has_ayat": "ayat" in content.lower(),
        }

        point = {
            "id": str(uuid.uuid4()),
            "vector": embedding,
            "payload": {
                "text": content,
                "metadata": metadata
            }
        }
        points.append(point)

        print(f"  Processed Pasal {pasal_num} ({bab_title[:30]}...)")

        # Upload in batches of 50
        if len(points) >= 50:
            print(f"  Uploading batch of {len(points)} points...")
            if upload_to_qdrant(points):
                print(f"  Uploaded successfully!")
            else:
                print(f"  Upload failed!")
            points = []

    # Upload remaining
    if points:
        print(f"Uploading final batch of {len(points)} points...")
        if upload_to_qdrant(points):
            print(f"Uploaded successfully!")
        else:
            print(f"Upload failed!")

    print(f"\n✅ Ingestion complete! Added {len(missing_nums)} missing pasals.")


if __name__ == "__main__":
    main()
