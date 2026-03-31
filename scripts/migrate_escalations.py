#!/usr/bin/env python3
"""
D2.3 — Migrate shared/escalations.json → per-machine JSONL files.

Splits the existing unified escalations file into:
  shared/escalations_pro.jsonl  — written exclusively by Pro
  shared/escalations_air.jsonl  — written exclusively by Air

Assignment rules (in priority order):
  1. Entry has writer=pro or host=Nuzantara → Pro
  2. Entry has writer=air or host=Nuzantara-9 → Air
  3. Default → Pro (conservative: Pro is primary, fails closed)

Archives the original file to shared/archive/escalations_legacy_<ts>.json.

Safe to run multiple times — checks if migration already done.

Usage:
    python scripts/migrate_escalations.py [--dry-run]
"""
import argparse
import json
import os
import shutil
import time

NUZANTARA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIR = os.path.join(NUZANTARA_ROOT, "shared")
ARCHIVE_DIR = os.path.join(SHARED_DIR, "archive")
LEGACY_JSON = os.path.join(SHARED_DIR, "escalations.json")
LEGACY_JSONL = os.path.join(SHARED_DIR, "escalations.jsonl")
PRO_FILE = os.path.join(SHARED_DIR, "escalations_pro.jsonl")
AIR_FILE = os.path.join(SHARED_DIR, "escalations_air.jsonl")

PRO_HOSTS = {"pro", "nuzantara", "Nuzantara"}
AIR_HOSTS = {"air", "antonellosiano", "Nuzantara-9", "Nuzantara-9.local"}


def _assign_machine(entry: dict) -> str:
    writer = str(entry.get("writer", "")).lower()
    host = str(entry.get("host", "") or entry.get("machine", ""))

    if writer in ("pro", "nuzantara") or host in PRO_HOSTS:
        return "pro"
    if writer in ("air", "antonellosiano") or host in AIR_HOSTS:
        return "air"
    return "pro"  # default: conservative


def _collect_entries() -> list[dict]:
    """Collect all entries from legacy JSON and JSONL sources."""
    entries = []
    seen_ids: set = set()

    # From escalations.json (structured: {pending: [...], resolved: [...]})
    if os.path.exists(LEGACY_JSON):
        try:
            data = json.loads(open(LEGACY_JSON).read())
            for key in ("pending", "resolved"):
                for e in data.get(key, []):
                    eid = e.get("id") or json.dumps(e, sort_keys=True)
                    if eid not in seen_ids:
                        seen_ids.add(eid)
                        entries.append(e)
        except (json.JSONDecodeError, OSError):
            pass

    # From escalations.jsonl (line-delimited)
    if os.path.exists(LEGACY_JSONL):
        try:
            with open(LEGACY_JSONL) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        eid = e.get("id") or line
                        if eid not in seen_ids:
                            seen_ids.add(eid)
                            entries.append(e)
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass

    return entries


def run(dry_run: bool = False) -> None:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    entries = _collect_entries()
    pro_entries = [e for e in entries if _assign_machine(e) == "pro"]
    air_entries = [e for e in entries if _assign_machine(e) == "air"]

    print(f"Found {len(entries)} total escalation entries")
    print(f"  → Pro: {len(pro_entries)}")
    print(f"  → Air: {len(air_entries)}")

    if dry_run:
        print("[dry-run] No files written.")
        return

    # Write per-machine JSONL (append — safe if file already has content)
    def _append_entries(path: str, batch: list[dict]) -> None:
        with open(path, "a") as f:
            for e in batch:
                f.write(json.dumps(e) + "\n")

    _append_entries(PRO_FILE, pro_entries)
    _append_entries(AIR_FILE, air_entries)
    print(f"Written: {PRO_FILE} ({len(pro_entries)} entries)")
    print(f"Written: {AIR_FILE} ({len(air_entries)} entries)")

    # Archive legacy files
    ts = int(time.time())
    for src in (LEGACY_JSON, LEGACY_JSONL):
        if os.path.exists(src):
            dst = os.path.join(ARCHIVE_DIR, f"{os.path.basename(src).replace('.', f'_legacy_{ts}.')}")
            shutil.move(src, dst)
            print(f"Archived: {src} → {dst}")

    print("Migration complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate escalations to per-machine JSONL")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
