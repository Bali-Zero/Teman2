import asyncio
import asyncpg
from backend.app.core.config import settings

async def query():
    try:
        # Sostituiamo flycast con localhost:15432 per usare il fly proxy
        db_url = settings.database_url.replace("nuzantara-postgres.flycast:5432", "localhost:15432")
        print(f"Connecting to {db_url.replace(db_url.split(':')[2].split('@')[0], '***')}")
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
