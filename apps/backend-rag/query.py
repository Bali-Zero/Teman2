import asyncio, asyncpg, os
async def check():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    res = await conn.fetch("SELECT c.company_name, cl.full_name, ccl.role FROM client_company_links ccl JOIN companies c ON c.id = ccl.company_id JOIN clients cl ON cl.id = ccl.client_id WHERE cl.full_name ILIKE '%Ariana Campolmi%' OR cl.full_name ILIKE '%Ricardo Guijarro%';")
    for r in res:
        print(f"{r['full_name']} -> {r['company_name']} ({r['role']})")
    await conn.close()
asyncio.run(check())
