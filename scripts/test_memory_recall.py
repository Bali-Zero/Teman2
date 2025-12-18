import requests
import json
import sys
import uuid
import time

# Configuration
API_URL = "https://nuzantara-rag.fly.dev"
EMAIL = "zero@balizero.com"
PASSWORD = "010719"  # From memory

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def log(msg, color=RESET):
    print(f"{color}{msg}{RESET}")

def run_test():
    session = requests.Session()
    session_id = f"test-session-{uuid.uuid4()}"
    
    TEST_USER_ID = f"test_user_{uuid.uuid4()}@example.com"
    log(f"🚀 Starting Memory Recall Test (Session: {session_id})")
    log(f"👤 Using Test User ID: {TEST_USER_ID}")

    # 1. Login
    log("🔐 Logging in...")
    try:
        login_payload = {"email": EMAIL, "password": PASSWORD}
        
        # Based on verify_memory_api.py, it expects token in response.
        resp = session.post(f"{API_URL}/api/auth/login", json=login_payload)
        if resp.status_code != 200:
            log(f"❌ Login failed: {resp.text}", RED)
            return False
            
        token_data = resp.json().get("data", {})
        token = token_data.get("token")
        if not token:
             log(f"❌ No access token in login response: {resp.text}", RED)
             return False
             
        headers = {"Authorization": f"Bearer {token}"}
        log("✅ Login successful")
        
    except Exception as e:
        log(f"❌ Login error: {e}", RED)
        return False

    # 2. Send Message 1: "My secret word is BANANA"
    query1 = "My secret word is BANANA. Please remember it."
    log(f"📤 Sending Query 1: '{query1}'")
    
    try:
        # We use the agentic-rag query endpoint
        payload = {
            "query": query1,
            "user_id": TEST_USER_ID,
            "session_id": session_id
        }
        resp = session.post(f"{API_URL}/api/agentic-rag/query", json=payload, headers=headers)
        if resp.status_code != 200:
            log(f"❌ Query 1 failed: {resp.status_code} {resp.text}", RED)
            return False
            
        ans1 = resp.json().get("answer", "")
        ans1 = resp.json().get("answer", "")
        debug1 = resp.json().get("debug_info")
        log(f"📥 Answer 1: {ans1}")
        if debug1:
            log(f"🐛 Debug 1: {json.dumps(debug1, indent=2)}")
        
    except Exception as e:
        log(f"❌ Query 1 Exception: {e}", RED)
        return False

    # 3. Save Conversation (User Msg + Assistant Ans)
    # The system EXPECTS the frontend to save the conversation.
    log("💾 Saving conversation to DB...")
    messages_to_save = [
        {"role": "user", "content": query1},
        {"role": "assistant", "content": ans1}
    ]
    
    try:
        save_payload = {
            "messages": messages_to_save,
            "session_id": session_id,
            "user_id": TEST_USER_ID, # Ignored by backend but kept for clarity
            "metadata": {"test": "true"}
        }
        resp = session.post(f"{API_URL}/api/bali-zero/conversations/save", json=save_payload, headers=headers)
        if resp.status_code != 200 and resp.status_code != 201:
            log(f"❌ Save failed: {resp.status_code} {resp.text}", RED)
            return False
        
        # Check if actually saved
        save_data = resp.json()
        if not save_data.get("success"):
            log(f"❌ Save reported failure: {save_data}", RED)
            return False
            
        log("✅ Conversation saved.")
        
    except Exception as e:
        log(f"❌ Save Exception: {e}", RED)
        return False

    # 3.5 Verify Save (Fetch by ID)
    conversation_id = save_data.get("conversation_id")
    if conversation_id:
        log(f"🔍 Verifying save for Conversation ID: {conversation_id}...")
        try:
            resp = session.get(f"{API_URL}/api/bali-zero/conversations/{conversation_id}", headers=headers)
            if resp.status_code == 200:
                verify_msgs = resp.json().get("messages", [])
                log(f"✅ Verified save. DB contains {len(verify_msgs)} messages.")
                # Optional: Print messages to be sure
                # log(f"DB Content: {json.dumps(verify_msgs, indent=2)}")
            else:
                log(f"❌ Failed to verify save: {resp.status_code} {resp.text}", RED)
        except Exception as e:
            log(f"❌ Verification Exception: {e}", RED)
    else:
        log("⚠️ No conversation_id returned, skipping verification.")

    # 4. Send Query 2: "What is my secret word?"
    # We pass session_id so it fetches history from DB.
    
    time.sleep(1) # Give DB a moment
    query2 = "What is my secret word?"
    log(f"📤 Sending Query 2: '{query2}'")
    
    try:
        payload = {
            "query": query2,
            "user_id": TEST_USER_ID,
            "session_id": session_id
        }
        resp = session.post(f"{API_URL}/api/agentic-rag/query", json=payload, headers=headers)
        if resp.status_code != 200:
            log(f"❌ Query 2 failed: {resp.status_code} {resp.text}", RED)
            # If 500, print traceback if available
            try:
                err_detail = resp.json().get("detail", "")
                log(f"Error detail: {err_detail}", RED)
            except Exception:
                pass
            return False
            
        ans2 = resp.json().get("answer", "")
        ans2 = resp.json().get("answer", "")
        debug2 = resp.json().get("debug_info")
        log(f"📥 Answer 2: {ans2}")
        if debug2:
            log(f"🐛 Debug 2 History Len: {debug2.get('history_len')}")
            log(f"🐛 Debug 2 History Capture: {json.dumps(debug2.get('history_capture'), indent=2)}")
            log(f"🐛 Debug 2 Prompt Tail: {debug2.get('initial_prompt_tail')}")
        
        # 5. Verify
        if "BANANA" in ans2.upper():
            log("✅ SUCCESS: 'BANANA' found in response!", GREEN)
            return True
        else:
            log(f"❌ FAILURE: 'BANANA' NOT found in response. Got: {ans2}", RED)
            return False

    except Exception as e:
        log(f"❌ Query 2 Exception: {e}", RED)
        return False

if __name__ == "__main__":
    if run_test():
        sys.exit(0)
    else:
        sys.exit(1)
