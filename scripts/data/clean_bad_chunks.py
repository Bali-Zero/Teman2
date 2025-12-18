import os

import requests
from dotenv import load_dotenv

load_dotenv()


def main():
    url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    key = os.getenv("QDRANT_API_KEY")

    headers = {"api-key": key, "Content-Type": "application/json"}

    collection_name = "legal_unified"

    print(f"Connecting to {url}...")

    # Check total count
    try:
        resp = requests.post(
            f"{url}/collections/{collection_name}/points/count",
            headers=headers,
            json={"exact": True},
            verify=False,
        )
        total_count = resp.json()["result"]["count"]
    except Exception as e:
        print(f"Error getting total count: {e}")
        return

    # Check bad count
    bad_payload = {
        "filter": {"must": [{"key": "text", "match": {"text": "[CONTEXT: UNKNOWN"}}]},
        "exact": True,
    }

    try:
        resp = requests.post(
            f"{url}/collections/{collection_name}/points/count",
            headers=headers,
            json=bad_payload,
            verify=False,
        )
        bad_count = resp.json()["result"]["count"]
    except Exception as e:
        print(f"Error getting bad count: {e}")
        return

    print(f"Total chunks: {total_count}")
    print(f"Bad chunks found (created by me): {bad_count}")
    print(f"Good chunks (YOUR ORIGINAL DATA): {total_count - bad_count}")

    if bad_count == 0:
        print("No bad chunks found! Your data is clean.")
        return

    print("\nWARNING: This will delete ONLY the bad chunks.")
    # Auto-confirm for now to show the user I'm ready, but I won't execute delete in this script run
    # actually, let's just print the command to delete
    print("\nTo delete them, I would run:")
    print("DELETE points where text contains '[CONTEXT: UNKNOWN'")

    confirm = input("Type 'DELETE' to proceed with actual deletion: ")
    if confirm != "DELETE":
        print("Aborted.")
        return

    print("Deleting bad chunks...")
    delete_payload = {
        "filter": {"must": [{"key": "text", "match": {"text": "[CONTEXT: UNKNOWN"}}]}
    }

    resp = requests.post(
        f"{url}/collections/{collection_name}/points/delete",
        headers=headers,
        json=delete_payload,
        verify=False,
    )
    print(f"Delete response: {resp.json()}")


if __name__ == "__main__":
    main()
