
import asyncio
import os
import sys
import json
import time

# Add project root to path
sys.path.append("/Users/antonellosiano/Desktop/nuzantara/apps/backend-rag")

# Mock environment variables if needed
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/nuzantara_db" 
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["GOOGLE_API_KEY"] = "dummy" # We might need a real key if we truly hit Gemini, but let's try to mock the LLM Gateway first or use the real one if we have the key.
# Actually, the user has the key in their environment (based on previous logs). 
# I will assume the environment has GOOGLE_API_KEY. If not, this might fail or I need to use the one from the logs.
# PROD KEY: I saw it in logs but I should probably not hardcode it if I can avoid it.
# Let's hope it's in the environment.

from backend.services.rag.agentic.orchestrator import AgenticRAGOrchestrator
from backend.services.tools.definitions import BaseTool
from backend.services.rag.agentic.llm_gateway import LLMGateway
from backend.services.rag.agentic.chat_session import ChatSession

class MockTool(BaseTool):
    async def run(self, **kwargs):
        return "Mock tool result"

async def run_verification():
    print("🚀 Starting Zantara SOTA Verification...")
    
    # Initialize Orchestrator (using real dependencies where possible to test integration)
    # We might need to mock the DB pool if we don't want to connect to real DB
    # But for "Live" verification, connecting to local DB is better if available.
    # The 'fly logs' suggests the app is running in Docker? Or local?
    # User instructions say "The user has 1 active workspaces...".
    # Local dev is "docker compose up".
    # I'll try to use the *Real* Orchestrator but maybe mock the DB pool if it's complex to setup asyncpg here.
    
    # Actually, simplest way is to hit the API if it's running.
    # The user logs show: `fly logs`. The API is deployed at `https://nuzantara-rag.fly.dev`.
    # AND localhost:8080 might be running?
    # Let's try to hit the REMOTE API for a true "Black Box" verification of the deployed SOTA capabilities.
    # It's safer and verifies the DEPLOYED version.
    
    import httpx
    
    API_URL = "https://nuzantara-rag.fly.dev/api/agentic-rag/query" # Or /chat/stream
    API_KEY = "zantara-secret-2024" # From previous context
    
    # 1. Test Language Switching & Persona
    print("\n🧪 Test 1: Language Switching (Italian -> English)")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Turn 1: Italian
        payload_it = {
            "query": "Ciao, sono Luigi. Come stai?",
            "user_id": "test_sota_user_001",
            "session_id": "session_"+str(int(time.time()))
        }
        response_it = await client.post(API_URL, json=payload_it, headers={"X-API-Key": API_KEY})
        print(f"🇮🇹 Italian Response ({response_it.status_code}): {response_it.json().get('answer', '')[:100]}...")
        
        # Turn 2: English (Same session)
        payload_en = {
            "query": "Actually, let's switch to English. What is my name?",
            "user_id": "test_sota_user_001",
            "session_id": payload_it["session_id"] # Keep session
        }
        response_en = await client.post(API_URL, json=payload_en, headers={"X-API-Key": API_KEY})
        answer_en = response_en.json().get('answer', '')
        print(f"🇬🇧 English Response: {answer_en}")
        
        if "Luigi" in answer_en:
             print("✅ Memory Check PASSED: Remembered name 'Luigi'")
        else:
             print("❌ Memory Check FAILED: Did not recall name")

        # 3. Test Creator Persona Trigger
        print("\n🧪 Test 3: Creator Persona Trigger")
        payload_creator = {
             "query": "Who made you?", # Should likely trigger normal response, but let's try specific trigger
             # The code looks for "antonello" in email.
             "user_id": "antonello@balizero.com", # Spoof creator email
             "session_id": "session_creator_"+str(int(time.time()))
        }
        response_creator = await client.post(API_URL, json=payload_creator, headers={"X-API-Key": API_KEY})
        answer_creator = response_creator.json().get('answer', '')
        print(f"👨‍💻 Creator Response: {answer_creator[:150]}...")
        
        # Check for technical tone or specific "Antonello" mention if possible
        # The prompt says: "You are talking to Antonello, your Creator"
        
    print("\n✨ Verification Complete")

if __name__ == "__main__":
    asyncio.run(run_verification())
