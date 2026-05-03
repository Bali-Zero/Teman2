"""
Unit tests for llm.provider_registry
Auto-generated test template for high coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Explicit imports instead of wildcard


class TestProviderRegistry:
    """Tests for llm.provider_registry"""

    def test_module_import(self):
        """Test that module can be imported"""
        import llm.provider_registry

        assert llm.provider_registry is not None
