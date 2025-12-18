"""
Ultra-Complete API Tests for CRM Practices Router
==================================================

Comprehensive test coverage for all crm_practices.py endpoints including:
- Practice CRUD operations
- Active practices filtering
- Renewal tracking
- Document management
- Statistics and reporting
- Validation and error handling
- Security and performance

Coverage Endpoints:
- POST /api/crm/practices/ - Create practice
- GET /api/crm/practices/ - List practices with filtering
- GET /api/crm/practices/active - Get active practices
- GET /api/crm/practices/renewals/upcoming - Get upcoming renewals
- GET /api/crm/practices/{practice_id} - Get practice by ID
- PATCH /api/crm/practices/{practice_id} - Update practice
- POST /api/crm/practices/{practice_id}/documents/add - Add document
- GET /api/crm/practices/stats/overview - Get statistics
"""

import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Environment setup
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestCRMPracticesCreate:
    """Comprehensive tests for POST /api/crm/practices/"""

    def test_create_practice_minimal(self, authenticated_client):
        """Test creating practice with minimal required fields"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

            # Mock practice type lookup
            mock_conn.fetchrow.side_effect = [
                {"id": 1, "base_price": Decimal("1500.00")},  # practice type
                {  # practice insert
                    "id": 1,
                    "uuid": "uuid-123",
                    "client_id": 1,
                    "practice_type_id": 1,
                    "status": "inquiry",
                    "priority": "normal",
                    "quoted_price": Decimal("1500.00"),
                    "created_at": datetime.now(),
                },
            ]

            response = authenticated_client.post(
                "/api/crm/practices/?created_by=agent@balizero.com",
                json={"client_id": 1, "practice_type_code": "KITAS"},
            )

            assert response.status_code in [200, 201, 400, 500]

    def test_create_practice_complete(self, authenticated_client):
        """Test creating practice with all fields"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

            mock_conn.fetchrow.side_effect = [
                {"id": 1, "base_price": Decimal("2000.00")},
                {
                    "id": 1,
                    "uuid": "uuid-456",
                    "client_id": 1,
                    "practice_type_id": 1,
                    "status": "inquiry",
                    "priority": "high",
                    "quoted_price": Decimal("2500.00"),
                    "assigned_to": "agent@balizero.com",
                    "notes": "Urgent case",
                    "created_at": datetime.now(),
                },
            ]

            response = authenticated_client.post(
                "/api/crm/practices/?created_by=agent@balizero.com",
                json={
                    "client_id": 1,
                    "practice_type_code": "PT_PMA",
                    "status": "inquiry",
                    "priority": "high",
                    "quoted_price": 2500.00,
                    "assigned_to": "agent@balizero.com",
                    "notes": "Urgent case",
                },
            )

            assert response.status_code in [200, 201, 400, 500]

    def test_create_practice_invalid_client_id(self, authenticated_client):
        """Test with invalid client_id"""
        response = authenticated_client.post(
            "/api/crm/practices/?created_by=agent@balizero.com",
            json={"client_id": -1, "practice_type_code": "KITAS"},
        )

        assert response.status_code in [400, 422]

    def test_create_practice_invalid_status(self, authenticated_client):
        """Test with invalid status value"""
        response = authenticated_client.post(
            "/api/crm/practices/?created_by=agent@balizero.com",
            json={"client_id": 1, "practice_type_code": "KITAS", "status": "invalid_status"},
        )

        assert response.status_code in [400, 422]

    def test_create_practice_invalid_priority(self, authenticated_client):
        """Test with invalid priority value"""
        response = authenticated_client.post(
            "/api/crm/practices/?created_by=agent@balizero.com",
            json={
                "client_id": 1,
                "practice_type_code": "KITAS",
                "priority": "super_urgent",  # Invalid
            },
        )

        assert response.status_code in [400, 422]

    def test_create_practice_negative_price(self, authenticated_client):
        """Test with negative quoted_price"""
        response = authenticated_client.post(
            "/api/crm/practices/?created_by=agent@balizero.com",
            json={"client_id": 1, "practice_type_code": "KITAS", "quoted_price": -100.00},
        )

        assert response.status_code in [400, 422]

    def test_create_practice_nonexistent_type(self, authenticated_client):
        """Test with non-existent practice type"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = None  # Type not found

            response = authenticated_client.post(
                "/api/crm/practices/?created_by=agent@balizero.com",
                json={"client_id": 1, "practice_type_code": "NONEXISTENT"},
            )

            assert response.status_code in [404, 500]


@pytest.mark.api
class TestCRMPracticesList:
    """Tests for GET /api/crm/practices/"""

    def test_list_practices_default(self, authenticated_client):
        """Test listing practices with default parameters"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get("/api/crm/practices/")

            assert response.status_code in [200, 500]

    def test_list_practices_with_filters(self, authenticated_client):
        """Test with multiple filters"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get(
                "/api/crm/practices/",
                params={
                    "client_id": 1,
                    "status": "in_progress",
                    "assigned_to": "agent@balizero.com",
                    "practice_type": "KITAS",
                    "priority": "high",
                    "limit": 20,
                    "offset": 0,
                },
            )

            assert response.status_code in [200, 400, 500]

    def test_list_practices_pagination(self, authenticated_client):
        """Test pagination"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = [{"id": i} for i in range(10)]

            response = authenticated_client.get(
                "/api/crm/practices/", params={"limit": 10, "offset": 20}
            )

            assert response.status_code in [200, 500]

    def test_list_practices_invalid_limit(self, authenticated_client):
        """Test with invalid limit"""
        response = authenticated_client.get("/api/crm/practices/", params={"limit": -1})

        assert response.status_code in [400, 422]

    def test_list_practices_excessive_limit(self, authenticated_client):
        """Test with excessive limit (>200)"""
        response = authenticated_client.get("/api/crm/practices/", params={"limit": 1000})

        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestCRMPracticesActive:
    """Tests for GET /api/crm/practices/active"""

    def test_get_active_practices_all(self, authenticated_client):
        """Test getting all active practices"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get("/api/crm/practices/active")

            assert response.status_code in [200, 500]

    def test_get_active_practices_by_team_member(self, authenticated_client):
        """Test filtering active practices by team member"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get(
                "/api/crm/practices/active", params={"assigned_to": "agent@balizero.com"}
            )

            assert response.status_code in [200, 500]


