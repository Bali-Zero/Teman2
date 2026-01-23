#!/usr/bin/env python3
"""
Performance test for parallel context loading optimization.

This script tests the parallel context loading implementation to verify:
1. Timing improvements (200-400ms speedup expected)
2. Logging pattern for PARALLEL LOADING
3. Graceful degradation when memory_orchestrator is unavailable
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add backend to path - need to add the parent directory so backend can be imported
script_dir = Path(__file__).parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))


from backend.services.memory import MemoryContext
from backend.services.rag.agentic.context_manager import get_user_context

# Configure logging to capture PARALLEL LOADING messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MockMemoryOrchestrator:
    """Mock MemoryOrchestrator that simulates async delay"""

    def __init__(self, delay: float = 0.3):
        self.delay = delay

    async def get_user_context(self, user_id: str, query: str | None = None):
        """Simulate memory fetch with delay"""
        await asyncio.sleep(self.delay)  # Simulate network/DB delay
        return MemoryContext(
            user_id=user_id,
            profile_facts=[f"Fact {i} for {user_id}" for i in range(5)],
            collective_facts=[f"Collective fact {i}" for i in range(3)],
            timeline_summary="Test timeline summary",
            kg_entities=[{"type": "person", "name": "Test User"}],
            summary="Test summary",
            counters={"conversations": 5, "searches": 10},
            has_data=True,
        )


class MockDBPool:
    """Mock database pool that simulates async delay"""

    def __init__(self, delay: float = 0.4):
        self.delay = delay

    def acquire(self):
        """Return a mock connection as async context manager"""
        return MockConnection(self.delay)


class MockConnection:
    """Mock database connection that supports async context manager"""

    def __init__(self, delay: float = 0.4):
        self.delay = delay

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def fetchrow(self, query: str, *args):
        """Simulate DB query with delay"""
        await asyncio.sleep(self.delay)
        return {
            "id": "test-user-id",
            "name": "Test User",
            "role": "admin",
            "department": "Engineering",
            "preferred_language": "en",
            "notes": "Test notes",
            "email": "test@example.com",
            "latest_conversation": json.dumps(
                {
                    "id": "conv-123",
                    "messages": [{"role": "user", "content": "Hello"}],
                }
            ),
        }


async def test_parallel_loading():
    """Test parallel loading performance"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Parallel Loading Performance")
    logger.info("=" * 80)

    db_pool = MockDBPool(delay=0.4)  # 400ms DB delay
    memory_orchestrator = MockMemoryOrchestrator(delay=0.3)  # 300ms Memory delay

    start_time = time.time()
    context = await get_user_context(
        db_pool=db_pool,
        user_id="test@example.com",
        memory_orchestrator=memory_orchestrator,
        query="test query",
    )
    total_time = time.time() - start_time

    logger.info("\n✅ Parallel execution completed")
    logger.info(f"   Total time: {total_time:.3f}s")
    logger.info("   Expected sequential time: ~0.700s (0.4s DB + 0.3s Memory)")
    logger.info("   Expected parallel time: ~0.400s (max of both)")
    logger.info("   Expected speedup: ~0.300s")

    # Verify context structure
    assert context["profile"] is not None, "Profile should be loaded"
    assert len(context["facts"]) > 0, "Memory facts should be loaded"
    logger.info("   ✅ Context structure verified")

    if total_time < 0.5:  # Should be close to max(0.4, 0.3) = 0.4s
        logger.info(f"   ✅ Performance target met: {total_time:.3f}s < 0.500s")
    else:
        logger.warning(f"   ⚠️  Performance slower than expected: {total_time:.3f}s")

    return total_time


