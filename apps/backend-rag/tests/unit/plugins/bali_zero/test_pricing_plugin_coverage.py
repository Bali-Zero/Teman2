import sys
import types

import pytest

services_module = types.ModuleType("services")
pricing_module = types.ModuleType("backend.services.pricing")
pricing_service_module = types.ModuleType("backend.services.pricing.pricing_service")
pricing_service_module.get_pricing_service = lambda: None

sys.modules.setdefault("services", services_module)
sys.modules.setdefault("backend.services.pricing", pricing_module)
sys.modules.setdefault("backend.services.pricing.pricing_service", pricing_service_module)

from backend.plugins.bali_zero.pricing_plugin import PricingPlugin, PricingQueryInput


class DummyPricingService:
    def __init__(self, *, loaded=True, result=None, search_result=None):
        self.loaded = loaded
        self._result = result
        self._search_result = search_result

    def get_pricing(self, _service_type):
        return self._result

    def search_service(self, _query):
        return self._search_result


@pytest.mark.asyncio
async def test_execute_not_loaded_returns_fallback():
    service = DummyPricingService(loaded=False, result=[])
    plugin = PricingPlugin(pricing_service=service)
    output = await plugin.execute(PricingQueryInput(service_type="all"))
    assert output.success is False
    assert output.fallback_contact["email"] == "info@balizero.com"


@pytest.mark.asyncio
async def test_execute_list_result_sets_prices():
    service = DummyPricingService(loaded=True, result=[{"name": "C1", "price": 1}])
    plugin = PricingPlugin(pricing_service=service)
    output = await plugin.execute(PricingQueryInput(service_type="visa"))
    assert output.success is True
    assert output.prices == [{"name": "C1", "price": 1}]
    assert output.data == [{"name": "C1", "price": 1}]


@pytest.mark.asyncio
async def test_execute_dict_results_flattens():
    search_result = {"results": {"visa": {"C1": {"price": 1}}}}
    service = DummyPricingService(loaded=True, search_result=search_result)
    plugin = PricingPlugin(pricing_service=service)
    output = await plugin.execute(PricingQueryInput(query="c1"))
    assert output.success is True
    assert output.prices == [{"category": "visa", "name": "C1", "price": 1}]
    assert output.data == search_result


@pytest.mark.asyncio
async def test_execute_dict_passthrough_keeps_prices_none():
    result = {"visa": {"C1": {"price": 1}}}
    service = DummyPricingService(loaded=True, result=result)
    plugin = PricingPlugin(pricing_service=service)
    output = await plugin.execute(PricingQueryInput(service_type="visa"))
    assert output.success is True
    assert output.prices is None
    assert output.data == result


@pytest.mark.asyncio
async def test_execute_uses_search_when_query_provided():
    service = DummyPricingService(loaded=True, search_result={"results": {}})
    plugin = PricingPlugin(pricing_service=service)
    output = await plugin.execute(PricingQueryInput(query="kitas"))
    assert output.success is True
    assert output.data == {"results": {}}


@pytest.mark.asyncio
async def test_execute_handles_exception():
    service = DummyPricingService(loaded=True)

    def boom(_service_type):
        raise RuntimeError("boom")

    service.get_pricing = boom
    plugin = PricingPlugin(pricing_service=service)
    output = await plugin.execute(PricingQueryInput(service_type="visa"))
    assert output.success is False
    assert "Pricing lookup failed: boom" in output.error
