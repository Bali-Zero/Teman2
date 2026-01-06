#!/usr/bin/env python3
"""
Script 4: Export Qdrant snapshots from Fly.io
Usage: python3 04-export-qdrant.sh
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import SnapshotDescription

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
    print_color(BLUE, "║  QDRANT SNAPSHOT EXPORT                ║")
    print_color(BLUE, "╚════════════════════════════════════════╝\n")

    # Get Qdrant URL
    print_color(YELLOW, "→ Enter Fly.io Qdrant URL:")
    print_color(BLUE, "  (e.g., https://nuzantara-qdrant.fly.dev)")
    qdrant_url = input().strip()

    print_color(YELLOW, "→ Enter Qdrant API key (or press Enter if none):")
    api_key = input().strip() or None

    # Connect
    print_color(YELLOW, "\n→ Connecting to Qdrant...")
    try:
        client = QdrantClient(url=qdrant_url, api_key=api_key)
        collections = client.get_collections().collections
        print_color(GREEN, f"✓ Connected! Found {len(collections)} collections\n")
    except Exception as e:
        print_color(RED, f"✗ Connection failed: {e}")
        sys.exit(1)

    # Create backup directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("backups/qdrant") / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    print_color(BLUE, "━━━ Creating Snapshots ━━━\n")

    # Create snapshots for each collection
    snapshots = {}
    for collection in collections:
        collection_name = collection.name
        print_color(YELLOW, f"→ Processing: {collection_name}")

        try:
            # Get collection info
            info = client.get_collection(collection_name)
            point_count = info.points_count
            print_color(BLUE, f"  Points: {point_count:,}")

            # Create snapshot
            print_color(YELLOW, f"  Creating snapshot...")
            snapshot = client.create_snapshot(collection_name=collection_name)

            # Download snapshot
            snapshot_path = backup_dir / f"{collection_name}.snapshot"
            print_color(YELLOW, f"  Downloading to {snapshot_path}...")

            client.download_snapshot(
                collection_name=collection_name,
                snapshot_name=snapshot.name,
                output_path=str(snapshot_path)
            )

            file_size = snapshot_path.stat().st_size / (1024 * 1024)  # MB
            print_color(GREEN, f"  ✓ Downloaded ({file_size:.2f} MB)\n")

            snapshots[collection_name] = {
                'points': point_count,
                'file': str(snapshot_path),
                'size_mb': file_size
            }

        except Exception as e:
            print_color(RED, f"  ✗ Error: {e}\n")
            continue

    # Save manifest
    manifest_path = backup_dir / "manifest.txt"
    with open(manifest_path, 'w') as f:
        f.write(f"Qdrant Backup Manifest\n")
        f.write(f"Created: {timestamp}\n")
        f.write(f"Source: {qdrant_url}\n\n")
        f.write("Collections:\n")
        for name, info in snapshots.items():
            f.write(f"  - {name}: {info['points']:,} points, {info['size_mb']:.2f} MB\n")

    # Summary
    print_color(BLUE, "\n╔════════════════════════════════════════╗")
    print_color(BLUE, "║  EXPORT SUMMARY                        ║")
    print_color(BLUE, "╚════════════════════════════════════════╝\n")

    total_size = sum(s['size_mb'] for s in snapshots.values())
    total_points = sum(s['points'] for s in snapshots.values())

    print_color(GREEN, f"✓ Collections exported: {len(snapshots)}")
    print_color(GREEN, f"✓ Total points: {total_points:,}")
    print_color(GREEN, f"✓ Total size: {total_size:.2f} MB")
    print_color(GREEN, f"✓ Location: {backup_dir}\n")

    print_color(YELLOW, "═══════════════════════════════════════")
    print_color(GREEN, "✓ Export complete!")
    print_color(YELLOW, "═══════════════════════════════════════")

    print_color(BLUE, f"\nNext step: Run ./05-import-qdrant.sh to import to new Qdrant\n")

if __name__ == "__main__":
    main()
