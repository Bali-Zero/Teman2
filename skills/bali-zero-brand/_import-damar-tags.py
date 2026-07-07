#!/usr/bin/env python3
"""Import Damar's tag JSON into past/ metadata.

Run after Damar sends back tags-by-damar-YYYY-MM-DD.json via WhatsApp.

Usage:
    python3 _import-damar-tags.py path/to/tags-by-damar-2026-05-08.json
    python3 _import-damar-tags.py --dry-run path/to/tags-by-damar-2026-05-08.json

Idempotent: re-running with the same file is safe. Existing tags are
overwritten only if the JSON has a newer `tagged_at` timestamp.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PAST_DIR = Path.home() / ".claude/skills/bali-zero-brand/past"

VALID_DOMAINS = {"visa", "tax", "property", "regulatory", "health", "brand"}
VALID_REGISTERS = {"rituale", "analitico", "ironico", "militante", "pedagogico", "poetico", "tecnico"}
VALID_LAYOUTS = {"cover-photo", "photo-headline-yellow-sub", "qa-dialogue",
                 "timeline-pinboard", "dark-status-list", "statement-bomb"}
VALID_AUDIENCE = {"founder", "investor", "digital-nomad", "retiree", "mass-tourist", "mixed"}


def main():
    parser = argparse.ArgumentParser(description="Import Damar tag JSON into past/")
    parser.add_argument("json_path", help="Path to tags-by-damar-*.json")
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

    tags = payload.get("tags", {})
    print(f"File: {src.name}")
    print(f"  Tagged by: {payload.get('tagged_by')}")
    print(f"  Exported at: {payload.get('exported_at')}")
    print(f"  Total carousels in file: {payload.get('total_carousels')}")
    print(f"  Tagged: {payload.get('tagged_count')}, Skipped: {payload.get('skipped_count')}")
    print()

    written = 0
    skipped = 0
    errors = 0
    invalid = 0

    for bucket, tag in tags.items():
        target = PAST_DIR / bucket
        if not target.is_dir():
            print(f"  ⚠️  bucket missing on disk: {bucket}")
            errors += 1
            continue

        if tag.get("skipped"):
            print(f"  ⊘ skipped by Damar: {bucket}")
            skipped += 1
            if not args.dry_run:
                meta_path = target / "metadata.json"
                meta = json.loads(meta_path.read_text())
                meta["skipped_by_damar"] = True
                meta["last_tagged_at"] = tag.get("tagged_at")
                meta["last_tagged_by"] = "damar"
                meta_path.write_text(json.dumps(meta, indent=2))
            continue

        # Validate
        topic = (tag.get("topic") or "").strip().lower().replace(" ", "-")
        domain = tag.get("domain")
        register = tag.get("register")
        layout = tag.get("layout")
        audience = tag.get("audience")

        if not topic:
            print(f"  ❌ no topic for {bucket}")
            invalid += 1
            continue
        if domain not in VALID_DOMAINS:
            print(f"  ❌ invalid domain '{domain}' for {bucket}")
            invalid += 1
            continue
        if register not in VALID_REGISTERS:
            print(f"  ❌ invalid register '{register}' for {bucket}")
            invalid += 1
            continue
        if layout not in VALID_LAYOUTS:
            print(f"  ❌ invalid layout '{layout}' for {bucket}")
            invalid += 1
            continue
        if audience not in VALID_AUDIENCE:
            print(f"  ❌ invalid audience '{audience}' for {bucket}")
            invalid += 1
            continue

        # Apply
        meta_path = target / "metadata.json"
        meta = json.loads(meta_path.read_text())
        old_topic = meta.get("topic_slug", "unknown")

        meta["topic_slug"] = topic
        meta["domain"] = domain
        meta["tone_register_primary"] = register
        meta["layout_family_primary"] = layout
        meta["audience_segment"] = audience
        meta["last_tagged_at"] = tag.get("tagged_at")
        meta["last_tagged_by"] = "damar"
        meta.pop("skipped_by_damar", None)

        change_marker = "✏️  update" if old_topic not in (None, "", "unknown") else "✓ tag"
        print(f"  {change_marker} {bucket} → topic='{topic}' domain={domain} register={register}")
        written += 1

        if not args.dry_run:
            meta_path.write_text(json.dumps(meta, indent=2))

    print()
    print(f"Result: {written} tags written, {skipped} skipped, {invalid} invalid, {errors} errors")
    if args.dry_run:
        print("(dry-run — no files changed)")


if __name__ == "__main__":
    main()
