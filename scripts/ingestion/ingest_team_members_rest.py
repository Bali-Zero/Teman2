#!/usr/bin/env python3
"""
Ingest Team Members into Qdrant via REST API
--------------------------------------------
Creates bali_zero_team collection and ingests team_members.json
Uses REST API to avoid SSL/connection issues with Qdrant Python client.
"""

import hashlib
import json
import os
from pathlib import Path

import httpx
from openai import OpenAI

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLLECTION_NAME = "bali_zero_team"
VECTOR_SIZE = 1536  # text-embedding-3-small

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_PATH = SCRIPT_DIR.parent / "backend" / "data" / "team_members.json"


def get_embedding(text: str, client: OpenAI) -> list[float]:
    """Generate embedding using OpenAI."""
    response = client.embeddings.create(model="text-embedding-3-small", input=text)
    return response.data[0].embedding


def create_collection():
    """Create collection if it doesn't exist."""
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    # Check if collection exists
    resp = httpx.get(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}", headers=headers, timeout=30
    )

    if resp.status_code == 200:
        print(f"✅ Collection {COLLECTION_NAME} already exists")
        return True

    # Create collection
    payload = {"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}}

    resp = httpx.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        headers=headers,
        json=payload,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        print(f"✅ Created collection {COLLECTION_NAME}")
        return True
    else:
        print(f"❌ Failed to create collection: {resp.status_code} - {resp.text}")
        return False


def member_to_text(member: dict) -> str:
    """Convert member dict to searchable text."""
    parts = [
        f"Team Member: {member['name']}",
        f"Email: {member['email']}",
        f"Role: {member['role']}",
        f"Department: {member['department']}",
    ]

    if member.get("team"):
        parts.append(f"Team: {member['team']}")
    if member.get("location"):
        parts.append(f"Location: {member['location']}")
    if member.get("languages"):
        parts.append(f"Languages: {', '.join(member['languages'])}")
    if member.get("expertise_level"):
        parts.append(f"Expertise: {member['expertise_level']}")
    if member.get("traits"):
        parts.append(f"Traits: {', '.join(member['traits'])}")
    if member.get("notes"):
        parts.append(f"Notes: {member['notes']}")
    if member.get("religion"):
        parts.append(f"Religion: {member['religion']}")
    if member.get("age"):
        parts.append(f"Age: {member['age']}")

    # Add emotional preferences if available
    if member.get("emotional_preferences"):
        prefs = member["emotional_preferences"]
        parts.append(
            f"Communication style: tone={prefs.get('tone', 'professional')}, formality={prefs.get('formality', 'medium')}"
        )

    return "\n".join(parts)


def ingest_members():
    """Main ingestion function."""
    print("🚀 Starting Team Members Ingestion...")

    # Load data
    if not DATA_PATH.exists():
        print(f"❌ Data file not found: {DATA_PATH}")
        return

    with open(DATA_PATH, encoding="utf-8") as f:
        members = json.load(f)

    print(f"📊 Loaded {len(members)} team members")

    # Create collection
    if not create_collection():
        return

    # Initialize OpenAI
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not set")
        return

    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # Prepare points
    points = []
    for member in members:
        text = member_to_text(member)

        # Generate embedding
        try:
            embedding = get_embedding(text, openai_client)
        except Exception as e:
            print(f"❌ Failed to generate embedding for {member['name']}: {e}")
            continue

        # Create point
        point_id = hashlib.md5(member["email"].encode()).hexdigest()[:16]
        # Convert hex to integer for Qdrant
        point_id_int = int(point_id, 16) % (2**63)

        points.append(
            {
                "id": point_id_int,
                "vector": embedding,
                "payload": {
                    "text": text,
                    "member_id": member["id"],
                    "name": member["name"],
                    "email": member["email"],
                    "role": member["role"],
                    "department": member["department"],
                    "team": member.get("team", member["department"]),
                    "location": member.get("location", ""),
                    "languages": member.get("languages", []),
                    "traits": member.get("traits", []),
                    "notes": member.get("notes", ""),
                    "expertise_level": member.get("expertise_level", "intermediate"),
                    "source_type": "team_member",
                },
            }
        )
        print(f"  ✓ Prepared: {member['name']} ({member['role']})")

    # Upsert to Qdrant
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    # Batch upsert
    batch_size = 10
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]

        resp = httpx.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
            headers=headers,
            json={"points": batch},
            timeout=60,
        )

        if resp.status_code in (200, 201):
            print(f"  ✅ Upserted batch {i // batch_size + 1} ({len(batch)} points)")
        else:
            print(
                f"  ❌ Failed batch {i // batch_size + 1}: {resp.status_code} - {resp.text}"
            )

    # Verify
    resp = httpx.get(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}", headers=headers, timeout=30
    )

    if resp.status_code == 200:
        info = resp.json()
        count = info.get("result", {}).get("points_count", 0)
        print(
            f"\n✅ Ingestion complete! Collection {COLLECTION_NAME} has {count} points"
        )
    else:
        print(f"\n⚠️ Could not verify collection: {resp.status_code}")


if __name__ == "__main__":
    ingest_members()
