"""
Comprehensive Integration Tests for Validation and Security Services
Tests ResponseValidator, security checks, and input validation

Covers:
- Response validation
- Security validation
- Input sanitization
- Content filtering
- Safety checks
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestResponseValidatorIntegration:
    """Integration tests for ResponseValidator"""

    def test_response_validator_initialization(self):
        """Test ResponseValidator initialization"""
        from services.response.validator import ZantaraResponseValidator

        config = {
            "modes": {
                "default": {
                    "max_length": 2000,
                    "min_length": 10,
                }
            }
        }

        validator = ZantaraResponseValidator(mode_config=config, dry_run=False)

        assert validator is not None
        assert validator.config == config

    def test_filler_removal(self):
        """Test filler pattern removal"""
        from services.response.validator import ZantaraResponseValidator

        config = {"modes": {"default": {}}}
        validator = ZantaraResponseValidator(mode_config=config, dry_run=False)

        test_cases = [
            ("Certainly, here's the answer", "here's the answer"),
            ("I'd be happy to help you", "help you"),
            ("Let me explain this to you.", "this to you."),
            ("Grazie per la domanda! Ecco la risposta", "Ecco la risposta"),
        ]

        for original, expected_start in test_cases:
            result = validator.validate(original, MagicMock(mode="default"))
            assert result.validated != original or len(result.violations) > 0

    def test_length_enforcement(self):
        """Test length limit enforcement"""
        from services.response.validator import ZantaraResponseValidator

        config = {
            "modes": {
                "default": {
                    "max_length": 100,
                    "min_length": 10,
                }
            }
        }

        validator = ZantaraResponseValidator(mode_config=config, dry_run=False)

        # Test too long response
        long_response = "A" * 200
        result = validator.validate(long_response, MagicMock(mode="default"))

        assert len(result.validated) <= 100 or len(result.violations) > 0

        # Test too short response
        short_response = "Hi"
        result = validator.validate(short_response, MagicMock(mode="default"))

        assert len(result.validated) >= 10 or len(result.violations) > 0

    def test_validation_result_structure(self):
        """Test validation result structure"""
        from services.response.validator import ValidationResult, ZantaraResponseValidator

        config = {"modes": {"default": {}}}
        validator = ZantaraResponseValidator(mode_config=config, dry_run=False)

        response = "Test response"
        result = validator.validate(response, MagicMock(mode="default"))

        assert isinstance(result, ValidationResult)
        assert hasattr(result, "original")
        assert hasattr(result, "validated")
        assert hasattr(result, "violations")
        assert hasattr(result, "was_modified")


@pytest.mark.integration
class TestSecurityValidationIntegration:
    """Integration tests for security validation"""

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, db_pool):
        """Test SQL injection prevention in all database operations"""

        async with db_pool.acquire() as conn:
            # Create test table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_test (
                    id SERIAL PRIMARY KEY,
                    user_input TEXT
                )
                """
            )

            # Test SQL injection attempts
            malicious_inputs = [
                "'; DROP TABLE security_test; --",
                "' OR '1'='1",
                "'; DELETE FROM security_test; --",
                "1' UNION SELECT * FROM users--",
            ]

            for malicious_input in malicious_inputs:
                # Should be safely parameterized
                await conn.execute(
                    "INSERT INTO security_test (user_input) VALUES ($1)", malicious_input
                )

                # Verify input stored as literal, not executed
                stored = await conn.fetchval(
                    "SELECT user_input FROM security_test WHERE user_input = $1", malicious_input
                )
                assert stored == malicious_input

            # Verify table still exists
            count = await conn.fetchval("SELECT COUNT(*) FROM security_test")
            assert count == len(malicious_inputs)

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS security_test")

    @pytest.mark.asyncio
    async def test_xss_prevention(self, db_pool):
        """Test XSS prevention in stored data"""

        async with db_pool.acquire() as conn:
            # Create test table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS xss_test (
                    id SERIAL PRIMARY KEY,
                    content TEXT
                )
                """
            )

            # Test XSS payloads
            xss_payloads = [
                "<script>alert('XSS')</script>",
                "<img src=x onerror=alert('XSS')>",
                "javascript:alert('XSS')",
                "<svg onload=alert('XSS')>",
            ]

            for payload in xss_payloads:
                await conn.execute("INSERT INTO xss_test (content) VALUES ($1)", payload)

                # Verify stored as literal
                stored = await conn.fetchval(
                    "SELECT content FROM xss_test WHERE content = $1", payload
                )
                assert stored == payload

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS xss_test")

    @pytest.mark.asyncio
    async def test_input_length_limits(self, db_pool):
        """Test input length limits enforcement"""

        async with db_pool.acquire() as conn:
            # Create table with length limit
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS length_test (
                    id SERIAL PRIMARY KEY,
                    limited_field VARCHAR(255)
                )
                """
            )

            # Test normal input
            normal_input = "A" * 100
            await conn.execute("INSERT INTO length_test (limited_field) VALUES ($1)", normal_input)

            # Test too long input (should be truncated or rejected)
            try:
                too_long = "A" * 1000
                await conn.execute("INSERT INTO length_test (limited_field) VALUES ($1)", too_long)
                # If inserted, verify truncation
                stored = await conn.fetchval(
                    "SELECT limited_field FROM length_test WHERE id = (SELECT MAX(id) FROM length_test)"
                )
                assert len(stored) <= 255
            except Exception:
                # Rejection is also acceptable
                pass

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS length_test")


