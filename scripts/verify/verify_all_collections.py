import os

import requests
from dotenv import load_dotenv

load_dotenv()


def main():
    url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    key = os.getenv("QDRANT_API_KEY")

    headers = {"api-key": key, "Content-Type": "application/json"}

    collections = [
        "legal_unified",
        "tax_genius",
        "visa_oracle",
        "kbli_unified",
        "property_unified",
        "litigation_oracle",
    ]

    print(f"Connecting to {url}...\n")

    total_good = 0
    total_bad = 0

    for col in collections:
        print(f"=== Checking Collection: {col} ===")
        try:
            # Get random points (using scroll with random offset if possible, or just scroll)
            # Since we can't easily random offset, we'll just take the first 10 for speed,
            # or try to filter by something common if needed. Let's just scroll.
            resp = requests.post(
                f"{url}/collections/{col}/points/scroll",
                headers=headers,
                json={"limit": 10, "with_payload": True},
                verify=False,
            )

            if resp.status_code != 200:
                print(f"Error accessing {col}: {resp.text}")
                continue

            points = resp.json()["result"]["points"]
            if not points:
                print(f"Collection {col} is empty.\n")
                continue

            print(f"Found {len(points)} sample points. Analyzing content:\n")

            for p in points:
                text = p["payload"].get("text", "")
                is_bad = "[CONTEXT: UNKNOWN" in text
                status = "❌ BAD" if is_bad else "✅ GOOD"

                if is_bad:
                    total_bad += 1
                else:
                    total_good += 1

                preview = text[:150].replace("\n", " ")
                print(f"{status} ID: {p['id']}")
                print(f"   Content: {preview}...")
                print("-" * 50)

        except Exception as e:
            print(f"Exception checking {col}: {e}")
        print("\n")

    print("=== SUMMARY ===")
    print(f"Total Verified: {total_good + total_bad}")
    print(f"✅ Good: {total_good}")
    print(f"❌ Bad: {total_bad}")


if __name__ == "__main__":
    main()
