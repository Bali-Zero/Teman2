import os
import requests
import urllib3
from dotenv import load_dotenv
from collections import Counter
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HEADERS = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

TARGETS = ["legal_unified", "visa_oracle", "tax_genius", "kbli_unified"]

# Keep repo root clean: generated reports belong in docs/.
OUTPUT_FILE = "docs/reports/PROJECT_DATA_INVENTORY.md"


def get_top_keywords(texts, n=10):
    # Simple heuristic: words > 4 chars, frequent
    words = []
    for t in texts:
        # Remove punctuation and lowercase
        clean = re.sub(r"[^\w\s]", "", t.lower())
        words.extend([w for w in clean.split() if len(w) > 4])

    # Filter common stop words (Indonesian/English mix)
    stop_words = {
        "yang",
        "dengan",
        "untuk",
        "dalam",
        "tidak",
        "adalah",
        "bahwa",
        "this",
        "that",
        "with",
        "from",
        "which",
    }
    words = [w for w in words if w not in stop_words]

    return [w[0] for w in Counter(words).most_common(n)]


def analyze_and_extract(name, file_handle):
    print(f"Processing {name}...")

    # 1. Get Info
    try:
        res = requests.get(
            f"{QDRANT_URL}/collections/{name}", headers=HEADERS, verify=False
        )
        info = res.json()["result"]
        count = info.get("points_count", 0)
        vector_size = (
            info.get("config", {})
            .get("params", {})
            .get("vectors", {})
            .get("size", "Unknown")
        )
        distance = (
            info.get("config", {})
            .get("params", {})
            .get("vectors", {})
            .get("distance", "Unknown")
        )
    except:
        count = 0
        vector_size = "Err"
        distance = "Err"

    file_handle.write(f"## 📂 COLLECTION: `{name}`\n\n")
    file_handle.write("### 📊 Technical Specs\n")
    file_handle.write(f"- **Total Documents:** {count}\n")
    file_handle.write(f"- **Vector Size:** {vector_size}\n")
    file_handle.write(f"- **Distance Metric:** {distance}\n\n")

    if count == 0:
        file_handle.write("> ⚠️ Collection is Empty.\n\n")
        return

    # 2. Fetch Candidates (Fetch 100, pick best 30)
    try:
        payload = {"limit": 100, "with_payload": True}
        res = requests.post(
            f"{QDRANT_URL}/collections/{name}/points/scroll",
            headers=HEADERS,
            json=payload,
            verify=False,
        )
        points = res.json()["result"]["points"]

        # Filter for "Excellent" chunks (Length > 100 chars)
        candidates = [
            p for p in points if len(p.get("payload", {}).get("text", "") or "") > 100
        ]

        # If not enough long ones, take what we have
        if len(candidates) < 30:
            candidates = points[:30]
        else:
            candidates = candidates[:30]

        # Extract Topics
        all_texts = [p.get("payload", {}).get("text", "") for p in candidates]
        topics = get_top_keywords(all_texts)

        # Extract Metadata Keys
        meta_keys = set()
        for p in candidates:
            meta_keys.update(p.get("payload", {}).get("metadata", {}).keys())

        file_handle.write("### 🧠 Semantic Analysis\n")
        file_handle.write(f"- **Detected Topics (Keywords):** {', '.join(topics)}\n")
        file_handle.write(f"- **Metadata Fields:** {', '.join(meta_keys)}\n")
        file_handle.write(
            f"- **Content Type:** {'Structured/Curated' if 'visa' in name or 'tax' in name else 'Raw Legal Text'}\n\n"
        )

        file_handle.write("### 💎 Top 30 High-Quality Chunks\n")
        for i, p in enumerate(candidates):
            text = p.get("payload", {}).get("text", "") or p.get("payload", {}).get(
                "content", ""
            )
            meta = p.get("payload", {}).get("metadata", {})

            # Clean text for display (remove excessive newlines)
            clean_text = text.strip().replace("\n\n", "\n")

            file_handle.write(f"#### Chunk {i + 1}\n")
            file_handle.write(f"**ID:** `{p['id']}`\n")
            file_handle.write(
                f"**Source:** {meta.get('source', 'Unknown')} | **Page:** {meta.get('page', 'N/A')}\n"
            )
            file_handle.write(f"```text\n{clean_text}\n```\n\n")

        file_handle.write("---\n\n")

    except Exception as e:
        file_handle.write(f"> ❌ Error extracting data: {e}\n\n")


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# 📑 Nuzantara Project: Data Inventory & Quality Report\n")
        f.write("Generated automatically from Qdrant Live Database.\n\n")

        for t in TARGETS:
            analyze_and_extract(t, f)

    print(f"✅ Report generated: {OUTPUT_FILE}")
