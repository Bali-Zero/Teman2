import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/backend-rag/backend")))

from app.core.config import settings
from app.core.database import db
from services.rag.agentic import create_agentic_rag
from services.rag.agentic.tools import get_all_tools

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("stress_test_results.log")
    ]
)
logger = logging.getLogger("stress_test")

async def run_stress_test():
    logger.info("🚀 STARTING ZANTARA STRESS TEST (THE GAUNTLET)")
    
    # 1. Initialize Database
    logger.info("🔌 Connecting to Database...")
    await db.connect()
    
    # 2. Initialize Agentic RAG
    logger.info("🧠 Initializing Agentic RAG Orchestrator...")
    try:
        # Get tool definitions
        tools = get_all_tools()
        
        # Initialize orchestrator directly
        orchestrator = create_agentic_rag(
            retriever=None, # Will be handled internally or by search tool
            db_pool=db.pool,
            web_search_client=None
        )
        await orchestrator.initialize()
        logger.info("✅ Orchestrator Ready")
    except Exception as e:
        logger.critical(f"❌ Failed to initialize orchestrator: {e}")
        return

    # 3. Load Scenarios
    scenario_path = os.path.join(os.path.dirname(__file__), "data/stress_test_scenarios.json")
    with open(scenario_path, "r") as f:
        scenarios = json.load(f)
    
    logger.info(f"📜 Loaded {len(scenarios)} scenarios from {scenario_path}")

    # 4. Execution Loop
    user_id = "stress_test_user_marco@example.com"
    session_id = f"stress_sess_{int(time.time())}"
    conversation_history = []
    
    consecutive_errors = 0
    total_start_time = time.time()
    
    results = []

    print("\n" + "="*60)
    print(f"🏁 STARTING GAUNTLET | USER: {user_id}")
    print("="*60 + "\n")

    for idx, turn in enumerate(scenarios):
        step_id = turn['id']
        query = turn['content']
        
        print(f"\n[{step_id}/{len(scenarios)}] USER: {query}")
        
        start_turn = time.time()
        
        try:
            # Execute Query
            # Using process_query (non-streaming) for simpler testing logic, 
            # but orchestrator handles both same way logic-wise.
            response_data = await orchestrator.process_query(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                session_id=session_id
            )
            
            duration = time.time() - start_turn
            answer = response_data.get("answer", "")
            tools_used = response_data.get("tools_called", 0)
            route = response_data.get("route_used", "unknown")
            
            # Validation
            if not answer or len(answer) < 5:
                raise ValueError("Empty or too short answer")
            
            # Update History
            conversation_history.append({"role": "user", "content": query})
            conversation_history.append({"role": "assistant", "content": answer})
            
            # Reset error counter on success
            consecutive_errors = 0
            
            # Log Success
            print(f"🤖 ZANTARA ({duration:.2f}s | {route}): {answer[:100]}...")
            if tools_used > 0:
                print(f"   🛠️  Tools Used: {tools_used}")
            
            results.append({
                "id": step_id,
                "status": "success",
                "duration": duration,
                "route": route,
                "tools": tools_used
            })

        except Exception as e:
            consecutive_errors += 1
            duration = time.time() - start_turn
            logger.error(f"❌ ERROR on step {step_id}: {e}")
            print(f"❌ ERROR: {e}")
            
            results.append({
                "id": step_id,
                "status": "error",
                "error": str(e),
                "duration": duration
            })

            if consecutive_errors >= 4:
                logger.critical("🚨 CIRCUIT BREAKER TRIPPED: 4 Consecutive Errors. Stopping Test.")
                print("\n" + "!"*60)
                print("🚨 STOPPING TEST: TOO MANY ERRORS")
                print("!"*60 + "\n")
                break
        
        # Small sleep to be polite to APIs
        await asyncio.sleep(1)

    # 5. Summary
    total_duration = time.time() - total_start_time
    success_count = len([r for r in results if r['status'] == 'success'])
    avg_latency = sum([r['duration'] for r in results]) / len(results) if results else 0
    
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    print(f"Total Steps: {len(results)}/{len(scenarios)}")
    print(f"Success Rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    print(f"Total Time: {total_duration:.1f}s")
    print(f"Avg Latency: {avg_latency:.2f}s")
    print("="*60)

    # Cleanup
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(run_stress_test())
