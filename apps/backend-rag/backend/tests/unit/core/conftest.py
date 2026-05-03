"""
Pytest configuration for backend/tests/unit/core/ tests.
Sets environment variables before any imports to prevent pydantic validation errors.

NOTE: Do NOT replace sys.modules["backend.app.core.config"] with a fake module.
That poisons the module cache for all tests running in the same session
(e.g. backend/tests/unit/app/deps/test_auth_hardened.py) and causes
cascading failures. The env vars below are sufficient for Settings validation.
"""

import os

# Set environment variables before any imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")
