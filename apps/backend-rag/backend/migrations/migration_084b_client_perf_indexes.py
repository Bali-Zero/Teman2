"""
Migration 084: Client performance indexes

Adds composite index for the LATERAL JOIN in list_clients
and passport_expiry filter index.
"""

UP_SQL = [
    # Composite index for LATERAL JOIN on interactions (list_clients query)
    """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interactions_client_date_desc
       ON interactions (client_id, interaction_date DESC)
       INCLUDE (sentiment, summary)""",
    # Passport expiry filter index
    """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_passport_expiry
       ON clients (passport_expiry)
       WHERE passport_expiry IS NOT NULL AND deleted_at IS NULL""",
]

DOWN_SQL = [
    "DROP INDEX IF EXISTS idx_interactions_client_date_desc",
    "DROP INDEX IF EXISTS idx_clients_passport_expiry",
]


async def up(conn):
    for stmt in UP_SQL:
        await conn.execute(stmt)


async def down(conn):
    for stmt in DOWN_SQL:
        await conn.execute(stmt)