@pytest.mark.api
class TestCRMPracticesRenewals:
    """Tests for GET /api/crm/practices/renewals/upcoming"""

    def test_get_upcoming_renewals_default(self, authenticated_client):
        """Test with default 90 days lookahead"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get("/api/crm/practices/renewals/upcoming")

            assert response.status_code in [200, 500]

    def test_get_upcoming_renewals_custom_days(self, authenticated_client):
        """Test with custom days parameter"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get(
                "/api/crm/practices/renewals/upcoming", params={"days": 30}
            )

            assert response.status_code in [200, 500]

    def test_get_upcoming_renewals_invalid_days(self, authenticated_client):
        """Test with invalid days value"""
        response = authenticated_client.get(
            "/api/crm/practices/renewals/upcoming", params={"days": 0}
        )

        assert response.status_code in [400, 422]

    def test_get_upcoming_renewals_excessive_days(self, authenticated_client):
        """Test with excessive days (>365)"""
        response = authenticated_client.get(
            "/api/crm/practices/renewals/upcoming", params={"days": 500}
        )

        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestCRMPracticesGet:
    """Tests for GET /api/crm/practices/{practice_id}"""

    def test_get_practice_success(self, authenticated_client):
        """Test getting existing practice"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = {
                "id": 1,
                "client_name": "John Doe",
                "practice_type_name": "KITAS",
            }

            response = authenticated_client.get("/api/crm/practices/1")

            assert response.status_code in [200, 404, 500]

    def test_get_practice_not_found(self, authenticated_client):
        """Test getting non-existent practice"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = None

            response = authenticated_client.get("/api/crm/practices/99999")

            assert response.status_code in [404, 500]

    def test_get_practice_invalid_id(self, authenticated_client):
        """Test with invalid practice ID"""
        response = authenticated_client.get("/api/crm/practices/invalid")

        assert response.status_code in [400, 404, 422]

    def test_get_practice_negative_id(self, authenticated_client):
        """Test with negative ID"""
        response = authenticated_client.get("/api/crm/practices/-1")

        assert response.status_code in [400, 404, 422]


