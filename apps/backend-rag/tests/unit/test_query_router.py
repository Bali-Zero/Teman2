"""
Unit tests for QueryRouter
Tests query routing functionality
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestQueryRouter:
    """Unit tests for QueryRouter"""

    def test_query_router_init(self):
        """Test QueryRouter initialization"""
        from backend.services.query_router import QueryRouter

        router = QueryRouter()
        assert router is not None
        assert hasattr(router, "VISA_KEYWORDS")
        assert hasattr(router, "KBLI_KEYWORDS")

    def test_visa_keywords(self):
        """Test VISA_KEYWORDS constant"""
        from backend.services.query_router import QueryRouter

        router = QueryRouter()
        assert isinstance(router.VISA_KEYWORDS, list)
        assert len(router.VISA_KEYWORDS) > 0

    def test_kbli_keywords(self):
        """Test KBLI_KEYWORDS constant"""
        from backend.services.query_router import QueryRouter

        router = QueryRouter()
        assert isinstance(router.KBLI_KEYWORDS, list)
        assert len(router.KBLI_KEYWORDS) > 0

    def test_tax_keywords(self):
        """Test TAX_KEYWORDS constant"""
        from backend.services.query_router import QueryRouter

        router = QueryRouter()
        assert isinstance(router.TAX_KEYWORDS, list)
        assert len(router.TAX_KEYWORDS) > 0
