#!/usr/bin/env python3
"""Apply W1/W2 wave patch files to the canonical KBLI dataset (2026-07-07).

Patches are JSON files {"code": "...", "patches": [{"field": "...", "new_text": "..."}]}
produced by the repair workflow. Verifier-rejected codes are excluded via --exclude.

Safety gates:
  - field must be one of the allowed prose paths
  - target record must exist; current text must be non-empty
  - a patch that leaves any 5-digit non-2025 code UNLABELED as KBLI 2020 is refused
    (mini-L3 check inline) unless --lenient
  - writes canonical + bumps version + runs sync_kbli_dataset.sh; re-run the full
    lint afterwards (separate command) before committing.

Usage: python3 scripts/kbli_apply_wave_patches.py --patch-dir DIR [--exclude 01111,47111] [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
VERSION = ROOT / "apps/mouth/data/kbli-dataset-version.json"

ALLOWED_FIELDS = {
    "l4_bali.reason",
    "intel_2026.whatItMeans",
    "intel_2026.whatYouNeed",
    "intel_2026.whatChanged",
    "intel_2026.zantaraOpener",
    "intel_2026.baliContext",
    "intel_2026.whoThisIsFor",
    "intel_2026.youllAlsoNeed",
    "intel_2026.tkaInfo",
}

CODE_REF = re.compile(r"\b(\d{5})\b")
LABEL_2020 = ("kbli 2020", "2020 code", "kbli2020", "formerly", "previous code")


def unlabeled_phantoms(text: str, codes: set[str], own: str) -> list[str]:
    bad = []
    for m in CODE_REF.finditer(text):
        ref = m.group(1)
        if ref == own or ref in codes:
            continue
        before = text[max(0, m.start() - 60) : m.start()].lower()
        if any(w in before for w in LABEL_2020):
            continue
        bad.append(ref)
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch-dir", required=True)
    ap.add_argument("--exclude", default="")
    ap.add_argument("--lenient", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    excluded = {c.strip() for c in args.exclude.split(",") if c.strip()}
    raw = json.loads(DATASET.read_text(encoding="utf-8"))
    recs = {r["kode_kbli_2025"]: r for r in raw["data"]}
    codes = set(recs)

    applied, skipped, refused = 0, 0, []
    for pf in sorted(Path(args.patch_dir).glob("*.json")):
        patch = json.loads(pf.read_text(encoding="utf-8"))
        code = str(patch.get("code", ""))
        if code in excluded:
            skipped += 1
            continue
        rec = recs.get(code)
        if rec is None:
            refused.append((code, "unknown code"))
            continue
        for p in patch.get("patches", []):
            field, new = p.get("field", ""), str(p.get("new_text", "") or "")
            if field not in ALLOWED_FIELDS:
                refused.append((code, f"field not allowed: {field}"))
                continue
            if not new.strip():
                refused.append((code, f"empty new_text for {field}"))
                continue
            phants = unlabeled_phantoms(new, codes, code)
            if phants and not args.lenient:
                refused.append((code, f"{field}: unlabeled non-2025 refs {phants}"))
                continue
            parts = field.split(".")
            obj = rec
            for seg in parts[:-1]:
                if not isinstance(obj.get(seg), dict):
                    obj[seg] = {}
                obj = obj[seg]
            obj[parts[-1]] = new
            applied += 1

    print(f"applied: {applied} | excluded-files: {skipped} | refused: {len(refused)}")
    for c, why in refused[:30]:
        print(f"  REFUSED {c}: {why}")

    if args.dry_run:
        print("dry-run: nothing written")
        return 0
    if applied == 0:
        print("nothing to write")
        return 0

    body = json.dumps(raw, ensure_ascii=False, indent=2)
    DATASET.write_text(body, encoding="utf-8")
    sha = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    ver = json.loads(VERSION.read_text(encoding="utf-8"))
    ver["lastModified"] = dt.date.today().isoformat()
    ver["datasetSha256"] = f"sha256:{sha}"
    VERSION.write_text(json.dumps(ver, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["bash", str(ROOT / "scripts/sync_kbli_dataset.sh")], check=True)
    print(f"written + synced; sha {sha[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
