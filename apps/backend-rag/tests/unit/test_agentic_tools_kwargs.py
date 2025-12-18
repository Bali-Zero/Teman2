import pytest

from services.rag.agentic import CalculatorTool, PricingTool, VectorSearchTool


class MockRetriever:
    async def search_with_reranking(self, query, **kwargs):
        return {"results": [{"text": "Result"}]}

    async def retrieve_with_graph_expansion(self, query, **kwargs):
        return {"primary_results": {"chunks": [{"text": "Result"}]}}


@pytest.mark.asyncio
async def test_vector_search_tool_kwargs():
    """Test that VectorSearchTool accepts extra kwargs (like _user_id) without error"""
    retriever = MockRetriever()
    tool = VectorSearchTool(retriever)

    # This calls execute with an extra argument '_user_id'
    # It should NOT raise TypeError
    result = await tool.execute(query="test", _user_id="user123")
    assert "Result" in result


@pytest.mark.asyncio
async def test_calculator_tool_kwargs():
    """Test that CalculatorTool accepts extra kwargs"""
    tool = CalculatorTool()
    result = await tool.execute(expression="1+1", _user_id="user123")
    assert "2" in result


@pytest.mark.asyncio
async def test_pricing_tool_kwargs():
    """Test that PricingTool accepts extra kwargs"""
    # Mocking pricing service is harder, but we just check if it explodes on args
    # We expect it to try to call the real service and maybe fail on logic,
    # but NOT on TypeError: execute() got an unexpected keyword argument
    tool = PricingTool()

    # Mock the internal service to avoid real calls
    class MockPricing:
        def get_pricing(self, *args):
            return "Price: 100"

    tool.pricing_service = MockPricing()

    result = await tool.execute(service_type="visa", _user_id="user123")
    assert "Price: 100" in result
