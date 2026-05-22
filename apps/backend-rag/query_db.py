import asyncio, asyncpg
async def query():
    try:
        conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag')
        
        # Cerca clienti con nome "Alberto Menico" o "Leonardo Fontana" per capire come sono stati salvati
        rows = await conn.fetch("SELECT id, company_name, company_type FROM companies WHERE company_name ILIKE '%Alberto Menico%' OR company_name ILIKE '%Leonardo Fontana%' LIMIT 10")
        print("=== RISULTATI DALLA TABELLA COMPANIES ===")
        for r in rows:
            print(dict(r))
            
        rows_clients = await conn.fetch("SELECT id, full_name FROM clients WHERE full_name ILIKE '%Alberto Menico%' OR full_name ILIKE '%Leonardo Fontana%' LIMIT 10")
        print("\n=== RISULTATI DALLA TABELLA CLIENTS ===")
        for r in rows_clients:
            print(dict(r))
            
        # Controlliamo anche Ariana Campolmi
        rows_ariana = await conn.fetch("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE '%Arianna Campolmi%' LIMIT 10")
        print("\n=== RISULTATI ARIANNA ===")
        for r in rows_ariana:
            print(dict(r))
            
        await conn.close()
    except Exception as e:
        print(f"Errore connessione DB: {e}")

asyncio.run(query())
