"""
Unit tests for llm.adapters.base
Auto-generated test template for high coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Explicit imports instead of wildcard


class TestBase:
    """Tests for llm.adapters.base"""

    def test_module_import(self):
        """Test that module can be imported"""
        import llm.adapters.base

        assert llm.adapters.base is not None
