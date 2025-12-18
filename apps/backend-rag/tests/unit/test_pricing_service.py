"""
Unit tests for PricingService
Tests pricing functionality
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestPricingService:
    """Unit tests for PricingService"""

    def test_pricing_service_init(self):
        """Test PricingService initialization"""
        from backend.services.pricing_service import PricingService

        service = PricingService()
        assert service is not None

    def test_get_pricing_success(self):
        """Test getting pricing successfully"""
        from backend.services.pricing_service import PricingService

        service = PricingService()
        pricing = service.get_pricing(service_type="visa")

        assert isinstance(pricing, dict)

    def test_get_pricing_invalid_type(self):
        """Test getting pricing for invalid service type"""
        from backend.services.pricing_service import PricingService

        service = PricingService()
        pricing = service.get_pricing(service_type="invalid_type")

        # May return dict with error or search result
        assert isinstance(pricing, dict)

    def test_get_pricing_service(self):
        """Test get_pricing_service function"""
        from backend.services.pricing_service import PricingService, get_pricing_service

        service = get_pricing_service()
        assert service is not None
        assert isinstance(service, PricingService)
