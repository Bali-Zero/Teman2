import sys
import os
import json
import time
import subprocess
import requests
import signal

# Configuration
BACKEND_DIR = "apps/backend-rag"
DATA_FILE = os.path.join(BACKEND_DIR, "backend/data/team_members.json")
HOST = "127.0.0.1"
PORT = 8080
BASE_URL = f"http://{HOST}:{PORT}"
LOGIN_URL = f"{BASE_URL}/api/auth/team/login"
HEALTH_URL = f"{BASE_URL}/health"

def start_server():
    print("Starting backend server...")
    env = os.environ.copy()
    
    # Set PYTHONPATH to include the 'backend' directory so 'app' and 'services' are importable
    backend_src_path = os.path.abspath(os.path.join(BACKEND_DIR, "backend"))
    env["PYTHONPATH"] = backend_src_path
    
    # Set DATABASE_URL to local system DB
    env["DATABASE_URL"] = "postgresql://antonellosiano@localhost:5432/nuzantara_dev"
    
    print(f"CWD: {BACKEND_DIR}")
    print(f"PYTHONPATH: {env['PYTHONPATH']}")
    
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
        stderr=subprocess.PIPE
    )
    return process

def wait_for_server(process):
    print("Waiting for server to be ready...")
    retries = 30
    for i in range(retries):
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"Server exited prematurely with code {process.returncode}")
            print("STDOUT:", stdout.decode())
            print("STDERR:", stderr.decode())
            return False
            
        try:
            response = requests.get(HEALTH_URL)
            if response.status_code == 200:
                print("Server is ready!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        
        time.sleep(1)
        print(f"Waiting... ({i+1}/{retries})")
    
    return False

def test_logins():
    print(f"Loading team members from {DATA_FILE}")
    try:
        with open(DATA_FILE, 'r') as f:
            team_members = json.load(f)
    except Exception as e:
        print(f"Failed to load team members: {e}")
        return

    print(f"Testing login for {len(team_members)} members...")
    
    results = []
    
    for member in team_members:
        email = member.get('email')
        pin = member.get('pin')
        name = member.get('name')
        
        print(f"Testing login for: {name} ({email})")
        
        try:
            payload = {
                "email": email,
                "pin": pin
            }
            
            response = requests.post(LOGIN_URL, json=payload)
            
            if response.status_code == 200:
                print(f"✅ SUCCESS: {name}")
                results.append({"name": name, "status": "SUCCESS"})
            else:
                print(f"❌ FAILED: {name} - Status: {response.status_code}")
                print(f"   Response: {response.text}")
                results.append({"name": name, "status": "FAILED", "code": response.status_code})
                
        except Exception as e:
            print(f"❌ ERROR: {name} - {e}")
            results.append({"name": name, "status": "ERROR", "error": str(e)})
            
    return results

def main():
    server_process = start_server()
    
    try:
        if wait_for_server(server_process):
            test_logins()
        else:
            print("Server failed to start properly.")
    finally:
        print("Stopping server...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")

if __name__ == "__main__":
    main()
