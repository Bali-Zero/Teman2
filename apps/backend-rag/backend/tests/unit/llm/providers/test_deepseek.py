"""
Unit tests for llm.providers.deepseek
Auto-generated test template for high coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from llm.providers.deepseek import DeepSeekProvider


class TestDeepseek:
    """Tests for llm.providers.deepseek"""

    def test_module_import(self):
        """Test that module can be imported"""
        import llm.providers.deepseek

        assert llm.providers.deepseek is not None
