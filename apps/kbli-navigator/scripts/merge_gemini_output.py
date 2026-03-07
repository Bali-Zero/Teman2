#!/usr/bin/env python3
"""
Merge Gemini output files into kbli-gold-content.ts

Usage:
  # Merge all 4 output files at once
  python3 scripts/merge_gemini_output.py /tmp/kbli_gemini_output_1.ts /tmp/kbli_gemini_output_2.ts /tmp/kbli_gemini_output_3.ts /tmp/kbli_gemini_output_4.ts

  # Merge single file
  python3 scripts/merge_gemini_output.py /tmp/kbli_gemini_output_1.ts

  # Dry run (preview only, don't write)
  python3 scripts/merge_gemini_output.py --dry-run /tmp/kbli_gemini_output_1.ts
"""

import re
import sys
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
GOLD_TS = REPO_ROOT / "lib" / "kbli-gold-content.ts"


def load_existing_codes() -> set[str]:
    content = GOLD_TS.read_text()
    return set(re.findall(r'"(\d{5})":\s*\{', content))


def extract_entries_from_output(text: str) -> list[tuple[str, str]]:
    """
    Extract TypeScript entries from Gemini output.
    Returns list of (code, full_entry_text) tuples.
    Handles messy output: markdown fences, extra text, partial entries.
    """
    # Remove markdown fences
    text = re.sub(r'```typescript\s*', '', text)
    text = re.sub(r'```ts\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    entries = []

    # Pattern: optional comment line + "XXXXX": { ... },
    # Use a pattern that matches from code declaration to closing },
    pattern = re.compile(
        r'(?:// AUTO-GENERATED: (\d{5})\s*\n\s*)?'  # optional comment
        r'"(\d{5})":\s*\{(.+?)\},\s*(?=\n\s*(?://|"|\Z))',
        re.DOTALL
    )

    for m in pattern.finditer(text):
        code_from_comment = m.group(1)
        code_from_key = m.group(2)
        body = m.group(3)
        code = code_from_key  # always use the actual key

        # Reconstruct clean entry
        comment = f"  // AUTO-GENERATED: {code}\n"
        entry_text = f'{comment}  "{code}": {{{body}}},\n'
        entries.append((code, entry_text))

    return entries


def validate_entry(code: str, entry_text: str) -> list[str]:
    """Check entry has all required fields. Returns list of missing fields."""
    required = ['whatItMeans', 'whatYouNeed', 'whatChanged', 'baliContext', 'youllAlsoNeed', 'zantaraOpener']
    missing = [f for f in required if f not in entry_text]
    return missing


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Gemini output into kbli-gold-content.ts")
    parser.add_argument("files", nargs="+", help="Gemini output .ts files to merge")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't write")
    parser.add_argument("--force", action="store_true", help="Overwrite codes already in gold-content.ts")
    args = parser.parse_args()

    existing = load_existing_codes()
    print(f"Existing codes in gold-content.ts: {len(existing)}")

    # Collect all entries from all files
    all_entries: dict[str, str] = {}  # code → entry_text
    stats = {"total": 0, "skipped_existing": 0, "skipped_invalid": 0, "skipped_dup": 0, "accepted": 0}

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"⚠️  File not found: {filepath} — skipping")
            continue

        text = path.read_text()
        entries = extract_entries_from_output(text)
        print(f"\n{path.name}: extracted {len(entries)} entries")

        for code, entry_text in entries:
            stats["total"] += 1

            # Skip already in gold-content.ts (unless --force)
            if code in existing and not args.force:
                stats["skipped_existing"] += 1
                continue

            # Skip duplicates within this merge run (first wins)
            if code in all_entries and not args.force:
                stats["skipped_dup"] += 1
                continue

            # Validate fields
            missing = validate_entry(code, entry_text)
            if missing:
                print(f"  ⚠️  {code}: missing fields {missing} — skipping")
                stats["skipped_invalid"] += 1
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

    # Sort by code
    sorted_entries = sorted(all_entries.items(), key=lambda x: x[0])

    if args.dry_run:
        print(f"\n[DRY RUN] Would write {len(sorted_entries)} entries. First 3:")
        for code, text in sorted_entries[:3]:
            print(f"\n--- {code} ---")
            # Show first 400 chars of entry
            preview = text.strip()[:400]
            print(preview)
            print("...")
        print(f"\n[DRY RUN] Run without --dry-run to write.")
        return

    # Append to gold-content.ts
    content = GOLD_TS.read_text()
    new_block = "\n".join(entry_text for _, entry_text in sorted_entries)

    marker = "\n};"
    idx = content.rfind(marker)
    if idx == -1:
        print("ERROR: Could not find closing '};' in kbli-gold-content.ts")
        sys.exit(1)

    new_content = content[:idx] + "\n" + new_block + content[idx:]
    GOLD_TS.write_text(new_content)

    print(f"\n✅ Written {len(sorted_entries)} entries to {GOLD_TS.name}")
    print(f"   New total: {len(existing) + len(sorted_entries)} codes in gold-content.ts")


if __name__ == "__main__":
    main()
