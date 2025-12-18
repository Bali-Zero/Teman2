import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import asyncpg
import fitz  # PyMuPDF
import google.generativeai as genai
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load env from parent directory
load_dotenv(Path(__file__).parent.parent / ".env")

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True
)
logger = logging.getLogger(__name__)

# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

import requests

# Configuration
# Force local DB connection
DB_URL = "postgres://antonellosiano@localhost:5432/nuzantara_dev"
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
if not QDRANT_API_KEY:
    logger.warning("⚠️ QDRANT_API_KEY not found in env. Qdrant operations may fail.")

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")  # Revert to 2.0 Flash for stability
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- 1. COGNITIVE ENGINE (The Brain) ---


async def analyze_document_structure(
    text_excerpt: str, filename: str = ""
) -> dict[str, Any]:
    """
    Uses Gemini to classify the document and extract basic metadata.
    Decides which collection it belongs to.
    """
    # Clean text (remove image markers)
    text_excerpt = text_excerpt.replace("[image]", "").strip()

    # Construct context: Head + Tail to catch Verdict at the end
    # Increased context window to 5000 chars to catch titles in messy PDFs
    head = text_excerpt[:5000]
    tail = text_excerpt[-3000:] if len(text_excerpt) > 8000 else ""
    context_text = f"{head}\n\n... [SKIPPED MIDDLE] ...\n\n{tail}"

    prompt = f"""
    Analyze this legal document (Head and Tail provided) and extract metadata JSON.

    FILENAME: {filename} (Use this as a strong hint for the title if the text is unclear)

    Rules for 'collection':
    - 'tax_genius' if about taxes (Pajak, PPh, PPN, KUP).
    - 'visa_oracle' if about visas, immigration, stay permits.
    - 'kbli_unified' if about business classification (KBLI).
    - 'property_unified' if about land, property, agrarian.
    - 'litigation_oracle' if it is a Court Ruling (Putusan Pengadilan, Mahkamah Agung).
    - 'legal_unified' for everything else (General Law, Manpower, Civil Code).

    Rules for 'title':
    - Extract the OFFICIAL title (e.g., "Undang-Undang Nomor 1 Tahun 1974").
    - If the text is messy or scanned, infer the title from the FILENAME.
    - NEVER return "Tidak Tersedia" or "Unknown". Use the filename as a fallback.

    Output JSON ONLY:
    {{
        "title": "Official Title",
        "type": "UU/PP/Putusan",
        "year": 2024,
        "number": "12/Pdt.G/2024",
        "collection": "legal_unified",
        "summary": "3-line summary. For Putusan, include the Verdict (Menolak/Mengabulkan).",
        "verdict": "Granted/Rejected/Partially Granted (Only for Putusan)"
    }}

    Text:
    {context_text}
    """
    try:
        response = await model.generate_content_async(prompt)
        # Clean markdown code blocks if present
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)

        # Fallback for bad titles
        if data.get("title") in [
            "Tidak Tersedia",
            "Unknown",
            "Tidak dapat ditentukan dari dokumen",
            None,
        ]:
            logger.warning(f"⚠️ AI failed to extract title. Using filename: {filename}")
            data["title"] = filename.replace(".pdf", "").replace("_", " ").title()

        return data
    except Exception as e:
        logger.error(f"AI Analysis failed: {e}")
        # Robust Fallback
        return {
            "title": filename.replace(".pdf", "").replace("_", " ").title(),
            "collection": "legal_unified",
            "summary": "Auto-ingested document (Metadata extraction failed).",
            "type": "Document",
        }


