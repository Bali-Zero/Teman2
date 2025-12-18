#!/usr/bin/env python3
"""
Ingest Bali Zero Team Data into Qdrant

Ingests team member profiles into Qdrant for RAG retrieval.
This ensures queries like "Chi è il fondatore?" return accurate team information.
"""

import asyncio
import logging
import requests
import sys
import uuid
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "apps" / "backend-rag"
sys.path.insert(0, str(backend_path))

from backend.core.embeddings import EmbeddingsGenerator
from backend.core.qdrant_db import QdrantClient
from backend.data.team_members import TEAM_MEMBERS

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

COLLECTION_NAME = "bali_zero_team"


def build_team_member_text(member: dict) -> str:
    """Build searchable text description for team member"""

    # Build role description
    role_info = f"{member['name']} is the {member['role']} at Bali Zero"

    # Add department info
    dept_info = f"working in the {member['department']} department"

    # Add expertise
    expertise_info = f"with {member['expertise_level']} level expertise"

    # Add languages
    lang_names = {
        "it": "Italian",
        "id": "Indonesian",
        "en": "English",
        "jv": "Javanese",
        "ban": "Balinese",
        "uk": "Ukrainian",
        "ua": "Ukrainian",
        "su": "Sundanese",
    }
    languages = [lang_names.get(lang, lang) for lang in member.get("languages", [])]
    lang_info = f"speaking {', '.join(languages)}" if languages else ""

    # Build full description
    parts = [role_info, dept_info, expertise_info]
    if lang_info:
        parts.append(lang_info)

    description = f"{'. '.join(parts)}."

    # Add notes if available
    if member.get("notes"):
        description += f" {member['notes']}"

    # Add email contact
    description += f" Contact: {member['email']}"

    # Add special founder marker
    if member["role"] == "Founder":
        description = f"FOUNDER OF BALI ZERO: {description}"
    if member["role"] == "CEO":
        description = f"CEO OF BALI ZERO: {description}"

    return description


def create_collection_if_not_exists(
    qdrant_url: str, collection_name: str, vector_size: int = 1536
):
    """Create Qdrant collection if it doesn't exist"""
    try:
        # Check if collection exists
        check_url = f"{qdrant_url}/collections/{collection_name}"
        response = requests.get(check_url, timeout=10)

        if response.status_code == 200:
            logger.info(f"Collection '{collection_name}' already exists")
            return True

        # Create collection
        logger.info(f"Creating collection '{collection_name}'...")
        create_url = f"{qdrant_url}/collections/{collection_name}"
        payload = {"vectors": {"size": vector_size, "distance": "Cosine"}}

        response = requests.put(create_url, json=payload, timeout=30)

        if response.status_code == 200:
            logger.info(f"✅ Collection '{collection_name}' created successfully")
            return True
        else:
            logger.error(
                f"❌ Failed to create collection: {response.status_code} - {response.text}"
            )
            return False

    except Exception as e:
        logger.error(f"❌ Error creating collection: {e}")
        return False


async def main():
    """Ingest all team members into Qdrant"""
    try:
        logger.info("=" * 60)
        logger.info("BALI ZERO TEAM DATA INGESTION")
        logger.info("=" * 60)

        # Initialize services
        logger.info("Initializing Qdrant client and embeddings generator...")
        qdrant_client = QdrantClient(collection_name=COLLECTION_NAME)
        embedder = EmbeddingsGenerator()

        # Create collection if it doesn't exist
        if not create_collection_if_not_exists(
            qdrant_client.qdrant_url, COLLECTION_NAME
        ):
            logger.error("Failed to create collection")
            return 1

        # Build text descriptions for all team members
        logger.info(f"Processing {len(TEAM_MEMBERS)} team members...")
        texts = []
        metadatas = []
        ids = []

        for member in TEAM_MEMBERS:
            # Build searchable text
            text = build_team_member_text(member)
            texts.append(text)

            # Build metadata
            metadata = {
                "title": f"{member['name']} - {member['role']}",
                "source": "team_members",
                "category": "team",
                "department": member["department"],
                "role": member["role"],
                "name": member["name"],
                "email": member["email"],
                "expertise_level": member["expertise_level"],
                "min_level": 0,  # Public information
            }
            metadatas.append(metadata)

            # Use UUID as document ID (Qdrant requires UUID or integer)
            # Generate deterministic UUID from member ID
            member_uuid = uuid.uuid5(
                uuid.NAMESPACE_DNS, f"balizero.team.{member['id']}"
            )
            ids.append(str(member_uuid))

            logger.info(f"  ✓ {member['name']} ({member['role']})")

        # Generate embeddings
        logger.info("\nGenerating embeddings...")
        embeddings = embedder.generate_embeddings(texts)
        logger.info(f"Generated {len(embeddings)} embeddings")

        # Upsert to Qdrant
        logger.info(f"\nUpserting to Qdrant collection '{COLLECTION_NAME}'...")
        result = qdrant_client.upsert_documents(
            chunks=texts, embeddings=embeddings, metadatas=metadatas, ids=ids
        )

        if result.get("success"):
            logger.info("=" * 60)
            logger.info("✅ INGESTION SUCCESSFUL")
            logger.info("=" * 60)
            logger.info(f"Collection: {COLLECTION_NAME}")
            logger.info(f"Documents added: {result['documents_added']}")
            logger.info("")
            logger.info("Team queries should now work:")
            logger.info("  - 'Chi è il fondatore?' → Zero (Founder)")
            logger.info("  - 'Who is the CEO?' → Zainal Abidin")
            logger.info("  - 'Conosci il team?' → Full team roster")
            logger.info("=" * 60)
        else:
            logger.error(f"❌ Ingestion failed: {result.get('error')}")
            return 1

        return 0

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
