import sys
import os
import json
import time
import subprocess
import requests
import signal

# Configuration
BACKEND_DIR = "apps/backend-rag"
HOST = "127.0.0.1"
PORT = 8081 # Use different port to avoid conflict if something else is running
BASE_URL = f"http://{HOST}:{PORT}"
QUERY_URL = f"{BASE_URL}/api/agentic-rag/query"
HEALTH_URL = f"{BASE_URL}/health"
DB_URL = "postgresql://antonellosiano@localhost:5432/nuzantara_dev"

def start_server():
    print("Starting backend server for Identity Awareness Test...")
    env = os.environ.copy()
    
    # Set PYTHONPATH
    backend_src_path = os.path.abspath(os.path.join(BACKEND_DIR, "backend"))
    env["PYTHONPATH"] = backend_src_path
    
    # Set DATABASE_URL
    env["DATABASE_URL"] = DB_URL
    
    # Set API_KEYS for bypass (the service splits by comma)
    env["API_KEYS"] = "admin-test-key,user-test-key"
    env["API_AUTH_ENABLED"] = "true" 
    
    # Enable debug logs for personality
    env["LOG_LEVEL"] = "INFO"
    
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "app.main_cloud:app", 
        "--host", HOST,
        "--port", str(PORT)
    ]
    
    process = subprocess.Popen(
        cmd,
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return process

def wait_for_server(process):
    print("Waiting for server to be ready...")
    retries = 30
    for i in range(retries):
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"Server exited prematurely with code {process.returncode}")
            print("STDERR:", stderr)
            return False
            
        try:
            response = requests.get(HEALTH_URL)
            if response.status_code == 200:
                print("Server is ready!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        
        time.sleep(2) # RAG initialization takes longer
        print(f"Waiting... ({i+1}/{retries})")
    
    return False

def test_identity_awareness(user_email, user_name, test_query):
    print(f"\n--- Testing Awareness for: {user_name} ({user_email}) ---")
    
    payload = {
        "query": test_query,
        "user_id": user_email, # Pass email as user_id to trigger DB lookup in agentic_rag.py
        "conversation_history": []
    }
    
    headers = {
        "X-API-Key": "admin-test-key",
        "Content-Type": "application/json"
    }
    
    try:
        start_time = time.time()
        response = requests.post(QUERY_URL, json=payload, headers=headers, timeout=60)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get("answer", "")
            print(f"✅ Response received in {elapsed:.2f}s")
            print(f"🤖 ZANTARA: {answer[:300]}...") # Print first 300 chars
            
            # Check for name or role references
            lower_answer = answer.lower()
            if user_name.lower() in lower_answer:
                print(f"🎯 IDENTITY MATCH: Zantara recognized the name '{user_name}'!")
            else:
                print(f"⚠️ NO NAME MATCH: Zantara did not explicitly use the name.")
                
            return answer
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None

def main():
    server_process = start_server()
    
    try:
        if wait_for_server(server_process):
            # Test 1: Zero (Founder)
            # Tono previsto: Diretto, efficiente, "sacred semar energy"
            test_identity_awareness(
                "zero@balizero.com", 
                "Zero", 
                "Ciao Zantara, chi sono io e qual è il mio ruolo qui?"
            )
            
            # Test 2: Veronika (Tax Manager)
            # Tono previsto: Preciso, metodico, formale
            test_identity_awareness(
                "tax@balizero.com", 
                "Veronika", 
                "Zantara, chi sono io? Ricordami le mie responsabilità."
            )
            
            # Test 3: Zainal (CEO)
            test_identity_awareness(
                "zainal@balizero.com", 
                "Zainal", 
                "Buongiorno Zantara, chi sono io?"
            )
            
        else:
            print("Server failed to start properly.")
    finally:
        print("\nStopping server...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")

if __name__ == "__main__":
    main()
