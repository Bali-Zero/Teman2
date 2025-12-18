import io

import requests

# Create a dummy file that looks like a webm but contains random text
# This is expected to fail at OpenAI's side, but it should REACH the backend service.
# If we get a 500/400 from OpenAI, the routing is FIXED.
# If we get a 404, the routing is still BROKEN.

url = "http://localhost:8000/api/audio/transcribe"
files = {"file": ("test.webm", io.BytesIO(b"fake audio content"), "audio/webm")}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, files=files)

    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 404:
        print("❌ FAILED: 404 Not Found. Route is still missing.")
    elif response.status_code == 200:
        print("✅ SUCCESS: Transcription worked (unexpected for fake audio).")
    else:
        # 422, 500, 400 are all "Success" in terms of routing/connectivity
        print(
            f"✅ CONNECTIVITY SUCCESS: Reached backend service (Error expected for fake audio: {response.status_code})"
        )

except Exception as e:
    print(f"❌ CONNECTION FAILED: {e}")
