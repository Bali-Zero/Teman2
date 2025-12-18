"""
Extreme Edge Cases Integration Tests
Tests the most extreme edge cases and boundary conditions

Covers:
- Maximum data sizes
- Minimum data sizes
- Boundary conditions
- Extreme concurrency
- Data corruption scenarios
- Resource exhaustion
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.slow
class TestExtremeEdgeCases:
    """Extreme edge case integration tests"""

    @pytest.mark.asyncio
    async def test_maximum_text_length(self, db_pool):
        """Test maximum text length handling"""

        async with db_pool.acquire() as conn:
            # Create table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extreme_text_test (
                    id SERIAL PRIMARY KEY,
                    content TEXT
                )
                """
            )

            # Test with very long text (1MB)
            max_text = "A" * (1024 * 1024)  # 1MB

            text_id = await conn.fetchval(
                "INSERT INTO extreme_text_test (content) VALUES ($1) RETURNING id",
                max_text,
            )

            # Verify storage
            stored = await conn.fetchval(
                "SELECT content FROM extreme_text_test WHERE id = $1", text_id
            )

            assert len(stored) == len(max_text)

            # Cleanup
            await conn.execute("DELETE FROM extreme_text_test WHERE id = $1", text_id)

    @pytest.mark.asyncio
    async def test_empty_strings(self, db_pool):
        """Test empty string handling"""

        async with db_pool.acquire() as conn:
            # Test empty strings in various fields
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "",  # Empty name
                "empty@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Verify empty string stored
            client = await conn.fetchrow("SELECT full_name FROM clients WHERE id = $1", client_id)

            assert client["full_name"] == ""

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_special_characters(self, db_pool):
        """Test special character handling"""

        async with db_pool.acquire() as conn:
            # Test with various special characters
            special_chars = [
                "Test & Company",
                "Test < > Company",
                "Test 'Company'",
                'Test "Company"',
                "Test\nCompany",
                "Test\tCompany",
                "Test Company™",
                "Test Company®",
                "Test Company©",
            ]

            for special_name in special_chars:
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (
                        full_name, email, status, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    special_name,
                    f"special{hash(special_name)}@example.com",
                    "active",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )

                # Verify special characters stored correctly
                stored = await conn.fetchval(
                    "SELECT full_name FROM clients WHERE id = $1", client_id
                )

                assert stored == special_name

                # Cleanup
                await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_unicode_characters(self, db_pool):
        """Test Unicode character handling"""

        async with db_pool.acquire() as conn:
            # Test with various Unicode characters
            unicode_names = [
                "Test 测试",
                "Test Тест",
                "Test テスト",
                "Test اختبار",
                "Test 🚀 Company",
                "Test 😀 Company",
            ]

            for unicode_name in unicode_names:
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (
                        full_name, email, status, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    unicode_name,
                    f"unicode{hash(unicode_name)}@example.com",
                    "active",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )

                # Verify Unicode stored correctly
                stored = await conn.fetchval(
                    "SELECT full_name FROM clients WHERE id = $1", client_id
                )

                assert stored == unicode_name

                # Cleanup
                await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_null_values(self, db_pool):
        """Test NULL value handling"""

        async with db_pool.acquire() as conn:
            # Test with NULL values
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, phone, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "NULL Test Client",
                "null@example.com",
                None,  # NULL phone
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Verify NULL handling
            client = await conn.fetchrow("SELECT phone FROM clients WHERE id = $1", client_id)

            assert client["phone"] is None

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_extreme_json_metadata(self, db_pool):
        """Test extreme JSON metadata"""
        import json

        async with db_pool.acquire() as conn:
            # Create deeply nested JSON
            deep_json = {
                "level1": {
                    "level2": {
                        "level3": {
                            "level4": {
                                "level5": {
                                    "level6": {
                                        "level7": {"level8": {"level9": {"level10": "deep value"}}}
                                    }
                                }
                            }
                        }
                    }
                }
            }

            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "JSON Test Client",
                "json@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
                json.dumps(deep_json),
            )

            # Verify JSON storage
            stored = await conn.fetchval("SELECT metadata FROM clients WHERE id = $1", client_id)

            assert stored is not None
            parsed = json.loads(stored) if isinstance(stored, str) else stored
            assert (
                parsed["level1"]["level2"]["level3"]["level4"]["level5"]["level6"]["level7"][
                    "level8"
                ]["level9"]["level10"]
                == "deep value"
            )

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_concurrent_writes_same_record(self, db_pool):
        """Test concurrent writes to same record"""
        import asyncio

        async with db_pool.acquire() as conn:
            # Create record
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Concurrent Test",
                "concurrent@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Concurrent updates
            async def update_client(update_num):
                async with db_pool.acquire() as update_conn:
                    await update_conn.execute(
                        """
                        UPDATE clients
                        SET full_name = $1, updated_at = NOW()
                        WHERE id = $2
                        """,
                        f"Concurrent Update {update_num}",
                        client_id,
                    )

            # Run 10 concurrent updates
            await asyncio.gather(*[update_client(i) for i in range(10)])

            # Verify final state
            final = await conn.fetchrow("SELECT full_name FROM clients WHERE id = $1", client_id)

            assert final is not None
            assert "Concurrent Update" in final["full_name"]

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_large_batch_operations(self, db_pool):
        """Test large batch operations"""

        async with db_pool.acquire() as conn:
            # Create 1000 clients in batch
            batch_size = 1000
            values = [
                (
                    f"Batch Client {i}",
                    f"batch{i}@example.com",
                    "active",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )
                for i in range(batch_size)
            ]

            # Batch insert
            await conn.executemany(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                values,
            )

            # Verify batch insert
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE email LIKE 'batch%@example.com'"
            )

            assert count == batch_size

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE email LIKE 'batch%@example.com'")
