"""
CRM Database Migration - Add Audit Logging Support
Creates tables and indexes for comprehensive audit trails
"""

import asyncio
from datetime import datetime

from app.dependencies import get_database_pool
from app.utils.logging_utils import get_logger

logger = get_logger(__name__)


async def create_crm_audit_tables():
    """Create CRM audit logging tables"""

    try:
        pool = await get_database_pool()

        async with pool.acquire() as conn:
            logger.info("🔧 [CRM MIGRATION] Creating audit logging tables...")

            # Create main audit log table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS crm_audit_log (
                    id SERIAL PRIMARY KEY,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id INTEGER NOT NULL,
                    change_type VARCHAR(50) NOT NULL,
                    user_email VARCHAR(255) NOT NULL,
                    old_state JSONB,
                    new_state JSONB,
                    changes JSONB,
                    metadata JSONB,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            # Create indexes for performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_crm_audit_entity ON crm_audit_log(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_crm_audit_user ON crm_audit_log(user_email);
                CREATE INDEX IF NOT EXISTS idx_crm_audit_timestamp ON crm_audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_crm_audit_changes ON crm_audit_log USING GIN(changes);
                CREATE INDEX IF NOT EXISTS idx_crm_audit_metadata ON crm_audit_log USING GIN(metadata);
            """)

            # Create audit summary table for quick metrics
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS crm_audit_summary (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    entity_type VARCHAR(50) NOT NULL,
                    change_type VARCHAR(50) NOT NULL,
                    total_changes INTEGER DEFAULT 0,
                    unique_entities INTEGER DEFAULT 0,
                    active_users INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(date, entity_type, change_type)
                );
            """)

            # Create indexes for summary table
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_crm_summary_date ON crm_audit_summary(date);
                CREATE INDEX IF NOT EXISTS idx_crm_summary_entity ON crm_audit_summary(entity_type, change_type);
            """)

            logger.info("✅ [CRM MIGRATION] Audit logging tables created successfully")

    except Exception as e:
        logger.error(f"❌ [CRM MIGRATION] Failed to create audit tables: {e}")
        raise


async def create_crm_metrics_tables():
    """Create tables for CRM metrics storage"""

    try:
        pool = await get_database_pool()

        async with pool.acquire() as conn:
            logger.info("🔧 [CRM MIGRATION] Creating metrics tables...")

            # Create metrics snapshot table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS crm_metrics_snapshots (
                    id SERIAL PRIMARY KEY,
                    snapshot_date TIMESTAMP WITH TIME ZONE NOT NULL,
                    metric_name VARCHAR(100) NOT NULL,
                    metric_value NUMERIC NOT NULL,
                    labels JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            # Create indexes for metrics
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_crm_metrics_date ON crm_metrics_snapshots(snapshot_date);
                CREATE INDEX IF NOT EXISTS idx_crm_metrics_name ON crm_metrics_snapshots(metric_name);
                CREATE INDEX IF NOT EXISTS idx_crm_metrics_labels ON crm_metrics_snapshots USING GIN(labels);
            """)

            # Create client lifecycle tracking table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS crm_client_lifecycle (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    lifecycle_stage VARCHAR(50) NOT NULL,
                    stage_start_date TIMESTAMP WITH TIME ZONE NOT NULL,
                    stage_end_date TIMESTAMP WITH TIME ZONE,
                    duration_seconds INTEGER,
                    notes TEXT,
                    created_by VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
            """)

            # Create indexes for lifecycle tracking
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_crm_lifecycle_client ON crm_client_lifecycle(client_id);
                CREATE INDEX IF NOT EXISTS idx_crm_lifecycle_stage ON crm_client_lifecycle(lifecycle_stage);
                CREATE INDEX IF NOT EXISTS idx_crm_lifecycle_dates ON crm_client_lifecycle(stage_start_date, stage_end_date);
            """)

            logger.info("✅ [CRM MIGRATION] Metrics tables created successfully")

    except Exception as e:
        logger.error(f"❌ [CRM MIGRATION] Failed to create metrics tables: {e}")
        raise


