import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()


def main():
    url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    key = os.getenv("QDRANT_API_KEY")

    headers = {"api-key": key, "Content-Type": "application/json"}

    print(f"Connecting to {url}...")

    resp = requests.post(
        f"{url}/collections/kbli_unified/points/scroll",
        headers=headers,
        json={"limit": 3, "with_payload": True},
        verify=False,
    )

    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2))
    else:
        print(f"Error: {resp.text}")


if __name__ == "__main__":
    main()
