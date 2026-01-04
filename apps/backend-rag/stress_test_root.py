import asyncio
import json
import logging
import os
import sys
import time

# Ensure we can import from backend package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.app.core.database import db

from backend.services.rag.agentic import create_agentic_rag

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("stress_test_results.log")],
)
# Silence noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("stress_test")


async def run_stress_test():
    logger.info("🚀 STARTING ZANTARA STRESS TEST (THE GAUNTLET)")

    # 1. Initialize Database
    logger.info("🔌 Connecting to Database...")
    try:
        await db.connect()
    except Exception as e:
        logger.error(f"DB Connection failed: {e}")
        # Proceed only if allowed (might fail later)

    # 2. Initialize Agentic RAG
    logger.info("🧠 Initializing Agentic RAG Orchestrator...")
    try:
        orchestrator = create_agentic_rag(retriever=None, db_pool=db.pool, web_search_client=None)
        if hasattr(orchestrator, "initialize"):
            await orchestrator.initialize()
        logger.info("✅ Orchestrator Ready")
    except Exception as e:
        logger.critical(f"❌ Failed to initialize orchestrator: {e}", exc_info=True)
        return

    # 3. Load Scenarios
    # Path relative to apps/backend-rag/
    scenario_path = os.path.join("backend", "data", "stress_test_scenarios.json")

    if not os.path.exists(scenario_path):
        logger.error(f"❌ Scenario file not found at {scenario_path}")
        # Create dummy if missing
        scenarios = [{"id": 1, "role": "user", "content": "Ciao, chi sei?"}]
    else:
        with open(scenario_path) as f:
            scenarios = json.load(f)

    logger.info(f"📜 Loaded {len(scenarios)} scenarios")

    # 4. Execution Loop
    user_id = "stress_test_user_marco@example.com"
    session_id = f"stress_sess_{int(time.time())}"
    conversation_history = []
    consecutive_errors = 0
    total_start_time = time.time()
    results = []

    print("\n" + "=" * 60)
    print(f"🏁 STARTING GAUNTLET | USER: {user_id}")
    print("=" * 60 + "\n")

    for idx, turn in enumerate(scenarios):
        step_id = turn.get("id", idx)
        query = turn["content"]

        print(f"\n[{step_id}/{len(scenarios)}] USER: {query}")
        start_turn = time.time()

        try:
            response_data = await orchestrator.process_query(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                session_id=session_id,
            )

            duration = time.time() - start_turn
            answer = response_data.get("answer", "")
            route = response_data.get("route_used", "unknown")

            if not answer or len(answer) < 5:
                raise ValueError("Empty or too short answer")

            conversation_history.append({"role": "user", "content": query})
            conversation_history.append({"role": "assistant", "content": answer})
            consecutive_errors = 0

            clean_answer = answer.replace("\n", " ")[:100]
            print(f"🤖 ZANTARA ({duration:.2f}s | {route}): {clean_answer}...")

            results.append({"id": step_id, "status": "success", "duration": duration})

        except Exception as e:
            consecutive_errors += 1
            duration = time.time() - start_turn
            logger.error(f"❌ ERROR on step {step_id}: {e}")
            print(f"❌ ERROR: {e}")
            results.append(
                {"id": step_id, "status": "error", "error": str(e), "duration": duration}
            )

            if consecutive_errors >= 4:
                logger.critical("🚨 CIRCUIT BREAKER TRIPPED")
                break

        await asyncio.sleep(0.5)

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(run_stress_test())
