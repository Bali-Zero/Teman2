import asyncio, asyncpg

async def run():
    conn = await asyncpg.connect("postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara")
    
    # 1. Who is Ariana?
    ariana = await conn.fetch("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE '%Ariana Campolmi%'")
    if not ariana:
        print("Ariana not found in DB!")
    else:
        for a in ariana:
            print(f"\n--- Ariana: {a['full_name']} ---")
            ccls = await conn.fetch("SELECT company_id, role FROM client_company_links WHERE client_id = $1", a['id'])
            for ccl in ccls:
                c = await conn.fetchrow("SELECT company_name FROM companies WHERE id = $1", ccl['company_id'])
                print(f"Linked to Company: {c['company_name']} (Role: {ccl['role']})")
                
                # Who else is linked to this company?
                others = await conn.fetch("SELECT client_id, role FROM client_company_links WHERE company_id = $1", ccl['company_id'])
                print("  Other linked clients:")
                for o in others:
                    other_client = await conn.fetchrow("SELECT full_name FROM clients WHERE id = $1", o['client_id'])
                    print(f"    - {other_client['full_name']} (Role: {o['role']})")

    # 2. Who is Ricardo?
    ricardo = await conn.fetch("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE '%Ricardo Guijarro%'")
    if not ricardo:
        print("\nRicardo not found in DB!")
    else:
        for r in ricardo:
            print(f"\n--- Ricardo: {r['full_name']} ---")
            ccls = await conn.fetch("SELECT company_id, role FROM client_company_links WHERE client_id = $1", r['id'])
            for ccl in ccls:
                c = await conn.fetchrow("SELECT company_name FROM companies WHERE id = $1", ccl['company_id'])
                print(f"Linked to Company: {c['company_name']} (Role: {ccl['role']})")

    await conn.close()

asyncio.run(run())
