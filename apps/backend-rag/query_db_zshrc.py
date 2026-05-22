import asyncio
import asyncpg
import os

async def query():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL non trovato!")
        return
        
    try:
        # Assicuriamoci di usare postgresql:// invece di postgres:// per asyncpg
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            
        print(f"Connecting to DB...")
        conn = await asyncpg.connect(db_url)
        
        # Query for Alberto and Leonardo in companies
        print("=== RISULTATI DALLA TABELLA COMPANIES ===")
        rows = await conn.fetch("SELECT id, company_name, company_type FROM companies WHERE company_name ILIKE '%Alberto Menico%' OR company_name ILIKE '%Leonardo Fontana%' LIMIT 10")
        for r in rows:
            print(dict(r))
            
        print("\n=== RISULTATI DALLA TABELLA CLIENTS ===")
        rows_clients = await conn.fetch("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE '%Alberto Menico%' OR full_name ILIKE '%Leonardo Fontana%' LIMIT 10")
        for r in rows_clients:
            print(dict(r))
            
        print("\n=== RISULTATI ARIANNA ===")
        rows_ariana = await conn.fetch("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE '%Arianna Campolmi%' LIMIT 10")
        for r in rows_ariana:
            print(dict(r))
            
        await conn.close()
    except Exception as e:
        print(f"Errore connessione DB: {e}")

asyncio.run(query())
