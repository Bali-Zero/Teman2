import asyncio
import json
import os
import asyncpg

VISA_TYPES = [
    ('C1', 'Visa Free', 'Visa Free/VOA', 'Official title: Visa Free', 'See details', 'Contact for Quote', [], {'source': 'zantara_curated_2026', 'is_agency_product': False}),
    ('C2', 'Visit Visa', 'Visit Visa', 'Official title: Visit Visa', 'See details', 'Contact for Quote', [], {'source': 'zantara_curated_2026', 'is_agency_product': False}),
    ('C7', 'Working Visa', 'Visit Visa', 'Official title: Working Visa', 'See details', 'Contact for Quote', [], {'source': 'zantara_curated_2026', 'is_agency_product': False}),
    ('C7AB', 'Investor Visa', 'Visit Visa', 'Official title: Investor Visa', 'See details', 'Contact for Quote', [], {'source': 'zantara_curated_2026', 'is_agency_product': False}),
    ('C18', 'Education Visa', 'Visit Visa', 'Official title: Education Visa', 'See details', 'Contact for Quote', [], {'source': 'zantara_curated_2026', 'is_agency_product': False}),
    ('C22A', 'Family Visa', 'Visit Visa', 'Official title: Family Visa', 'See details', 'Contact for Quote', [], {'source': 'zantara_curated_2026', 'is_agency_product': False}),
    ('C22B', 'Repatriation Visa', 'Visit Visa', 'Official title: Repatriation Visa', 'See details', 'Contact for Quote', [], {'source': 'zantara_curated_2026', 'is_agency_product': False}),
    ('D12', 'Former Indonesian Citizen Descendant', 'Multiple Entry', 'Official title: Former Indonesian Citizen Descendant', 'See details', 'Contact for Quote', [], {'source': 'zantara_curated_2026', 'is_agency_product': False}),
    ('E23', 'Second Home Visa', 'KITAS/Limited Stay', 'Official title: Second Home Visa', 'See details', 'IDR 34.500.000 (Offshore) / 36.000.000 (Onshore)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E23-FREELANCE', 'Freelance KITAS (E23)', 'KITAS/Limited Stay', 'Official title: Freelance KITAS (E23)', 'See details', 'IDR 25.800.000 (Offshore) / 27.500.000 (Onshore)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E33G', 'Working Holiday Visa', 'KITAS/Limited Stay', 'Official title: Working Holiday Visa', 'See details', 'IDR 13.000.000 (Offshore) / 14.000.000 (Onshore)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E28A', 'Tourism', 'KITAS/Limited Stay', 'Official title: Tourism', 'See details', 'IDR 17.000.000 (Offshore) / 19.000.000 (Onshore)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E31A', 'Business', 'KITAS/Limited Stay', 'Official title: Business', 'See details', 'IDR 11.000.000 (1 Year) / 15.000.000 (2 Years)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E31B', 'Medical Treatment', 'KITAS/Limited Stay', 'Official title: Medical Treatment', 'See details', 'IDR 11.000.000 (1 Year) / 15.000.000 (2 Years)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E31F', 'Government Assignment', 'KITAS/Limited Stay', 'Official title: Government Assignment', 'See details', 'IDR 11.000.000 (1 Year) / 15.000.000 (2 Years)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E33E', 'Ship and Aircraft Crew', 'KITAS/Limited Stay', 'Official title: Ship and Aircraft Crew', 'See details', 'IDR 14.000.000 (Offshore) / 16.000.000 (Onshore)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E33F', 'Ship Crew in Indonesian Waters', 'KITAS/Limited Stay', 'Official title: Ship Crew in Indonesian Waters', 'See details', 'IDR 14.000.000 (Offshore) / 16.000.000 (Onshore)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E35', 'Content Creator', 'KITAS/Limited Stay', 'Official title: Content Creator', 'See details', 'Contact for Quote', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('KITAP-INVESTOR', 'Social Activity', 'KITAS/Limited Stay', 'Official title: Social Activity', 'See details', 'IDR 55.000.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('KITAP-FAMILY', 'Arts and Culture Performance', 'KITAS/Limited Stay', 'Official title: Arts and Culture Performance', 'See details', 'IDR 33.000.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('KITAP-RETIREMENT', 'Music Performance', 'KITAS/Limited Stay', 'Official title: Music Performance', 'See details', 'IDR 45.000.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('EPO', 'Music Performance Crew', 'Immigration Service', 'Official title: Music Performance Crew', 'See details', 'IDR 700.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('ERP', 'Talent and Arts Performance', 'Immigration Service', 'Official title: Talent and Arts Performance', 'See details', 'IDR 800.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('SKTT', 'Sports Activity', 'Immigration Service', 'Official title: Sports Activity', 'See details', 'IDR 1.500.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('DOMICILE', 'Athlete', 'Immigration Service', 'Official title: Athlete', 'See details', 'IDR 800.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('E23-FREELANCE', 'Freelance KITAS (E23)', 'KITAS/Limited Stay', 'Official title: Freelance KITAS (E23)', 'See details', 'IDR 25.800.000 (Offshore) / 27.500.000 (Onshore)', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('EPO', 'EPO (Exit Permit Only)', 'Immigration Service', 'Official title: EPO (Exit Permit Only)', 'See details', 'IDR 700.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('ERP', 'ERP (Exit Re-entry Permit)', 'Immigration Service', 'Official title: ERP (Exit Re-entry Permit)', 'See details', 'IDR 800.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True}),
    ('SKTT', 'SKTT Registration', 'Immigration Service', 'Official title: SKTT Registration', 'See details', 'IDR 1.500.000', [], {'source': 'zantara_curated_2026', 'is_agency_product': True})
]

async def seed_visa_types():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url: return
    conn = await asyncpg.connect(db_url)
    try:
        print(f'Seeding {len(VISA_TYPES)} Curated Visa Types...')
        await conn.execute('CREATE TABLE IF NOT EXISTS visa_types (code TEXT PRIMARY KEY, name TEXT, category TEXT, description TEXT, duration TEXT, cost_visa TEXT, requirements TEXT[], metadata JSONB, created_at TIMESTAMP DEFAULT NOW(), last_updated TIMESTAMP DEFAULT NOW());')
        try: await conn.execute('ALTER TABLE visa_types ADD COLUMN IF NOT EXISTS description TEXT;')
        except: pass
        for visa in VISA_TYPES:
            exists = await conn.fetchval('SELECT 1 FROM visa_types WHERE code = $1', visa['code'])
            if exists:
                await conn.execute('UPDATE visa_types SET name=$2, category=$3, description=$4, duration=$5, cost_visa=$6, requirements=$7, metadata=$8, last_updated=NOW() WHERE code=$1', visa['code'], visa['name'], visa['category'], visa['description'], visa['duration'], visa['cost_visa'], visa['requirements'], json.dumps(visa['metadata']))
            else:
                await conn.execute('INSERT INTO visa_types (code, name, category, description, duration, cost_visa, requirements, metadata) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)', visa['code'], visa['name'], visa['category'], visa['description'], visa['duration'], visa['cost_visa'], visa['requirements'], json.dumps(visa['metadata']))
        print('Done.')
    finally: await conn.close()

if __name__ == '__main__':
    asyncio.run(seed_visa_types())
