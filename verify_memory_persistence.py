
import asyncio
import httpx
import time
import uuid

API_URL = "https://nuzantara-rag.fly.dev/api/agentic-rag/query"
API_KEY = "REDACTED-ROTATED-KEY" # Assumed from previous context

async def run_memory_audit():
    print("🧠 Starting Zantara Memory Persistence Audit...")
    
    # Generate a unique test identity to avoid collision with previous tests
    test_id = str(uuid.uuid4())[:8]
    user_id = f"auditor_{test_id}@nuzantara.com"
    profession = f"Quantum Architect {test_id}"
    origin = f"Nebula {test_id}"
    
    print(f"👤 User Identity: {user_id}")
    print(f"🔑 Fact to Inject: I am a {profession} from {origin}.")
    
    headers = {"X-API-Key": API_KEY}
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # --- SESSION A: INJECTION ---
        session_a = f"session_A_{test_id}"
        print(f"\n[Session A] Injecting memories... (ID: {session_a})")
        
        payload_inject = {
            "query": f"Hi, my name is TestUser. I work as a {profession} and I come from {origin}. Please remember this.",
            "user_id": user_id,
            "session_id": session_a
        }
        
        try:
            resp_a = await client.post(API_URL, json=payload_inject, headers=headers)
            resp_a.raise_for_status()
            print(f"✅ Session A Response: {resp_a.json().get('answer', '')[:100]}...")
        except Exception as e:
            print(f"❌ Session A Failed: {e}")
            return

        # Wait for Async Persistence (Critical Step)
        # The backend uses background tasks for memory persistence, give it time.
        print("\n⏳ Waiting 30 seconds for Async DB Persistence...")
        await asyncio.sleep(30)
        
        # --- SESSION B: RECALL ---
        session_b = f"session_B_{test_id}"
        print(f"\n[Session B] Testing Cross-Session Recall... (ID: {session_b})")
        
        payload_recall = {
            "query": "What is my profession and where am I from?",
            "user_id": user_id,
            "session_id": session_b # NEW SESSION ID
        }
        
        try:
            resp_b = await client.post(API_URL, json=payload_recall, headers=headers)
            resp_b.raise_for_status()
            answer_b = resp_b.json().get('answer', '')
            print(f"🗣️ Session B Response: {answer_b}")
            
            # Verification Logic
            success = True
            if profession in answer_b:
                print("✅ RECALL CONFIRMED: Profession found.")
            else:
                print(f"❌ RECALL FAILED: Profession '{profession}' not found.")
                success = False
                
            if origin in answer_b:
                print("✅ RECALL CONFIRMED: Origin found.")
            else:
                print(f"❌ RECALL FAILED: Origin '{origin}' not found.")
                success = False
                
            if success:
                print("\n🏆 MEMORY AUDIT PASSED: Persistent Memory is working across sessions.")
            else:
                print("\n⚠️ MEMORY AUDIT FAILED: Could not retrieve injected facts.")
                
        except Exception as e:
             print(f"❌ Session B Failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_memory_audit())
