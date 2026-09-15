#!/usr/bin/env python3
"""Apply the Lampiran II entry-46 specialised-retail allocation to canonical.

Separate from `apply_umkm_reservations.py`: its `judged_as` gate refuses any
code whose `bps_2020_ancestors` names a 2020 code OTHER than the one judged.
Every code here absorbs a generic mail-order/retail 2020 ancestor BPS fanned
into dozens of unrelated codes (dry-run REFUSE reproduced on 47241 before
this compiler existed); Lampiran II entry 47 allocates the SAME goods sold
by mail order separately, so that ancestor is a channel variant, a per-item
judgment (`self_ancestor`) not re-derived here. 47245/47246 split ONE
ancestor into TWO heirs that TOGETHER exhaust the row — a shape the base
compiler does not express.

`check()` refuses unless: the code exists; `self_ancestor` is among its
`bps_2020_ancestors`; `heirs_of(self_ancestor)` == `{code} | split_siblings`
exactly (no undeclared/missing sibling); every declared sibling is itself a
spec item (no partial split); no conflicting `pma_official_basis`; and
`was` still matches the record (refuses a spec the world has moved past).
Reuses `apply_umkm_reservations.py` for the patch tuple and consumer sync.
Dry-run is the default; nothing is written without --apply.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_umkm_reservations as base  # noqa: E402

CANONICAL = base.CANONICAL
CURE_SPECS = Path(__file__).resolve().parent / "cure_specs"
SPEC = CURE_SPECS / "lampiran2_specialised_retail_wh_pr3_2026_09_15.json"
EXIT_OK, EXIT_REFUSED = 0, 2


def check(spec: dict[str, Any], records: list[dict]) -> tuple[list[dict], list[str]]:
    by_code = {str(r["kode_kbli_2025"]): r for r in records}
    heirs = base.heirs_of(records)
    declared_codes = {item["code"] for item in spec["items"]}
    refusals: list[str] = []
    todo: list[dict[str, Any]] = []
    for item in spec["items"]:
        code = item["code"]
        record = by_code.get(code)
        if record is None:
            refusals.append(f"{code}: not in the dataset")
            continue
        ancestor = item["self_ancestor"]
        ancestors = [str(a) for a in (record.get("bps_2020_ancestors") or {}).get("codes") or []]
        if ancestor not in ancestors:
            refusals.append(
                f"{code}: self_ancestor {ancestor} is not among its bps_2020_ancestors {ancestors}"
            )
            continue
        declared_siblings = set(item.get("split_siblings") or [])
        expected = {code} | declared_siblings
        actual = set(heirs.get(ancestor, []))
        if actual != expected:
            refusals.append(
                f"{code}: heirs_of({ancestor}) = {sorted(actual)}, declared "
                f"split_siblings give {sorted(expected)} — undeclared sibling or "
                "a declared one missing from the crosswalk"
            )
            continue
        missing_sibling_items = declared_siblings - declared_codes
        if missing_sibling_items:
            refusals.append(
                f"{code}: split_siblings {sorted(missing_sibling_items)} are not "
                "themselves items in this spec — a partial split"
            )
            continue
        existing = record.get("pma_official_basis")
        if existing and existing != item["locator"]:
            refusals.append(f"{code}: already carries a different pma_official_basis")
            continue
        target = base.patch_for(item)
        if all(record.get(key) == value for key, value in target.items()):
            continue
        was = item.get("was") or {}
        now = {"pma_status": record.get("pma_status"), "pma_max_asing": record.get("pma_max_asing")}
        if was and was != now:
            refusals.append(f"{code}: moved since adjudication — spec {was}, now {now}")
            continue
        todo.append(item)
    return todo, refusals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--dataset", default=str(CANONICAL))
    ap.add_argument("--spec", default=str(SPEC))
    args = ap.parse_args(argv)
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    path = Path(args.dataset)
    payload, records, original = base.load(path)
    todo, refusals = check(spec, records)
    already_applied = len(spec["items"]) - len(todo) - len(refusals)
    print(
        f"spec items {len(spec['items'])} · applicable {len(todo)} · "
        f"already applied {already_applied} · refused {len(refusals)}"
    )
    for r in refusals:
        print(f"  REFUSE {r}")
    if refusals:
        print("\nrefusing to write: a spec wrong about one code is not trusted for the rest")
        return EXIT_REFUSED
    for item in todo:
        print(f"  {item['code']} (self_ancestor {item['self_ancestor']}): {item['was']} -> TERBATAS/0")
    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK
    if not todo:
        print("\nalready applied — clean no-op; nothing written or propagated")
        return EXIT_OK
    by_code = {str(r["kode_kbli_2025"]): r for r in records}
    for item in todo:
        by_code[item["code"]].update(base.patch_for(item))
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(body + ("\n" if original.endswith("\n") else ""), encoding="utf-8")
    _, again, _ = base.load(path)
    fresh = {str(r["kode_kbli_2025"]): r for r in again}
    wrong = [
        i["code"]
        for i in todo
        if fresh[i["code"]].get("pma_max_asing") != 0 or fresh[i["code"]].get("pma_status") != "TERBATAS"
    ]
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on {len(wrong)}: {wrong[:10]}")
        return EXIT_REFUSED
    print(f"\napplied and verified on re-read: {len(todo)} code(s)")

    if path.resolve() != CANONICAL.resolve():
        print(f"not canonical ({path}) — skipping consumer propagation")
        return EXIT_OK
    problems = base.propagate()
    for p in problems:
        print(f"  PROPAGATION FAILED: {p}")
    if problems:
        return EXIT_REFUSED
    print("consumer copies in sync with canonical")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
