#!/usr/bin/env python3
"""KBLI prose fix — pass 1 (deterministic, 2026-07-07).

Fixes, in apps/mouth/data/KBLI_2025_FINAL_CLEAN.json:
  1. Date canon in l4_bali.reason: "13/5/26", "28/1/2026", ISO "2026-06-28" → "13 May 2026" style.
  2. Twelve hand-curated English rewrites of Italian prose (5 l4 reasons + 7 intel whatChanged).
     Each rewrite is guarded by an expected-prefix assert: if the on-disk text moved, the script
     aborts loudly instead of patching the wrong thing.
  3. Bumps apps/mouth/data/kbli-dataset-version.json (lastModified + sha256) so the vitest
     dataset-version guard stays green.

Idempotent: re-running after success is a no-op (guards no longer match, dates already canonical).
Run from repo root: python3 scripts/kbli_fix_prose_pass1.py [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
VERSION = ROOT / "apps/mouth/data/kbli-dataset-version.json"

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def canon_dates(text: str) -> str:
    def slash(m: re.Match) -> str:
        day, mon, yr = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= mon <= 12 and 1 <= day <= 31):
            return m.group(0)
        year = int(yr) + 2000 if len(yr) == 2 else int(yr)
        return f"{day} {MONTHS[mon - 1]} {year}"

    def iso(m: re.Match) -> str:
        year, mon, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= mon <= 12 and 1 <= day <= 31):
            return m.group(0)
        return f"{day} {MONTHS[mon - 1]} {year}"

    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", slash, text)
    text = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", iso, text)
    return text


# (code, field_path, expected_prefix_of_current_text, replacement)
REWRITES: list[tuple[str, str, str, str]] = [
    (
        "01111", "l4_bali.reason",
        "agricoltura base riservata",
        "Reserved basic (staple-crop) agriculture — closed to PMA registration in Bali.",
    ),
    (
        "47111", "l4_bali.reason",
        "minimarket/supermarket riservato WNI",
        "Minimarkets/supermarkets are reserved for Indonesian citizens (WNI) — closed to PMA.",
    ),
    (
        "47112", "l4_bali.reason",
        "minimarket/supermarket riservato WNI",
        "Minimarkets/supermarkets are reserved for Indonesian citizens (WNI) — closed to PMA.",
    ),
    (
        "69102", "l4_bali.reason",
        "Servizi legali riservati avvocati WNI iscritti",
        "Legal services are reserved for Indonesian-licensed advocates (UU 18/2003 on Advocates). "
        "The KBLI catalogue lists the code as TERBUKA, but the profession itself is closed to foreign nationals.",
    ),
    (
        "70209", "l4_bali.reason",
        "consulenza mgmt: chiuso PMA Bali dal",
        "Management consultancy — closed to PMA registration in Bali since 28 January 2026 "
        "(the first of the seven announced sectoral closures).",
    ),
    (
        "46632", "intel_2026.whatChanged",
        "Renumbered/adjusted from KBLI 2020. In KBLI 2020 la compravendita moto usate",
        "Renumbered/adjusted from KBLI 2020. Under KBLI 2020, trade in used motorcycles was often folded "
        "into the 45xxx retail codes with no wholesale/retail distinction; KBLI 2025 isolates the wholesale "
        "trade under 46632.",
    ),
    (
        "46752", "intel_2026.whatChanged",
        "Renumbered/adjusted from KBLI 2020. Distinguere da prodotti chimici industriali",
        "Renumbered/adjusted from KBLI 2020. Distinct from industrial chemicals (Category C): agrochemical "
        "distribution runs on a separate Ministry of Agriculture licensing chain from the industrial one.",
    ),
    (
        "49293", "intel_2026.whatChanged",
        "Renumbered/adjusted from KBLI 2020. KBLI 2020: 49293 (Angkutan Taksi)",
        "Renumbered/adjusted from KBLI 2020. KBLI 2020 code 49293 (taxi transport) carries over unchanged "
        "in KBLI 2025. The sector is under Ministry of Transportation (Kemenhub) scrutiny for ride-hailing "
        "integration. With the June 2026 transition window closed, verify and update the NIB record now.",
    ),
    (
        "64930", "intel_2026.whatChanged",
        "Renumbered/adjusted from KBLI 2020. KBLI 64930 invariato",
        "Unchanged 2020→2025. POJK 46/2024 covers all financing (pembiayaan) activities, including "
        "factoring. With the June 2026 transition window closed, verify and update the OSS record now.",
    ),
    (
        "65111", "intel_2026.whatChanged",
        "Renumbered/adjusted from KBLI 2020. KBLI 65111 invariato",
        "Unchanged 2020→2025. UU 4/2023 (P2SK) is the overarching legislative framework modernising the "
        "sector. With the June 2026 transition window closed, verify and update the OSS record now.",
    ),
    (
        "66162", "intel_2026.whatChanged",
        "Renumbered/adjusted from KBLI 2020. KBLI 66162 invariato",
        "Unchanged 2020→2025 as a code distinct from the conventional variant. POJK 40/2024 covers both "
        "versions. KBLI 2025 is the first edition to codify this explicitly as a separate activity.",
    ),
    (
        "66301", "intel_2026.whatChanged",
        "Renumbered/adjusted from KBLI 2020. KBLI 2020: 6631",
        "Recodified from KBLI 2020 group 6631 into 66301. With the June 2026 transition window closed, "
        "verify and update the code in AHU and OSS records now.",
    ),
]


def get_field(rec: dict, path: str):
    obj = rec
    parts = path.split(".")
    for p in parts[:-1]:
        obj = obj.get(p) or {}
    return obj, parts[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    raw = json.loads(DATASET.read_text(encoding="utf-8"))
    recs = {r["kode_kbli_2025"]: r for r in raw["data"]}

    # --- 2. guarded rewrites -------------------------------------------------
    applied = skipped = 0
    for code, path, expected, replacement in REWRITES:
        rec = recs.get(code)
        if rec is None:
            print(f"FATAL: code {code} not in dataset", file=sys.stderr)
            return 2
        obj, leaf = get_field(rec, path)
        current = str(obj.get(leaf) or "")
        if current == replacement:
            skipped += 1
            continue
        if not current.startswith(expected):
            print(
                f"FATAL: {code} {path} does not start with expected prefix.\n"
                f"  expected: {expected[:80]}\n  current:  {current[:80]}",
                file=sys.stderr,
            )
            return 2
        obj[leaf] = replacement
        applied += 1

    # --- 1. date canon over every l4 reason ----------------------------------
    dated = 0
    for rec in raw["data"]:
        l4 = rec.get("l4_bali")
        if isinstance(l4, dict) and l4.get("reason"):
            new = canon_dates(str(l4["reason"]))
            if new != l4["reason"]:
                l4["reason"] = new
                dated += 1

    print(f"rewrites applied: {applied} (idempotent-skip {skipped}) | reasons date-normalized: {dated}")

    if args.dry_run:
        print("dry-run: nothing written")
        return 0

    raw["metadata"]["total_codes"] = len(raw["data"])  # was stale (1563 from the v8 era)
    raw["metadata"]["prose_pass1_fix"] = dt.date.today().isoformat()
    body = json.dumps(raw, ensure_ascii=False, indent=2)
    DATASET.write_text(body, encoding="utf-8")

    sha = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    ver = json.loads(VERSION.read_text(encoding="utf-8"))
    ver["lastModified"] = dt.date.today().isoformat()
    ver["datasetSha256"] = f"sha256:{sha}"
    VERSION.write_text(json.dumps(ver, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"dataset written; version bumped → {ver['lastModified']} {ver['datasetSha256'][:20]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
