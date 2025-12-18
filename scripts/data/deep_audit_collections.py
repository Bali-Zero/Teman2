import os
import requests
import urllib3
import json
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HEADERS = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

TARGETS = [
    "legal_unified",
    "visa_oracle",
    "tax_genius",
    "kbli_unified",
    "property_unified",
]


def audit_collection(name):
    print(f"\n🕵️‍♂️ Deep Audit: {name.upper()}")
    output_file = f"audit_{name}.txt"

    try:
        # Get Count
        res = requests.get(
            f"{QDRANT_URL}/collections/{name}", headers=HEADERS, verify=False
        )
        count = res.json()["result"].get("points_count", 0)

        if count == 0:
            print("   ❌ Empty Collection")
            return

        # Fetch 100 points (using scroll with random offset if possible, but scroll is sequential)
        # We'll just fetch the first 100 for now to check structure.
        # Ideally we'd pick random, but Qdrant random access is tricky without IDs.
        # We can try to fetch 100 points starting from a random offset if we knew UUIDs.
        # Let's just fetch the first 100.

        payload = {"limit": 100, "with_payload": True}

        res = requests.post(
            f"{QDRANT_URL}/collections/{name}/points/scroll",
            headers=HEADERS,
            json=payload,
            verify=False,
        )
        points = res.json()["result"]["points"]

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"AUDIT REPORT FOR {name}\n")
            f.write(f"Total Docs: {count}\n")
            f.write("=" * 50 + "\n\n")

            valid_text_count = 0
            avg_len = 0

            for i, p in enumerate(points):
                payload_data = p.get("payload", {})
                text = (
                    payload_data.get("text", "")
                    or payload_data.get("content", "")
                    or str(payload_data)
                )
                metadata = payload_data.get("metadata", {})

                f.write(f"--- CHUNK {i + 1} ---\n")
                f.write(f"ID: {p['id']}\n")
                f.write(f"Metadata: {json.dumps(metadata, ensure_ascii=False)}\n")
                f.write(f"Content:\n{text}\n")
                f.write("\n")

                if len(text) > 50:
                    valid_text_count += 1
                avg_len += len(text)

            if points:
                avg_len /= len(points)

            print(f"   ✅ Extracted {len(points)} chunks to {output_file}")
            print("   📊 Quality Stats:")
            print(f"      - Avg Length: {avg_len:.0f} chars")
            print(f"      - Valid/Long Chunks: {valid_text_count}/100")

            # Peek at the first one
            if points:
                first_text = (
                    points[0]
                    .get("payload", {})
                    .get("text", "")[:100]
                    .replace("\n", " ")
                )
                print(f"      - Sample: {first_text}...")

    except Exception as e:
        print(f"   ⚠️ Error: {e}")


if __name__ == "__main__":
    for t in TARGETS:
        audit_collection(t)
