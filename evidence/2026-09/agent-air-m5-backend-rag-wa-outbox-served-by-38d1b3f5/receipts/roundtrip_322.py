import asyncio, asyncpg
from backend.db.migration_manager import MigrationManager

async def cols():
    conn = await asyncpg.connect("postgresql://nuzantara@localhost:5432/nuzantara_test_wa322")
    row = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='wa_outbox' AND column_name='served_by')")
    sv = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM _schema_versions WHERE migration_number=322)")
    sm = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE migration_name='322_wa_outbox_served_by')")
    await conn.close()
    return row, sv, sm

async def main():
    print("BEFORE:", await cols())
    mgr = MigrationManager("postgresql://nuzantara@localhost:5432/nuzantara_test_wa322")
    await mgr.connect()
    ok = await mgr.rollback_migration("322_wa_outbox_served_by")
    print("rollback_ok:", ok)
    print("AFTER ROLLBACK:", await cols())
    result = await mgr.apply_all_pending()
    print("reapply result:", {k: v for k, v in result.items() if k in ("applied","skipped","failed")})
    print("AFTER REAPPLY:", await cols())
    await mgr.close()

asyncio.run(main())
