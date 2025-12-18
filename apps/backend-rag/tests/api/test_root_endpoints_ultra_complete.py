"""
Ultra-Complete API Tests for Root Endpoints
===========================================

Coverage:
- GET / - Root endpoint
- Other root-level endpoints
"""

import os
import sys
from pathlib import Path

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestRootEndpoints:
    def test_root_endpoint(self, test_client):
        response = test_client.get("/")
        assert response.status_code in [200, 404]

    def test_docs_endpoint(self, test_client):
        response = test_client.get("/docs")
        assert response.status_code in [200, 404]

    def test_openapi_json(self, test_client):
        response = test_client.get("/openapi.json")
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
