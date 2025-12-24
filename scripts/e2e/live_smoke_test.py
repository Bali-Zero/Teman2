import json
import time
import sys
import urllib.request
import urllib.error

BASE_URL = "https://nuzantara-rag.fly.dev"
TOKEN = None

def run_test(name, url, method="GET", data=None):
    global TOKEN
    print(f"\n🔹 Testing: {name}")
    print(f"   URL: {url}")
    
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    
    if data:
        data_bytes = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    else:
        req = urllib.request.Request(url, headers=headers, method=method)
        
    start_time = time.time()
    try:
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            duration = time.time() - start_time
            
            print(f"   ✅ Status: {status}")
            print(f"   ⏱️  Time: {duration:.2f}s")
            
            try:
                json_body = json.loads(body)
                print(f"   📄 Response (JSON preview): {str(json_body)[:200]}...")
                return True, json_body
            except:
                print(f"   📄 Response: {body[:200]}...")
                return True, body
                
    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP Error: {e.code} - {e.reason}")
        try:
            body = e.read().decode('utf-8')
            print(f"   📄 Body: {body[:500]}")
        except:
            pass
        return False, None
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False, None

def main():
    global TOKEN
    print("🚀 STARTED: Complex Live Test on Nuzantara Production")
    print("===================================================")
    
    # 1. Health Check
    success, _ = run_test("Backend Health", f"{BASE_URL}/health")
    if not success:
        print("💥 Critical: Backend is down!")
        sys.exit(1)

    # 2. Login
    print("\n🔐 Authenticating...")
    login_payload = {
        "email": "zero@balizero.com",
        "pin": "010719"
    }
    success, resp = run_test("Login", f"{BASE_URL}/api/auth/login", "POST", login_payload)
    if success and resp and resp.get("success"):
        # The token is in resp["data"]["token"] based on previous run
        TOKEN = resp.get("data", {}).get("token")
        if TOKEN:
            print("   ✅ Authentication Successful")
        else:
            print("   ❌ Authentication Failed: Token missing in response")
            sys.exit(1)
    else:
        print("   ❌ Authentication Failed: Response unsuccessful")
        sys.exit(1)

    # 3. Agentic RAG Query (Simple)
    payload_simple = {
        "query": "What is the capital of Indonesia?",
        "user_id": "zero@balizero.com",
        "session_id": "test_session_live_001"
    }
    success, resp = run_test("Simple RAG Query", f"{BASE_URL}/api/agentic-rag/query", "POST", payload_simple)
    
    if success and resp:
        print(f"   🔍 Answer: {resp.get('answer')}")
        print(f"   📚 Sources: {len(resp.get('sources', []))}")

    # 4. Cell-Giant Complex Query (Business)
    payload_complex = {
        "query": "Quali sono i requisiti minimi di capitale per una PT PMA in Indonesia nel 2025?",
        "user_id": "zero@balizero.com",
        "session_id": "test_session_live_002"
    }
    success, resp = run_test("Cell-Giant Pipeline (PT PMA)", f"{BASE_URL}/api/agentic-rag/query/cell-giant", "POST", payload_complex)

    if success and resp:
        print(f"   🧠 Route Used: {resp.get('route_used')}")
        print(f"   🔍 Answer: {resp.get('answer')}")
        
    print("\n===================================================")
    print("✅ Live Test Sequence Completed")

if __name__ == "__main__":
    main()
