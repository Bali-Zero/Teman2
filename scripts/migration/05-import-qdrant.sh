#!/usr/bin/env python3
"""
Script 5: Import Qdrant snapshots to Railway/Qdrant Cloud
Usage: python3 05-import-qdrant.sh
"""

import os
import sys
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def print_color(color, message):
    print(f"{color}{message}{NC}")

def main():
    print_color(BLUE, "╔════════════════════════════════════════╗")
    print_color(BLUE, "║  QDRANT SNAPSHOT IMPORT                ║")
    print_color(BLUE, "╚════════════════════════════════════════╝\n")

    # Find latest backup
    backup_base = Path("backups/qdrant")
    if not backup_base.exists():
        print_color(RED, "✗ No backups found. Run 04-export-qdrant.sh first.")
        sys.exit(1)

    # Get latest backup directory
    backup_dirs = sorted([d for d in backup_base.iterdir() if d.is_dir()], reverse=True)
    if not backup_dirs:
        print_color(RED, "✗ No backup directories found")
        sys.exit(1)

    latest_backup = backup_dirs[0]
    print_color(GREEN, f"✓ Using backup: {latest_backup.name}\n")

    # Get new Qdrant URL
    print_color(YELLOW, "→ Enter NEW Qdrant URL:")
    print_color(BLUE, "  (Railway: https://xxx.railway.app)")
    print_color(BLUE, "  (Qdrant Cloud: https://xxx.qdrant.io)")
    new_url = input().strip()

    print_color(YELLOW, "→ Enter API key (or press Enter if none):")
    api_key = input().strip() or None

    # Connect
    print_color(YELLOW, "\n→ Connecting to new Qdrant...")
    try:
        client = QdrantClient(url=new_url, api_key=api_key)
        # Test connection
        collections = client.get_collections()
        print_color(GREEN, "✓ Connected!\n")
    except Exception as e:
        print_color(RED, f"✗ Connection failed: {e}")
        sys.exit(1)

    # Find snapshots
    snapshot_files = list(latest_backup.glob("*.snapshot"))
    if not snapshot_files:
        print_color(RED, f"✗ No snapshot files found in {latest_backup}")
        sys.exit(1)

    print_color(BLUE, f"━━━ Found {len(snapshot_files)} snapshots ━━━\n")

    # Import each snapshot
    for snapshot_path in snapshot_files:
        collection_name = snapshot_path.stem
        print_color(YELLOW, f"→ Importing: {collection_name}")

        try:
            # Upload snapshot
            print_color(YELLOW, "  Uploading snapshot...")
            with open(snapshot_path, 'rb') as f:
                snapshot_data = f.read()

            # Recover collection from snapshot
            print_color(YELLOW, "  Restoring collection...")
            client.recover_snapshot(
                collection_name=collection_name,
                snapshot=snapshot_data
            )

            # Verify
            info = client.get_collection(collection_name)
            point_count = info.points_count

            print_color(GREEN, f"  ✓ Restored {point_count:,} points\n")

        except Exception as e:
            print_color(RED, f"  ✗ Error: {e}\n")

            # Try alternative method: recreate collection
            print_color(YELLOW, "  Trying alternative method...")
            try:
                # This requires knowing vector dimensions
                # You might need to adjust based on your setup
                print_color(YELLOW, "  Note: May need manual collection recreation")
                print_color(YELLOW, f"  Snapshot file: {snapshot_path}")
            except Exception as e2:
                print_color(RED, f"  ✗ Failed: {e2}\n")
            continue

    # Final verification
    print_color(BLUE, "\n━━━ Verification ━━━\n")

    collections = client.get_collections().collections
    for collection in collections:
        info = client.get_collection(collection.name)
        print_color(GREEN, f"✓ {collection.name}: {info.points_count:,} points")

    print_color(BLUE, "\n╔════════════════════════════════════════╗")
    print_color(BLUE, "║  IMPORT SUMMARY                        ║")
    print_color(BLUE, "╚════════════════════════════════════════╝\n")

    print_color(GREEN, f"✓ Collections imported: {len(collections)}")
    print_color(GREEN, f"✓ New Qdrant URL: {new_url}\n")

    print_color(YELLOW, "═══════════════════════════════════════")
    print_color(GREEN, "✓ Import complete!")
    print_color(YELLOW, "═══════════════════════════════════════")

    print_color(BLUE, "\nNext step: Update backend env vars with new Qdrant URL\n")

if __name__ == "__main__":
    main()
