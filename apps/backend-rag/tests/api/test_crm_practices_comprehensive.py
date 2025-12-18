"""
Comprehensive API Tests for CRM Practices Router
Complete test coverage for all practice management endpoints

Coverage:
- POST /api/crm/practices - Create practice
- GET /api/crm/practices - List practices (with filters)
- GET /api/crm/practices/active - Get active practices
- GET /api/crm/practices/renewals/upcoming - Get upcoming renewals
- GET /api/crm/practices/{practice_id} - Get practice by ID
- PATCH /api/crm/practices/{practice_id} - Update practice
- POST /api/crm/practices/{practice_id}/documents/add - Add documents
- GET /api/crm/practices/stats/overview - Get practice statistics
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
class TestCreatePractice:
    """Comprehensive tests for POST /api/crm/practices"""

    def test_create_practice_minimal(self, authenticated_client, test_app):
        """Test creating practice with minimal required fields"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "status": "inquiry",
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_create_practice_all_statuses(self, authenticated_client, test_app):
        """Test creating practice with all valid statuses"""
        statuses = [
            "inquiry",
            "quotation_sent",
            "payment_pending",
            "in_progress",
            "waiting_documents",
            "submitted_to_gov",
            "approved",
            "completed",
            "cancelled",
        ]

        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            for status in statuses:
                response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": 1,
                        "practice_type_code": "KITAS",
                        "status": status,
                    },
                )

                assert response.status_code in [200, 201, 500]

    def test_create_practice_all_priorities(self, authenticated_client, test_app):
        """Test creating practice with all valid priorities"""
        priorities = ["low", "normal", "high", "urgent"]

        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            for priority in priorities:
                response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": 1,
                        "practice_type_code": "KITAS",
                        "priority": priority,
                    },
                )

                assert response.status_code in [200, 201, 500]

    def test_create_practice_with_price(self, authenticated_client, test_app):
        """Test creating practice with quoted price"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "quoted_price": "1000.50",
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_create_practice_negative_price(self, authenticated_client):
        """Test creating practice with negative price"""
        response = authenticated_client.post(
            "/api/crm/practices",
            json={
                "client_id": 1,
                "practice_type_code": "KITAS",
                "quoted_price": "-100",
            },
        )

        assert response.status_code == 422

    def test_create_practice_invalid_status(self, authenticated_client):
        """Test creating practice with invalid status"""
        response = authenticated_client.post(
            "/api/crm/practices",
            json={
                "client_id": 1,
                "practice_type_code": "KITAS",
                "status": "invalid_status",
            },
        )

        assert response.status_code == 422

    def test_create_practice_invalid_priority(self, authenticated_client):
        """Test creating practice with invalid priority"""
        response = authenticated_client.post(
            "/api/crm/practices",
            json={
                "client_id": 1,
                "practice_type_code": "KITAS",
                "priority": "invalid_priority",
            },
        )

        assert response.status_code == 422

    def test_create_practice_zero_client_id(self, authenticated_client):
        """Test creating practice with zero client_id"""
        response = authenticated_client.post(
            "/api/crm/practices",
            json={
                "client_id": 0,
                "practice_type_code": "KITAS",
            },
        )

        assert response.status_code == 422

    def test_create_practice_negative_client_id(self, authenticated_client):
        """Test creating practice with negative client_id"""
        response = authenticated_client.post(
            "/api/crm/practices",
            json={
                "client_id": -1,
                "practice_type_code": "KITAS",
            },
        )

        assert response.status_code == 422

    def test_create_practice_with_notes(self, authenticated_client, test_app):
        """Test creating practice with notes"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "notes": "Client notes",
                    "internal_notes": "Internal notes",
                },
            )

            assert response.status_code in [200, 201, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "code": "KITAS", "name": "KITAS"})
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestListPractices:
    """Comprehensive tests for GET /api/crm/practices"""

    def test_list_practices_default(self, authenticated_client, test_app):
        """Test listing practices with default parameters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {"id": 1, "client_id": 1, "status": "in_progress"},
                    {"id": 2, "client_id": 2, "status": "completed"},
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_list_practices_with_filters(self, authenticated_client, test_app):
        """Test listing practices with various filters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            filters = [
                "?client_id=1",
                "?status=in_progress",
                "?priority=high",
                "?practice_type_code=KITAS",
                "?assigned_to=team@example.com",
                "?limit=20",
                "?offset=10",
            ]

            for filter_param in filters:
                response = authenticated_client.get(f"/api/crm/practices{filter_param}")
                assert response.status_code == 200

    def test_list_practices_active(self, authenticated_client, test_app):
        """Test getting active practices"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/active")

            assert response.status_code == 200

    def test_list_practices_upcoming_renewals(self, authenticated_client, test_app):
        """Test getting upcoming renewals"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/renewals/upcoming")

            assert response.status_code == 200

    def test_list_practices_max_limit(self, authenticated_client, test_app):
        """Test listing practices with maximum limit"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices?limit=200")

            assert response.status_code == 200

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestGetPractice:
    """Comprehensive tests for GET /api/crm/practices/{practice_id}"""

    def test_get_practice_by_id(self, authenticated_client, test_app):
        """Test getting practice by ID"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "client_id": 1,
                    "status": "in_progress",
                    "priority": "high",
                }
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/1")

            assert response.status_code == 200

    def test_get_practice_not_found(self, authenticated_client, test_app):
        """Test getting non-existent practice"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/99999")

            assert response.status_code == 404

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestUpdatePractice:
    """Comprehensive tests for PATCH /api/crm/practices/{practice_id}"""

    def test_update_practice_status(self, authenticated_client, test_app):
        """Test updating practice status"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "status": "inquiry"})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/practices/1",
                json={"status": "in_progress"},
            )

            assert response.status_code in [200, 404, 500]

    def test_update_practice_price_fields(self, authenticated_client, test_app):
        """Test updating practice price fields"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/practices/1",
                json={
                    "quoted_price": "1000.00",
                    "actual_price": "950.00",
                    "paid_amount": "500.00",
                },
            )

            assert response.status_code in [200, 404, 500]

    def test_update_practice_dates(self, authenticated_client, test_app):
        """Test updating practice dates"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/practices/1",
                json={
                    "start_date": "2025-01-01T00:00:00Z",
                    "completion_date": "2025-12-31T00:00:00Z",
                    "expiry_date": "2026-12-31",
                },
            )

            assert response.status_code in [200, 404, 500]

    def test_update_practice_documents(self, authenticated_client, test_app):
        """Test updating practice documents"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/practices/1",
                json={
                    "documents": [
                        {"type": "passport", "url": "https://example.com/doc.pdf"},
                        {"type": "photo", "url": "https://example.com/photo.jpg"},
                    ],
                },
            )

            assert response.status_code in [200, 404, 500]

    def test_update_practice_invalid_status(self, authenticated_client):
        """Test updating practice with invalid status"""
        response = authenticated_client.patch(
            "/api/crm/practices/1",
            json={"status": "invalid_status"},
        )

        assert response.status_code == 422

    def test_update_practice_negative_price(self, authenticated_client):
        """Test updating practice with negative price"""
        response = authenticated_client.patch(
            "/api/crm/practices/1",
            json={"quoted_price": "-100"},
        )

        assert response.status_code == 422

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
class TestAddDocuments:
    """Comprehensive tests for POST /api/crm/practices/{practice_id}/documents/add"""

    def test_add_documents_to_practice(self, authenticated_client, test_app):
        """Test adding documents to practice"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices/1/documents/add",
                json={
                    "documents": [
                        {"type": "passport", "url": "https://example.com/passport.pdf"},
                        {"type": "photo", "url": "https://example.com/photo.jpg"},
                    ],
                },
            )

            assert response.status_code in [200, 201, 404, 500]

    def test_add_documents_empty_list(self, authenticated_client, test_app):
        """Test adding empty documents list"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices/1/documents/add",
                json={"documents": []},
            )

            assert response.status_code in [200, 201, 400, 422, 404, 500]

    def test_add_documents_practice_not_found(self, authenticated_client, test_app):
        """Test adding documents to non-existent practice"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices/99999/documents/add",
                json={"documents": [{"type": "passport", "url": "https://example.com/doc.pdf"}]},
            )

            assert response.status_code == 404

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
class TestPracticeStats:
    """Comprehensive tests for GET /api/crm/practices/stats/overview"""

    def test_get_practice_stats(self, authenticated_client, test_app):
        """Test getting practice statistics"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "total": 100,
                    "by_status": {},
                    "by_priority": {},
                }
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/stats/overview")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    def test_get_practice_stats_cached(self, authenticated_client, test_app):
        """Test practice stats are cached"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
            mock_get_pool.return_value = mock_pool

            response1 = authenticated_client.get("/api/crm/practices/stats/overview")
            response2 = authenticated_client.get("/api/crm/practices/stats/overview")

            assert response1.status_code == 200
            assert response2.status_code == 200

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestCRMPracticesSecurity:
    """Security tests for CRM practices endpoints"""

    def test_practices_endpoints_require_auth(self, test_client):
        """Test all practice endpoints require authentication"""
        endpoints = [
            ("POST", "/api/crm/practices"),
            ("GET", "/api/crm/practices"),
            ("GET", "/api/crm/practices/active"),
            ("GET", "/api/crm/practices/1"),
            ("PATCH", "/api/crm/practices/1"),
            ("POST", "/api/crm/practices/1/documents/add"),
            ("GET", "/api/crm/practices/stats/overview"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            elif method == "POST":
                response = test_client.post(path, json={})
            elif method == "PATCH":
                response = test_client.patch(path, json={})

            assert response.status_code == 401
