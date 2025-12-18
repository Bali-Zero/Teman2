import os
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HEADERS = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

TARGETS = [
    "kbli_unified",
    "tax_genius",
    "visa_oracle",
    "property_unified",
    "bali_zero_pricing",
]


def analyze(name):
    print(f"\n🔍 {name.upper()}")
    try:
        # Count
        res = requests.get(
            f"{QDRANT_URL}/collections/{name}", headers=HEADERS, verify=False
        )
        count = res.json()["result"].get("points_count", 0)
        print(f"   📊 Count: {count}")

        # Sample
        if count > 0:
            payload = {"limit": 1, "with_payload": True}
            res = requests.post(
                f"{QDRANT_URL}/collections/{name}/points/scroll",
                headers=HEADERS,
                json=payload,
                verify=False,
            )
            points = res.json()["result"]["points"]
            if points:
                p = points[0]
                text = p.get("payload", {}).get("text", "") or p.get("payload", {}).get(
                    "content", ""
                )
                print(f"   📝 Sample: {text[:100]}...")
        else:
            print("   ❌ EMPTY")

    except Exception as e:
        print(f"   ⚠️ Error: {e}")


if __name__ == "__main__":
    for t in TARGETS:
        analyze(t)
