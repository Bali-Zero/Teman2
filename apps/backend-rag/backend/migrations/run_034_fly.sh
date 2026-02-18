#!/bin/bash
# Run migration 034 on Fly.io
# Usage: fly ssh console -a nuzantara-backend --command "bash /app/backend/migrations/run_034_fly.sh"

echo "======================================================================"
echo "ZANTARA - Company-Centric CRM Migration (034)"
echo "======================================================================"
echo ""

cd /app

python3 << 'PYTHON_SCRIPT'
import os
import sys

os.environ['PYTHONPATH'] = '/app'

from sqlalchemy import create_engine, text
from backend.app.core.config import settings
import pathlib

database_url = settings.database_url
if not database_url:
    print("❌ DATABASE_URL not set")
    sys.exit(1)

# Convert asyncpg URL to psycopg2 if needed
if database_url.startswith('postgresql+asyncpg://'):
    database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

print(f"🗄️  Target: PostgreSQL on Fly.io")
print("")

# Read SQL
sql_file = pathlib.Path('/app/backend/db/migrations_v2/034_company_centric_crm.sql')
sql = sql_file.read_text()

# Connect and execute
print("🔌 Connecting to database...")
engine = create_engine(database_url)

with engine.connect() as conn:
    # Check if already applied
    result = conn.execute(text('SELECT version FROM schema_migrations WHERE version = 34'))
    if result.fetchone():
        print("⚠️  Migration 034 already applied - skipping")
        sys.exit(0)
    
    print("⚙️  Executing migration SQL...")
    conn.execute(text(sql))
    
    # Record migration
    conn.execute(text("INSERT INTO schema_migrations (version, applied_at) VALUES (34, NOW())"))
    
    conn.commit()
    
    # Verify
    result = conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('companies', 'client_company_links', 'company_documents', 'tax_records', 'tax_documents')
        ORDER BY table_name
    """))
    tables = result.fetchall()
    
    print("")
    print(f"✅ Migration completed successfully!")
    print("")
    print(f"📊 Created {len(tables)} tables:")
    for t in tables:
        print(f"   ✓ {t[0]}")

print("")
print("======================================================================")
print("🎉 Company-Centric CRM database is ready!")
print("======================================================================")
PYTHON_SCRIPT
