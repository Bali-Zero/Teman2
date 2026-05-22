import asyncio
import os
import asyncpg

async def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("No DATABASE_URL found")
        return
        
    conn = await asyncpg.connect(db_url)
    
    print("\n=== VERIFICA TIPO CLIENTE ===")
    names = ['%Alberto Menico%', '%Leonardo Fontana%', '%Arianna Campolmi%']
    for name in names:
        rows = await conn.fetch("SELECT id, full_name, client_type, google_drive_folder_id FROM clients WHERE full_name ILIKE $1", name)
        for r in rows: 
            print(dict(r))
            
    print("\n=== AGGIORNAMENTO TIPO CLIENTE ===")
    # Update to 'individual'
    for name in names:
        result = await conn.execute("UPDATE clients SET client_type = 'individual' WHERE full_name ILIKE $1 AND client_type = 'company'", name)
        print(f"Update for {name}: {result}")
        
    print("\n=== DOPO AGGIORNAMENTO ===")
    for name in names:
        rows = await conn.fetch("SELECT id, full_name, client_type, google_drive_folder_id FROM clients WHERE full_name ILIKE $1", name)
        for r in rows: 
            print(dict(r))
            
    await conn.close()

asyncio.run(main())