async def create_crm_procedures():
    """Create stored procedures for CRM operations"""

    try:
        pool = await get_database_pool()

        async with pool.acquire() as conn:
            logger.info("🔧 [CRM MIGRATION] Creating stored procedures...")

            # Procedure to update audit summary
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_crm_audit_summary()
                RETURNS TRIGGER AS $$
                BEGIN
                    INSERT INTO crm_audit_summary (
                        date, entity_type, change_type, total_changes, unique_entities, active_users
                    )
                    SELECT 
                        DATE(Timestamp),
                        entity_type,
                        change_type,
                        COUNT(*) as total_changes,
                        COUNT(DISTINCT entity_id) as unique_entities,
                        COUNT(DISTINCT user_email) as active_users
                    FROM crm_audit_log
                    WHERE DATE(timestamp) = DATE(NEW.timestamp)
                    AND entity_type = NEW.entity_type
                    AND change_type = NEW.change_type
                    GROUP BY DATE(timestamp), entity_type, change_type
                    ON CONFLICT (date, entity_type, change_type)
                    DO UPDATE SET
                        total_changes = EXCLUDED.total_changes,
                        unique_entities = EXCLUDED.unique_entities,
                        active_users = EXCLUDED.active_users,
                        created_at = NOW();
                    
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)

            # Create trigger for automatic summary updates
            await conn.execute("""
                DROP TRIGGER IF EXISTS trigger_crm_audit_summary ON crm_audit_log;
                CREATE TRIGGER trigger_crm_audit_summary
                    AFTER INSERT ON crm_audit_log
                    FOR EACH ROW
                    EXECUTE FUNCTION update_crm_audit_summary();
            """)

            # Procedure to track client lifecycle
            await conn.execute("""
                CREATE OR REPLACE FUNCTION track_client_lifecycle()
                RETURNS TRIGGER AS $$
                BEGIN
                    -- When client status changes, end previous stage and start new one
                    IF TG_OP = 'UPDATE' AND OLD.status IS DISTINCT FROM NEW.status THEN
                        -- End previous stage
                        UPDATE crm_client_lifecycle
                        SET stage_end_date = NOW(),
                            duration_seconds = EXTRACT(EPOCH FROM (NOW() - stage_start_date))::INTEGER
                        WHERE client_id = NEW.id
                        AND stage_end_date IS NULL;
                        
                        -- Start new stage
                        INSERT INTO crm_client_lifecycle (
                            client_id, lifecycle_stage, stage_start_date, created_by
                        ) VALUES (
                            NEW.id, NEW.status, NOW(), NEW.updated_by
                        );
                    END IF;
                    
                    -- For new clients, start initial stage
                    IF TG_OP = 'INSERT' THEN
                        INSERT INTO crm_client_lifecycle (
                            client_id, lifecycle_stage, stage_start_date, created_by
                        ) VALUES (
                            NEW.id, NEW.status, NOW(), NEW.created_by
                        );
                    END IF;
                    
                    RETURN COALESCE(NEW, OLD);
                END;
                $$ LANGUAGE plpgsql;
            """)

            # Create trigger for lifecycle tracking
            await conn.execute("""
                DROP TRIGGER IF EXISTS trigger_client_lifecycle ON clients;
                CREATE TRIGGER trigger_client_lifecycle
                    AFTER INSERT OR UPDATE ON clients
                    FOR EACH ROW
                    EXECUTE FUNCTION track_client_lifecycle();
            """)

            logger.info("✅ [CRM MIGRATION] Stored procedures created successfully")

    except Exception as e:
        logger.error(f"❌ [CRM MIGRATION] Failed to create procedures: {e}")
        raise


async def backfill_existing_data():
    """Backfill audit data for existing clients"""

    try:
        pool = await get_database_pool()

        async with pool.acquire() as conn:
            logger.info("🔄 [CRM MIGRATION] Backfilling existing client data...")

            # Get all existing clients
            clients = await conn.fetch("SELECT * FROM clients ORDER BY created_at")

            backfilled_count = 0

            for client in clients:
                # Create audit entry for client creation
                await conn.execute(
                    """
                    INSERT INTO crm_audit_log (
                        entity_type, entity_id, change_type, user_email,
                        old_state, new_state, changes, metadata, timestamp
                    ) VALUES (
                        'client', $1, 'create', COALESCE($2, 'system'),
                        '{}', $3, $4, $5, $6
                    )
                """,
                    client["id"],
                    client["created_by"],
                    json.dumps(dict(client)),
                    json.dumps({"created": True}),
                    json.dumps({"migration": True, "backfilled": datetime.now().isoformat()}),
                    client["created_at"],
                )

                # Initialize lifecycle tracking
                await conn.execute(
                    """
                    INSERT INTO crm_client_lifecycle (
                        client_id, lifecycle_stage, stage_start_date, created_by
                    ) VALUES (
                        $1, $2, $3, $4
                    )
                    ON CONFLICT DO NOTHING
                """,
                    client["id"],
                    client["status"],
                    client["created_at"],
                    client["created_by"] or "system",
                )

                backfilled_count += 1

            logger.info(f"✅ [CRM MIGRATION] Backfilled {backfilled_count} existing clients")

    except Exception as e:
        logger.error(f"❌ [CRM MIGRATION] Failed to backfill data: {e}")
        raise


async def run_crm_migration():
    """Run complete CRM migration"""

    migration_start = datetime.now()

    try:
        logger.info("🚀 [CRM MIGRATION] Starting CRM audit logging migration...")

        # Step 1: Create audit tables
        await create_crm_audit_tables()

        # Step 2: Create metrics tables
        await create_crm_metrics_tables()

        # Step 3: Create stored procedures
        await create_crm_procedures()

        # Step 4: Backfill existing data
        await backfill_existing_data()

        migration_duration = (datetime.now() - migration_start).total_seconds()

        logger.info(
            f"🎉 [CRM MIGRATION] Migration completed successfully in {migration_duration:.2f}s"
        )

        return {
            "success": True,
            "migration_time": migration_duration,
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        migration_duration = (datetime.now() - migration_start).total_seconds()
        logger.error(f"❌ [CRM MIGRATION] Migration failed after {migration_duration:.2f}s: {e}")

        return {
            "success": False,
            "error": str(e),
            "migration_time": migration_duration,
            "failed_at": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    # Run migration directly
    import asyncio

    async def main():
        result = await run_crm_migration()
        print(f"Migration result: {result}")

    asyncio.run(main())
