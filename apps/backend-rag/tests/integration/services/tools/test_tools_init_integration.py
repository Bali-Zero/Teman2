"""
Integration Tests for services/tools/__init__.py
Tests tool module initialization
"""

import os
import sys
from pathlib import Path

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestToolsInitIntegration:
    """Integration tests for tools module initialization"""

    def test_module_imports(self):
        """Test that tools module can be imported"""
        from services.tools import __all__

        assert __all__ == []

    def test_module_has_docstring(self):
        """Test that module has documentation"""
        import services.tools

        assert services.tools.__doc__ is not None
        assert "Tools" in services.tools.__doc__
