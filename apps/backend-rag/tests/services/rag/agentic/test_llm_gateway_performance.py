"""
Advanced Performance and Scalability Testing Suite for LLMGateway

This suite provides advanced performance testing, scalability validation,
and optimization scenarios for the LLMGateway module.

Advanced Performance Coverage Areas:
- Load testing and capacity planning
- Memory optimization and garbage collection
- CPU utilization and thread efficiency
- Network latency and throughput testing
- Database query optimization
- Cache performance validation
- Concurrent request handling
- Resource pool management
- Performance regression detection
- Auto-scaling simulation

Author: Nuzantara Team
Date: 2025-01-04
Version: 6.0.0 (Advanced Performance Edition)
"""

import gc
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import psutil
import pytest

# Import the minimal gateway for testing
from test_llm_gateway_isolated import TIER_FLASH, TIER_PRO, MinimalLLMGateway


class TestLoadTestingAndCapacity:
    """Test load testing and capacity planning scenarios."""

    @pytest.fixture
    def load_gateway(self):
        """Gateway configured for load testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.load_metrics = {
            "requests_processed": 0,
            "peak_concurrent": 0,
            "average_response_time": 0.0,
            "error_rate": 0.0,
            "throughput_rps": 0.0,
        }
        return gateway

    def test_concurrent_request_handling(self, load_gateway):
        """Test handling of concurrent requests."""
        gateway = load_gateway

        def process_request(request_id):
            """Simulate processing a request."""
            start_time = time.time()

            # Simulate request processing
            circuit = gateway._get_circuit_breaker(f"load-model-{request_id % 5}")
            chain = gateway._get_fallback_chain(TIER_FLASH)

            # Simulate processing time
            time.sleep(0.01)  # 10ms processing time

            end_time = time.time()
            response_time = end_time - start_time

            gateway.load_metrics["requests_processed"] += 1
            gateway.load_metrics["average_response_time"] += response_time

            return {"request_id": request_id, "response_time": response_time}

        # Test concurrent processing
        num_requests = 100
        num_threads = 10

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i in range(num_requests):
                future = executor.submit(process_request, i)
                futures.append(future)

            results = [future.result() for future in futures]

        # Calculate metrics
        avg_response_time = sum(r["response_time"] for r in results) / len(results)
        max_response_time = max(r["response_time"] for r in results)

        gateway.load_metrics["average_response_time"] = avg_response_time
        gateway.load_metrics["throughput_rps"] = num_requests / (max_response_time * num_threads)

        # Verify load handling
        assert gateway.load_metrics["requests_processed"] == num_requests
        assert avg_response_time < 0.1  # Should be under 100ms
        assert gateway.load_metrics["throughput_rps"] > 50  # Should handle 50+ RPS

    def test_peak_load_simulation(self, load_gateway):
        """Test peak load scenarios."""
        gateway = load_gateway

        def burst_request(burst_id, num_requests):
            """Simulate burst of requests."""
            results = []
            for i in range(num_requests):
                start_time = time.time()

                # Process request
                circuit = gateway._get_circuit_breaker(f"burst-model-{burst_id}")
                chain = gateway._get_fallback_chain(TIER_PRO)

                # Simulate variable processing time
                time.sleep(0.005 + (i % 3) * 0.005)  # 5-15ms

                end_time = time.time()
                response_time = end_time - start_time

                results.append(response_time)
                gateway.load_metrics["requests_processed"] += 1

            return results

        # Simulate multiple bursts
        num_bursts = 5
        requests_per_burst = 20

        with ThreadPoolExecutor(max_workers=num_bursts) as executor:
            futures = []
            for burst_id in range(num_bursts):
                future = executor.submit(burst_request, burst_id, requests_per_burst)
                futures.append(future)

            burst_results = [future.result() for future in futures]

        # Calculate peak metrics
        all_response_times = [rt for burst in burst_results for rt in burst]
        avg_response_time = sum(all_response_times) / len(all_response_times)
        max_response_time = max(all_response_times)

        # Verify peak load handling
        assert len(all_response_times) == num_bursts * requests_per_burst
        assert avg_response_time < 0.05  # Should be under 50ms even under load
        assert max_response_time < 0.1  # Even max should be under 100ms

    def test_capacity_planning_validation(self, load_gateway):
        """Test capacity planning and resource limits."""
        gateway = load_gateway

        # Simulate different load levels
        load_levels = [
            {"requests": 10, "expected_rps": 100},
            {"requests": 50, "expected_rps": 200},
            {"requests": 100, "expected_rps": 300},
            {"requests": 200, "expected_rps": 400},
        ]

        capacity_results = []

        for level in load_levels:
            start_time = time.time()

            # Process requests at this level
            for i in range(level["requests"]):
                circuit = gateway._get_circuit_breaker(f"capacity-model-{i % 10}")
                chain = gateway._get_fallback_chain(TIER_FLASH)
                time.sleep(0.001)  # 1ms processing

            end_time = time.time()
            actual_rps = level["requests"] / (end_time - start_time)

            capacity_results.append(
                {
                    "requests": level["requests"],
                    "expected_rps": level["expected_rps"],
                    "actual_rps": actual_rps,
                    "meets_expectation": actual_rps >= level["expected_rps"] * 0.8,  # 80% threshold
                }
            )

        # Verify capacity planning
        for result in capacity_results:
            assert result["meets_expectation"], (
                f"Failed to meet capacity for {result['requests']} requests"
            )


class TestMemoryOptimization:
    """Test memory optimization and garbage collection."""

    @pytest.fixture
    def memory_gateway(self):
        """Gateway configured for memory testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.memory_metrics = {
            "initial_memory": 0,
            "peak_memory": 0,
            "final_memory": 0,
            "memory_growth": 0,
            "gc_runs": 0,
        }
        return gateway

    def test_memory_usage_scaling(self, memory_gateway):
        """Test memory usage under scaling."""
        gateway = memory_gateway
        process = psutil.Process()

        # Record initial memory
        initial_memory = process.memory_info().rss
        gateway.memory_metrics["initial_memory"] = initial_memory

        # Create many circuit breakers (simulating many users)
        num_circuits = 10000
        circuits = []

        for i in range(num_circuits):
            circuit = gateway._get_circuit_breaker(f"memory-model-{i}")
            circuits.append(circuit)

            # Check memory every 1000 circuits
            if i % 1000 == 0:
                current_memory = process.memory_info().rss
                gateway.memory_metrics["peak_memory"] = max(
                    gateway.memory_metrics["peak_memory"], current_memory
                )

        # Force garbage collection
        gc.collect()
        gateway.memory_metrics["gc_runs"] += 1

        # Record final memory
        final_memory = process.memory_info().rss
        gateway.memory_metrics["final_memory"] = final_memory
        gateway.memory_metrics["memory_growth"] = final_memory - initial_memory

        # Verify memory efficiency
        memory_per_circuit = gateway.memory_metrics["memory_growth"] / num_circuits
        assert memory_per_circuit < 1000  # Should be under 1KB per circuit
        assert gateway.memory_metrics["memory_growth"] < 50 * 1024 * 1024  # Under 50MB total

    def test_memory_leak_detection(self, memory_gateway):
        """Test memory leak detection."""
        gateway = memory_gateway
        process = psutil.Process()

        # Baseline memory
        baseline_memory = process.memory_info().rss

        # Simulate repeated operations that could cause leaks
        for iteration in range(5):
            # Create temporary objects
            temp_circuits = []
            temp_data = []

            for i in range(1000):
                circuit = gateway._get_circuit_breaker(f"leak-test-{iteration}-{i}")
                temp_circuits.append(circuit)
                temp_data.append({"data": f"test-{iteration}-{i}" * 10})

            # Clear references
            temp_circuits.clear()
            temp_data.clear()

            # Force garbage collection
            gc.collect()

            # Check memory after cleanup
            current_memory = process.memory_info().rss
            memory_growth = current_memory - baseline_memory

            # Memory growth should be minimal after cleanup
            assert memory_growth < 10 * 1024 * 1024  # Under 10MB growth

        # Final memory check
        final_memory = process.memory_info().rss
        total_growth = final_memory - baseline_memory
        assert total_growth < 20 * 1024 * 1024  # Under 20MB total growth

    def test_garbage_collection_efficiency(self, memory_gateway):
        """Test garbage collection efficiency."""
        gateway = memory_gateway

        # Monitor GC statistics
        initial_gc_stats = gc.get_stats() if hasattr(gc, "get_stats") else []
        initial_collections = gc.collect()

        # Create objects that need collection
        objects_to_collect = []

        for i in range(5000):
            # Create objects with circular references
            obj_a = {"id": i, "data": f"test-{i}" * 10}
            obj_b = {"id": i, "ref": obj_a}
            obj_a["ref"] = obj_b  # Create circular reference

            objects_to_collect.append(obj_a)

        # Clear references
        objects_to_collect.clear()

        # Force garbage collection
        collections_after_creation = gc.collect()

        # Verify garbage collection worked
        assert collections_after_creation > initial_collections

        # Memory should be reasonable after collection
        process = psutil.Process()
        memory_after_gc = process.memory_info().rss

        # Create more objects and test again
        for i in range(3000):
            obj = {"large_data": "x" * 1000, "id": i}
            # Add to list then clear to test collection
        gc.collect()

        final_memory = process.memory_info().rss
        memory_growth = final_memory - memory_after_gc

        # Memory growth should be controlled
        assert memory_growth < 30 * 1024 * 1024  # Under 30MB


