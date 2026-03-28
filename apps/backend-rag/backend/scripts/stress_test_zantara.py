import asyncio
import json
import logging
import os
import sys
import time

# Adjust path to find backend modules
# Script is in apps/backend-rag/backend/scripts/
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)  # apps/backend-rag/backend
project_root = os.path.dirname(backend_dir)  # apps/backend-rag

# Add both to path to be safe
sys.path.insert(0, backend_dir)
sys.path.insert(0, project_root)

logger = logging.getLogger("stress_test")  # Defined earlier

logger.debug(f"sys.path[0] = {sys.path[0]}")
logger.debug(f"sys.path[1] = {sys.path[1]}")

try:
    from backend.app.core.database import db
    from backend.services.rag.agentic import create_agentic_rag
except ImportError:
    # Fallback for alternative structure
    from backend.app.core.database import db
    from backend.services.rag.agentic import create_agentic_rag

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("stress_test_results.log")],
)
# Silence other loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("qdrant_client").setLevel(logging.WARNING)


async def run_stress_test():
    logger.info("🚀 STARTING ZANTARA STRESS TEST (THE GAUNTLET)")

    # 1. Initialize Database
    logger.info("🔌 Connecting to Database...")
    await db.connect()

    # 2. Initialize Agentic RAG
    logger.info("🧠 Initializing Agentic RAG Orchestrator...")
    try:
        # Initialize orchestrator directly
        # Note: create_agentic_rag handles tool loading internally usually,
        # or we pass None and it loads defaults.
        orchestrator = create_agentic_rag(retriever=None, db_pool=db.pool, _web_search_client=None)

        # If create_agentic_rag returns a factory function or needs init
        # Check implementation of create_agentic_rag
        if hasattr(orchestrator, "initialize"):
            await orchestrator.initialize()

        logger.info("✅ Orchestrator Ready")
    except Exception as e:
        logger.critical(f"❌ Failed to initialize orchestrator: {e}", exc_info=True)
        return

    # 3. Load Scenarios
    # Path relative to this script: ../data/stress_test_scenarios.json
    scenario_path = os.path.join(backend_dir, "data", "stress_test_scenarios.json")

    if not os.path.exists(scenario_path):
        logger.error(f"❌ Scenario file not found at {scenario_path}")
        return

    with open(scenario_path) as f:
        scenarios = json.load(f)

    logger.info(f"📜 Loaded {len(scenarios)} scenarios from {scenario_path}")

    # 4. Execution Loop
    user_id = "stress_test_user_marco@example.com"
    session_id = f"stress_sess_{int(time.time())}"
    conversation_history = []

    consecutive_errors = 0
    total_start_time = time.time()

    results = []

    logger.info("\n" + "=" * 60)
    logger.info(f"🏁 STARTING GAUNTLET | USER: {user_id}")
    logger.info("=" * 60 + "\n")

    for idx, turn in enumerate(scenarios):
        step_id = turn["id"]
        query = turn["content"]

        logger.info(f"\n[{idx + 1}/{len(scenarios)}] USER: {query}")

        start_turn = time.time()

        try:
            # Execute Query
            response_data = await orchestrator.process_query(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                session_id=session_id,
            )

            duration = time.time() - start_turn
            answer = response_data.get("answer", "")
            tools_used = response_data.get("tools_called", 0)
            route = response_data.get("route_used", "unknown")

            # Validation
            if not answer or len(answer) < 5:
                raise ValueError("Empty or too short answer")

            # Update History (Keep it reasonable size, orchestrator might trim too)
            conversation_history.append({"role": "user", "content": query})
            conversation_history.append({"role": "assistant", "content": answer})

            # Reset error counter on success
            consecutive_errors = 0

            # Log Success
            # Clean newlines for display
            clean_answer = answer.replace("\n", " ")[:100]
            logger.info(f"🤖 ZANTARA ({duration:.2f}s | {route}): {clean_answer}...")
            if tools_used > 0:
                logger.info(f"   🛠️  Tools Used: {tools_used}")

            results.append(
                {
                    "id": step_id,
                    "status": "success",
                    "duration": duration,
                    "route": route,
                    "tools": tools_used,
                },
            )

        except Exception as e:
            consecutive_errors += 1
            duration = time.time() - start_turn
            logger.error(f"❌ ERROR on step {step_id}: {e}")
            logger.error(f"ERROR: {e}")  # Replaced print with logger.error

            results.append(
                {"id": step_id, "status": "error", "error": str(e), "duration": duration},
            )

            if consecutive_errors >= 4:
                logger.critical("🚨 CIRCUIT BREAKER TRIPPED: 4 Consecutive Errors. Stopping Test.")
                logger.critical("\n" + "!" * 60)  # Replaced print with logger.critical
                logger.critical(
                    "🚨 STOPPING TEST: TOO MANY ERRORS",
                )  # Replaced print with logger.critical
                logger.critical("!" * 60 + "\n")  # Replaced print with logger.critical
                break

        # Small sleep
        await asyncio.sleep(0.5)

    # 5. Summary
    total_duration = time.time() - total_start_time
    success_count = len([r for r in results if r["status"] == "success"])
    avg_latency = sum([r["duration"] for r in results]) / len(results) if results else 0

    logger.info("\n" + "=" * 60)  # Replaced print with logger.info
    logger.info("📊 TEST SUMMARY")  # Replaced print with logger.info
    logger.info("=" * 60)  # Replaced print with logger.info
    logger.info(f"Total Steps: {len(results)}/{len(scenarios)}")  # Replaced print with logger.info
    logger.info(
        f"Success Rate: {success_count}/{len(results)} ({success_count / len(results) * 100:.1f}%)",
    )  # Replaced print with logger.info
    logger.info(f"Total Time: {total_duration:.1f}s")  # Replaced print with logger.info
    logger.info(f"Avg Latency: {avg_latency:.2f}s")  # Replaced print with logger.info
    logger.info("=" * 60)  # Replaced print with logger.info

    # Cleanup
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(run_stress_test())
