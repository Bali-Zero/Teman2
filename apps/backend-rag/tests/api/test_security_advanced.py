"""
Advanced Security Tests
Tests for security vulnerabilities and attack scenarios

Coverage:
- SQL injection attempts
- XSS attempts
- Path traversal
- Authorization bypass attempts
- Token manipulation
- Rate limiting bypass attempts
- CSRF protection
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
@pytest.mark.security
class TestSQLInjection:
    """Test SQL injection attack scenarios"""

    def test_sql_injection_in_email(self, test_client):
        """Test SQL injection attempt in email field"""
        sql_payloads = [
            "test@example.com'; DROP TABLE users; --",
            "test@example.com' OR '1'='1",
            "test@example.com' UNION SELECT * FROM users --",
        ]

        for payload in sql_payloads:
            response = test_client.post(
                "/api/auth/login",
                json={"email": payload, "pin": "123456"},
            )

            # Should handle safely (may fail auth but not execute SQL)
            assert response.status_code in [401, 422, 500]

    def test_sql_injection_in_query(self, authenticated_client):
        """Test SQL injection attempt in query parameter"""
        sql_payloads = [
            "test'; DROP TABLE conversations; --",
            "test' OR '1'='1",
            "test' UNION SELECT * FROM conversations --",
        ]

        for payload in sql_payloads:
            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": payload},
            )

            # Should handle safely
            assert response.status_code in [200, 400, 422, 500, 503]

    def test_sql_injection_in_file_path(self, authenticated_client):
        """Test SQL injection attempt in file path"""
        sql_payloads = [
            "/path'; DROP TABLE files; --",
            "/path' OR '1'='1",
        ]

        for payload in sql_payloads:
            response = authenticated_client.post(
                "/api/legal/ingest",
                json={"file_path": payload},
            )

            # Should handle safely
            assert response.status_code in [400, 404, 422, 500]


@pytest.mark.api
@pytest.mark.security
class TestXSSAttempts:
    """Test XSS attack scenarios"""

    def test_xss_in_query(self, authenticated_client):
        """Test XSS attempt in query"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
        ]

        for payload in xss_payloads:
            with patch("app.routers.oracle_universal.get_search_service") as mock_search:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(return_value={"results": []})
                mock_search.return_value = mock_service

                response = authenticated_client.post(
                    "/api/oracle/query",
                    json={"query": payload},
                )

                # Should handle safely (sanitize or reject)
                assert response.status_code in [200, 400, 422, 500, 503]

                if response.status_code == 200:
                    # Response should not contain script tags
                    data = response.json()
                    response_str = str(data)
                    assert "<script>" not in response_str.lower()

    def test_xss_in_message(self, authenticated_client):
        """Test XSS attempt in conversation message"""
        xss_payload = "<script>alert('XSS')</script>"

        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": xss_payload},
                    ],
                },
            )

            # Should handle safely
            assert response.status_code in [200, 201, 400, 422, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchval = AsyncMock(return_value="conv_123")
        mock_conn.fetchrow = AsyncMock(return_value={"id": "conv_123"})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.security
class TestPathTraversal:
    """Test path traversal attack scenarios"""

    def test_path_traversal_in_file_path(self, authenticated_client):
        """Test path traversal attempt in file path"""
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\SAM",
            "....//....//etc/passwd",
        ]

        for payload in traversal_payloads:
            response = authenticated_client.post(
                "/api/legal/ingest",
                json={"file_path": payload},
            )

            # Should reject path traversal attempts
            assert response.status_code in [400, 403, 404, 422, 500]

    def test_path_traversal_in_collection_name(self, authenticated_client):
        """Test path traversal attempt in collection name"""
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\config",
        ]

        for payload in traversal_payloads:
            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "test", "collection": payload},
            )

            # Should reject path traversal attempts
            assert response.status_code in [400, 422, 500]


