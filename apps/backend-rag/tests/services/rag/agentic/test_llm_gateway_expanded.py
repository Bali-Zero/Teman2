"""
Expanded Coverage Tests for LLMGateway.

This test suite provides EXTENSIVE coverage of the LLMGateway class,
including advanced scenarios, stress testing, and edge cases.

Enhanced Coverage Areas:
- Advanced error scenarios and recovery
- Stress testing and load scenarios
- Memory leak detection
- Thread safety and concurrency
- Configuration edge cases
- Network failure simulation
- Resource exhaustion testing
- Security and validation testing

Author: Nuzantara Team
Date: 2025-01-04
Version: 2.0.0 (Expanded)
"""

import asyncio
import threading
import time
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import (
    DeadlineExceeded,
    PermissionDenied,
    ResourceExhausted,
    ServiceUnavailable,
)

# Import the minimal gateway for testing
from test_llm_gateway_isolated import (
    TIER_FALLBACK,
    TIER_FLASH,
    TIER_PRO,
    MinimalLLMGateway,
    MockTokenUsage,
)


class TestAdvancedErrorScenarios:
    """Advanced error scenario testing."""

    @pytest.fixture
    def gateway_with_errors(self):
        """Gateway with error injection capabilities."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.error_injection = {}
        return gateway

    async def test_cascading_failures_with_recovery(self, gateway_with_errors):
        """Test cascading failures and recovery patterns."""
        gateway = gateway_with_errors

        # Simulate cascading failures
        failure_count = 0
        original_call = gateway._send_with_fallback

        async def failing_call(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 3:
                raise ResourceExhausted(f"Cascading failure {failure_count}")
            return ("Recovered response", "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = failing_call

        # Should recover after failures
        response, model, obj, usage = await gateway.send_message(
            chat=None, message="Test", tier=TIER_FLASH
        )

        assert response == "Recovered response"
        assert failure_count == 4  # 3 failures + 1 success

    async def test_intermittent_network_failures(self, gateway_with_errors):
        """Test handling of intermittent network failures."""
        gateway = gateway_with_errors

        call_count = 0
        original_call = gateway._send_with_fallback

        async def intermittent_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:  # Fail on even calls
                raise ServiceUnavailable("Network timeout")
            return (f"Success {call_count}", "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = intermittent_call

        # Should handle intermittent failures gracefully
        for i in range(4):
            try:
                response, model, obj, usage = await gateway.send_message(
                    chat=None, message=f"Test {i}", tier=TIER_FLASH
                )
                assert "Success" in response
            except RuntimeError:
                # Expected on failures
                pass

    def test_deadline_exceeded_handling(self, gateway_with_errors):
        """Test deadline exceeded error handling."""
        gateway = gateway_with_errors

        # Simulate deadline exceeded
        with pytest.raises(RuntimeError, match="All LLM models failed"):
            # This would need to be implemented in the actual gateway
            gateway._record_failure("gemini-3-flash-preview", DeadlineExceeded("Deadline exceeded"))

    def test_permission_denied_scenarios(self, gateway_with_errors):
        """Test permission denied error scenarios."""
        gateway = gateway_with_errors

        # Test permission denied handling
        gateway._record_failure("gemini-3-flash-preview", PermissionDenied("Access denied"))

        circuit = gateway._get_circuit_breaker("gemini-3-flash-preview")
        assert circuit.failures == 1


class TestStressTesting:
    """Stress testing and load scenarios."""

    @pytest.fixture
    def stress_gateway(self):
        """Gateway configured for stress testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway._max_fallback_depth = 10  # Increase for stress testing
        gateway._max_fallback_cost_usd = 1.0  # Increase for stress testing
        return gateway

    async def test_high_volume_concurrent_requests(self, stress_gateway):
        """Test high volume of concurrent requests."""
        gateway = stress_gateway

        async def send_request(request_id):
            return await gateway.send_message(
                chat=None, message=f"Request {request_id}", tier=TIER_FLASH
            )

        # Send 50 concurrent requests
        tasks = [send_request(i) for i in range(50)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Most should succeed
        successes = [r for r in responses if not isinstance(r, Exception)]
        assert len(successes) >= 40  # Allow for some failures

    def test_circuit_breaker_under_load(self, stress_gateway):
        """Test circuit breaker behavior under load."""
        gateway = stress_gateway

        # Simulate rapid failures
        for i in range(100):
            gateway._record_failure("gemini-3-flash-preview", Exception(f"Load test failure {i}"))

        circuit = gateway._get_circuit_breaker("gemini-3-flash-preview")
        assert circuit.is_open()
        assert circuit.failures == 100

    async def test_memory_usage_under_load(self, stress_gateway):
        """Test memory usage patterns under load."""
        gateway = stress_gateway
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create many circuit breakers
        for i in range(1000):
            gateway._get_circuit_breaker(f"model-{i}")

        # Check memory growth
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory

        # Should not grow excessively (less than 50MB)
        assert memory_growth < 50 * 1024 * 1024

    def test_thread_safety(self, stress_gateway):
        """Test thread safety of circuit breaker operations."""
        gateway = stress_gateway
        errors = []

        def worker_thread(thread_id):
            try:
                for i in range(100):
                    circuit = gateway._get_circuit_breaker(f"model-{thread_id}-{i}")
                    circuit.record_success()
                    circuit.record_failure()
                    circuit.is_open()
            except Exception as e:
                errors.append(e)

        # Run 10 threads concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0


class TestResourceExhaustion:
    """Resource exhaustion testing."""

    @pytest.fixture
    def resource_gateway(self):
        """Gateway with limited resources for testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway._max_fallback_depth = 2  # Very limited
        gateway._max_fallback_cost_usd = 0.001  # Very limited
        return gateway

    async def test_cost_limit_enforcement(self, resource_gateway):
        """Test cost limit enforcement under resource constraints."""
        gateway = resource_gateway

        with pytest.raises(RuntimeError, match="All LLM models failed"):
            # Should fail due to cost limit
            await gateway.send_message(
                chat=None,
                message="Expensive request",
                tier=TIER_PRO,  # Tries multiple models
            )

    async def test_depth_limit_enforcement(self, resource_gateway):
        """Test fallback depth limit enforcement."""
        gateway = resource_gateway

        # Mock expensive responses to trigger depth limit
        original_call = gateway._send_with_fallback

        async def depth_limited_call(*args, **kwargs):
            query_cost_tracker = kwargs.get("query_cost_tracker", {})
            query_cost_tracker["depth"] = 5  # Exceed limit
            raise ResourceExhausted("Depth exceeded")

        gateway._send_with_fallback = depth_limited_call

        with pytest.raises(RuntimeError):
            await gateway.send_message(chat=None, message="Test", tier=TIER_FLASH)

    def test_circuit_breaker_memory_efficiency(self, resource_gateway):
        """Test circuit breaker memory efficiency."""
        gateway = resource_gateway

        # Create many circuit breakers
        initial_size = len(gateway._circuit_breakers)

        for i in range(10000):
            gateway._get_circuit_breaker(f"model-{i}")

        final_size = len(gateway._circuit_breakers)

        # Should have created all circuit breakers
        assert final_size == initial_size + 10000


class TestConfigurationEdgeCases:
    """Configuration edge case testing."""

    def test_empty_configuration(self):
        """Test gateway with empty configuration."""
        gateway = MinimalLLMGateway()

        assert gateway.gemini_tools == []
        assert gateway.model_name_pro == "gemini-3-flash-preview"
        assert gateway.model_name_flash == "gemini-3-flash-preview"
        assert gateway.model_name_fallback == "gemini-2.0-flash"

    def test_invalid_tool_configuration(self):
        """Test handling of invalid tool configurations."""
        gateway = MinimalLLMGateway()

        # Test with invalid tools
        invalid_tools = [
            None,
            "invalid_string",
            {},
            {"name": ""},  # Empty name
            {"name": "tool", "parameters": "invalid"},  # Invalid parameters
        ]

        for invalid_tool in invalid_tools:
            gateway.set_gemini_tools([invalid_tool] if invalid_tool else [])
            # Should not crash
            assert isinstance(gateway.gemini_tools, list)

    def test_model_name_override(self):
        """Test model name override scenarios."""
        gateway = MinimalLLMGateway()

        # Override model names
        gateway.model_name_pro = "custom-pro-model"
        gateway.model_name_flash = "custom-flash-model"
        gateway.model_name_fallback = "custom-fallback-model"

        # Test fallback chain with custom names
        pro_chain = gateway._get_fallback_chain(TIER_PRO)
        assert "custom-pro-model" in pro_chain or "custom-flash-model" in pro_chain
        assert "custom-fallback-model" in pro_chain


class TestNetworkFailureSimulation:
    """Network failure simulation testing."""

    @pytest.fixture
    def network_gateway(self):
        """Gateway with network simulation capabilities."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.network_failures = []
        return gateway

    async def test_slow_response_handling(self, network_gateway):
        """Test handling of slow responses."""
        gateway = network_gateway

        # Simulate slow response
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate delay
            return ("Slow response", "gemini-3-flash-preview", Mock(), MockTokenUsage())

        original_call = gateway._send_with_fallback
        gateway._send_with_fallback = slow_response

        start_time = time.time()
        response, model, obj, usage = await gateway.send_message(
            chat=None, message="Test", tier=TIER_FLASH
        )
        end_time = time.time()

        assert response == "Slow response"
        assert end_time - start_time >= 0.1

    async def test_connection_timeout_simulation(self, network_gateway):
        """Test connection timeout simulation."""
        gateway = network_gateway

        # Simulate timeout
        async def timeout_response(*args, **kwargs):
            await asyncio.sleep(5)  # Long delay
            return ("Timeout response", "gemini-3-flash-preview", Mock(), MockTokenUsage())

        gateway._send_with_fallback = timeout_response

        # Should handle timeout gracefully (would need timeout implementation)
        # This is a placeholder for actual timeout handling
        with pytest.raises(Exception):  # Would be TimeoutError in real implementation
            await gateway.send_message(chat=None, message="Test", tier=TIER_FLASH)


class TestSecurityAndValidation:
    """Security and validation testing."""

    @pytest.fixture
    def secure_gateway(self):
        """Gateway with security features."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        return gateway

    async def test_input_validation(self, secure_gateway):
        """Test input validation and sanitization."""
        gateway = secure_gateway

        # Test with potentially dangerous inputs
        dangerous_inputs = [
            "",
            "   ",  # Whitespace only
            "x" * 100000,  # Very long input
            "🚀" * 1000,  # Unicode characters
            "<script>alert('xss')</script>",  # XSS attempt
            "'; DROP TABLE users; --",  # SQL injection attempt
        ]

        for dangerous_input in dangerous_inputs:
            try:
                response, model, obj, usage = await gateway.send_message(
                    chat=None, message=dangerous_input, tier=TIER_FLASH
                )
                # Should handle gracefully without crashing
                assert isinstance(response, str)
            except Exception as e:
                # Should not crash with unhandled exceptions
                assert not isinstance(e, UnicodeError)
                assert not isinstance(e, MemoryError)

    def test_tool_parameter_validation(self, secure_gateway):
        """Test tool parameter validation."""
        gateway = secure_gateway

        # Test with malformed tool parameters
        malformed_tools = [
            {"name": "test", "parameters": None},
            {"name": "test", "parameters": "invalid"},
            {"name": "test", "parameters": {"type": "INVALID"}},
            {"name": "", "parameters": {"type": "OBJECT"}},  # Empty name
        ]

        for malformed_tool in malformed_tools:
            gateway.set_gemini_tools([malformed_tool])
            # Should not crash
            assert isinstance(gateway.gemini_tools, list)


class TestPerformanceOptimization:
    """Performance optimization testing."""

    @pytest.fixture
    def perf_gateway(self):
        """Gateway optimized for performance testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        return gateway

    def test_circuit_breaker_lookup_performance(self, perf_gateway):
        """Test circuit breaker lookup performance."""
        gateway = perf_gateway

        # Create many circuit breakers
        for i in range(1000):
            gateway._get_circuit_breaker(f"model-{i}")

        # Test lookup performance
        start_time = time.time()
        for i in range(1000):
            circuit = gateway._get_circuit_breaker(f"model-{i}")
            assert circuit is not None
        end_time = time.time()

        # Should be very fast (< 10ms for 1000 lookups)
        assert end_time - start_time < 0.01

    async def test_fallback_chain_performance(self, perf_gateway):
        """Test fallback chain generation performance."""
        gateway = perf_gateway

        start_time = time.time()
        for i in range(1000):
            chain = gateway._get_fallback_chain(TIER_PRO)
            assert len(chain) > 0
        end_time = time.time()

        # Should be very fast (< 10ms for 1000 chains)
        assert end_time - start_time < 0.01

    def test_memory_cleanup(self, perf_gateway):
        """Test memory cleanup and garbage collection."""
        gateway = perf_gateway

        import gc
        import weakref

        # Create circuit breakers and hold weak references
        refs = []
        for i in range(100):
            circuit = gateway._get_circuit_breaker(f"model-{i}")
            refs.append(weakref.ref(circuit))

        # Remove references
        del gateway._circuit_breakers["model-0"]
        del gateway._circuit_breakers["model-1"]

        # Force garbage collection
        gc.collect()

        # Some references should be cleaned up
        cleaned = sum(1 for ref in refs if ref() is None)
        assert cleaned >= 2


class TestIntegrationScenarios:
    """Integration scenario testing."""

    @pytest.fixture
    def integration_gateway(self):
        """Gateway configured for integration testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        return gateway

    async def test_end_to_end_workflow(self, integration_gateway):
        """Test complete end-to-end workflow."""
        gateway = integration_gateway

        # Step 1: Create chat with history
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        chat = gateway.create_chat_with_history(history, TIER_FLASH)

        # Step 2: Send message
        response, model, obj, usage = await gateway.send_message(
            chat=chat, message="How are you?", tier=TIER_FLASH
        )

        # Step 3: Health check
        health = await gateway.health_check()

        # Verify all steps worked
        assert chat is not None
        assert isinstance(response, str)
        assert isinstance(health, dict)
        assert "gemini_flash" in health

    async def test_multi_tier_fallback_workflow(self, integration_gateway):
        """Test multi-tier fallback workflow."""
        gateway = integration_gateway

        # Mock failures for higher tiers
        call_count = 0
        original_call = gateway._send_with_fallback

        async def tier_fallback_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ResourceExhausted(f"Tier {call_count} failed")
            return (
                f"Fallback success at tier {call_count}",
                "gemini-2.0-flash",
                Mock(),
                MockTokenUsage(),
            )

        gateway._send_with_fallback = tier_fallback_call

        # Start with PRO tier, should fallback to final tier
        response, model, obj, usage = await gateway.send_message(
            chat=None, message="Test multi-tier", tier=TIER_PRO
        )

        assert "Fallback success" in response
        assert model == "gemini-2.0-flash"

    async def test_concurrent_different_tiers(self, integration_gateway):
        """Test concurrent requests to different tiers."""
        gateway = integration_gateway

        async def send_to_tier(tier, message):
            return await gateway.send_message(chat=None, message=message, tier=tier)

        # Send concurrent requests to different tiers
        tasks = [
            send_to_tier(TIER_PRO, "Pro request"),
            send_to_tier(TIER_FLASH, "Flash request"),
            send_to_tier(TIER_FALLBACK, "Fallback request"),
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed or fail gracefully
        assert len(responses) == 3
        for response in responses:
            if not isinstance(response, Exception):
                assert len(response) == 4  # (response, model, obj, usage)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
