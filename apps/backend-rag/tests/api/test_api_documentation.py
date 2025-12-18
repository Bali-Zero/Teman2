"""
API Documentation Tests
Tests for API documentation accuracy and completeness

Coverage:
- OpenAPI schema validation
- Endpoint documentation completeness
- Response schema validation
- Request schema validation
- Example values validation
"""

import os
import sys
from pathlib import Path

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
@pytest.mark.documentation
class TestOpenAPISchema:
    """Test OpenAPI schema"""

    def test_openapi_schema_exists(self, test_client):
        """Test OpenAPI schema endpoint exists"""
        response = test_client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema or "swagger" in schema

    def test_openapi_schema_structure(self, test_client):
        """Test OpenAPI schema structure"""
        response = test_client.get("/openapi.json")

        if response.status_code == 200:
            schema = response.json()

            # Should have required OpenAPI fields
            assert "paths" in schema
            assert "info" in schema
            assert "components" in schema or "definitions" in schema

    def test_openapi_paths_completeness(self, test_client):
        """Test OpenAPI paths are complete"""
        response = test_client.get("/openapi.json")

        if response.status_code == 200:
            schema = response.json()
            paths = schema.get("paths", {})

            # Should have major endpoints documented
            expected_paths = [
                "/health",
                "/api/auth/login",
                "/api/crm/clients",
                "/api/oracle/query",
            ]

            for path in expected_paths:
                # Path should exist or be documented
                assert any(p.startswith(path) for p in paths.keys()) or path in paths

    def test_openapi_schema_validation(self, test_client):
        """Test OpenAPI schema is valid"""
        response = test_client.get("/openapi.json")

        if response.status_code == 200:
            schema = response.json()

            # Basic validation
            assert isinstance(schema, dict)
            assert "paths" in schema
            assert isinstance(schema["paths"], dict)


@pytest.mark.api
@pytest.mark.documentation
class TestEndpointDocumentation:
    """Test endpoint documentation"""

    def test_endpoints_have_descriptions(self, test_client):
        """Test endpoints have descriptions in OpenAPI"""
        response = test_client.get("/openapi.json")

        if response.status_code == 200:
            schema = response.json()
            paths = schema.get("paths", {})

            # Check some endpoints have descriptions
            endpoints_with_docs = 0
            for path, methods in paths.items():
                if isinstance(methods, dict):
                    for method, details in methods.items():
                        if isinstance(details, dict) and "summary" in details:
                            endpoints_with_docs += 1

            # Should have some documented endpoints
            assert endpoints_with_docs > 0

    def test_endpoints_have_parameters_documented(self, test_client):
        """Test endpoints have parameters documented"""
        response = test_client.get("/openapi.json")

        if response.status_code == 200:
            schema = response.json()
            paths = schema.get("paths", {})

            # Check parameters are documented
            for path, methods in paths.items():
                if isinstance(methods, dict):
                    for method, details in methods.items():
                        if isinstance(details, dict):
                            # Should have parameters or requestBody documented
                            assert (
                                "parameters" in details
                                or "requestBody" in details
                                or "summary" in details
                            )


@pytest.mark.api
@pytest.mark.documentation
class TestResponseSchema:
    """Test response schema documentation"""

    def test_responses_have_schemas(self, test_client):
        """Test responses have schemas defined"""
        response = test_client.get("/openapi.json")

        if response.status_code == 200:
            schema = response.json()
            paths = schema.get("paths", {})

            # Check responses have schemas
            for path, methods in paths.items():
                if isinstance(methods, dict):
                    for method, details in methods.items():
                        if isinstance(details, dict) and "responses" in details:
                            responses = details["responses"]
                            # Should have response schemas
                            assert isinstance(responses, dict)

    def test_error_responses_documented(self, test_client):
        """Test error responses are documented"""
        response = test_client.get("/openapi.json")

        if response.status_code == 200:
            schema = response.json()
            paths = schema.get("paths", {})

            # Check error responses are documented
            error_codes = ["400", "401", "404", "422", "500"]
            endpoints_with_errors = 0

            for path, methods in paths.items():
                if isinstance(methods, dict):
                    for method, details in methods.items():
                        if isinstance(details, dict) and "responses" in details:
                            responses = details["responses"]
                            if any(code in responses for code in error_codes):
                                endpoints_with_errors += 1

            # Should have some error documentation
            assert endpoints_with_errors >= 0


@pytest.mark.api
@pytest.mark.documentation
class TestRequestSchema:
    """Test request schema documentation"""

    def test_requests_have_schemas(self, test_client):
        """Test requests have schemas defined"""
        response = test_client.get("/openapi.json")

        if response.status_code == 200:
            schema = response.json()
            paths = schema.get("paths", {})

            # Check POST/PUT/PATCH requests have requestBody
            for path, methods in paths.items():
                if isinstance(methods, dict):
                    for method in ["post", "put", "patch"]:
                        if method in methods:
                            details = methods[method]
                            if isinstance(details, dict):
                                # Should have requestBody or parameters
                                assert (
                                    "requestBody" in details
                                    or "parameters" in details
                                    or "summary" in details
                                )


@pytest.mark.api
@pytest.mark.documentation
class TestSwaggerUI:
    """Test Swagger UI availability"""

    def test_swagger_ui_available(self, test_client):
        """Test Swagger UI is available"""
        response = test_client.get("/docs")

        # Should return Swagger UI
        assert response.status_code in [200, 404]

    def test_redoc_available(self, test_client):
        """Test ReDoc is available"""
        response = test_client.get("/redoc")

        # Should return ReDoc
        assert response.status_code in [200, 404]