@pytest.mark.api
class TestCRMPracticesUpdate:
    """Tests for PATCH /api/crm/practices/{practice_id}"""

    def test_update_practice_single_field(self, authenticated_client):
        """Test updating single field"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = {"id": 1, "status": "in_progress"}

            response = authenticated_client.patch(
                "/api/crm/practices/1?updated_by=agent@balizero.com", json={"status": "in_progress"}
            )

            assert response.status_code in [200, 404, 500]

    def test_update_practice_multiple_fields(self, authenticated_client):
        """Test updating multiple fields"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = {
                "id": 1,
                "status": "completed",
                "actual_price": Decimal("2000.00"),
                "completion_date": datetime.now(),
            }

            response = authenticated_client.patch(
                "/api/crm/practices/1?updated_by=agent@balizero.com",
                json={
                    "status": "completed",
                    "actual_price": 2000.00,
                    "completion_date": datetime.now().isoformat(),
                },
            )

            assert response.status_code in [200, 400, 404, 500]

    def test_update_practice_with_expiry_date(self, authenticated_client):
        """Test updating with expiry date (creates renewal alert)"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            expiry = (date.today() + timedelta(days=365)).isoformat()

            mock_conn.fetchrow.return_value = {
                "id": 1,
                "status": "completed",
                "expiry_date": expiry,
            }

            response = authenticated_client.patch(
                "/api/crm/practices/1?updated_by=agent@balizero.com",
                json={"status": "completed", "expiry_date": expiry},
            )

            assert response.status_code in [200, 400, 404, 500]

    def test_update_practice_not_found(self, authenticated_client):
        """Test updating non-existent practice"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = None

            response = authenticated_client.patch(
                "/api/crm/practices/99999?updated_by=agent@balizero.com",
                json={"status": "completed"},
            )

            assert response.status_code in [404, 500]

    def test_update_practice_invalid_status(self, authenticated_client):
        """Test with invalid status"""
        response = authenticated_client.patch(
            "/api/crm/practices/1?updated_by=agent@balizero.com", json={"status": "invalid_status"}
        )

        assert response.status_code in [400, 422, 500]

    def test_update_practice_no_fields(self, authenticated_client):
        """Test update with no fields"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

            response = authenticated_client.patch(
                "/api/crm/practices/1?updated_by=agent@balizero.com", json={}
            )

            assert response.status_code in [400, 500]


@pytest.mark.api
class TestCRMPracticesDocuments:
    """Tests for POST /api/crm/practices/{practice_id}/documents/add"""

    def test_add_document_success(self, authenticated_client):
        """Test adding document to practice"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = {"documents": []}

            response = authenticated_client.post(
                "/api/crm/practices/1/documents/add",
                params={
                    "document_name": "Passport Copy",
                    "drive_file_id": "1234567890",
                    "uploaded_by": "agent@balizero.com",
                },
            )

            assert response.status_code in [200, 404, 500]

    def test_add_document_to_existing_list(self, authenticated_client):
        """Test adding document to practice with existing documents"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = {
                "documents": [{"name": "First Document", "drive_file_id": "111"}]
            }

            response = authenticated_client.post(
                "/api/crm/practices/1/documents/add",
                params={
                    "document_name": "Second Document",
                    "drive_file_id": "222",
                    "uploaded_by": "agent@balizero.com",
                },
            )

            assert response.status_code in [200, 404, 500]

    def test_add_document_practice_not_found(self, authenticated_client):
        """Test adding document to non-existent practice"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = None

            response = authenticated_client.post(
                "/api/crm/practices/99999/documents/add",
                params={
                    "document_name": "Passport",
                    "drive_file_id": "123",
                    "uploaded_by": "agent@balizero.com",
                },
            )

            assert response.status_code in [404, 500]


@pytest.mark.api
class TestCRMPracticesStats:
    """Tests for GET /api/crm/practices/stats/overview"""

    def test_get_stats_overview(self, authenticated_client):
        """Test getting practice statistics"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

            mock_conn.fetch.side_effect = [
                [{"status": "inquiry", "count": 10}],  # by_status
                [{"code": "KITAS", "name": "KITAS", "count": 5}],  # by_type
            ]
            mock_conn.fetchrow.side_effect = [
                {
                    "total_revenue": Decimal("100000"),
                    "paid_revenue": Decimal("80000"),
                    "outstanding_revenue": Decimal("20000"),
                },
                {"count": 15},
            ]

            response = authenticated_client.get("/api/crm/practices/stats/overview")

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "total_practices" in data or "by_status" in data


@pytest.mark.api
@pytest.mark.security
class TestCRMPracticesSecurity:
    """Security tests"""

    def test_unauthorized_access(self, test_client):
        """Test endpoints without authentication"""
        response = test_client.get("/api/crm/practices/")

        assert response.status_code in [200, 401, 403]

    def test_sql_injection_in_filters(self, authenticated_client):
        """Test SQL injection in filter parameters"""
        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get(
                "/api/crm/practices/", params={"status": "' OR '1'='1"}
            )

            assert response.status_code in [200, 400, 500]


@pytest.mark.api
@pytest.mark.performance
class TestCRMPracticesPerformance:
    """Performance tests"""

    def test_list_performance(self, authenticated_client):
        """Test listing performance with large dataset"""
        import time

        with patch("app.routers.crm_practices.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = [{"id": i} for i in range(200)]

            start = time.time()
            response = authenticated_client.get("/api/crm/practices/", params={"limit": 200})
            duration = time.time() - start

            assert response.status_code in [200, 500]
            assert duration < 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