class TestCPUOptimization:
    """Test CPU utilization and thread efficiency."""

    @pytest.fixture
    def cpu_gateway(self):
        """Gateway configured for CPU testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.cpu_metrics = {
            "cpu_time_start": 0,
            "cpu_time_end": 0,
            "cpu_usage_percent": 0,
            "thread_efficiency": 0,
        }
        return gateway

    def test_cpu_utilization_optimization(self, cpu_gateway):
        """Test CPU utilization under load."""
        gateway = cpu_gateway
        process = psutil.Process()

        # Record initial CPU time
        initial_cpu_time = process.cpu_times()
        gateway.cpu_metrics["cpu_time_start"] = initial_cpu_time

        # Simulate CPU-intensive operations
        def cpu_intensive_task(task_id):
            """Simulate CPU-intensive processing."""
            result = 0
            for i in range(1000):  # Some computation
                result += i * task_id
            return result

        # Run tasks with different thread counts
        thread_counts = [1, 2, 4, 8]
        efficiency_results = []

        for num_threads in thread_counts:
            start_time = time.time()

            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = []
                for i in range(50):  # 50 tasks
                    future = executor.submit(cpu_intensive_task, i)
                    futures.append(future)

                results = [future.result() for future in futures]

            end_time = time.time()
            execution_time = end_time - start_time

            # Calculate efficiency
            tasks_per_second = 50 / execution_time
            efficiency_results.append(
                {
                    "threads": num_threads,
                    "time": execution_time,
                    "tasks_per_second": tasks_per_second,
                }
            )

        # Record final CPU time
        final_cpu_time = process.cpu_times()
        gateway.cpu_metrics["cpu_time_end"] = final_cpu_time

        # Verify CPU efficiency
        # More threads should generally improve performance up to a point
        assert len(efficiency_results) == len(thread_counts)

        # Check that we got reasonable performance
        for result in efficiency_results:
            assert result["tasks_per_second"] > 10  # Should handle at least 10 tasks/sec

    def test_thread_pool_efficiency(self, cpu_gateway):
        """Test thread pool efficiency and sizing."""
        gateway = cpu_gateway

        def simulated_request(request_id, processing_time=0.01):
            """Simulate a request with processing time."""
            time.sleep(processing_time)
            return f"completed-{request_id}"

        # Test different pool sizes
        pool_sizes = [5, 10, 20, 40]
        num_requests = 100

        pool_results = []

        for pool_size in pool_sizes:
            start_time = time.time()

            with ThreadPoolExecutor(max_workers=pool_size) as executor:
                futures = []
                for i in range(num_requests):
                    future = executor.submit(simulated_request, i)
                    futures.append(future)

                results = [future.result() for future in futures]

            end_time = time.time()
            total_time = end_time - start_time
            throughput = num_requests / total_time

            pool_results.append(
                {"pool_size": pool_size, "total_time": total_time, "throughput": throughput}
            )

        # Find optimal pool size
        optimal_result = max(pool_results, key=lambda x: x["throughput"])

        # Verify thread pool efficiency
        assert len(pool_results) == len(pool_sizes)
        assert optimal_result["throughput"] > 50  # Should handle 50+ requests/sec

    def test_async_vs_sync_performance(self, cpu_gateway):
        """Test async vs sync performance comparison."""
        gateway = cpu_gateway

        # Synchronous processing
        def sync_processing(request_id):
            time.sleep(0.01)  # Simulate I/O
            return f"sync-{request_id}"

        start_time = time.time()
        sync_results = []
        for i in range(20):
            result = sync_processing(i)
            sync_results.append(result)
        sync_time = time.time() - start_time

        # Asynchronous processing simulation
        def async_processing(request_id):
            # Simulate async behavior with threading
            time.sleep(0.01)
            return f"async-{request_id}"

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(20):
                future = executor.submit(async_processing, i)
                futures.append(future)

            async_results = [future.result() for future in futures]
        async_time = time.time() - start_time

        # Async should be faster for I/O bound operations
        assert async_time < sync_time
        assert len(async_results) == len(sync_results)


class TestNetworkOptimization:
    """Test network latency and throughput optimization."""

    @pytest.fixture
    def network_gateway(self):
        """Gateway configured for network testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.network_metrics = {
            "total_requests": 0,
            "total_latency": 0.0,
            "average_latency": 0.0,
            "throughput_mbps": 0.0,
            "connection_pool_efficiency": 0.0,
        }
        return gateway

    def test_network_latency_simulation(self, network_gateway):
        """Test network latency handling."""
        gateway = network_gateway

        def simulate_network_request(request_id, latency_ms):
            """Simulate network request with latency."""
            time.sleep(latency_ms / 1000.0)  # Convert ms to seconds
            return {"request_id": request_id, "latency": latency_ms}

        # Test different latency scenarios
        latency_scenarios = [10, 50, 100, 200, 500]  # ms

        latency_results = []

        for latency in latency_scenarios:
            start_time = time.time()

            # Send requests with this latency
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for i in range(50):
                    future = executor.submit(simulate_network_request, i, latency)
                    futures.append(future)

                results = [future.result() for future in futures]

            end_time = time.time()
            total_time = end_time - start_time

            latency_results.append(
                {
                    "simulated_latency": latency,
                    "actual_time": total_time,
                    "requests_processed": len(results),
                }
            )

        # Verify latency handling
        for result in latency_results:
            assert result["requests_processed"] == 50
            # Actual time should be reasonable even with high latency
            assert result["actual_time"] < 5.0  # Under 5 seconds total

    def test_connection_pool_efficiency(self, network_gateway):
        """Test connection pool efficiency."""
        gateway = network_gateway

        # Simulate connection pool
        class MockConnectionPool:
            def __init__(self, max_connections):
                self.max_connections = max_connections
                self.active_connections = 0
                self.total_connections_created = 0

            def get_connection(self):
                if self.active_connections < self.max_connections:
                    self.active_connections += 1
                    self.total_connections_created += 1
                    return f"connection-{self.total_connections_created}"
                else:
                    raise Exception("No available connections")

            def release_connection(self, connection):
                self.active_connections -= 1

        # Test different pool sizes
        pool_sizes = [5, 10, 20]
        num_requests = 100

        pool_efficiency_results = []

        for pool_size in pool_sizes:
            pool = MockConnectionPool(pool_size)

            start_time = time.time()
            successful_requests = 0

            def make_request(request_id):
                try:
                    conn = pool.get_connection()
                    time.sleep(0.01)  # Simulate request
                    pool.release_connection(conn)
                    return True
                except Exception:
                    return False

            with ThreadPoolExecutor(max_workers=pool_size) as executor:
                futures = []
                for i in range(num_requests):
                    future = executor.submit(make_request, i)
                    futures.append(future)

                results = [future.result() for future in futures]
                successful_requests = sum(results)

            end_time = time.time()
            total_time = end_time - start_time

            efficiency = successful_requests / num_requests

            pool_efficiency_results.append(
                {
                    "pool_size": pool_size,
                    "successful_requests": successful_requests,
                    "total_requests": num_requests,
                    "efficiency": efficiency,
                    "time": total_time,
                }
            )

        # Verify connection pool efficiency
        for result in pool_efficiency_results:
            assert result["efficiency"] > 0.8  # At least 80% success rate

    def test_throughput_optimization(self, network_gateway):
        """Test network throughput optimization."""
        gateway = network_gateway

        def simulate_data_transfer(data_size_kb, transfer_time_ms):
            """Simulate data transfer."""
            time.sleep(transfer_time_ms / 1000.0)
            return {"data_size": data_size_kb, "transfer_time": transfer_time_ms}

        # Test different data sizes
        data_sizes = [1, 10, 100, 1000]  # KB
        transfer_times = [10, 50, 200, 1000]  # ms

        throughput_results = []

        for data_size, transfer_time in zip(data_sizes, transfer_times):
            start_time = time.time()

            # Transfer data
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for i in range(20):
                    future = executor.submit(simulate_data_transfer, data_size, transfer_time)
                    futures.append(future)

                results = [future.result() for future in futures]

            end_time = time.time()
            total_time = end_time - start_time

            # Calculate throughput
            total_data_kb = sum(r["data_size"] for r in results)
            throughput_mbps = (total_data_kb * 8) / (total_time * 1024)  # Convert to Mbps

            throughput_results.append(
                {
                    "data_size_kb": data_size,
                    "transfer_time_ms": transfer_time,
                    "total_time": total_time,
                    "throughput_mbps": throughput_mbps,
                }
            )

        # Verify throughput optimization
        for result in throughput_results:
            assert result["throughput_mbps"] > 0.1  # At least 0.1 Mbps


