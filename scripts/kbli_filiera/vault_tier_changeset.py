#!/usr/bin/env python3
"""vault_tier_changeset.py — the PINNED change-set definition between two vault
snapshots (spec docs/specs/2026-09-11-kbli-l2-oss-resnapshot-reingest-spec.md §6
ruling 5): per scope `localization.id.uraian`, per `KbliResikos[]` entry
`SkalaUsaha.kode` and `Resiko.localization.id.uraian`; a code is "changed" when
its SET of triples differs. One definition, so PR-B's predicted diff has one
number (181 for July -> September 2026) and the transform's measured tier
changes can be checked against it code by code.

Pure: reads <vault>/oss/<code>/ruang_lingkup.json for every 5-digit code in the
ground truth, no network, no timestamps. A code absent on one side (no data
file) is reported in `old_only` / `new_only`, never counted as changed.

Usage:
    python3 scripts/kbli_filiera/vault_tier_changeset.py \\
        --old ~/nuzantara-vault --new ~/nuzantara-vault-20260911 \\
        --out /tmp/l2/changed_pinned.txt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from kbli_filiera.vault_to_risk_jsonl import load_five_digit_codes, DEFAULT_GROUND_TRUTH
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera.vault_to_risk_jsonl import load_five_digit_codes, DEFAULT_GROUND_TRUTH


def _loc(d, field="uraian"):
    try:
        return d["localization"]["id"][field]
    except (KeyError, TypeError):
        return None


def triples(payload: dict) -> frozenset:
    """{(scope uraian, SkalaUsaha.kode, Resiko uraian)} for one raw ruang_lingkup payload."""
    out = set()
    for rl in payload.get("data") or []:
        scope = _loc(rl)
        for res in rl.get("KbliResikos") or []:
            skala = (res.get("SkalaUsaha") or {}).get("kode")
            out.add((scope, skala, _loc(res.get("Resiko"))))
    return frozenset(out)


def read_triples(vault_root: Path, code: str):
    p = vault_root / "oss" / code / "ruang_lingkup.json"
    if not p.exists():
        return None
    return triples(json.loads(p.read_text(encoding="utf-8")))


def changeset(old_root: Path, new_root: Path, ground_truth: Path) -> dict:
    changed, old_only, new_only, both = [], [], [], 0
    for code, _uuid in load_five_digit_codes(ground_truth):
        o, n = read_triples(old_root, code), read_triples(new_root, code)
        if o is None and n is None:
            continue
        if o is None:
            new_only.append(code)
            continue
        if n is None:
            old_only.append(code)
            continue
        both += 1
        if o != n:
            changed.append(code)
    return {"changed": changed, "old_only": old_only, "new_only": new_only, "both": both}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True, type=Path)
    ap.add_argument("--new", required=True, type=Path)
    ap.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    ap.add_argument("--out", type=Path, default=None, help="write the changed codes, one per line")
    args = ap.parse_args(argv)
    r = changeset(args.old.expanduser(), args.new.expanduser(), args.ground_truth)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(c + "\n" for c in r["changed"]), encoding="utf-8")
    print(
        f"vault_tier_changeset: both={r['both']} changed={len(r['changed'])} "
        f"old_only={len(r['old_only'])} new_only={len(r['new_only'])}"
    )
    print("old_only: " + " ".join(r["old_only"]))
    print("new_only: " + " ".join(r["new_only"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
