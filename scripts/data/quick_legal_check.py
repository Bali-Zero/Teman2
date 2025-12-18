import os
import requests
import urllib3
from openai import OpenAI
from dotenv import load_dotenv

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not QDRANT_URL or not QDRANT_API_KEY or not OPENAI_API_KEY:
    print("❌ Error: Missing environment variables. Check your .env file.")
    exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)


def get_embedding(text):
    try:
        response = client.embeddings.create(input=text, model="text-embedding-3-small")
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ OpenAI Error: {e}")
        return None


def search_qdrant(query):
    vector = get_embedding(query)
    if not vector:
        return None

    payload = {"vector": vector, "limit": 5, "with_payload": True}
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    try:
        response = requests.post(
            f"{QDRANT_URL}/collections/legal_unified/points/search",
            headers=headers,
            json=payload,
            verify=False,  # Bypass SSL verification
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Qdrant Error: {e}")
        return None


if __name__ == "__main__":
    print("\n🦖 NUZANTARA LEGAL SEARCH TEST")
    print("==============================")

    while True:
        query = input("\n🔎 Enter legal question (or 'q' to quit): ")
        if query.lower() in ["q", "quit", "exit"]:
            break

        print(f"   Searching for: '{query}'...")
        results = search_qdrant(query)

        if results and "result" in results:
            print("\n--- TOP RESULTS ---\n")
            for i, hit in enumerate(results["result"]):
                score = hit["score"]
                payload = hit.get("payload", {})
                text = payload.get("text", "No text")
                metadata = payload.get("metadata", {})
                source = metadata.get("source", "Unknown Source")

                print(f"[{i + 1}] Score: {score:.4f} | 📄 {source}")
                clean_text = text[:300].replace("\n", " ")
                print(f"    {clean_text}...")
                print("-" * 50)
        else:
            print("❌ No results found or error occurred.")
