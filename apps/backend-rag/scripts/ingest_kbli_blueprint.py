import os
import sys
import asyncio
import json
import shutil
import pdfplumber
import glob
from pathlib import Path
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.http import models
import asyncpg
from dotenv import load_dotenv
import tempfile

# Load Environment
load_dotenv("apps/backend-rag/.env")

# Config
DATABASE_URL = os.getenv("DATABASE_URL")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", "zerosphere-api")
GOOGLE_LOCATION = os.getenv("GOOGLE_LOCATION", "us-central1")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

# Paths
BASE_DIR = Path("apps/backend-rag/data")
INBOX_DIR = BASE_DIR / "INBOX"
STORAGE_DIR = BASE_DIR / "knowledge_library/blueprints"
PROCESSED_DIR = BASE_DIR / "PROCESSED"

# Ensure dirs exist
INBOX_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Initialize Vertex AI client
def get_genai_client():
    """Get genai client using Vertex AI with service account."""
    if GOOGLE_CREDENTIALS_JSON:
        # Write credentials to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(GOOGLE_CREDENTIALS_JSON)
            creds_path = f.name
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path

    return genai.Client(
        vertexai=True,
        project=GOOGLE_PROJECT_ID,
        location=GOOGLE_LOCATION
    )

client_genai = get_genai_client()

async def extract_blueprint_data(pdf_path):
    print(f"📖 Reading PDF: {pdf_path.name}")
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"❌ Error reading PDF {pdf_path.name}: {e}")
        return None
    
    print(f"🧠 Extracting intelligence from {pdf_path.name}...")
    prompt = f"""
    You are an expert Indonesian Regulatory Analyst. 
    Analyze this KBLI Blueprint and extract structured information.
    
    TEXT:
    {text[:30000]}
    
    OUTPUT JSON FORMAT:
    {{
        "kbli_code": "string (e.g. 55110)",
        "title": "string",
        "risk_level": "string",
        "min_capital": "string",
        "summary": "string (short executive summary)",
        "kg_entities": [
            {{"id": "unique_id", "type": "Requirement|Permit|Step|Location", "name": "string", "description": "string"}}
        ],
        "kg_relationships": [
            {{"source": "kbli_code", "target": "entity_id", "type": "REQUIRES|PREREQUISITE_FOR|SUITABLE_FOR"}}
        ]
    }}
    """
    
    try:
        response = client_genai.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        parsed_data = json.loads(response.text)
        
        # Robustness: Handle list response
        if isinstance(parsed_data, list):
            if len(parsed_data) > 0:
                print("⚠️ Received list from LLM, using first item.")
                parsed_data = parsed_data[0]
            else:
                print("❌ Received empty list from LLM.")
                return None
                
        return parsed_data
    except Exception as e:
        print(f"❌ AI Extraction failed for {pdf_path.name}: {e}")
        return None

async def ingest_to_postgres(data, pdf_final_path):
    print("🐘 Updating PostgreSQL...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        # 1. Update kbli_blueprints
        await conn.execute("""
            INSERT INTO kbli_blueprints (kbli_code, title, pdf_path, risk_level, min_capital, summary, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (kbli_code) DO UPDATE SET
                title = EXCLUDED.title,
                pdf_path = EXCLUDED.pdf_path,
                risk_level = EXCLUDED.risk_level,
                min_capital = EXCLUDED.min_capital,
                summary = EXCLUDED.summary,
                metadata = EXCLUDED.metadata,
                updated_at = NOW();
        """, data['kbli_code'], data['title'], str(pdf_final_path), data['risk_level'], data['min_capital'], data['summary'], json.dumps(data))

        # 2. Update Knowledge Graph Nodes (Main KBLI)
        await conn.execute("""
            INSERT INTO kg_nodes (entity_id, entity_type, name, description, source_collection)
            VALUES ($1, 'KBLI', $2, $3, 'blueprints')
            ON CONFLICT (entity_id) DO UPDATE SET description = EXCLUDED.description;
        """, data['kbli_code'], data['title'], data['summary'])

        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

async def process_file(pdf_path):
    print(f"\n⚙️ Processing: {pdf_path.name}")
    
    # 1. AI Extraction
    data = await extract_blueprint_data(pdf_path)
    if not data or data.get('kbli_code') in [None, 'N/A', 'string']:
        print(f"❌ Could not extract valid KBLI code from {pdf_path.name}. Skipping.")
        return

    # 2. Move to Storage (Rename standard format)
    filename = f"KBLI_{data['kbli_code']}_Blueprint.pdf"
    dest_path = STORAGE_DIR / filename
    shutil.copy(str(pdf_path), str(dest_path))
    
    # 3. Ingest
    print(f"📥 Ingesting {data['kbli_code']} - {data['title']}...")
    db_success = await ingest_to_postgres(data, dest_path)
    
    if db_success:
        print(f"✅ COMPLETED: {data['kbli_code']} - {data['title']}")
        # 4. Move processed file
        shutil.move(str(pdf_path), str(PROCESSED_DIR / pdf_path.name))
    else:
        print(f"⚠️ SKIPPED: {data['kbli_code']} due to database error.")

async def main():
    # Mode 1: Single file argument
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if input_path.exists():
            await process_file(input_path)
        else:
            print(f"❌ File not found: {input_path}")
        return

    # Mode 2: INBOX Batch Processing
    print(f"📂 Scanning INBOX: {INBOX_DIR}")
    files = list(INBOX_DIR.glob("*.pdf"))
    
    if not files:
        print("📭 Inbox is empty. Drag PDF files into 'apps/backend-rag/data/INBOX' to process them.")
        return

    print(f"found {len(files)} files.")
    for pdf_file in files:
        await process_file(pdf_file)

if __name__ == "__main__":
    asyncio.run(main())
