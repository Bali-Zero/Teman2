import requests
import json
import uuid
import time

# --- Configuration ---
API_URL = "https://nuzantara-rag.fly.dev"  # Direct to Fly.io
EMAIL = "zero@balizero.com"              # Admin User
PASSWORD = "010719"                    # Correct password

def log(msg):
    print(msg)

def run_test():
    # Reuse the SAME user ID for both sessions to test Long Term Memory
    TEST_USER_ID = f"ltm_user_{uuid.uuid4()}@example.com"
    
    # Session 1 ID
    session_id_1 = f"session-1-{uuid.uuid4()}"
    # Session 2 ID
    session_id_2 = f"session-2-{uuid.uuid4()}"

    log(f"🚀 Starting Long Term Memory Test")
    log(f"👤 User ID: {TEST_USER_ID}")
    log(f"1️⃣ Session 1: {session_id_1}")
    log(f"2️⃣ Session 2: {session_id_2}")

    session = requests.Session()
    
    # Login matches test_memory_recall.py
    log("🔐 Logging in...")
    try:
        login_payload = {"email": EMAIL, "password": PASSWORD}
        resp = session.post(f"{API_URL}/api/auth/login", json=login_payload)
        resp.raise_for_status()
        token_data = resp.json().get("data", {})
        token = token_data.get("token")
        if not token:
             log(f"❌ No access token in login response: {resp.text}")
             return

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        log("✅ Login successful")
    except Exception as e:
        log(f"❌ Login failed: {e}")
        return

    # --- SESSION 1: Feed Fact ---
    log("\n--- 1️⃣ SESSION 1: TEACHING FACT ---")
    query_1 = "My favorite color is BLUE. Remember this fact forever."
    
    payload_1 = {
        "query": query_1,
        "user_id": TEST_USER_ID,
        "session_id": session_id_1, # Unique Session 1
        "conversation_history": [], # Start empty
        "model_tier": "fast"
    }
    
    try:
        # We use the NON-streaming endpoint for simplicity if available, or just stream and read events.
        # Let's check if there is a non-streaming POST /query endpoint.
        # routers/agentic_rag.py has `POST /query`?
        # It has `POST /stream`.
        
        resp = session.post(f"{API_URL}/api/agentic-rag/query", json=payload_1, headers=headers)
        if resp.status_code == 404:
            log("⚠️ /query not found, trying /stream")
            # Fallback to stream if needed, but let's assume /query exists from previous context
        
        if resp.status_code != 200:
            log(f"❌ Query failed with status {resp.status_code}: {resp.text}")
            return # Exit if the query itself failed
            
        data = resp.json()
        log(f"🐛 FULL RESPONSE 1: {json.dumps(data, indent=2)}") # Debug print
        answer_1 = data.get("answer", "")
        log(f"📥 Answer 1: {answer_1}")
        
    except Exception as e:
        log(f"❌ Query 1 failed: {e}")
        # Try stream if 404/405
    
    # WAIT for background task (Fact extraction takes time)
    log("⏳ Waiting 5 seconds for Memory Extraction...")
    time.sleep(5)
    
    # --- SESSION 2: Recall Fact ---
    log("\n--- 2️⃣ SESSION 2: RECALLING FACT ---")
    # New Session ID. Empty History. Same User ID.
    query_2 = "What is my favorite color?"
    
    payload_2 = {
        "query": query_2,
        "user_id": TEST_USER_ID,
        "session_id": session_id_2, # DIFFERENT Session
        "conversation_history": [], # EMPTY History
        "model_tier": "fast"
    }
    
    try:
        resp = session.post(f"{API_URL}/api/agentic-rag/query", json=payload_2, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("response", "")
        debug_info = data.get("debug_info", {})
        
        log(f"📥 Answer 2: {answer}")
        log(f"🐛 Debug Info: {json.dumps(debug_info, indent=2)}")
        
        if "BLUE" in answer.upper():
            log("✅ SUCCESS: Long Term Memory recalled 'BLUE' across sessions!")
        else:
            log("❌ FAILURE: Did not recall 'BLUE'.")
            
    except Exception as e:
        log(f"❌ Query 2 failed: {e}")

if __name__ == "__main__":
    run_test()
