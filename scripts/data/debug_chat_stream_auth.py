import requests
import json

# Configuration
BASE_URL = "https://nuzantara-rag.fly.dev"
LOGIN_URL = f"{BASE_URL}/api/auth/team/login"
CHAT_STREAM_URL = f"{BASE_URL}/bali-zero/chat-stream"
EMAIL = "anton@balizero.com"
PIN = "538147"


def debug_auth():
    print(f"[-] Logging in to {LOGIN_URL}...")
    try:
        login_resp = requests.post(LOGIN_URL, json={"email": EMAIL, "pin": PIN})
        print(f"[-] Login Status: {login_resp.status_code}")

        if login_resp.status_code != 200:
            print(f"[!] Login failed: {login_resp.text}")
            return

        data = login_resp.json()
        # The frontend proxy expects 'token' in the response data
        # Let's see what we actually get
        print(f"[-] Login Response Keys: {data.keys()}")

        token = data.get("data", {}).get("token")
        if not token:
            # Try direct token key if structure is different
            token = data.get("token")

        if not token:
            print("[!] No token found in login response")
            print(f"[-] Full Response: {json.dumps(data, indent=2)}")
            return

        print(f"[-] Token received: {token[:15]}...")

        # Now simulate the chat stream request
        print(f"[-] Calling Chat Stream at {CHAT_STREAM_URL}...")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            # Proxy also sends X-API-Key, let's try without first, then with if needed
        }

        params = {"query": "Hello, testing auth", "stream": "true"}

        # Note: The backend expects GET for this endpoint according to the proxy code
        stream_resp = requests.get(
            CHAT_STREAM_URL, headers=headers, params=params, stream=True
        )

        print(f"[-] Stream Status: {stream_resp.status_code}")

        if stream_resp.status_code == 200:
            print("[-] Stream success! Reading first chunk...")
            for chunk in stream_resp.iter_content(chunk_size=1024):
                if chunk:
                    print(f"[-] Chunk: {chunk.decode('utf-8')[:100]}...")
                    break
        else:
            print(f"[!] Stream failed: {stream_resp.text}")

    except Exception as e:
        print(f"[!] Exception: {e}")


if __name__ == "__main__":
    debug_auth()
