import os
import time

import requests

URL = "http://localhost:8000/api/agentic-rag/stream"

# SECURITY: Load API key from environment
API_KEY = os.getenv("ZANTARA_API_KEY")
if not API_KEY:
    raise ValueError("ZANTARA_API_KEY environment variable not set")

payload = {
    "query": "Hello, are you there?",
    "user_id": "anonymous",
    "conversation_history": [],
    "model": "gpt-4o",
}

print(f"Connecting to {URL}...")
start_time = time.time()

try:
    headers = {"X-API-Key": API_KEY}
    with requests.post(URL, json=payload, headers=headers, stream=True, timeout=60) as response:
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error Content: {response.text}")
            exit(1)

        print("Connected! Waiting for events...")
        count = 0
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode("utf-8")
                print(f"Received: {decoded_line[:100]}...")  # Print first 100 chars
                count += 1
                if count >= 3:
                    print("Received enough events, working!")
                    break

        elapsed = time.time() - start_time
        print(f"Finished in {elapsed:.2f}s")

except Exception as e:
    print(f"❌ Failed: {e}")