async def extract_knowledge_graph(text_chunk: str) -> dict[str, Any]:
    """
    Extracts entities and relationships for the Knowledge Graph.
    """
    prompt = f"""
    Extract entities and relationships from this legal text.

    Entities: Laws, Organizations (PT PMA), Concepts (Minimum Capital), Permits (KITAS).
    Relationships: MODIFIES, REQUIRES, DEFINES, CONTRADICTS.

    Output JSON ONLY:
    {{
        "entities": [
            {{"name": "Entity Name", "type": "LAW/ORG/CONCEPT"}}
        ],
        "relationships": [
            {{"source": "Entity A", "target": "Entity B", "type": "RELATION_TYPE", "desc": "Short description"}}
        ]
    }}

    Text:
    {text_chunk[:3000]}
    """
    try:
        response = await model.generate_content_async(prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        logger.warning(f"Graph extraction failed: {e}")
        return {"entities": [], "relationships": []}


async def generate_hyde_questions(text_chunk: str) -> list[str]:
    """
    Generates hypothetical questions that this text answers.
    """
    prompt = f"""
    Generate 3 hypothetical user questions that are best answered by this legal text.
    Questions should be in Indonesian and English mixed (natural language).

    Text:
    {text_chunk[:1000]}

    Output JSON list of strings only:
    ["Question 1?", "Question 2?", "Question 3?"]
    """
    try:
        response = await model.generate_content_async(prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception:
        return []


# --- 2. DOCUMENT PROCESSOR (The Hands) ---

import sys

sys.path.append(str(Path(__file__).parent.parent))  # Add apps/backend-rag
sys.path.append(
    str(Path(__file__).parent.parent / "backend")
)  # Add apps/backend-rag/backend for 'core' imports
from backend.services.rag.chunking import SemanticChunker

# Initialize Chunker (Global to avoid reloading model)
# Use a smaller model for splitting to be fast, or the default one
chunker = SemanticChunker(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    min_chunk_size=200,
    max_chunk_size=1500,
)


def read_pdf(path: Path) -> str:
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text


def chunk_text(text: str, metadata: dict = None) -> list[str]:
    """
    Uses SemanticChunker (Hybrid Mode) to split text.
    Returns list of strings (text content of chunks).
    """
    try:
        semantic_chunks = chunker.chunk_document(
            text, method="hybrid", metadata=metadata
        )
        return [c.text for c in semantic_chunks]
    except Exception as e:
        logger.error(f"Semantic chunking failed: {e}. Fallback to simple chunking.")
        # Fallback to simple overlap
        chunks = []
        chunk_size = 1000
        for i in range(0, len(text), chunk_size - 100):
            chunks.append(text[i : i + chunk_size])
        return chunks


# --- 3. STORAGE MANAGER (The Vault) ---


async def save_to_postgres(conn, doc_id, metadata, full_text, summary):
    # Save Parent Document
    await conn.execute(
        """
        INSERT INTO parent_documents (id, document_id, title, full_text, summary, metadata)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE
        SET title = EXCLUDED.title,
            full_text = EXCLUDED.full_text,
            summary = EXCLUDED.summary,
            metadata = EXCLUDED.metadata
    """,
        doc_id,
        doc_id,
        metadata.get("title"),
        full_text,
        summary,
        json.dumps(metadata),
    )


async def save_graph_to_postgres(conn, graph_data):
    # 1. Collect all unique entities (from entities list AND relationships)
    unique_entities = {}

    # Add explicit entities
    for entity in graph_data.get("entities", []):
        e_id = entity["name"].lower().replace(" ", "_")[:64]
        unique_entities[e_id] = {"name": entity["name"], "type": entity["type"]}

    # Add implicit entities from relationships
    for rel in graph_data.get("relationships", []):
        s_id = rel["source"].lower().replace(" ", "_")[:64]
        t_id = rel["target"].lower().replace(" ", "_")[:64]

        if s_id not in unique_entities:
            unique_entities[s_id] = {"name": rel["source"], "type": "UNKNOWN"}
        if t_id not in unique_entities:
            unique_entities[t_id] = {"name": rel["target"], "type": "UNKNOWN"}

    # 2. Save ALL Entities first
    for e_id, data in unique_entities.items():
        await conn.execute(
            """
            INSERT INTO kg_entities (id, name, type)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO NOTHING
        """,
            e_id,
            data["name"],
            data["type"],
        )

    # 3. Save Relationships
    for rel in graph_data.get("relationships", []):
        s_id = rel["source"].lower().replace(" ", "_")[:64]
        t_id = rel["target"].lower().replace(" ", "_")[:64]

        await conn.execute(
            """
            INSERT INTO kg_relationships (source_entity_id, target_entity_id, relationship_type, properties)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
        """,
            s_id,
            t_id,
            rel["type"],
            json.dumps({"description": rel["desc"]}),
        )


async def ingest_file(file_path: Path, conn, dry_run=False):
    logger.info(f"🚀 Processing: {file_path.name}")

    # 0. Check if already exists (Incremental Ingestion)
    doc_id = file_path.stem[:64]
    exists = await conn.fetchval("SELECT 1 FROM parent_documents WHERE id = $1", doc_id)
    if exists:
        logger.info(f"⏭️  Skipping {file_path.name} (Already ingested)")
        return

    # 1. Read
    if file_path.suffix == ".pdf":
        text = read_pdf(file_path)
    else:
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="latin-1", errors="replace")

    if not text:
        logger.warning(f"Empty text for {file_path.name}")
        return

    # 2. Analyze (AI)
    meta = await analyze_document_structure(text, filename=file_path.name)
    collection_name = meta.get("collection", "legal_unified")
    logger.info(f"   🏷️  Classified as: {collection_name} | Title: {meta.get('title')}")

    # 3. Save Parent (Postgres)
    doc_id = file_path.stem[:64]  # Truncate to 64 chars to fit DB column
    await save_to_postgres(conn, doc_id, meta, text, meta.get("summary"))

    # 4. Chunk & Vectorize
    chunks = chunk_text(text, metadata=meta)
    points = []

    # Ensure collection exists (REST API)
    headers = {"api-key": QDRANT_API_KEY}
    try:
        # Check if collection exists
        resp = requests.get(
            f"{QDRANT_URL}/collections/{collection_name}", headers=headers
        )
        if resp.status_code != 200:
            logger.info(f"   🆕 Creating collection: {collection_name}")
            requests.put(
                f"{QDRANT_URL}/collections/{collection_name}",
                headers=headers,
                json={
                    "vectors": {
                        "size": 1536,
                        "distance": "Cosine",
                    }  # OpenAI embedding size is 1536
                },
            )
    except Exception as e:
        logger.error(f"Failed to check/create collection: {e}")

    # Process chunks (Limit to 5 chunks for dry run to save time/cost)
    limit_chunks = 5 if dry_run else len(chunks)

    for i, chunk in enumerate(chunks[:limit_chunks]):
        # Graph Extraction (only on first few chunks to save cost)
        if i < 2:
            graph_data = await extract_knowledge_graph(chunk)
            await save_graph_to_postgres(conn, graph_data)

        # HyDE Generation
        hyde_questions = await generate_hyde_questions(chunk)

        # Embedding (OpenAI)
        try:
            embedding_resp = await openai_client.embeddings.create(
                input=chunk, model="text-embedding-3-small"
            )
            vector = embedding_resp.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding failed for chunk {i}: {e}")
            continue

        payload = {
            "text": chunk,
            "parent_id": doc_id,
            "chunk_index": i,
            "hyde_questions": hyde_questions,
            "source_file": file_path.name,
            "title": meta.get("title"),
        }

        import uuid

        points.append({"id": str(uuid.uuid4()), "vector": vector, "payload": payload})

    # Upsert to Qdrant (REST API)
    if points:
        resp = requests.put(
            f"{QDRANT_URL}/collections/{collection_name}/points",
            headers=headers,
            json={"points": points},
        )
        if resp.status_code == 200:
            logger.info(f"   ✅ Indexed {len(points)} chunks to {collection_name}")
        else:
            logger.error(f"   ❌ Failed to index: {resp.text}")


async def main():
    conn = await asyncpg.connect(DB_URL)

    # Directories (Absolute paths to be safe)
    base_dir = Path("/Users/antonellosiano/Desktop/nuzantara")
    raw_laws = base_dir / "apps/scraper/data/raw_laws"
    raw_targeted = base_dir / "apps/scraper/data/raw_laws_targeted"
    raw_putusan = base_dir / "apps/scraper/data/raw_putusan"
    raw_kbli = base_dir / "apps/scraper/data/raw_laws_local/Company&Licenses/kbli"
    raw_laws_local = base_dir / "apps/scraper/data/raw_laws_local"

    # --- DEDUPLICATION LOGIC ---
    unique_files = {}  # filename -> Path

    # 1. Priority: Local Categorized Laws (raw_laws_local)
    # We prefer these because they are already categorized in folders
    logger.info("📂 Scanning raw_laws_local (Priority 1)...")
    local_count = 0
    for f in raw_laws_local.rglob("*.pdf"):
        unique_files[f.name] = f
        local_count += 1
    logger.info(f"   Found {local_count} categorized laws.")

    # 2. Priority: Raw Laws (raw_laws)
    # Only add if not already present (deduplication)
    logger.info("📂 Scanning raw_laws (Priority 2)...")
    raw_count = 0
    for f in raw_laws.glob("*.pdf"):
        if f.name not in unique_files:
            unique_files[f.name] = f
            raw_count += 1
    logger.info(f"   Added {raw_count} new files from raw_laws (skipped duplicates).")

    # 3. Priority: Putusan
    logger.info("📂 Scanning raw_putusan...")
    putusan_count = 0
    for f in raw_putusan.glob("*.pdf"):
        if f.name not in unique_files:
            unique_files[f.name] = f
            putusan_count += 1
    logger.info(f"   Added {putusan_count} putusan files.")

    # 4. Priority: KBLI (Markdown)
    logger.info("📂 Scanning KBLI...")
    kbli_count = 0
    for f in raw_kbli.glob("*.md"):
        unique_files[f.name] = f
        kbli_count += 1
    logger.info(f"   Added {kbli_count} KBLI files.")

    # Final list
    files = list(unique_files.values())

    logger.info(
        f"🏁 Starting Intelligent Ingestion (FULL RUN: {len(files)} unique files)"
    )

    for f in files:
        try:
            await ingest_file(f, conn, dry_run=False)
        except Exception as e:
            logger.error(f"Failed to ingest {f.name}: {e}")

    await conn.close()
    logger.info("🎉 Ingestion Complete!")


if __name__ == "__main__":
    asyncio.run(main())
