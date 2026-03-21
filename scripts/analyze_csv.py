import asyncio, asyncpg, json

async def main():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:5555/nuzantara_rag?sslmode=disable')

    total = await conn.fetchval("SELECT count(*) FROM clients WHERE deleted_at IS NULL")

    print(f'=== FILL RATES ({total} clients) ===')
    fields = [
        ('full_name', 'Full Name'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('whatsapp', 'WhatsApp'),
        ('nationality', 'Nationality'),
        ('passport_number', 'Passport'),
        ('passport_expiry', 'Passport Expiry'),
        ('date_of_birth', 'DOB'),
        ('gender', 'Gender'),
        ('birthplace', 'Birthplace'),
        ('address', 'Address'),
        ('assigned_to', 'Assigned To'),
        ('lead_source', 'Lead Source'),
    ]
    for col, label in fields:
        n = await conn.fetchval(f"SELECT count(*) FROM clients WHERE deleted_at IS NULL AND {col} IS NOT NULL AND TRIM(CAST({col} AS TEXT)) != ''")
        pct = n * 100 / total
        bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
        print(f'  {label:20s}: {n:5d} ({pct:5.1f}%) {bar}')

    print('\n=== STATUS ===')
    rows = await conn.fetch("SELECT COALESCE(status,'NULL') as s, count(*) as c FROM clients WHERE deleted_at IS NULL GROUP BY status ORDER BY c DESC")
    for r in rows: print(f'  {r["s"]:15s}: {r["c"]}')

    print('\n=== CORPORATE CLIENTS DATA QUALITY ===')
    r = await conn.fetchrow("""
        SELECT count(DISTINCT c.id) as total,
            count(DISTINCT c.id) FILTER (WHERE c.passport_number IS NOT NULL AND c.passport_number != '') as has_passport,
            count(DISTINCT c.id) FILTER (WHERE c.email IS NOT NULL AND c.email != '') as has_email,
            count(DISTINCT c.id) FILTER (WHERE c.nationality IS NOT NULL AND c.nationality != '') as has_nationality,
            count(DISTINCT c.id) FILTER (WHERE c.date_of_birth IS NOT NULL) as has_dob
        FROM clients c
        JOIN client_company_links ccl ON ccl.client_id = c.id
        WHERE c.deleted_at IS NULL
    """)
    print(f'  Total corporate: {r["total"]}')
    print(f'  With passport:   {r["has_passport"]} ({r["has_passport"]*100//r["total"]}%)')
    print(f'  With email:      {r["has_email"]} ({r["has_email"]*100//r["total"]}%)')
    print(f'  With nationality:{r["has_nationality"]} ({r["has_nationality"]*100//r["total"]}%)')
    print(f'  With DOB:        {r["has_dob"]} ({r["has_dob"]*100//r["total"]}%)')

    print('\n=== TOP 15 NATIONALITIES ===')
    rows = await conn.fetch("SELECT nationality, count(*) as c FROM clients WHERE deleted_at IS NULL AND nationality IS NOT NULL AND nationality != '' GROUP BY nationality ORDER BY c DESC LIMIT 15")
    for r in rows: print(f'  {r["nationality"]:25s}: {r["c"]}')

    print('\n=== DUPLICATES ===')
    n = await conn.fetchval("SELECT count(*) FROM (SELECT phone, count(*) FROM clients WHERE deleted_at IS NULL AND phone IS NOT NULL AND phone != '' GROUP BY phone HAVING count(*) > 1) x")
    print(f'  Phones shared by 2+ clients: {n}')
    n2 = await conn.fetchval("SELECT count(*) FROM (SELECT UPPER(TRIM(full_name)), count(*) FROM clients WHERE deleted_at IS NULL GROUP BY UPPER(TRIM(full_name)) HAVING count(*) > 1) x")
    print(f'  Names shared by 2+ clients: {n2}')

    print('\n=== CLIENTS WITH MULTIPLE COMPANIES ===')
    r = await conn.fetchrow("SELECT count(*) FILTER (WHERE cnt = 1) as one, count(*) FILTER (WHERE cnt = 2) as two, count(*) FILTER (WHERE cnt >= 3) as three_plus FROM (SELECT client_id, count(*) as cnt FROM client_company_links GROUP BY client_id) x")
    print(f'  1 company:  {r["one"]}')
    print(f'  2 companies: {r["two"]}')
    print(f'  3+ companies:{r["three_plus"]}')

    print('\n=== ASSIGNED TO (top 10) ===')
    rows = await conn.fetch("SELECT COALESCE(assigned_to, 'UNASSIGNED') as a, count(*) as c FROM clients WHERE deleted_at IS NULL GROUP BY assigned_to ORDER BY c DESC LIMIT 10")
    for r in rows: print(f'  {r["a"]:35s}: {r["c"]}')

    print('\n=== EMPTY CLIENTS (only name+phone, nothing else) ===')
    n = await conn.fetchval("""
        SELECT count(*) FROM clients WHERE deleted_at IS NULL
        AND (email IS NULL OR email = '')
        AND (nationality IS NULL OR nationality = '')
        AND (passport_number IS NULL OR passport_number = '')
        AND NOT EXISTS (SELECT 1 FROM client_company_links ccl WHERE ccl.client_id = clients.id)
    """)
    print(f'  Clients with only name+phone (no email, no nationality, no passport, no company): {n}')

    await conn.close()

asyncio.run(main())
