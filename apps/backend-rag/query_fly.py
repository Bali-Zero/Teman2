import asyncio
import os
import asyncpg

async def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("No DATABASE_URL found")
        return
        
    conn = await asyncpg.connect(db_url)
    
    print("\n=== 1. CLIENTI ERRONEAMENTE REGISTRATI COME AZIENDE ===")
    rows = await conn.fetch("SELECT id, company_name, company_type FROM companies WHERE company_name ILIKE '%Alberto Menico%' OR company_name ILIKE '%Leonardo Fontana%' LIMIT 5")
    for r in rows: print(dict(r))
    
    print("\n=== 2. CONTROLLO PROFILO ARIANNA ===")
    rows = await conn.fetch("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE '%Arianna Campolmi%' LIMIT 5")
    for r in rows: print(dict(r))
    
    await conn.close()

asyncio.run(main())
