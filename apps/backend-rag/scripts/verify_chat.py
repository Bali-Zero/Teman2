import requests

URL_DIRECT = "http://localhost:8000/agentic-rag/stream"
URL_DIRECT_API = "http://localhost:8000/api/agentic-rag/stream"

payload = {"message": "Hello", "conversation_history": [], "model": "gpt-4o"}

print(f"Testing {URL_DIRECT}...")
try:
    # Use stream=True and timeout to detect connection
    resp = requests.post(URL_DIRECT, json=payload, stream=True, timeout=2)
    print(f"Response Status: {resp.status_code}")
    if resp.status_code == 404:
        print("❌ 404 Not Found")
    else:
        print("✅ Endpoint Exists (Connection successful)")
        resp.close()
except requests.exceptions.ReadTimeout:
    print("✅ Endpoint Exists (Read Timeout means server accepted connection)")
except Exception as e:
    print(f"❌ Failed: {e}")

print(f"\nTesting {URL_DIRECT_API}...")
try:
    resp = requests.post(URL_DIRECT_API, json=payload, stream=True, timeout=2)
    print(f"Response Status: {resp.status_code}")
    if resp.status_code == 404:
        print("❌ 404 Not Found")
    else:
        print("✅ Endpoint Exists (Connection successful)")
        resp.close()
except requests.exceptions.ReadTimeout:
    print("✅ Endpoint Exists (Read Timeout means server accepted connection)")
except Exception as e:
    print(f"❌ Failed: {e}")
