import os
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

headers = {"api-key": QDRANT_API_KEY}

try:
    res = requests.get(f"{QDRANT_URL}/collections", headers=headers, verify=False)
    collections = res.json()["result"]["collections"]
    print(f"Found {len(collections)} collections:")
    for c in collections:
        print(f" - {c['name']}")
except Exception as e:
    print(e)
