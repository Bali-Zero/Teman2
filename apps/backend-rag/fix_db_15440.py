import asyncio
import asyncpg
import sys

async def main():
    # Use 15440 which will be our new tunnel
    db_url = "postgresql://backend_rag_v2:1w32Hrm33npis9rncTVjye3hPEwaVta@localhost:15440/nuzantara_rag"
    
    try:
        print("Connettendo a localhost:15440...")
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        return
        
    names = ['%Alberto Menico%', '%Leonardo Fontana%', '%Arianna Campolmi%']
    print("\n=== ESECUZIONE UPDATE ===")
    
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
