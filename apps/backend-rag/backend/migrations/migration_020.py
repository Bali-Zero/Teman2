"""
Migration 020: Collective Memory Vector Search
Sets up Qdrant collection and backfills embeddings for existing memories
"""

import asyncio
import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)


class Migration020:
    """Collective Memory Vector Search Migration"""

    migration_number = 20
    description = "Setup Qdrant collection and backfill embeddings for collective memories"
    dependencies = [18]  # Depends on collective memory system

    def __init__(self):
        self.sql_file = (
            Path(__file__).parent.parent / "db" / "migrations" / "020_collective_embeddings.sql"
        )

    async def apply(self, conn: asyncpg.Connection) -> bool:
        """Apply the migration"""
        try:
            # Check if already applied
            if await self.is_applied(conn):
                logger.info("Migration 020 already applied, skipping")
                return True

            # Read and execute SQL
            sql = self.sql_file.read_text()
            await conn.execute(sql)

            # Record migration
            await conn.execute(
                """
                INSERT INTO schema_migrations (migration_name, migration_number, description)
                VALUES ($1, $2, $3)
                ON CONFLICT (migration_name) DO NOTHING
                """,
                "migration_020",
                self.migration_number,
                self.description,
            )

            logger.info("Migration 020 SQL applied successfully")

            # Try to setup Qdrant collection and backfill (non-blocking)
            try:
                await self._setup_qdrant_and_backfill(conn)
            except Exception as e:
                logger.warning(f"Qdrant setup/backfill deferred: {e}")
                # Don't fail migration - Qdrant can be set up later

            return True

        except Exception as e:
            logger.error(f"Migration 020 failed: {e}")
            return False

    async def _setup_qdrant_and_backfill(self, conn: asyncpg.Connection) -> None:
        """Setup Qdrant collection and backfill existing memories"""
        try:
            from core.embeddings import create_embeddings_generator
            from core.qdrant_db import QdrantClient

            from app.core.config import settings
        except ImportError as e:
            logger.warning(f"Cannot import required modules for Qdrant setup: {e}")
            return

        # Create Qdrant client for collective_memories collection
        qdrant = QdrantClient(
            qdrant_url=settings.qdrant_url,
            collection_name="collective_memories",
        )

        try:
            # Create collection if not exists
            created = await qdrant.create_collection(
                vector_size=1536,  # OpenAI text-embedding-3-small
                distance="Cosine",
            )
            if created:
                logger.info("Created Qdrant collection 'collective_memories'")

            # Get memories that need embedding
            memories = await conn.fetch(
                """
                SELECT id, content, category, confidence, source_count, is_promoted
                FROM collective_memories
                WHERE embedding_synced = FALSE OR embedding_synced IS NULL
                """
            )

            if not memories:
                logger.info("No memories to backfill")
                return

            logger.info(f"Backfilling {len(memories)} memories to Qdrant")

            # Generate embeddings
            embedder = create_embeddings_generator()
            contents = [m["content"] for m in memories]
            embeddings = embedder.generate_embeddings(contents)

            # Prepare for upsert
            ids = [f"cm_{m['id']}" for m in memories]
            metadatas = [
                {
                    "id": m["id"],
                    "category": m["category"],
                    "confidence": m["confidence"],
                    "source_count": m["source_count"],
                    "is_promoted": m["is_promoted"],
                }
                for m in memories
            ]

            # Upsert to Qdrant
            result = await qdrant.upsert_documents(
                chunks=contents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids,
            )

            if result.get("success"):
                # Mark as synced in PostgreSQL
                memory_ids = [m["id"] for m in memories]
                await conn.execute(
                    """
                    UPDATE collective_memories
                    SET embedding_synced = TRUE
                    WHERE id = ANY($1)
                    """,
                    memory_ids,
                )
                logger.info(f"Backfilled {len(memories)} memories to Qdrant")
            else:
                logger.error(f"Qdrant upsert failed: {result}")

        finally:
            await qdrant.close()

    async def is_applied(self, conn: asyncpg.Connection) -> bool:
        """Check if migration was already applied"""
        try:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE migration_number = $1)",
                self.migration_number,
            )
            return result
        except Exception:
            return False

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify migration was applied correctly"""
        # Check column exists
        column_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'collective_memories' AND column_name = 'embedding_synced'
            )
            """
        )
        if not column_exists:
            logger.error("Column embedding_synced not found")
            return False
        return True


async def run_migration():
    """Run migration standalone"""
    import os

    database_url = os.getenv(
        "DATABASE_URL", "postgresql://balizero:test1234@localhost:5432/balizero"
    )

    conn = await asyncpg.connect(database_url)
    try:
        migration = Migration020()
        success = await migration.apply(conn)
        if success:
            verified = await migration.verify(conn)
            if verified:
                print("Migration 020 completed and verified")
            else:
                print("Migration 020 applied but verification failed")
        else:
            print("Migration 020 failed")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
