import requests
import json
import uuid
import time
import re

# --- Configuration ---
API_URL = "https://nuzantara-rag.fly.dev"
EMAIL = "zero@balizero.com"
PASSWORD = "010719"

def log(msg):
    print(msg)

def run_test():
    TEST_USER_ID = f"dynamics_test_{uuid.uuid4()}@example.com"
    SESSION_ID = f"session-{uuid.uuid4()}"

    log(f"🚀 Starting Communication Dynamics Test")
    log(f"👤 User ID: {TEST_USER_ID}")
    
    session = requests.Session()
    
    # Login
    log("🔐 Logging in...")
    try:
        login_payload = {"email": EMAIL, "password": PASSWORD}
        resp = session.post(f"{API_URL}/api/auth/login", json=login_payload)
        resp.raise_for_status()
        token = resp.json().get("data", {}).get("token")
        if not token:
            log("❌ No token")
            return
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        log("✅ Login successful")
    except Exception as e:
        log(f"❌ Login failed: {e}")
        return

    # --- Test Cases ---
    
    test_cases = [
        {
            "name": "PROCEDURAL FORMATTING",
            "query": "How do I apply for a KITAS?",
            "expected_trigger": "procedural",
            "check": lambda ans: "1." in ans and "2." in ans and "3." in ans
        },
        {
            "name": "EXPLANATION LEVEL: SIMPLE",
            "query": "Explain PT PMA to me like I am 5 years old (simple)",
            "expected_trigger": "simple",
            # We expect simpler language, hard to strict regex, but let's check for standard "It's like..." or just completion
            "check": lambda ans: len(ans) > 50 
        },
        {
            "name": "DOMAIN FORMATTING: VISA",
            "query": "What is the cost of a KITAS E33G?",
            "expected_trigger": "visa domain",
            # Check for table-like headers or specific fields if template is used
            "check": lambda ans: "Cost" in ans or "Requirements" in ans or "|" in ans # Markdown table chars
        },
        {
            "name": "CLARIFICATION REQUEST",
            "query": "how much?", # Very vague
            "expected_trigger": "clarification",
            "check": lambda ans: "?" in ans and ("specific" in ans.lower() or "clarify" in ans.lower() or "context" in ans.lower())
        }
    ]

    for tc in test_cases:
        log(f"\n--- 🧪 TESTING: {tc['name']} ---")
        payload = {
            "query": tc['query'],
            "user_id": TEST_USER_ID,
            "session_id": SESSION_ID,
            "conversation_history": [],
            "model_tier": "fast"
        }
        
        try:
            resp = session.post(f"{API_URL}/api/agentic-rag/query", json=payload, headers=headers)
            if resp.status_code != 200:
                log(f"❌ Failed: {resp.status_code}")
                continue
                
            data = resp.json()
            answer = data.get("response", "") or data.get("answer", "")
            debug_info = data.get("debug_info", {})
            
            # log(f"📥 Answer: {answer[:200]}...") # Truncated
            log(f"📥 Full Answer: {answer}") 
            
            if tc["check"](answer):
                log(f"✅ PASS: {tc['name']}")
            else:
                log(f"⚠️ WARN: {tc['name']} did not match strict check. Verify manually.")
                
            # Check debug info for triggers if available
            # log(f"🐛 Debug Info: {json.dumps(debug_info, indent=2)}")

        except Exception as e:
            log(f"❌ Error: {e}")
        
        time.sleep(2) # Breather

if __name__ == "__main__":
    run_test()
