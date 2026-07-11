#!/usr/bin/env python3
"""Import Damar's anchor JSON: copy chosen covers to anchors/<domain>-anchor.jpg.

Usage:
    python3 _import-damar-anchors.py path/to/anchors-by-damar-2026-05-08.json
    python3 _import-damar-anchors.py --dry-run path/to/anchors-by-damar-2026-05-08.json
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path.home() / ".claude/skills/bali-zero-brand"
PAST_DIR = SKILL_DIR / "past"
ANCHORS_DIR = SKILL_DIR / "anchors"

VALID_DOMAINS = {"visa", "tax", "property", "regulatory", "health"}


def main():
    parser = argparse.ArgumentParser(description="Import Damar anchor JSON into anchors/")
    parser.add_argument("json_path", help="Path to anchors-by-damar-*.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()

    src = Path(args.json_path).expanduser()
    if not src.exists():
        print(f"File not found: {src}", file=sys.stderr)
        sys.exit(1)

    payload = json.loads(src.read_text())
    if payload.get("version") != 1:
        print(f"Unexpected version: {payload.get('version')}", file=sys.stderr)
        sys.exit(1)

    anchors = payload.get("anchors", {})
    print(f"File: {src.name}")
    print(f"  Picked by: {payload.get('picked_by')}")
    print(f"  Exported at: {payload.get('exported_at')}")
    print(f"  Completed: {payload.get('completed')}")
    print()

    if not args.dry_run:
        ANCHORS_DIR.mkdir(parents=True, exist_ok=True)
        archive_dir = ANCHORS_DIR / "_archive"
        archive_dir.mkdir(exist_ok=True)

    written = 0
    errors = 0

    for domain in VALID_DOMAINS:
        bucket = anchors.get(domain)
        if not bucket:
            print(f"  ⊘ no anchor picked for {domain}")
            continue

        source_dir = PAST_DIR / bucket
        source_jpg = source_dir / "01.jpg"
        if not source_jpg.exists():
            print(f"  ❌ source slide missing for {domain}: {source_jpg}")
            errors += 1
            continue

        dest_jpg = ANCHORS_DIR / f"{domain}-anchor.jpg"
        dest_meta = ANCHORS_DIR / f"{domain}-anchor.json"

        # Archive previous if exists
        if dest_jpg.exists() and not args.dry_run:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            shutil.copy(dest_jpg, archive_dir / f"{domain}-anchor-{ts}.jpg")
            if dest_meta.exists():
                shutil.copy(dest_meta, archive_dir / f"{domain}-anchor-{ts}.json")

        action = "✓ assign" if not dest_jpg.exists() else "✏️  replace"
        print(f"  {action} {domain} ← {bucket}")
        written += 1

        if not args.dry_run:
            shutil.copy(source_jpg, dest_jpg)
            meta = {
                "domain": domain,
                "source_bucket": bucket,
                "source_slide": 1,
                "assigned_at": datetime.now(timezone.utc).isoformat(),
                "assigned_by": "damar",
                "imported_from": str(src),
            }
            dest_meta.write_text(json.dumps(meta, indent=2))

    print()
    print(f"Result: {written} anchors written, {errors} errors")
    if args.dry_run:
        print("(dry-run — no files changed)")


if __name__ == "__main__":
    main()
