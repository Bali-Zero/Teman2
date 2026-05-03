"""
Migration 041: Add Missing Columns to Clients Table

Adds:
- avatar_url (already in backend model but missing in DB)
- passport_expiry (frontend sends, backend ignores)
- date_of_birth (frontend sends, backend ignores)
- lead_source (frontend sends, backend ignores)
- service_interest (frontend sends, backend ignores)
- company_name (present in frontend formData)
"""

migration_sql = """
-- Add missing columns to clients table

-- avatar_url: Already in backend Pydantic model, missing in DB
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'avatar_url'
    ) THEN
        ALTER TABLE clients ADD COLUMN avatar_url TEXT;
        RAISE NOTICE 'Added avatar_url column to clients table';
    END IF;
END $$;

-- passport_expiry: Date field for passport expiration tracking
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'passport_expiry'
    ) THEN
        ALTER TABLE clients ADD COLUMN passport_expiry DATE;
        RAISE NOTICE 'Added passport_expiry column to clients table';
    END IF;
END $$;

-- date_of_birth: Client's birth date for age verification
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'date_of_birth'
    ) THEN
        ALTER TABLE clients ADD COLUMN date_of_birth DATE;
        RAISE NOTICE 'Added date_of_birth column to clients table';
    END IF;
END $$;

-- lead_source: How we acquired this lead (website, referral, event, etc)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'lead_source'
    ) THEN
        ALTER TABLE clients ADD COLUMN lead_source VARCHAR(100);
        RAISE NOTICE 'Added lead_source column to clients table';
    END IF;
END $$;

-- service_interest: Array of services client is interested in
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'service_interest'
    ) THEN
        ALTER TABLE clients ADD COLUMN service_interest JSONB DEFAULT '[]'::jsonb;
        RAISE NOTICE 'Added service_interest column to clients table';
    END IF;
END $$;

-- company_name: For corporate clients (client_type = 'company')
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'company_name'
    ) THEN
        ALTER TABLE clients ADD COLUMN company_name VARCHAR(255);
        RAISE NOTICE 'Added company_name column to clients table';
    END IF;
END $$;

-- Create index for lead_source filtering
CREATE INDEX IF NOT EXISTS idx_clients_lead_source ON clients(lead_source);

-- Create GIN index for service_interest array queries
CREATE INDEX IF NOT EXISTS idx_clients_service_interest ON clients USING GIN(service_interest);
"""

rollback_sql = """
-- Rollback migration 041

DROP INDEX IF EXISTS idx_clients_service_interest;
DROP INDEX IF EXISTS idx_clients_lead_source;

ALTER TABLE clients DROP COLUMN IF EXISTS company_name;
ALTER TABLE clients DROP COLUMN IF EXISTS service_interest;
ALTER TABLE clients DROP COLUMN IF EXISTS lead_source;
ALTER TABLE clients DROP COLUMN IF EXISTS date_of_birth;
ALTER TABLE clients DROP COLUMN IF EXISTS passport_expiry;
ALTER TABLE clients DROP COLUMN IF EXISTS avatar_url;
"""


async def apply_migration(conn):
    """Apply migration 041"""
    await conn.execute(migration_sql)
    print("✅ Migration 041 applied: Added 6 missing columns to clients table")


async def rollback_migration(conn):
    """Rollback migration 041"""
    await conn.execute(rollback_sql)
    print("✅ Migration 041 rolled back: Removed 6 columns from clients table")
