"""
Example usage of The Generals Multi-Agent System

This demonstrates how to use the system from ZANTARA's perspective.
"""

import asyncio
import logging

from backend.generals.coding_general import CodingGeneral
from backend.generals.intelligence_general import IntelligenceGeneral
from backend.generals.task_coordinator import TaskCoordinator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_submit_and_wait():
    """Example: Submit a task and wait for completion."""
    coordinator = TaskCoordinator()
    await coordinator.initialize()

    try:
        # Submit a code task
        task_id = await coordinator.submit_task(
            task_type="code",
            title="Run Python script",
            description="Execute a Python script",
            payload={"command": "python -c 'logger.info(\"Hello from Coding General!\")'"},
            priority=7,
        )
        logger.info(f"✅ Submitted task {task_id}")

        # Wait for completion
        result = await coordinator.wait_for_task(task_id, timeout=60)
        if result:
            logger.info(f"✅ Task completed: {result['status']}")
            logger.info(f"Result: {result.get('result', {})}")
        else:
            logger.warning("⚠️ Task timeout or error")

    finally:
        await coordinator.close()


async def example_research_task():
    """Example: Submit a research task."""
    coordinator = TaskCoordinator()
    await coordinator.initialize()

    try:
        # Submit a research task
        task_id = await coordinator.submit_task(
            task_type="research",
            title="Research AI trends",
            description="What are the latest trends in AI?",
            payload={
                "query": "What are the latest trends in artificial intelligence in 2026?",
                "max_tokens": 4096,
                "temperature": 0.7,
                "save_to_memory": True,
                "memory_key": "ai_trends_2026",
            },
            priority=8,
        )
        logger.info(f"✅ Submitted research task {task_id}")

        # Wait for completion
        result = await coordinator.wait_for_task(task_id, timeout=120)
        if result and result["status"] == "completed":
            analysis = result.get("result", {}).get("analysis", "")
            logger.info(f"✅ Research completed:\n{analysis[:500]}...")

            # Retrieve from memory
            memory = await coordinator.get_memory("ai_trends_2026")
            if memory:
                logger.info(f"✅ Retrieved from memory: {memory['value']['query']}")

    finally:
        await coordinator.close()


async def example_run_generals():
    """Example: Run generals in background and submit tasks."""
    coordinator = TaskCoordinator()
    await coordinator.initialize()

    coding_general = CodingGeneral(poll_interval=2)
    intelligence_general = IntelligenceGeneral(poll_interval=2)

    try:
        await coding_general.initialize()
        await intelligence_general.initialize()

        # Start generals in background
        coding_task = asyncio.create_task(coding_general.run_loop())
        intelligence_task = asyncio.create_task(intelligence_general.run_loop())

        logger.info("🚀 Generals started")

        # Submit multiple tasks
        task_ids = []
        for i in range(3):
            task_id = await coordinator.submit_task(
                task_type="code",
                title=f"Task {i + 1}",
                payload={"command": f"echo 'Task {i + 1} completed'"},
                priority=5,
            )
            task_ids.append(task_id)
            logger.info(f"✅ Submitted task {task_id}")

        # Wait a bit for processing
        await asyncio.sleep(10)

        # Check results
        for task_id in task_ids:
            result = await coordinator.get_task_result(task_id)
            if result:
                logger.info(f"✅ Task {task_id}: {result['status']}")

        # Stop generals
        coding_general.stop()
        intelligence_general.stop()
        coding_task.cancel()
        intelligence_task.cancel()

    finally:
        await coding_general.close()
        await intelligence_general.close()
        await coordinator.close()


async def example_memory_sharing():
    """Example: Share memory between tasks."""
    coordinator = TaskCoordinator()
    await coordinator.initialize()

    try:
        # First task: Research and save to memory
        research_id = await coordinator.submit_task(
            task_type="research",
            title="Initial Research",
            payload={
                "query": "What is machine learning?",
                "save_to_memory": True,
                "memory_key": "ml_basics",
            },
            priority=9,
        )

        # Wait for research
        await coordinator.wait_for_task(research_id, timeout=120)

        # Second task: Use previous research
        followup_id = await coordinator.submit_task(
            task_type="research",
            title="Follow-up Research",
            payload={
                "query": "What are the applications of machine learning?",
                "memory_keys": ["ml_basics"],  # Use previous research
                "save_to_memory": True,
                "memory_key": "ml_applications",
            },
            priority=8,
        )

        # Wait for follow-up
        result = await coordinator.wait_for_task(followup_id, timeout=120)
        if result:
            logger.info("✅ Follow-up research completed using shared memory")

        # Check memory
        ml_basics = await coordinator.get_memory("ml_basics")
        ml_apps = await coordinator.get_memory("ml_applications")
        logger.info(
            f"✅ Memory keys available: ml_basics={ml_basics is not None}, ml_applications={ml_apps is not None}"
        )

    finally:
        await coordinator.close()


async def example_monitoring():
    """Example: Monitor system stats and activity."""
    coordinator = TaskCoordinator()
    await coordinator.initialize()

    try:
        # Get system stats
        stats = await coordinator.get_stats()
        logger.info("📊 System Stats:")
        logger.info(f"  Tasks: {stats['tasks']}")
        logger.info(f"  Memory: {stats['memory']}")
        logger.info(f"  Activity: {stats['activity']}")

        # Get recent activity
        activities = await coordinator.get_activity(limit=10)
        logger.info(f"📋 Recent Activity ({len(activities)} entries):")
        for activity in activities[:5]:
            logger.info(
                f"  {activity['general_name']}: {activity['activity_type']} - {activity['message']}"
            )

        # Get pending tasks
        pending = await coordinator.get_tasks(status="pending")
        logger.info(f"⏳ Pending Tasks: {len(pending)}")

    finally:
        await coordinator.close()


if __name__ == "__main__":
    logger.info("The Generals Multi-Agent System - Examples")
    logger.info("=" * 50)
    logger.info("\n1. Submit and Wait Example")
    asyncio.run(example_submit_and_wait())
    logger.info("\n2. Research Task Example")
    asyncio.run(example_research_task())
    logger.info("\n3. Memory Sharing Example")
    asyncio.run(example_memory_sharing())
    logger.info("\n4. Monitoring Example")
    asyncio.run(example_monitoring())
