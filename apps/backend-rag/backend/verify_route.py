import io

import requests

# Create a dummy file that looks like a webm but contains random text
# This is expected to fail at OpenAI's side, but it should REACH the backend service.
# If we get a 500/400 from OpenAI, the routing is FIXED.
# If we get a 404, the routing is still BROKEN.

url = "http://localhost:8000/api/audio/transcribe"
files = {"file": ("test.webm", io.BytesIO(b"fake audio content"), "audio/webm")}

try:
    response = requests.post(url, files=files)


    if response.status_code == 404 or response.status_code == 200:
        pass
    else:
        # 422, 500, 400 are all "Success" in terms of routing/connectivity
        pass

except Exception:
    pass
