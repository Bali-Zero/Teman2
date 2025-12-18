import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend"))
)  # Add backend dir

from dotenv import load_dotenv

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env")))

# Mock missing env vars to satisfy Pydantic
os.environ[
    "JWT_SECRET_KEY"
] = "mock_secret_must_be_very_long_to_satisfy_pydantic_validation_rules_12345"
os.environ["API_KEYS"] = '{"mock": "key"}'
os.environ["TS_BACKEND_URL"] = "http://mock"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "mock"
os.environ["INSTAGRAM_VERIFY_TOKEN"] = "mock"
# Override DB URL to use local port 5432
os.environ["DATABASE_URL"] = "postgres://antonellosiano@localhost:5432/nuzantara_dev"
# QDRANT_API_KEY must be set in environment (do not hardcode secrets)

from backend.services.context.agentic_rag_orchestrator import AgenticRAGOrchestrator

# Configure logging
logging.basicConfig(level=logging.INFO)


async def test_brain():
    print("🧠 Initializing Agentic Brain...")
    orchestrator = AgenticRAGOrchestrator()
    await orchestrator.initialize()

    query = "Quali sono le tasse per un ristorante a Bali per un investitore straniero?"
    print(f"\n❓ Query: {query}")
    print("-" * 60)

    try:
        result = await orchestrator.process_query(query, user_id="test_user_123")

        print("\n✅ Result:")
        print(f"Answer: {result['answer'][:200]}...")  # Preview
        print(f"Sources: {len(result['sources'])}")
        print(f"HyDE Used: {result.get('hyde_used')}")
        print(f"Steps Taken: {result.get('steps')}")

        print("\n📜 Full Answer:")
        print(result["answer"])
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

    await orchestrator.close()


if __name__ == "__main__":
    asyncio.run(test_brain())
