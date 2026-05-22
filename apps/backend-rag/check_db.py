import os, asyncio, asyncpg
from dotenv import load_dotenv

load_dotenv()

DB = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
if "flycast" in DB and not os.getenv("FLY_APP_NAME"):
    DB = DB.replace("nuzantara-postgres.flycast:5432", "127.0.0.1:15432")
elif "localhost" in DB:
    DB = DB.replace("localhost", "127.0.0.1")

if not DB:
    DB = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@127.0.0.1:15432/nuzantara_rag?sslmode=disable"

async def check():
    conn = await asyncpg.connect(DB)
    
    # Get Ariana
    ariana = await conn.fetch("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE $1", "%Ariana Campolmi%")
    print("Ariana clients:", ariana)
    
    if ariana:
        ariana_id = ariana[0]["id"]
        links = await conn.fetch("SELECT company_id FROM client_company_links WHERE client_id = $1", ariana_id)
        for link in links:
            comp = await conn.fetchrow("SELECT company_name, google_drive_folder_id FROM companies WHERE id = $1", link["company_id"])
            if comp:
                print("Ariana is linked to: " + comp["company_name"])
            
    # Get Ricardo
    ricardo = await conn.fetch("SELECT id, full_name, google_drive_folder_id FROM clients WHERE full_name ILIKE $1", "%Ricardo Guijarro%")
    print("Ricardo clients:", ricardo)
    
    if ricardo:
        ricardo_id = ricardo[0]["id"]
        links = await conn.fetch("SELECT company_id FROM client_company_links WHERE client_id = $1", ricardo_id)
        for link in links:
            comp = await conn.fetchrow("SELECT company_name, google_drive_folder_id FROM companies WHERE id = $1", link["company_id"])
            if comp:
                print("Ricardo is linked to: " + comp["company_name"])
    
    await conn.close()
asyncio.run(check())
