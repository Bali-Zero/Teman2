"""KBLI Triangle — apply the forced, reversible LOW auto-patch.

Reads _out/auto-patch-LOW.json (produced by sweep.py), applies each fix to the
dataset in place, and writes:
  - the patched KBLI_2025_FINAL_CLEAN.json
  - _out/applied-patch.json : the exact reversible record actually applied

HARD GATES (abort on any failure):
  1. No fix may target a frozen PMA field (pma_status/pma_max_asing/pma_kondisi).
  2. sha256 of the PMA fingerprint is asserted UNCHANGED before==after.
  3. Each fix's `old` must still match the on-disk value (no drift since sweep).

Idempotent: re-running after a successful apply is a no-op (old==new already).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kbli_triangle.invariants import PMA_FROZEN  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DATASET = REPO / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
OUT = Path(__file__).resolve().parent / "_out"
PATCH = OUT / "auto-patch-LOW.json"


def pma_fingerprint(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for r in rows:
        code = str(r.get("kode_kbli_2025") or "")
        for f in PMA_FROZEN:
            h.update(f"{code}|{f}|{r.get(f)!r}\n".encode())
    return h.hexdigest()


def set_path(rec: dict, dotted: str, value) -> None:
    segs = dotted.split(".")
    cur = rec
    for s in segs[:-1]:
        cur = cur.setdefault(s, {})
    cur[segs[-1]] = value


def get_path(rec: dict, dotted: str):
    cur = rec
    for s in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(s)
    return cur


def main() -> None:
    raw = json.loads(DATASET.read_text())
    is_wrapped = isinstance(raw, dict) and "data" in raw
    rows = raw["data"] if is_wrapped else raw
    by_code = {str(r.get("kode_kbli_2025")): r for r in rows}

    fp_before = pma_fingerprint(rows)
    patch = json.loads(PATCH.read_text())

    applied, skipped = [], []
    for fix in patch:
        path = fix["path"]
        top = path.split(".")[0]
        assert top not in PMA_FROZEN, f"REFUSED: patch targets frozen pma field {path}"
        rec = by_code.get(fix["code"])
        if rec is None:
            skipped.append({**fix, "skip": "code not found"})
            continue
        cur = get_path(rec, path)
        if cur == fix["new"]:
            skipped.append({**fix, "skip": "already applied (idempotent)"})
            continue
        if cur != fix["old"]:
            # drift since sweep — do NOT blindly overwrite; report for re-sweep.
            skipped.append({**fix, "skip": f"drift: on-disk={cur!r} != expected old={fix['old']!r}"})
            continue
        set_path(rec, path, fix["new"])
        applied.append(fix)

    fp_after = pma_fingerprint(rows)
    assert fp_before == fp_after, "PMA FINGERPRINT MUTATED — abort, rolling nothing"

    DATASET.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
    (OUT / "applied-patch.json").write_text(
        json.dumps({"applied": applied, "skipped": skipped}, ensure_ascii=False, indent=1)
    )
    print(f"applied: {len(applied)}  skipped: {len(skipped)}")
    print(f"PMA fingerprint unchanged: {fp_before[:16]}… == {fp_after[:16]}… ✓")
    from collections import Counter
    print("applied by rule:", dict(Counter(f["rule_id"] for f in applied)))


if __name__ == "__main__":
    main()
