import asyncio
from backend.core.database import SessionLocal
from sqlalchemy import text

async def query():
    try:
        async with SessionLocal() as session:
            # Query for Alberto and Leonardo
            result = await session.execute(text("SELECT id, company_name, company_type, google_drive_folder_id FROM companies WHERE company_name ILIKE '%Alberto Menico%' OR company_name ILIKE '%Leonardo Fontana%' LIMIT 10"))
            print("=== RISULTATI DALLA TABELLA COMPANIES ===")
            for row in result:
                print(dict(row._mapping))
                
            result = await session.execute(text("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE '%Alberto Menico%' OR full_name ILIKE '%Leonardo Fontana%' LIMIT 10"))
            print("\n=== RISULTATI DALLA TABELLA CLIENTS ===")
            for row in result:
                print(dict(row._mapping))
                
            result = await session.execute(text("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE '%Arianna Campolmi%' LIMIT 10"))
            print("\n=== RISULTATI ARIANNA ===")
            for row in result:
                print(dict(row._mapping))
                
    except Exception as e:
        print(f"Errore connessione DB: {e}")

asyncio.run(query())
