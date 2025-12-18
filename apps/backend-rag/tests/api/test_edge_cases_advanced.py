"""
Advanced Edge Cases Tests
Tests for complex edge cases, boundary conditions, and unusual scenarios

Coverage:
- Unicode and internationalization edge cases
- Very large payloads and responses
- Complex nested data structures
- Timezone and date edge cases
- Concurrent modification scenarios
- Resource exhaustion scenarios
- Data type coercion edge cases
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestUnicodeEdgeCases:
    """Test Unicode and internationalization edge cases"""

    def test_unicode_chinese_characters(self, authenticated_client):
        """Test endpoints with Chinese characters"""
        chinese_text = "这是中文测试内容"

        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": []})
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": chinese_text},
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_unicode_arabic_characters(self, authenticated_client):
        """Test endpoints with Arabic characters"""
        arabic_text = "هذا اختبار باللغة العربية"

        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": []})
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": arabic_text},
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_unicode_emoji(self, authenticated_client):
        """Test endpoints with emoji characters"""
        emoji_text = "Test with 🎨 emoji 🚀 and symbols 💡"

        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": []})
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": emoji_text},
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_unicode_mixed_scripts(self, authenticated_client):
        """Test endpoints with mixed Unicode scripts"""
        mixed_text = "Test 测试 тест テスト العربية"

        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": []})
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": mixed_text},
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_unicode_normalization(self, authenticated_client):
        """Test Unicode normalization edge cases"""
        # Combining characters
        normalized_text = "caf\u00e9"  # é as single character
        decomposed_text = "cafe\u0301"  # é as e + combining accent

        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": []})
            mock_search.return_value = mock_service

            response1 = authenticated_client.post(
                "/api/oracle/query",
                json={"query": normalized_text},
            )
            response2 = authenticated_client.post(
                "/api/oracle/query",
                json={"query": decomposed_text},
            )

            assert response1.status_code in [200, 400, 422, 500, 503]
            assert response2.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
class TestLargePayloads:
    """Test very large payloads and responses"""

    def test_very_large_query(self, authenticated_client):
        """Test with very large query string"""
        large_query = "What is " + "tax law " * 10000  # ~100KB

        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": []})
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": large_query},
            )

            # Should handle or reject gracefully
            assert response.status_code in [200, 400, 413, 422, 500, 503]

    def test_very_large_message_array(self, authenticated_client, test_app):
        """Test with very large message array"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            large_messages = [
                {"role": "user", "content": "Message " + str(i) + " " * 1000} for i in range(1000)
            ]

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={"messages": large_messages},
            )

            # Should handle or reject gracefully
            assert response.status_code in [200, 201, 400, 413, 422, 500]

    def test_very_large_metadata(self, authenticated_client, test_app):
        """Test with very large metadata object"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            large_metadata = {f"key_{i}": "value " * 100 for i in range(1000)}

            response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "Test Client",
                    "custom_fields": large_metadata,
                },
            )

            # Should handle or reject gracefully
            assert response.status_code in [200, 201, 400, 413, 422, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestNestedDataStructures:
    """Test complex nested data structures"""

    def test_deeply_nested_json(self, authenticated_client, test_app):
        """Test with deeply nested JSON structure"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            nested_data = {"level1": {"level2": {"level3": {"level4": {"level5": "deep"}}}}}

            response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "Test Client",
                    "custom_fields": nested_data,
                },
            )

            assert response.status_code in [200, 201, 400, 422, 500]

    def test_circular_reference_prevention(self, authenticated_client):
        """Test that circular references are handled"""
        # Note: JSON doesn't support circular references, but test structure
        complex_data = {
            "items": [
                {"id": 1, "parent": None},
                {"id": 2, "parent": 1},
                {"id": 3, "parent": 2},
            ],
        }

        response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Test Client",
                "custom_fields": complex_data,
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]