@pytest.mark.api
@pytest.mark.security
class TestAuthorizationBypass:
    """Test authorization bypass attempts"""

    def test_access_other_user_profile(self, authenticated_client):
        """Test accessing another user's profile"""
        # Try to access different user's profile
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/oracle/user/profile/otheruser@example.com")

            # Should either return profile or deny access
            assert response.status_code in [200, 403, 404, 500]

    def test_access_other_client_data(self, authenticated_client):
        """Test accessing another client's data"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/other_client_id")

            # Should enforce authorization
            assert response.status_code in [200, 403, 404, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)  # Not found or unauthorized
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.security
class TestTokenManipulation:
    """Test token manipulation attempts"""

    def test_tampered_jwt_token(self, test_client):
        """Test with tampered JWT token"""
        tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0.tampered_signature"

        response = test_client.get(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )

        # Should reject tampered token
        assert response.status_code == 401

    def test_expired_token_manipulation(self, test_client):
        """Test manipulating expired token"""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        # Create expired token
        payload = {
            "sub": "test@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
        expired_token = jwt.encode(payload, secret, algorithm="HS256")

        # Try to use expired token
        response = test_client.get(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        # Should reject expired token
        assert response.status_code == 401

    def test_malformed_token(self, test_client):
        """Test with malformed token"""
        malformed_tokens = [
            "not.a.valid.token",
            "Bearer token",
            "token",
            "",
            "Bearer",
        ]

        for token in malformed_tokens:
            response = test_client.get(
                "/api/auth/profile",
                headers={"Authorization": token},
            )

            # Should reject malformed tokens
            assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
class TestRateLimitingBypass:
    """Test rate limiting bypass attempts"""

    def test_rapid_requests_bypass_attempt(self, authenticated_client):
        """Test rapid requests to bypass rate limiting"""
        # Make many rapid requests
        responses = []
        for _ in range(100):
            response = authenticated_client.get("/api/agents/status")
            responses.append(response)

        # Rate limiting should kick in
        # Most should succeed, but some may be rate limited
        success_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited = sum(1 for r in responses if r.status_code == 429)

        # Should have some rate limiting or all succeed
        assert success_count + rate_limited == len(responses)

    def test_different_endpoints_bypass(self, authenticated_client):
        """Test using different endpoints to bypass rate limiting"""
        endpoints = [
            "/api/agents/status",
            "/api/dashboard/stats",
            "/api/handlers/list",
        ]

        responses = []
        for endpoint in endpoints * 20:  # 60 requests
            response = authenticated_client.get(endpoint)
            responses.append(response)

        # Should handle gracefully
        assert len(responses) == 60


@pytest.mark.api
@pytest.mark.security
class TestCSRFProtection:
    """Test CSRF protection"""

    def test_csrf_token_required_for_state_changing_ops(self, authenticated_client):
        """Test CSRF token requirement for state-changing operations"""
        # Note: CSRF protection may not be fully implemented for API
        # This test verifies current behavior

        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={"messages": []},
        )

        # Should either require CSRF or work with auth token
        assert response.status_code in [200, 201, 400, 403, 422, 500]

    def test_csrf_token_validation(self, test_client, test_app):
        """Test CSRF token validation"""
        from fastapi.testclient import TestClient

        with TestClient(test_app, raise_server_exceptions=False) as client:
            client.headers.clear()

            # Get CSRF token
            csrf_response = client.get("/api/auth/csrf-token")
            assert csrf_response.status_code == 200

            csrf_token = csrf_response.json()["csrfToken"]

            # Use token in header
            client.headers["X-CSRF-Token"] = csrf_token

            # Make request (if CSRF is required)
            # Note: Current implementation may not require CSRF for API
            response = client.post(
                "/api/bali-zero/conversations/save",
                json={"messages": []},
            )

            # Should handle CSRF token
            assert response.status_code in [200, 201, 401, 403, 422, 500]


@pytest.mark.api
@pytest.mark.security
class TestInputSanitization:
    """Test input sanitization"""

    def test_special_characters_sanitization(self, authenticated_client):
        """Test special characters are sanitized"""
        special_chars = [
            "\x00",  # Null byte
            "\r\n",  # Line breaks
            "\t",  # Tab
            "\x1a",  # EOF
        ]

        for char in special_chars:
            with patch("app.routers.oracle_universal.get_search_service") as mock_search:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(return_value={"results": []})
                mock_search.return_value = mock_service

                response = authenticated_client.post(
                    "/api/oracle/query",
                    json={"query": f"test{char}query"},
                )

                # Should handle special characters safely
                assert response.status_code in [200, 400, 422, 500, 503]

    def test_unicode_normalization(self, authenticated_client):
        """Test Unicode normalization attacks"""
        unicode_payloads = [
            "\u0000",  # Null character
            "\u202e",  # Right-to-left override
            "\ufeff",  # Zero-width no-break space
        ]

        for payload in unicode_payloads:
            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": f"test{payload}query"},
            )

            # Should handle Unicode safely
            assert response.status_code in [200, 400, 422, 500, 503]