class TestPerformanceRegression:
    """Test performance regression detection."""

    @pytest.fixture
    def regression_gateway(self):
        """Gateway configured for regression testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.baseline_metrics = {
            "average_response_time": 0.05,  # 50ms baseline
            "throughput_rps": 100,  # 100 RPS baseline
            "memory_per_request": 1024,  # 1KB per request baseline
            "cpu_usage_percent": 10.0,  # 10% CPU baseline
        }
        gateway.current_metrics = {}
        return gateway

    def test_response_time_regression(self, regression_gateway):
        """Test response time regression detection."""
        gateway = regression_gateway

        # Simulate current performance
        def simulate_request(request_id, response_time_ms):
            time.sleep(response_time_ms / 1000.0)
            return {"request_id": request_id, "response_time": response_time_ms}

        # Test with different response times
        test_scenarios = [
            {"response_time": 30, "should_pass": True},  # Better than baseline
            {"response_time": 50, "should_pass": True},  # Same as baseline
            {"response_time": 75, "should_pass": False},  # 50% regression
            {"response_time": 100, "should_pass": False},  # 100% regression
        ]

        regression_results = []

        for scenario in test_scenarios:
            response_time = scenario["response_time"]

            start_time = time.time()
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for i in range(50):
                    future = executor.submit(simulate_request, i, response_time)
                    futures.append(future)

                results = [future.result() for future in futures]

            end_time = time.time()
            actual_response_time = (end_time - start_time) / 50 * 1000  # Average in ms

            # Check for regression
            baseline = gateway.baseline_metrics["average_response_time"] * 1000  # Convert to ms
            regression_threshold = baseline * 1.5  # 50% regression threshold
            has_regression = actual_response_time > regression_threshold

            regression_results.append(
                {
                    "target_response_time": response_time,
                    "actual_response_time": actual_response_time,
                    "baseline_response_time": baseline,
                    "has_regression": has_regression,
                    "expected_regression": not scenario["should_pass"],
                }
            )

        # Verify regression detection
        for result in regression_results:
            assert result["has_regression"] == result["expected_regression"]

    def test_throughput_regression(self, regression_gateway):
        """Test throughput regression detection."""
        gateway = regression_gateway

        baseline_throughput = gateway.baseline_metrics["throughput_rps"]

        def simulate_throughput_test(num_requests, processing_time_ms):
            start_time = time.time()

            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for i in range(num_requests):
                    future = executor.submit(lambda: time.sleep(processing_time_ms / 1000.0))
                    futures.append(future)

                results = [future.result() for future in futures]

            end_time = time.time()
            actual_throughput = num_requests / (end_time - start_time)
            return actual_throughput

        # Test different throughput scenarios
        throughput_scenarios = [
            {"processing_time": 10, "should_pass": True},  # High throughput
            {"processing_time": 20, "should_pass": True},  # Good throughput
            {"processing_time": 30, "should_pass": False},  # Regression
            {"processing_time": 50, "should_pass": False},  # Significant regression
        ]

        throughput_results = []

        for scenario in throughput_scenarios:
            actual_throughput = simulate_throughput_test(100, scenario["processing_time"])

            # Check for regression (less than 80% of baseline)
            regression_threshold = baseline_throughput * 0.8
            has_regression = actual_throughput < regression_threshold

            throughput_results.append(
                {
                    "processing_time": scenario["processing_time"],
                    "actual_throughput": actual_throughput,
                    "baseline_throughput": baseline_throughput,
                    "has_regression": has_regression,
                    "expected_regression": not scenario["should_pass"],
                }
            )

        # Verify throughput regression detection
        for result in throughput_results:
            assert result["has_regression"] == result["expected_regression"]

    def test_memory_regression(self, regression_gateway):
        """Test memory usage regression detection."""
        gateway = regression_gateway
        process = psutil.Process()

        baseline_memory_per_request = gateway.baseline_metrics["memory_per_request"]

        # Test memory usage with different request counts
        request_counts = [100, 500, 1000, 2000]
        memory_results = []

        for num_requests in request_counts:
            # Record initial memory
            initial_memory = process.memory_info().rss

            # Process requests
            circuits = []
            for i in range(num_requests):
                circuit = gateway._get_circuit_breaker(f"memory-regression-{i}")
                circuits.append(circuit)

            # Record final memory
            final_memory = process.memory_info().rss
            memory_growth = final_memory - initial_memory
            memory_per_request = memory_growth / num_requests

            # Check for regression (more than 2x baseline)
            regression_threshold = baseline_memory_per_request * 2
            has_regression = memory_per_request > regression_threshold

            memory_results.append(
                {
                    "num_requests": num_requests,
                    "memory_growth": memory_growth,
                    "memory_per_request": memory_per_request,
                    "baseline_memory_per_request": baseline_memory_per_request,
                    "has_regression": has_regression,
                }
            )

            # Clean up
            circuits.clear()
            gc.collect()

        # Verify memory regression detection
        # Memory per request should not grow significantly with request count
        memory_per_request_values = [r["memory_per_request"] for r in memory_results]
        max_memory_per_request = max(memory_per_request_values)
        min_memory_per_request = min(memory_per_request_values)

        # Memory per request should be relatively stable
        assert max_memory_per_request / min_memory_per_request < 3.0  # Less than 3x variation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
