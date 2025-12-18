import requests
import json
import sys

BASE_URL = "https://nuzantara-rag.fly.dev"
# BASE_URL = "http://localhost:8000" # For local testing if needed

EMAIL = "zero@balizero.com"
PASSWORD = "010719" # From memory

def test_api():
    print(f"🚀 Testing API at {BASE_URL}...")
    
    # 1. Health Check
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Health: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ Health check failed: {resp.text}")
            return
    except Exception as e:
        print(f"❌ Health check connection error: {e}")
        return

    # 2. Login
    print(f"🔐 Logging in as {EMAIL}...")
    try:
        # Check if auth endpoint uses form data or json
        # Based on FastAPI OAuth2PasswordRequestForm usually it's form data
        # But let's try JSON first or check code? 
        # Assuming standard /auth/login or similar.
        # Living Architecture says: /api/bali-zero/auth/login
        
        # Correct path from auth.py analysis: /api/auth/login
        login_url = f"{BASE_URL}/api/auth/login"
        # Try form data (username/password)
        data = {"username": EMAIL, "password": PASSWORD}
        # Note: auth.py uses Pydantic model for body, so it expects JSON, NOT form data (unless it's OAuth2PasswordRequestForm)
        # auth.py: class LoginRequest(BaseModel): email, pin/password
        # Endpoint: async def login(request: LoginRequest, ...):
        # So it expects JSON!
        
        login_data = {
            "email": EMAIL,
            "password": PASSWORD
        }
        
        print(f"📡 POST {login_url}")
        resp = requests.post(login_url, json=login_data)
        
        if resp.status_code != 200:
             print(f"❌ Login failed: {resp.status_code} {resp.text}")
             # Try /api/bali-zero/auth/login just in case 
             # ... no, let's stick to code analysis
             return

            
        response_json = resp.json()
        token_data = response_json.get("data", {})
        access_token = token_data.get("token")
        
        if not access_token:
            print(f"❌ No token in response: {response_json}")
            return
            
        print("✅ Login successful!")
        
    except Exception as e:
        print(f"❌ Login error: {e}")
        return

    # 3. Get History
    print("📜 Fetching History...")
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        history_url = f"{BASE_URL}/api/bali-zero/conversations/history"
        resp = requests.get(history_url, headers=headers)
        
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            history = resp.json()
            # print(json.dumps(history, indent=2))
            print(f"✅ History retrieved! Items: {len(history.get('history', [])) if isinstance(history, dict) else 'Unknown'}")
        else:
            print(f"❌ History failed: {resp.status_code} {resp.text}")
            
    except Exception as e:
        print(f"❌ History error: {e}")

if __name__ == "__main__":
    test_api()