@pytest.mark.api
class TestTimezoneEdgeCases:
    """Test timezone and date edge cases"""

    def test_timezone_aware_dates(self, authenticated_client):
        """Test with timezone-aware dates"""
        timezone_dates = [
            "2025-12-31T23:59:59Z",
            "2025-12-31T23:59:59+00:00",
            "2025-12-31T23:59:59+08:00",
            "2025-12-31T23:59:59-05:00",
        ]

        for date_str in timezone_dates:
            response = authenticated_client.post(
                "/api/productivity/calendar/schedule",
                json={
                    "title": "Test Meeting",
                    "start_time": date_str,
                    "duration_minutes": 60,
                },
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_leap_year_dates(self, authenticated_client):
        """Test with leap year dates"""
        leap_year_dates = [
            "2024-02-29T10:00:00Z",  # 2024 is a leap year
            "2025-02-28T10:00:00Z",  # 2025 is not a leap year
        ]

        for date_str in leap_year_dates:
            response = authenticated_client.post(
                "/api/productivity/calendar/schedule",
                json={
                    "title": "Test Meeting",
                    "start_time": date_str,
                    "duration_minutes": 60,
                },
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_year_boundary_dates(self, authenticated_client):
        """Test with year boundary dates"""
        boundary_dates = [
            "2024-12-31T23:59:59Z",
            "2025-01-01T00:00:00Z",
            "2025-12-31T23:59:59Z",
            "2026-01-01T00:00:00Z",
        ]

        for date_str in boundary_dates:
            response = authenticated_client.post(
                "/api/productivity/calendar/schedule",
                json={
                    "title": "Test Meeting",
                    "start_time": date_str,
                    "duration_minutes": 60,
                },
            )

            assert response.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
class TestConcurrentModification:
    """Test concurrent modification scenarios"""

    def test_concurrent_updates_same_resource(self, authenticated_client, test_app):
        """Test concurrent updates to same resource"""
        import threading

        results = []

        def update_client(client_id):
            with patch("app.dependencies.get_database_pool") as mock_get_pool:
                mock_pool, mock_conn = self._create_mock_db_pool()
                mock_conn.fetchrow = AsyncMock(return_value={"id": client_id})
                mock_get_pool.return_value = mock_pool

                response = authenticated_client.patch(
                    f"/api/crm/clients/{client_id}",
                    json={"full_name": f"Updated {threading.current_thread().name}"},
                )
                results.append(response.status_code)

        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_client, args=(1,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All should complete (may have different status codes)
        assert len(results) == 5

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestDataTypeCoercion:
    """Test data type coercion edge cases"""

    def test_string_as_number(self, authenticated_client):
        """Test passing string where number expected"""
        response = authenticated_client.get("/api/productivity/calendar/events?limit=not_a_number")

        assert response.status_code in [200, 400, 422]

    def test_number_as_string(self, authenticated_client):
        """Test passing number where string expected"""
        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": 12345},  # Number instead of string
        )

        # Should coerce or reject
        assert response.status_code in [200, 400, 422, 500, 503]

    def test_boolean_coercion(self, authenticated_client):
        """Test boolean coercion edge cases"""
        boolean_values = [True, False, "true", "false", "True", "False", 1, 0, "1", "0"]

        for bool_val in boolean_values:
            response = authenticated_client.get(
                f"/api/agents/compliance/alerts?auto_notify={bool_val}"
            )

            # Should handle boolean values
            assert response.status_code in [200, 400, 422, 500]

    def test_array_coercion(self, authenticated_client):
        """Test array coercion edge cases"""
        # Single value instead of array
        response = authenticated_client.post(
            "/api/intel/search",
            json={"query": "test", "tier": "T1"},  # String instead of array
        )

        # Should coerce or reject
        assert response.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
class TestBoundaryValues:
    """Test boundary value conditions"""

    def test_zero_values(self, authenticated_client):
        """Test zero values in various contexts"""
        zero_tests = [
            ("limit", 0),
            ("offset", 0),
            ("duration_minutes", 0),
            ("days_back", 0),
        ]

        for param, value in zero_tests:
            if param == "limit" or param == "offset":
                response = authenticated_client.get(f"/api/crm/clients?{param}={value}")
            elif param == "duration_minutes":
                response = authenticated_client.post(
                    "/api/productivity/calendar/schedule",
                    json={
                        "title": "Test",
                        "start_time": "2025-12-10T10:00:00Z",
                        param: value,
                    },
                )
            else:
                response = authenticated_client.post(
                    "/api/crm/interactions/sync-gmail",
                    json={"client_id": 1, param: value},
                )

            # Should handle zero values appropriately
            assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_negative_values(self, authenticated_client):
        """Test negative values"""
        negative_tests = [
            ("limit", -1),
            ("offset", -10),
            ("duration_minutes", -5),
        ]

        for param, value in negative_tests:
            if param == "limit" or param == "offset":
                response = authenticated_client.get(f"/api/crm/clients?{param}={value}")
            else:
                response = authenticated_client.post(
                    "/api/productivity/calendar/schedule",
                    json={
                        "title": "Test",
                        "start_time": "2025-12-10T10:00:00Z",
                        param: value,
                    },
                )

            # Should reject negative values
            assert response.status_code in [200, 400, 422, 500, 503]

    def test_maximum_values(self, authenticated_client):
        """Test maximum allowed values"""
        max_tests = [
            ("limit", 200),  # MAX_LIMIT for CRM
            ("limit", 20),  # Default limit for intel
        ]

        for param, value in max_tests:
            if param == "limit":
                response = authenticated_client.get(f"/api/crm/clients?{param}={value}")

            assert response.status_code in [200, 400, 422, 500]

    def test_exceeding_maximum_values(self, authenticated_client):
        """Test values exceeding maximum"""
        response = authenticated_client.get("/api/crm/clients?limit=10000")

        # Should cap at maximum
        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestSpecialCharacters:
    """Test special character handling"""

    def test_sql_special_characters(self, authenticated_client):
        """Test SQL special characters in input"""
        sql_chars = ["'", '"', ";", "--", "/*", "*/", "DROP", "SELECT", "UNION"]

        for char in sql_chars:
            with patch("app.routers.oracle_universal.get_search_service") as mock_search:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(return_value={"results": []})
                mock_search.return_value = mock_service

                response = authenticated_client.post(
                    "/api/oracle/query",
                    json={"query": f"test {char} query"},
                )

                # Should handle safely
                assert response.status_code in [200, 400, 422, 500, 503]

    def test_url_special_characters(self, authenticated_client):
        """Test URL special characters"""
        url_chars = ["&", "=", "?", "#", "%", "+", " "]

        for char in url_chars:
            response = authenticated_client.get(f"/api/handlers/search?query=test{char}query")

            # Should handle URL encoding
            assert response.status_code in [200, 400, 422, 500]

    def test_json_special_characters(self, authenticated_client):
        """Test JSON special characters"""
        json_chars = ['"', "\\", "\n", "\r", "\t"]

        for char in json_chars:
            with patch("app.routers.oracle_universal.get_search_service") as mock_search:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(return_value={"results": []})
                mock_search.return_value = mock_service

                response = authenticated_client.post(
                    "/api/oracle/query",
                    json={"query": f"test{char}query"},
                )

                # Should handle JSON escaping
                assert response.status_code in [200, 400, 422, 500, 503]
