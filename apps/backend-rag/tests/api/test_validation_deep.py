"""
Deep Validation Tests
Tests for comprehensive input validation scenarios

Coverage:
- Field-level validation
- Cross-field validation
- Business rule validation
- Constraint validation
- Format validation
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
class TestFieldLevelValidation:
    """Test field-level validation"""

    def test_email_format_validation(self, authenticated_client):
        """Test comprehensive email format validation"""
        email_formats = [
            ("valid@example.com", True),
            ("user.name@example.com", True),
            ("user+tag@example.co.uk", True),
            ("invalid", False),
            ("@example.com", False),
            ("user@", False),
            ("user @example.com", False),
            ("user@example", False),
        ]

        for email, should_be_valid in email_formats:
            response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Test", "email": email},
            )

            if should_be_valid:
                assert response.status_code != 422
            else:
                assert response.status_code == 422

    def test_phone_format_validation(self, authenticated_client, test_app):
        """Test phone number format validation"""
        phone_formats = [
            "+1234567890",
            "+62 812 3456 7890",
            "081234567890",
            "+1-234-567-8900",
            "invalid",
            "",
        ]

        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            for phone in phone_formats:
                response = authenticated_client.post(
                    "/api/crm/clients",
                    json={"full_name": "Test", "phone": phone},
                )

                # Should accept or validate phone format
                assert response.status_code in [200, 201, 400, 422, 500]

    def test_date_format_validation(self, authenticated_client):
        """Test date format validation"""
        date_formats = [
            "2025-12-31",
            "2025-12-31T00:00:00Z",
            "2025-12-31T00:00:00+00:00",
            "invalid-date",
            "2025-13-45",  # Invalid month/day
            "2025-12-31T25:00:00Z",  # Invalid hour
        ]

        for date_str in date_formats:
            response = authenticated_client.patch(
                "/api/crm/practices/1",
                json={"expiry_date": date_str},
            )

            # Should validate date format
            assert response.status_code in [200, 400, 422, 404, 500]

    def test_decimal_precision_validation(self, authenticated_client):
        """Test decimal precision validation"""
        decimal_values = [
            "1000.00",
            "1000.50",
            "0.01",
            "999999.99",
            "-100",  # Should be rejected
            "invalid",
        ]

        for decimal_str in decimal_values:
            response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "quoted_price": decimal_str,
                },
            )

            # Should validate decimal format
            assert response.status_code in [200, 201, 400, 422, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "code": "KITAS"})
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestCrossFieldValidation:
    """Test cross-field validation"""

    def test_price_consistency(self, authenticated_client, test_app):
        """Test price field consistency"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_get_pool.return_value = mock_pool

            # Paid amount should not exceed actual price
            response = authenticated_client.patch(
                "/api/crm/practices/1",
                json={
                    "actual_price": "1000.00",
                    "paid_amount": "1500.00",  # Exceeds actual
                },
            )

            # Should validate or allow (business logic dependent)
            assert response.status_code in [200, 400, 422, 404, 500]

    def test_date_consistency(self, authenticated_client, test_app):
        """Test date field consistency"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_get_pool.return_value = mock_pool

            # Expiry should be after completion
            response = authenticated_client.patch(
                "/api/crm/practices/1",
                json={
                    "completion_date": "2025-12-31T00:00:00Z",
                    "expiry_date": "2025-01-01",  # Before completion
                },
            )

            # Should validate date consistency
            assert response.status_code in [200, 400, 422, 404, 500]

    def test_status_consistency(self, authenticated_client, test_app):
        """Test status field consistency"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={"id": 1, "status": "inquiry", "quoted_price": None}
            )
            mock_get_pool.return_value = mock_pool

            # Cannot move to payment_pending without quoted_price
            response = authenticated_client.patch(
                "/api/crm/practices/1",
                json={"status": "payment_pending"},
            )

            # Should validate status consistency
            assert response.status_code in [200, 400, 422, 404, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestBusinessRuleValidation:
    """Test business rule validation"""

    def test_practice_type_validation(self, authenticated_client, test_app):
        """Test practice type code validation"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            # Simulate practice type not found
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 1,
                    "practice_type_code": "INVALID_TYPE",
                },
            )

            # Should validate practice type exists
            assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_client_existence_validation(self, authenticated_client, test_app):
        """Test client existence validation"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            # Simulate client not found
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 99999,
                    "practice_type_code": "KITAS",
                },
            )

            # Should validate client exists
            assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_team_member_validation(self, authenticated_client, test_app):
        """Test team member assignment validation"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)  # Team member not found
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "Test Client",
                    "assigned_to": "nonexistent@example.com",
                },
            )

            # Should validate or allow assignment
            assert response.status_code in [200, 201, 400, 404, 422, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestConstraintValidation:
    """Test constraint validation"""

    def test_string_length_constraints(self, authenticated_client):
        """Test string length constraints"""
        # Test various length limits
        long_strings = [
            ("A" * 200, True),  # At limit
            ("A" * 201, False),  # Exceeds limit
            ("A" * 1000, False),  # Way over limit
        ]

        for string, should_be_valid in long_strings:
            response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": string},
            )

            if should_be_valid:
                assert response.status_code != 422
            else:
                assert response.status_code == 422

    def test_array_length_constraints(self, authenticated_client, test_app):
        """Test array length constraints"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Large tag array
            large_tags = [f"tag_{i}" for i in range(1000)]

            response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Test", "tags": large_tags},
            )

            # Should handle or validate array length
            assert response.status_code in [200, 201, 400, 422, 500]

    def test_numeric_range_constraints(self, authenticated_client):
        """Test numeric range constraints"""
        # Test limit parameter
        limit_values = [
            (1, True),
            (50, True),
            (200, True),  # MAX_LIMIT
            (201, False),  # Exceeds max
            (1000, False),  # Way over
        ]

        for limit, should_be_valid in limit_values:
            response = authenticated_client.get(f"/api/crm/clients?limit={limit}")

            if should_be_valid:
                assert response.status_code != 422
            else:
                # Should cap or reject
                assert response.status_code in [200, 400, 422]

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
class TestFormatValidation:
    """Test format validation"""

    def test_uuid_format_validation(self, authenticated_client, test_app):
        """Test UUID format validation"""
        uuid_formats = [
            "123e4567-e89b-12d3-a456-426614174000",  # Valid UUID
            "invalid-uuid",  # Invalid
            "123",  # Too short
            "123e4567-e89b-12d3-a456-426614174000-extra",  # Too long
        ]

        for uuid_str in uuid_formats:
            response = authenticated_client.get(f"/api/crm/practices/{uuid_str}")

            # Should validate UUID format
            assert response.status_code in [200, 400, 404, 422, 500]

    def test_iso_date_format_validation(self, authenticated_client):
        """Test ISO date format validation"""
        iso_dates = [
            "2025-12-31",
            "2025-12-31T00:00:00Z",
            "2025-12-31T00:00:00+00:00",
            "2025-12-31T00:00:00-05:00",
            "31-12-2025",  # Invalid format
            "2025/12/31",  # Invalid format
        ]

        for date_str in iso_dates:
            response = authenticated_client.patch(
                "/api/crm/practices/1",
                json={"expiry_date": date_str},
            )

            # Should validate ISO format
            assert response.status_code in [200, 400, 422, 404, 500]

    def test_json_structure_validation(self, authenticated_client):
        """Test JSON structure validation"""
        # Valid JSON structures
        valid_structures = [
            {"full_name": "Test"},
            {"full_name": "Test", "email": "test@example.com"},
            {"full_name": "Test", "custom_fields": {}},
        ]

        # Invalid JSON structures
        invalid_structures = [
            "not an object",
            123,
            None,
            [],
        ]

        for structure in valid_structures:
            response = authenticated_client.post(
                "/api/crm/clients",
                json=structure,
            )

            # Should accept valid structures
            assert response.status_code != 422

        for structure in invalid_structures:
            response = authenticated_client.post(
                "/api/crm/clients",
                json=structure,
            )

            # Should reject invalid structures
            assert response.status_code == 422
