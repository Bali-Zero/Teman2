#!/usr/bin/env python3
"""
Force Upload to Qdrant via REST API (Battering Ram Approach)
Uploads prepared payloads from ready_to_curl.json using curl subprocess.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
PAYLOAD_FILE = SCRIPT_DIR / "ready_to_curl.json"
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not QDRANT_API_KEY:
    print("❌ ERROR: QDRANT_API_KEY environment variable is required")
    print("   Set it with: export QDRANT_API_KEY=your_api_key")
    sys.exit(1)

BATCH_SIZE = 10
VECTOR_SIZE = 1536  # text-embedding-3-small dimensions


def create_collection(collection_name: str) -> bool:
    """Create collection if it doesn't exist."""
    url = f"{QDRANT_URL}/collections/{collection_name}"

    # Check if collection exists
    check_cmd = [
        "curl",
        "-X",
        "GET",
        url,
        "-H",
        f"api-key: {QDRANT_API_KEY}",
        "-s",
        "-S",
        "--max-time",
        "30",
    ]

    try:
        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and "error" not in result.stdout.lower():
            print(f"✅ Collection {collection_name} already exists")
            return True
    except:
        pass

    # Create collection
    payload = {"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(payload, tmp)
        tmp_path = tmp.name

    create_cmd = [
        "curl",
        "-X",
        "PUT",
        url,
        "-H",
        f"api-key: {QDRANT_API_KEY}",
        "-H",
        "Content-Type: application/json",
        "--data-binary",
        f"@{tmp_path}",
        "-w",
        "\nHTTP_CODE:%{http_code}",
        "-s",
        "-S",
        "--max-time",
        "30",
    ]

    try:
        result = subprocess.run(create_cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout

        if "HTTP_CODE:200" in output or "HTTP_CODE:201" in output:
            print(f"✅ Created collection {collection_name}")
            return True
        else:
            print(f"❌ Failed to create collection: {output}")
            return False
    except Exception as e:
        print(f"❌ Error creating collection: {e}")
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


def main():
    """Main upload function."""
    print("🚀 Force Upload to Qdrant")
    print("=" * 60)

    # Check if payload file exists
    if not PAYLOAD_FILE.exists():
        print(f"❌ Error: Payload file not found: {PAYLOAD_FILE}")
        print("   Run prepare_payloads.py first to generate ready_to_curl.json")
        sys.exit(1)

    # Load payload data
    with open(PAYLOAD_FILE) as f:
        data = json.load(f)

    collection = data["collection"]
    points = data["points"]
    total = len(points)

    print(f"Collection: {collection}")
    print(f"Total Points: {total}")
    print(f"Batch Size: {BATCH_SIZE}")
    print()

    # Create collection if it doesn't exist
    if not create_collection(collection):
        print("❌ Cannot proceed without collection")
        sys.exit(1)

    print()

    # Upload in batches
    success_count = 0
    failed_count = 0

    for i in range(0, total, BATCH_SIZE):
        batch = points[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        payload = {"points": batch}

        # Create temp JSON file for curl
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(payload, tmp)
            tmp_path = tmp.name

        # Upload via curl
        url = f"{QDRANT_URL}/collections/{collection}/points"
        cmd = [
            "curl",
            "-X",
            "PUT",
            url,
            "-H",
            f"api-key: {QDRANT_API_KEY}",
            "-H",
            "Content-Type: application/json",
            "--data-binary",
            f"@{tmp_path}",
            "-w",
            "\nHTTP_CODE:%{http_code}",
            "-s",
            "-S",
            "--max-time",
            "60",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            output = result.stdout

            if "HTTP_CODE:200" in output or "HTTP_CODE:201" in output:
                print(f"✅ Batch {batch_num}/{total_batches}: {len(batch)} points uploaded")
                success_count += len(batch)
            else:
                print(f"❌ Batch {batch_num}/{total_batches} failed")
                print(f"   Response: {output}")
                failed_count += len(batch)
        except subprocess.TimeoutExpired:
            print(f"❌ Batch {batch_num}/{total_batches} timed out")
            failed_count += len(batch)
        except Exception as e:
            print(f"❌ Batch {batch_num}/{total_batches} error: {e}")
            failed_count += len(batch)
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

    print()
    print("=" * 60)
    if failed_count == 0:
        print(f"✅ Upload complete! Successfully uploaded {success_count} points to {collection}")
        sys.exit(0)
    else:
        print("⚠️  Upload completed with errors")
        print(f"   Success: {success_count} points")
        print(f"   Failed: {failed_count} points")
        sys.exit(1)


if __name__ == "__main__":
    main()
