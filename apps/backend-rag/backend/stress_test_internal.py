import asyncio
import json
import logging
import os
import sys
import time
import asyncpg

# Script running from apps/backend-rag/backend/
# PYTHONPATH should be set to .

from app.core.config import settings
from services.rag.agentic import create_agentic_rag

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("stress_test_results.log")
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("stress_test")

async def run_stress_test():
    logger.info("🚀 STARTING ZANTARA STRESS TEST (THE GAUNTLET)")
    
    db_pool = None
    
    # 1. Initialize Database
    if settings.database_url:
        logger.info("🔌 Connecting to Database...")
        try:
            db_pool = await asyncpg.create_pool(dsn=settings.database_url)
            logger.info("✅ Database Connected")
        except Exception as e:
            logger.error(f"❌ DB Connection failed: {e}")
            # Proceed even without DB if possible (in-memory fallback might work for RAG)
    else:
        logger.warning("⚠️ No DATABASE_URL set")
    
    # 2. Initialize Agentic RAG
    logger.info("🧠 Initializing Agentic RAG Orchestrator...")
    try:
        orchestrator = create_agentic_rag(
            retriever=None, 
            db_pool=db_pool,
            web_search_client=None
        )
        # Note: initialize() might need await
        if hasattr(orchestrator, 'initialize'):
             init_res = orchestrator.initialize()
             if asyncio.iscoroutine(init_res):
                 await init_res
                 
        logger.info("✅ Orchestrator Ready")
    except Exception as e:
        logger.critical(f"❌ Failed to initialize orchestrator: {e}", exc_info=True)
        if db_pool:
            await db_pool.close()
        return

    # 3. Load Scenarios
    scenario_path = os.path.join("data", "stress_test_scenarios.json")
    if not os.path.exists(scenario_path):
        logger.error(f"❌ Scenario file not found at {scenario_path}")
        if db_pool:
            await db_pool.close()
        return

    with open(scenario_path, "r") as f:
        scenarios = json.load(f)
    
    logger.info(f"📜 Loaded {len(scenarios)} scenarios")

    # 4. Execution Loop
    user_id = "stress_test_user_marco@example.com"
    session_id = f"stress_sess_{int(time.time())}"
    conversation_history = []
    consecutive_errors = 0
    total_start_time = time.time()

    print("\n" + "="*60)
    print(f"🏁 STARTING GAUNTLET | USER: {user_id}")
    print("="*60 + "\n")

    for idx, turn in enumerate(scenarios):
        step_id = turn.get('id', idx)
        query = turn['content']
        
        print(f"\n[{step_id}/{len(scenarios)}] USER: {query}")
        start_turn = time.time()
        
        try:
            # process_query is async
            response_data = await orchestrator.process_query(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                session_id=session_id
            )
            
            duration = time.time() - start_turn
            answer = response_data.get("answer", "")
            route = response_data.get("route_used", "unknown")
            
            if not answer or len(answer) < 5:
                raise ValueError("Empty or too short answer")
            
            conversation_history.append({"role": "user", "content": query})
            conversation_history.append({"role": "assistant", "content": answer})
            consecutive_errors = 0
            
            clean_answer = answer.replace('\n', ' ')[:100]
            print(f"🤖 ZANTARA ({duration:.2f}s | {route}): {clean_answer}...")

        except Exception as e:
            consecutive_errors += 1
            logger.error(f"❌ ERROR: {e}")
            if consecutive_errors >= 4:
                logger.critical("🚨 CIRCUIT BREAKER TRIPPED")
                break
        
        await asyncio.sleep(0.5)

    if db_pool:
        await db_pool.close()

if __name__ == "__main__":
    asyncio.run(run_stress_test())
