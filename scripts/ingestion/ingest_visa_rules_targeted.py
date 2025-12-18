#!/usr/bin/env python3
"""
Ingest Visa Rules from raw_laws_targeted into visa_oracle collection.

This script ingests the official visa information scraped from imigrasi.go.id
into the existing visa_oracle Qdrant collection, using the same metadata format.
"""

import asyncio
import logging
import os
import re
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
COLLECTION_NAME = "visa_oracle"
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions

# Path to visa rules
VISA_RULES_DIR = (
    Path(__file__).parent.parent.parent / "scraper" / "data" / "raw_laws_targeted"
)


def clean_text(text: str) -> str:
    """Clean and normalize text from scraped files."""
    # Remove excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" +", " ", text)
    # Remove navigation menu items
    text = re.sub(
        r"^(Menu|Beranda|Warga Negara|Informasi|FAQ|Situs Terkait).*$",
        "",
        text,
        flags=re.MULTILINE,
    )
    return text.strip()


def extract_visa_code(filename: str) -> str:
    """Extract visa code from filename like visa_d12-visa-pra-investasi.txt -> D12"""
    match = re.match(r"visa_([a-z0-9]+)-", filename.lower())
    if match:
        return match.group(1).upper()
    return filename


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence end
            for sep in [". ", ".\n", "\n\n"]:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start + chunk_size // 2:
                    end = last_sep + len(sep)
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]


def generate_hyde_questions(text: str, visa_code: str) -> list[str]:
    """Generate HyDE-style questions for better retrieval."""
    questions = []

    # Generic questions based on visa code
    questions.append(f"Apa itu visa {visa_code}? What is {visa_code} visa?")
    questions.append(f"Berapa lama bisa tinggal dengan visa {visa_code}?")
    questions.append(f"How long can I stay with {visa_code} visa?")

    # Extract specific info from text
    if "180 hari" in text or "180 days" in text:
        questions.append(
            f"Berapa hari bisa stay dengan {visa_code}? Is it 60 or 180 days?"
        )

    if "multiple" in text.lower() or "beberapa kali" in text.lower():
        questions.append(f"Is {visa_code} single or multiple entry?")

    if "sponsor" in text.lower() or "penjamin" in text.lower():
        questions.append(f"Do I need a sponsor for {visa_code} visa?")

    return questions[:5]  # Max 5 questions


def get_embeddings(texts: list[str], client: OpenAI) -> list[list[float]]:
    """Get embeddings for a list of texts."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


async def upsert_points_rest(
    points: list[dict], http_client: httpx.AsyncClient
) -> bool:
    """Upsert points using REST API."""
    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points"
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    payload = {"points": points}

    try:
        response = await http_client.put(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Upsert failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Upsert error: {e}")
        return False


async def ingest_visa_file(
    file_path: Path, http_client: httpx.AsyncClient, openai_client: OpenAI
) -> int:
    """Ingest a single visa rules file."""
    logger.info(f"Processing: {file_path.name}")

    try:
        # Read file
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Extract metadata
        visa_code = extract_visa_code(file_path.name)

        # Extract title from content
        title_match = re.search(r"Halaman:\s*(.+)", content)
        title = title_match.group(1).strip() if title_match else f"Visa {visa_code}"

        # Clean and chunk text
        cleaned = clean_text(content)
        chunks = chunk_text(cleaned, chunk_size=1500, overlap=200)

        if not chunks:
            logger.warning(f"No content found in {file_path.name}")
            return 0

        # Prepare points
        points = []
        parent_id = f"visa_targeted_{visa_code.lower()}"

        # Get embeddings for all chunks
        embeddings = get_embeddings(chunks, openai_client)

        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Generate HyDE questions
            hyde_questions = generate_hyde_questions(chunk, visa_code)

            # Create point
            point_id = str(uuid.uuid4())

            point = {
                "id": point_id,
                "vector": embedding,
                "payload": {
                    "text": chunk,
                    "parent_id": parent_id,
                    "chunk_index": idx,
                    "hyde_questions": hyde_questions,
                    "source_file": file_path.name,
                    "title": title,
                    "visa_code": visa_code,
                    "source_type": "imigrasi_official",
                },
            }
            points.append(point)

        # Upsert to Qdrant via REST
        success = await upsert_points_rest(points, http_client)

        if success:
            logger.info(f"  ✅ Ingested {len(points)} chunks for {visa_code}")
            return len(points)
        else:
            return 0

    except Exception as e:
        logger.error(f"  ❌ Error processing {file_path.name}: {e}")
        return 0


async def main():
    """Main ingestion function."""
    logger.info("🚀 Starting Visa Rules Ingestion into visa_oracle...")

    # Validate environment
    if not OPENAI_API_KEY:
        logger.error("❌ OPENAI_API_KEY not set")
        return

    if not QDRANT_API_KEY:
        logger.error("❌ QDRANT_API_KEY not set")
        return

    # Check directory
    if not VISA_RULES_DIR.exists():
        logger.error(f"❌ Directory not found: {VISA_RULES_DIR}")
        return

    # Initialize OpenAI client
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # Use httpx for Qdrant REST API
    async with httpx.AsyncClient() as http_client:
        # Verify collection exists via REST
        try:
            headers = {"api-key": QDRANT_API_KEY}
            response = await http_client.get(
                f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
                headers=headers,
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                points_count = data.get("result", {}).get("points_count", 0)
                logger.info(
                    f"📊 Collection {COLLECTION_NAME}: {points_count} existing points"
                )
            else:
                logger.error(f"❌ Collection check failed: {response.status_code}")
                return
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant: {e}")
            return

        # Find visa files
        visa_files = sorted(VISA_RULES_DIR.glob("visa_*.txt"))
        logger.info(f"📁 Found {len(visa_files)} visa rule files")

        # Ingest each file
        total_chunks = 0
        success_count = 0

        for file_path in visa_files:
            chunks = await ingest_visa_file(file_path, http_client, openai_client)
            if chunks > 0:
                total_chunks += chunks
                success_count += 1

        # Final stats
        logger.info("=" * 50)
        logger.info("🎉 Ingestion Complete!")
        logger.info(f"Files processed: {success_count}/{len(visa_files)}")
        logger.info(f"Total chunks ingested: {total_chunks}")

        # Verify final count
        response = await http_client.get(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
            headers={"api-key": QDRANT_API_KEY},
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            points_count = data.get("result", {}).get("points_count", 0)
            logger.info(f"📊 Collection now has: {points_count} total points")


if __name__ == "__main__":
    asyncio.run(main())