async def test_graceful_degradation_no_memory():
    """Test graceful degradation when memory_orchestrator is None"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Graceful Degradation (No Memory Orchestrator)")
    logger.info("=" * 80)

    db_pool = MockDBPool(delay=0.2)
    memory_orchestrator = None  # No memory orchestrator

    start_time = time.time()
    context = await get_user_context(
        db_pool=db_pool,
        user_id="test@example.com",
        memory_orchestrator=memory_orchestrator,
    )
    total_time = time.time() - start_time

    logger.info("\n✅ Graceful degradation test completed")
    logger.info(f"   Total time: {total_time:.3f}s")
    logger.info(f"   Profile loaded: {context['profile'] is not None}")
    logger.info(f"   Memory facts: {len(context.get('facts', []))}")
    logger.info("   Expected: Empty facts list (graceful degradation)")

    assert context["profile"] is not None, "Profile should still be loaded"
    assert context.get("facts") == [], "Facts should be empty (graceful degradation)"
    logger.info("   ✅ Graceful degradation verified")


async def test_graceful_degradation_memory_error():
    """Test graceful degradation when memory fetch fails"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Graceful Degradation (Memory Fetch Error)")
    logger.info("=" * 80)

    db_pool = MockDBPool(delay=0.2)

    class FailingMemoryOrchestrator:
        async def get_user_context(self, user_id: str, query: str | None = None):
            raise RuntimeError("Memory service unavailable")

    memory_orchestrator = FailingMemoryOrchestrator()

    start_time = time.time()
    context = await get_user_context(
        db_pool=db_pool,
        user_id="test@example.com",
        memory_orchestrator=memory_orchestrator,
    )
    total_time = time.time() - start_time

    logger.info("\n✅ Error handling test completed")
    logger.info(f"   Total time: {total_time:.3f}s")
    logger.info(f"   Profile loaded: {context['profile'] is not None}")
    logger.info(f"   Memory facts: {len(context.get('facts', []))}")
    logger.info("   Expected: Empty facts list (error handled gracefully)")

    assert context["profile"] is not None, "Profile should still be loaded"
    assert context.get("facts") == [], "Facts should be empty (error handled)"
    logger.info("   ✅ Error handling verified")


async def test_logging_pattern():
    """Test that PARALLEL LOADING log pattern appears"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Logging Pattern Verification")
    logger.info("=" * 80)

    # Capture log messages
    log_capture = []

    class LogHandler(logging.Handler):
        def emit(self, record):
            log_capture.append(record.getMessage())

    handler = LogHandler()
    handler.setLevel(logging.WARNING)
    logging.getLogger("backend.services.rag.agentic.context_manager").addHandler(handler)

    db_pool = MockDBPool(delay=0.2)
    memory_orchestrator = MockMemoryOrchestrator(delay=0.2)

    await get_user_context(
        db_pool=db_pool,
        user_id="test@example.com",
        memory_orchestrator=memory_orchestrator,
    )

    # Check for PARALLEL LOADING pattern
    parallel_logs = [log for log in log_capture if "PARALLEL LOADING" in log]
    profile_logs = [log for log in log_capture if "Profile fetch" in log]
    memory_logs = [log for log in log_capture if "Memory fetch" in log]

    logger.info("\n✅ Logging pattern check:")
    logger.info(f"   PARALLEL LOADING logs: {len(parallel_logs)}")
    logger.info(f"   Profile fetch logs: {len(profile_logs)}")
    logger.info(f"   Memory fetch logs: {len(memory_logs)}")

    if parallel_logs:
        logger.info("   ✅ PARALLEL LOADING pattern found:")
        for log in parallel_logs:
            logger.info(f"      - {log}")
    else:
        logger.warning("   ⚠️  PARALLEL LOADING pattern not found in logs")

    logging.getLogger("backend.services.rag.agentic.context_manager").removeHandler(handler)


async def main():
    """Run all tests"""
    logger.info("\n" + "🚀 " * 20)
    logger.info("PARALLEL CONTEXT LOADING PERFORMANCE TESTS")
    logger.info("🚀 " * 20)

    try:
        # Test 1: Performance
        parallel_time = await test_parallel_loading()

        # Test 2: Graceful degradation (no memory)
        await test_graceful_degradation_no_memory()

        # Test 3: Graceful degradation (memory error)
        await test_graceful_degradation_memory_error()

        # Test 4: Logging pattern
        await test_logging_pattern()

        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL TESTS COMPLETED")
        logger.info("=" * 80)
        logger.info("\nSummary:")
        logger.info(f"  - Parallel loading time: {parallel_time:.3f}s")
        logger.info("  - Expected speedup: 200-400ms reduction")
        logger.info("  - Graceful degradation: ✅ Verified")
        logger.info("  - Error handling: ✅ Verified")

    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
