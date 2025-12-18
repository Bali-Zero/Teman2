"""
Integration Tests for CRM Batch Operations
Tests bulk operations, batch updates, and bulk imports

Covers:
- Bulk client creation
- Batch practice updates
- Bulk interaction logging
- Batch document uploads
- Bulk status updates
- Import/export operations
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.database
class TestCRMBulkOperationsIntegration:
    """Test CRM bulk operations with real PostgreSQL"""

    @pytest.mark.asyncio
    async def test_bulk_client_creation(self, db_pool):
        """Test creating multiple clients in batch"""

        async with db_pool.acquire() as conn:
            # Prepare batch data
            clients_data = [
                (
                    f"Bulk Client {i}",
                    f"bulk.client{i}@example.com",
                    f"+6281234567{i:03d}",
                    "active",
                    "test@team.com",
                    datetime.now(),
                    datetime.now(),
                )
                for i in range(10)
            ]

            # Bulk insert
            client_ids = await conn.fetch(
                """
                INSERT INTO clients (full_name, email, phone, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                *zip(*clients_data),
            )

            assert len(client_ids) == 10

            # Verify all clients created
            for client_id_row in client_ids:
                client_id = client_id_row["id"]
                client = await conn.fetchrow(
                    "SELECT full_name, email FROM clients WHERE id = $1", client_id
                )
                assert client is not None

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE email LIKE 'bulk.client%@example.com'")

    @pytest.mark.asyncio
    async def test_batch_practice_status_update(self, db_pool):
        """Test batch updating practice statuses"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Batch Test Client",
                "batch.test@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Create multiple practices
            practice_ids = []
            for i in range(5):
                practice_id = await conn.fetchval(
                    """
                    INSERT INTO practices (client_id, practice_type_code, status, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    client_id,
                    "KITAS",
                    "inquiry",
                    datetime.now(),
                    datetime.now(),
                )
                practice_ids.append(practice_id)

            # Batch update all practices to "in_progress"
            updated_count = await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = $2
                WHERE id = ANY($3)
                """,
                "in_progress",
                datetime.now(),
                practice_ids,
            )

            assert updated_count is not None

            # Verify updates
            practices = await conn.fetch(
                "SELECT status FROM practices WHERE id = ANY($1)", practice_ids
            )
            assert all(p["status"] == "in_progress" for p in practices)

            # Cleanup
            await conn.execute("DELETE FROM practices WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_bulk_interaction_logging(self, db_pool):
        """Test logging multiple interactions in batch"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Bulk Interaction Client",
                "bulk.interaction@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Prepare bulk interactions
            interactions_data = [
                (
                    client_id,
                    "chat",
                    f"Interaction {i}",
                    "web_chat",
                    "test@team.com",
                    datetime.now(),
                )
                for i in range(20)
            ]

            # Bulk insert interactions
            interaction_ids = await conn.fetch(
                """
                INSERT INTO interactions (client_id, interaction_type, notes, channel, created_by, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                *zip(*interactions_data),
            )

            assert len(interaction_ids) == 20

            # Verify interactions
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM interactions WHERE client_id = $1", client_id
            )
            assert count == 20

            # Cleanup
            await conn.execute("DELETE FROM interactions WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_bulk_document_upload(self, db_pool):
        """Test bulk document uploads for practices"""

        async with db_pool.acquire() as conn:
            # Create client and practice
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Bulk Document Client",
                "bulk.doc@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (client_id, practice_type_code, status, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "in_progress",
                datetime.now(),
                datetime.now(),
            )

            # Bulk insert documents
            documents_data = [
                (
                    practice_id,
                    f"Document {i}",
                    f"drive_file_id_{i}",
                    "test@team.com",
                    datetime.now(),
                )
                for i in range(10)
            ]

            doc_ids = await conn.fetch(
                """
                INSERT INTO practice_documents (practice_id, document_name, drive_file_id, uploaded_by, uploaded_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                *zip(*documents_data),
            )

            assert len(doc_ids) == 10

            # Verify documents
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM practice_documents WHERE practice_id = $1", practice_id
            )
            assert count == 10

            # Cleanup
            await conn.execute("DELETE FROM practice_documents WHERE practice_id = $1", practice_id)
            await conn.execute("DELETE FROM practices WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_batch_client_search(self, db_pool):
        """Test searching multiple clients efficiently"""

        async with db_pool.acquire() as conn:
            # Create test clients
            client_ids = []
            for i in range(50):
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (full_name, email, phone, status, created_by, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    f"Search Client {i}",
                    f"search.client{i}@example.com",
                    f"+6281234567{i:03d}",
                    "active",
                    "test@team.com",
                    datetime.now(),
                    datetime.now(),
                )
                client_ids.append(client_id)

            # Search clients
            results = await conn.fetch(
                """
                SELECT id, full_name, email
                FROM clients
                WHERE email LIKE 'search.client%@example.com'
                ORDER BY created_at DESC
                LIMIT 20
                """
            )

            assert len(results) <= 20
            assert all("search.client" in r["email"] for r in results)

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE email LIKE 'search.client%@example.com'")

    @pytest.mark.asyncio
    async def test_bulk_status_transition(self, db_pool):
        """Test bulk status transitions for practices"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Status Transition Client",
                "status.transition@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Create practices in different statuses
            practice_ids = []
            statuses = ["inquiry", "quotation_sent", "payment_pending"]
            for status in statuses:
                for _ in range(3):
                    practice_id = await conn.fetchval(
                        """
                        INSERT INTO practices (client_id, practice_type_code, status, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING id
                        """,
                        client_id,
                        "KITAS",
                        status,
                        datetime.now(),
                        datetime.now(),
                    )
                    practice_ids.append(practice_id)

            # Bulk transition all to "in_progress"
            await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = $2
                WHERE id = ANY($3)
                """,
                "in_progress",
                datetime.now(),
                practice_ids,
            )

            # Verify all transitions
            practices = await conn.fetch(
                "SELECT status FROM practices WHERE id = ANY($1)", practice_ids
            )
            assert all(p["status"] == "in_progress" for p in practices)

            # Cleanup
            await conn.execute("DELETE FROM practices WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)


@pytest.mark.integration
@pytest.mark.database
class TestCRMImportExportIntegration:
    """Test CRM import/export operations"""

    @pytest.mark.asyncio
    async def test_client_export_csv(self, db_pool):
        """Test exporting clients to CSV format"""
        import csv
        import io

        async with db_pool.acquire() as conn:
            # Create test clients
            for i in range(5):
                await conn.execute(
                    """
                    INSERT INTO clients (full_name, email, phone, status, created_by, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    f"Export Client {i}",
                    f"export.client{i}@example.com",
                    f"+6281234567{i:03d}",
                    "active",
                    "test@team.com",
                    datetime.now(),
                    datetime.now(),
                )

            # Fetch clients
            clients = await conn.fetch(
                """
                SELECT full_name, email, phone, status
                FROM clients
                WHERE email LIKE 'export.client%@example.com'
                """
            )

            # Export to CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["full_name", "email", "phone", "status"])
            for client in clients:
                writer.writerow(
                    [client["full_name"], client["email"], client["phone"], client["status"]]
                )

            csv_content = output.getvalue()

            assert csv_content is not None
            assert "Export Client" in csv_content
            assert len(csv_content.split("\n")) >= 6  # Header + 5 clients

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE email LIKE 'export.client%@example.com'")

    @pytest.mark.asyncio
    async def test_practice_analytics_batch(self, db_pool):
        """Test batch analytics queries for practices"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Analytics Client",
                "analytics@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Create practices with different statuses
            statuses = ["inquiry", "in_progress", "completed", "cancelled"]
            for status in statuses:
                for _ in range(5):
                    await conn.execute(
                        """
                        INSERT INTO practices (client_id, practice_type_code, status, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        client_id,
                        "KITAS",
                        status,
                        datetime.now(),
                        datetime.now(),
                    )

            # Batch analytics query
            analytics = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM practices
                WHERE client_id = $1
                GROUP BY status
                """,
                client_id,
            )

            assert len(analytics) == len(statuses)
            assert all(row["count"] == 5 for row in analytics)

            # Cleanup
            await conn.execute("DELETE FROM practices WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)
