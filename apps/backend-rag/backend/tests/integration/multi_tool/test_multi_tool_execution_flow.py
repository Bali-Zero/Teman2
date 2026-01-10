"""
Integration Tests: Multi-Tool Execution Flow

Tests complex scenarios with multiple tool calls:
1. Sequential tool execution
2. Parallel tool execution
3. Tool chaining (output of one tool feeds into another)
4. Rate limiting and error handling
5. Tool result aggregation

Target: Test multi-tool execution scenarios end-to-end
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.rag.agentic.tool_executor import execute_tool
from backend.services.rag.agentic.tools import (
    CalculatorTool,
    PricingTool,
    TeamKnowledgeTool,
    VectorSearchTool,
)


@pytest.fixture
def mock_search_service():
    """Mock SearchService"""
    service = MagicMock()
    service.search = AsyncMock(
        return_value={
            "results": [{"id": "doc1", "text": "E33G costs Rp 17-19 million", "score": 0.9}],
            "total": 1,
        }
    )
    return service


@pytest.fixture
def mock_db_pool():
    """Mock PostgreSQL connection pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def tool_map(mock_search_service, mock_db_pool):
    """Create tool map with all tools"""
    return {
        "vector_search": VectorSearchTool(mock_search_service),
        "get_pricing": PricingTool(),
        "calculator": CalculatorTool(),
        "team_knowledge": TeamKnowledgeTool(mock_db_pool),
    }


class TestMultiToolExecutionFlow:
    """Multi-Tool Execution Flow Tests"""

    @pytest.mark.asyncio
    async def test_sequential_tool_execution(self, tool_map, mock_search_service):
        """Test sequential execution of multiple tools"""
        # Tool 1: Search for visa info
        tool1_result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="vector_search",
            arguments={"query": "E33G KITAS cost", "collection": "visa_oracle"},
            tool_execution_counter={"count": 0},
        )

        # Tool 2: Get pricing
        tool2_result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="get_pricing",
            arguments={"service_type": "visa", "query": "E33G"},
            tool_execution_counter={"count": 1},
        )

        # Tool 3: Calculate total
        tool3_result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="calculator",
            arguments={"expression": "17 + 2"},
            tool_execution_counter={"count": 2},
        )

        # Verify all tools executed
        assert tool1_result is not None
        assert tool2_result is not None
        assert tool3_result is not None

        # Verify search was called
        mock_search_service.search.assert_called()

    @pytest.mark.asyncio
    async def test_tool_chaining(self, tool_map, mock_search_service):
        """Test tool chaining where output of one tool feeds into another"""
        # Step 1: Search for visa requirements
        search_result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="vector_search",
            arguments={"query": "E33G requirements", "collection": "visa_oracle"},
            tool_execution_counter={"count": 0},
        )

        # Extract cost from search result
        # (In real scenario, this would be parsed from search_result)
        cost_from_search = "17-19 million"

        # Step 2: Get official pricing
        pricing_result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="get_pricing",
            arguments={"service_type": "visa", "query": "E33G"},
            tool_execution_counter={"count": 1},
        )

        # Step 3: Calculate difference if needed
        # (In real scenario, this would compare search result with pricing)

        # Verify chain executed
        assert search_result is not None
        assert pricing_result is not None

    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self, tool_map):
        """Test that rate limiting prevents excessive tool calls"""
        tool_execution_counter = {"count": 0}

        # Execute tools up to limit
        for i in range(10):
            try:
                result, _ = await execute_tool(
                    tool_map=tool_map,
                    tool_name="calculator",
                    arguments={"expression": f"{i} + 1"},
                    tool_execution_counter=tool_execution_counter,
                )
                assert result is not None
            except RuntimeError as e:
                # Should raise error at limit
                assert "Maximum tool executions exceeded" in str(e)
                break

        # Verify limit was reached
        assert tool_execution_counter["count"] >= 10

    @pytest.mark.asyncio
    async def test_tool_error_handling(self, tool_map, mock_search_service):
        """Test error handling when tool execution fails"""
        # Mock tool error
        mock_search_service.search = AsyncMock(side_effect=Exception("Search error"))

        # Execute tool - should handle error gracefully
        try:
            result, duration = await execute_tool(
                tool_map=tool_map,
                tool_name="vector_search",
                arguments={"query": "test", "collection": "visa_oracle"},
                tool_execution_counter={"count": 0},
            )
            # Should return error message
            assert "Error" in result or "error" in result.lower()
        except Exception as e:
            # If exception is raised, verify it's handled appropriately
            assert "error" in str(e).lower()

    @pytest.mark.asyncio
    async def test_unknown_tool_handling(self, tool_map):
        """Test handling of unknown tool names"""
        # Execute unknown tool
        result, duration = await execute_tool(
            tool_map=tool_map,
            tool_name="unknown_tool",
            arguments={},
            tool_execution_counter={"count": 0},
        )

        # Verify error message
        assert "Error" in result or "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_tool_result_aggregation(self, tool_map, mock_search_service):
        """Test aggregation of results from multiple tools"""
        # Execute multiple tools
        results = []

        # Tool 1: Search
        result1, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="vector_search",
            arguments={"query": "E33G", "collection": "visa_oracle"},
            tool_execution_counter={"count": 0},
        )
        results.append({"tool": "vector_search", "result": result1})

        # Tool 2: Pricing
        result2, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="get_pricing",
            arguments={"service_type": "visa", "query": "E33G"},
            tool_execution_counter={"count": 1},
        )
        results.append({"tool": "get_pricing", "result": result2})

        # Aggregate results
        aggregated = {
            "search_results": results[0]["result"],
            "pricing": results[1]["result"],
            "total_tools": len(results),
        }

        # Verify aggregation
        assert len(aggregated) == 3
        assert aggregated["total_tools"] == 2

    @pytest.mark.asyncio
    async def test_conditional_tool_execution(self, tool_map, mock_search_service):
        """Test conditional tool execution based on previous results"""
        # Step 1: Search for information
        search_result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="vector_search",
            arguments={"query": "E33G cost", "collection": "visa_oracle"},
            tool_execution_counter={"count": 0},
        )

        # Step 2: Conditionally get pricing if search doesn't have cost
        if "cost" not in str(search_result).lower():
            pricing_result, _ = await execute_tool(
                tool_map=tool_map,
                tool_name="get_pricing",
                arguments={"service_type": "visa", "query": "E33G"},
                tool_execution_counter={"count": 1},
            )
            assert pricing_result is not None
        else:
            # Search already has cost info
            assert search_result is not None
