import asyncio, asyncpg, csv, io, json

async def main():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:5555/nuzantara_rag?sslmode=disable')

    rows = await conn.fetch("""
        SELECT
            c.id, c.full_name, c.email, c.phone, c.whatsapp,
            c.nationality, c.passport_number, c.passport_expiry,
            c.date_of_birth, c.gender, c.birthplace, c.address,
            c.status, c.client_type, c.assigned_to, c.lead_source,
            c.google_drive_folder_id, c.created_at,
            co.company_name, co.company_type, co.nib, co.npwp_company,
            co.kbli_code, co.registered_address as company_address,
            co.company_email, co.company_phone,
            co.akta_pendirian_no, co.akta_pendirian_date,
            co.sk_menhumkam_no,
            co.custom_fields,
            ccl.role as company_role, ccl.ownership_percentage
        FROM clients c
        LEFT JOIN LATERAL (
            SELECT * FROM client_company_links
            WHERE client_id = c.id
            ORDER BY is_primary DESC NULLS LAST, created_at ASC
            LIMIT 1
        ) ccl ON true
        LEFT JOIN companies co ON co.id = ccl.company_id
        WHERE c.deleted_at IS NULL
        ORDER BY c.id
    """)

    # Check who has visa practices
    visa_clients = set()
    visa_rows = await conn.fetch("""
        SELECT DISTINCT client_id FROM practices p
        JOIN practice_types pt ON pt.id = p.practice_type_id
        WHERE pt.category IN ('visa', 'immigration') OR pt.code ILIKE '%kitas%' OR pt.code ILIKE '%visa%'
    """)
    for r in visa_rows:
        visa_clients.add(r["client_id"])

    def classify(r):
        has_company = r['company_name'] is not None
        has_nationality = r['nationality'] and r['nationality'].strip()
        has_passport = r['passport_number'] and r['passport_number'].strip()
        has_email = r['email'] and r['email'].strip()
        has_visa = r['id'] in visa_clients
        status = r['status'] or 'lead'
        role = (r['company_role'] or '').lower()

        if has_company and 'director' in role:
            return 'Corporate Director'
        if has_company and 'commissioner' in role:
            return 'Corporate Commissioner'
        if has_company and 'shareholder' in role:
            return 'Corporate Shareholder'
        if has_company:
            return 'Corporate'
        if has_visa or (has_passport and status == 'active'):
            return 'Individual Visa'
        if not has_nationality and not has_passport and not has_email:
            return 'Unqualified'
        if status == 'lead':
            return 'Individual Lead'
        return 'Individual Active'

    def get_sheet(profile, status):
        if profile == 'Unqualified':
            return 'garbage'
        if status in ('active', 'prospect') or profile.startswith('Corporate') or profile == 'Individual Visa':
            return 'active'
        return 'leads'

    header = [
        'ID', 'Full Name', 'Profile',
        'Email', 'Phone', 'WhatsApp', 'Nationality',
        'Passport Number', 'Passport Expiry', 'Date of Birth',
        'Gender', 'Birthplace', 'Address',
        'Status', 'Assigned To', 'Lead Source', 'Created At',
        'Company Name', 'Company Type', 'Role in Company', 'Ownership %',
        'NIB', 'NPWP', 'KBLI', 'Company Address',
        'Company Email', 'Company Phone',
        'Akta No', 'Akta Date', 'SK Kemenkumham',
        'Investment Type', 'Company Status', 'Tax Office (KPP)',
    ]

    sheets = {'active': [], 'leads': [], 'garbage': []}
    profile_counts = {}

    for r in rows:
        profile = classify(r)
        profile_counts[profile] = profile_counts.get(profile, 0) + 1
        sheet = get_sheet(profile, r['status'] or 'lead')

        cf = r['custom_fields'] or {}
        if isinstance(cf, str):
            try: cf = json.loads(cf)
            except: cf = {}
        if not isinstance(cf, dict): cf = {}

        row = [
            r['id'], r['full_name'], profile,
            r['email'] or '', r['phone'] or '', r['whatsapp'] or '',
            r['nationality'] or '', r['passport_number'] or '',
            str(r['passport_expiry']) if r['passport_expiry'] else '',
            str(r['date_of_birth']) if r['date_of_birth'] else '',
            r['gender'] or '', r['birthplace'] or '', r['address'] or '',
            r['status'] or '', r['assigned_to'] or '', r['lead_source'] or '',
            str(r['created_at'].date()) if r['created_at'] else '',
            r['company_name'] or '', r['company_type'] or '',
            r['company_role'] or '',
            str(r['ownership_percentage']) if r['ownership_percentage'] else '',
            r['nib'] or '', r['npwp_company'] or '', r['kbli_code'] or '',
            r['company_address'] or '', r['company_email'] or '', r['company_phone'] or '',
            r['akta_pendirian_no'] or '',
            str(r['akta_pendirian_date']) if r['akta_pendirian_date'] else '',
            r['sk_menhumkam_no'] or '',
            cf.get('investment_type', ''), cf.get('company_status', ''), cf.get('tax_office', ''),
        ]
        sheets[sheet].append(row)

    # Write 3 CSV files
    for name, data in sheets.items():
        path = f'/tmp/crm_{name}.csv'
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(header)
            # Sort: Corporate first, then by name
            data.sort(key=lambda x: (0 if 'Corporate' in x[2] else 1, x[1]))
            w.writerows(data)
        print(f'{name:10s}: {len(data):5d} rows → {path}')

    print(f'\n=== PROFILE BREAKDOWN ===')
    for p, c in sorted(profile_counts.items(), key=lambda x: -x[1]):
        print(f'  {p:25s}: {c}')

    print(f'\n=== SHEET TOTALS ===')
    for name, data in sheets.items():
        print(f'  {name:10s}: {len(data)}')

    await conn.close()

asyncio.run(main())
