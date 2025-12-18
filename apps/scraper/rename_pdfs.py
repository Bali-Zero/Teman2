"""
Script per rinominare i PDF esistenti usando i metadata
Legge laws_metadata.jsonl e rinomina i file PDF con il titolo invece dell'ID
"""

import json
from pathlib import Path
import re

DATA_DIR = Path(__file__).parent / "data"
RAW_LAWS_DIR = DATA_DIR / "raw_laws"
METADATA_FILE = DATA_DIR / "laws_metadata.jsonl"


def clean_filename(title: str) -> str:
    """Clean title for use as filename"""
    # Remove invalid filename characters
    safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
    # Keep alphanumeric, spaces, hyphens, parentheses
    safe_title = re.sub(r"[^\w\s\-()]", "", safe_title)
    # Normalize multiple spaces
    safe_title = re.sub(r"\s+", " ", safe_title)
    safe_title = safe_title.strip()

    # Limit length
    if len(safe_title) > 200:
        safe_title = safe_title[:200].rsplit(" ", 1)[0]

    return safe_title


def rename_pdfs():
    """Rename existing PDFs using metadata"""
    if not METADATA_FILE.exists():
        print(f"Metadata file not found: {METADATA_FILE}")
        return

    # Read metadata
    metadata_map = {}
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    item = json.loads(line)
                    regulation_id = item.get("regulation_id")
                    local_filename = item.get("local_filename")
                    title = item.get("title", "unknown")

                    if regulation_id and local_filename:
                        # Generate new filename
                        new_filename = f"{clean_filename(title)}.pdf"
                        metadata_map[local_filename] = {
                            "new_filename": new_filename,
                            "title": title,
                            "regulation_id": regulation_id,
                        }
                except json.JSONDecodeError:
                    continue

    print(f"Found {len(metadata_map)} items in metadata")

    # Rename files
    renamed = 0
    skipped = 0
    errors = 0

    for old_filename, info in metadata_map.items():
        old_path = RAW_LAWS_DIR / old_filename
        new_filename = info["new_filename"]
        new_path = RAW_LAWS_DIR / new_filename

        if not old_path.exists():
            print(f"⚠️  File not found: {old_filename}")
            skipped += 1
            continue

        if new_path.exists() and old_path != new_path:
            print(f"⚠️  Target already exists, skipping: {new_filename}")
            skipped += 1
            continue

        try:
            old_path.rename(new_path)
            print(f"✓ Renamed: {old_filename} -> {new_filename}")
            print(f"  Title: {info['title']}")
            renamed += 1
        except Exception as e:
            print(f"✗ Error renaming {old_filename}: {e}")
            errors += 1

    print("\n" + "=" * 50)
    print("RENAME SUMMARY")
    print("=" * 50)
    print(f"Renamed: {renamed}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print("=" * 50)


if __name__ == "__main__":
    rename_pdfs()
