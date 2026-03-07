#!/usr/bin/env python3
"""
Merge Gemini hero image outputs into GOLD_HERO_IMAGES in page.tsx

Usage:
  python3 scripts/merge_hero_images.py /tmp/hero_output_1.ts /tmp/hero_output_2.ts ...
  python3 scripts/merge_hero_images.py --dry-run /tmp/hero_output_1.ts
"""

import re
import sys
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PAGE_TSX = REPO_ROOT / "app" / "kbli" / "[code]" / "page.tsx"

MARKER_START = "const GOLD_HERO_IMAGES"
MARKER_END = "};\n"


def load_existing_codes() -> set:
    content = PAGE_TSX.read_text()
    return set(re.findall(r'"(\d{5})":\s*\{', content))


def extract_entries(text: str) -> list:
    """Extract hero image entries. Returns list of (code, entry_text)."""
    # Remove markdown fences
    text = re.sub(r'```typescript\s*', '', text)
    text = re.sub(r'```ts\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    entries = []
    # Match: "XXXXX": { src: "...", alt: "...", overlay: "...", },
    pattern = re.compile(
        r'"(\d{5})":\s*\{\s*\n'
        r'(\s+src:\s*"[^"]+",\s*\n)'
        r'(\s+alt:\s*"[^"]+",\s*\n)'
        r'(\s+overlay:\s*"[^"]+",\s*\n)'
        r'\s*\},',
        re.MULTILINE
    )

    for m in pattern.finditer(text):
        code = m.group(1)
        entry_text = (
            f'  "{code}": {{\n'
            f'{m.group(2)}'
            f'{m.group(3)}'
            f'{m.group(4)}'
            f'  }},\n'
        )
        entries.append((code, entry_text))

    return entries


def main():
    parser = argparse.ArgumentParser(description="Merge hero images into page.tsx")
    parser.add_argument("files", nargs="+", help="Gemini output .ts files")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--force", action="store_true", help="Overwrite existing codes")
    args = parser.parse_args()

    existing = load_existing_codes()
    print(f"Existing hero codes in page.tsx: {len(existing)}")

    all_entries: dict = {}
    stats = {"total": 0, "skipped_existing": 0, "skipped_dup": 0, "skipped_invalid": 0, "accepted": 0}

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"⚠️  File not found: {filepath} — skipping")
            continue

        text = path.read_text()
        entries = extract_entries(text)
        print(f"\n{path.name}: extracted {len(entries)} entries")

        for code, entry_text in entries:
            stats["total"] += 1

            if code in existing and not args.force:
                stats["skipped_existing"] += 1
                continue

            if code in all_entries and not args.force:
                stats["skipped_dup"] += 1
                continue

            all_entries[code] = entry_text
            stats["accepted"] += 1

    print(f"\n{'='*50}")
    print(f"Total extracted:      {stats['total']}")
    print(f"Skipped (existing):   {stats['skipped_existing']}")
    print(f"Skipped (duplicate):  {stats['skipped_dup']}")
    print(f"Skipped (invalid):    {stats['skipped_invalid']}")
    print(f"Accepted:             {stats['accepted']}")

    if not all_entries:
        print("\nNothing to write.")
        return

    sorted_entries = sorted(all_entries.items(), key=lambda x: x[0])

    if args.dry_run:
        print(f"\n[DRY RUN] Would write {len(sorted_entries)} entries. First 3:")
        for code, text in sorted_entries[:3]:
            print(f"\n--- {code} ---")
            print(text.strip())
        print(f"\n[DRY RUN] Run without --dry-run to write.")
        return

    # Insert before closing }; of GOLD_HERO_IMAGES
    content = PAGE_TSX.read_text()
    new_block = "".join(entry_text for _, entry_text in sorted_entries)

    # Find the closing }; of GOLD_HERO_IMAGES dict
    # Pattern: find GOLD_HERO_IMAGES declaration, then its closing };
    start_idx = content.find(MARKER_START)
    if start_idx == -1:
        print("ERROR: Cannot find GOLD_HERO_IMAGES in page.tsx")
        sys.exit(1)

    # Find the closing }; after GOLD_HERO_IMAGES
    # Look for the last entry in existing dict then the };
    end_pattern = re.compile(r'\n\};\s*\n', re.MULTILINE)
    match = None
    for m in end_pattern.finditer(content, start_idx):
        match = m
        break  # First }; after start is the closing of GOLD_HERO_IMAGES

    if not match:
        print("ERROR: Cannot find closing }; for GOLD_HERO_IMAGES")
        sys.exit(1)

    insert_pos = match.start()  # Insert before the \n};
    new_content = content[:insert_pos] + "\n" + new_block + content[insert_pos:]
    PAGE_TSX.write_text(new_content)

    print(f"\n✅ Written {len(sorted_entries)} entries to page.tsx")
    print(f"   New total: {len(existing) + len(sorted_entries)} hero codes")


if __name__ == "__main__":
    main()
