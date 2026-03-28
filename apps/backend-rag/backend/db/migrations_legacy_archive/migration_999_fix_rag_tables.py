"""
Migration 999: Fix Missing Agentic RAG Tables
Ensures parent_documents, golden_routes and query_route_clusters exist.
"""

from backend.db.migration_base import BaseMigration


class Migration999(BaseMigration):
    def __init__(self) -> None:
        super().__init__(
            migration_number=999,
            sql_file="013_fix_missing_rag_tables.sql",
            description="Fix missing parent_documents and golden_routes tables",
        )

    async def verify(self, conn) -> bool:
        tables = ["parent_documents", "golden_routes", "query_route_clusters"]
        for t in tables:
            exists = await conn.fetchval(
                f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{t}')"
            )
            if not exists:
                return False
        return True