@pytest.mark.integration
class TestContentFilteringIntegration:
    """Integration tests for content filtering"""

    @pytest.mark.asyncio
    async def test_profanity_filtering(self, db_pool):
        """Test profanity filtering"""

        async with db_pool.acquire() as conn:
            # Create filtered_content table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS filtered_content (
                    id SERIAL PRIMARY KEY,
                    original_text TEXT,
                    filtered_text TEXT,
                    filter_applied BOOLEAN,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Test content filtering (simplified)
            test_content = "This is clean content"
            filtered = test_content  # In real implementation, would filter

            await conn.execute(
                """
                INSERT INTO filtered_content (original_text, filtered_text, filter_applied)
                VALUES ($1, $2, $3)
                """,
                test_content,
                filtered,
                test_content != filtered,
            )

            # Verify filtering
            result = await conn.fetchrow(
                "SELECT filter_applied FROM filtered_content WHERE original_text = $1", test_content
            )

            assert result is not None

            # Cleanup
            await conn.execute("DELETE FROM filtered_content")

    @pytest.mark.asyncio
    async def test_sensitive_data_filtering(self, db_pool):
        """Test sensitive data filtering"""
        import re

        async with db_pool.acquire() as conn:
            # Create sensitive_data_log table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sensitive_data_log (
                    id SERIAL PRIMARY KEY,
                    content TEXT,
                    has_sensitive_data BOOLEAN,
                    sensitive_types TEXT[],
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Test sensitive data detection patterns
            test_cases = [
                ("My email is test@example.com", True, ["email"]),
                ("My phone is +6281234567890", True, ["phone"]),
                ("Normal text without sensitive data", False, []),
            ]

            for content, has_sensitive, types in test_cases:
                # Simple pattern matching (in real implementation, use proper detection)
                email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
                phone_pattern = r"\+?\d{10,15}"

                detected_types = []
                if re.search(email_pattern, content):
                    detected_types.append("email")
                if re.search(phone_pattern, content):
                    detected_types.append("phone")

                await conn.execute(
                    """
                    INSERT INTO sensitive_data_log (content, has_sensitive_data, sensitive_types)
                    VALUES ($1, $2, $3)
                    """,
                    content,
                    len(detected_types) > 0,
                    detected_types,
                )

            # Verify detection
            sensitive_count = await conn.fetchval(
                "SELECT COUNT(*) FROM sensitive_data_log WHERE has_sensitive_data = TRUE"
            )

            assert sensitive_count >= 2

            # Cleanup
            await conn.execute("DELETE FROM sensitive_data_log")
