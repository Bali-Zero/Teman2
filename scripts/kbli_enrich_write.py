#!/usr/bin/env python3
"""Phase 3: Write enriched content to kbli-gold-all.json and test build.
Output format: flat JSON object {code: {6 fields + optional tkaInfo}}.
Merges with existing entries (preserves tkaInfo, overwrites content fields).
"""
import json
import subprocess
from pathlib import Path

GOLD_JSON = Path(__file__).parent.parent / "apps" / "mouth" / "data" / "kbli-gold-all.json"
KBLI_NAV_ROOT = Path(__file__).parent.parent / "apps" / "kbli-navigator"


def load_existing_gold() -> dict:
    """Load existing kbli-gold-all.json."""
    if GOLD_JSON.exists():
        with open(GOLD_JSON) as f:
            return json.load(f)
    return {}


def merge_and_write(new_entries: dict[str, dict], dry_run: bool = False) -> int:
    """Merge new entries into kbli-gold-all.json.
    Preserves existing tkaInfo. Overwrites content fields.
    Returns count of entries written.
    """
    existing = load_existing_gold()
    merged_count = 0

    for code, content in new_entries.items():
        if code in existing:
            # Preserve tkaInfo if it exists
            tka_info = existing[code].get("tkaInfo")
            existing[code].update(content)
            if tka_info:
                existing[code]["tkaInfo"] = tka_info
        else:
            existing[code] = content
        merged_count += 1

    if dry_run:
        print(f"DRY RUN: Would write {merged_count} entries to {GOLD_JSON}")
        return merged_count

    # Write with sorted keys for stable diffs
    with open(GOLD_JSON, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"  Wrote {merged_count} entries to {GOLD_JSON}")
    print(f"  Total entries in file: {len(existing)}")
    return merged_count


def test_build() -> bool:
    """Run Next.js build to verify SSG pages generate correctly."""
    print("  Running Next.js build test...")
    try:
        result = subprocess.run(
            ["npx", "next", "build"],
            capture_output=True, text=True, timeout=600,
            cwd=str(KBLI_NAV_ROOT),
        )
        if result.returncode == 0:
            # Check for SSG page count
            if "1595" in result.stdout or "Generating static pages" in result.stdout:
                print("  Build OK ✓")
                return True
        print(f"  Build FAILED (exit {result.returncode})")
        print(f"  stderr: {result.stderr[:500]}")
        return False
    except subprocess.TimeoutExpired:
        print("  Build TIMEOUT")
        return False
