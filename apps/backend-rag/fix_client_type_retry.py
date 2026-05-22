import asyncio
import os
import asyncpg

async def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("No DATABASE_URL found")
        return
        
    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"First connect failed: {e}. Trying again with ssl=False...")
        # Sometimes Fly proxy closes the connection on first attempt
        await asyncio.sleep(2)
        conn = await asyncpg.connect(db_url)
    
    names = ['%Alberto Menico%', '%Leonardo Fontana%', '%Arianna Campolmi%']
    print("\n=== AGGIORNAMENTO TIPO CLIENTE IN 'INDIVIDUAL' ===")
    
    for name in names:
        result = await conn.execute("UPDATE clients SET client_type = 'individual' WHERE full_name ILIKE $1", name)
        print(f"Update for {name}: {result}")
        
    print("\n=== VERIFICA DOPO AGGIORNAMENTO ===")
    for name in names:
        rows = await conn.fetch("SELECT id, full_name, client_type, google_drive_folder_id FROM clients WHERE full_name ILIKE $1", name)
        for r in rows: 
            print(dict(r))
            
    await conn.close()

asyncio.run(main())
