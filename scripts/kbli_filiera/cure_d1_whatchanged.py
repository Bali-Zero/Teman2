#!/usr/bin/env python3
"""D-1 (Zero, 2026-10-11): nine `whatChanged` fields carried pipeline provenance instead of a sentence for the client.

WHAT WAS WRONG
--------------
The app's detail card, the website's `/kbli/<code>` page and the conversational channels read `whatChanged` as the
answer to "what changed for this code between KBLI 2020 and 2025?". For nine codes the field held the cure's own
working notes: PR numbers, `pp28_sources`, `score=`, render file names, Italian ("match con aggregazione",
"codice rinumerato") and internal correction dates that a client reads as a change in the law. Two of them
(01309, 08996) asserted "same activity, new code number" from an automatic title match (73%, 75%) against codes
the official BPS table sends elsewhere (02119 -> 02102, 07309 -> 07229).

THE CURE
--------
One sentence per code, as Zero approved it (`PREVIEW-kbli-nav-design/D1-whatchanged.md`), pinned verbatim in
`cure_specs/d1_whatchanged_2026_10_11.json`. This module applies pinned old -> new pairs; it does not author prose.
Each sentence states what the record's own `bps_2020_ancestors.codes` carries (`expect`), and where it says more
(a split, a reused number) the BPS Lampiran 10 edge that carries it (`expect_bps_edges`, read from
`data/kbli-filiera/bps-crosswalk/edges-lampiran10.json`). A sentence cannot outlive the fact it states: a moved
ancestor list or a missing edge is a refusal, before anything is written.

Surfaces: canonical (`intel_2026.whatChanged`, then `scripts/sync_kbli_dataset.sh` carries it to the tracked copies
and the version sidecar, as the 90200 cure does) and the website's gold layer (`apps/mouth/data/kbli-gold-all.json`,
which wins over canonical for 46100, 60103 and 60203). The website draws either only where the code's PMA verdict is
verified (`discloseKbliEditorial`); none of the nine is today, so there the sentence waits behind that gate. The
knowledge graph is `kg_cure_d1_whatchanged.py`, run after the merge against the live database.

Hardening is `_hardened_cure_io`: the whole-record `old_sha256` pin (`new_sha256` for the idempotent no-op), atomic
writes, and `verify_untouched` (only `intel_2026.whatChanged` of the nine codes may move). Gold is checked the same
way by hand: every other gold entry and every other gold field is compared before and after.

Dry-run is the default; nothing is written without --apply.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parent)
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import _hardened_cure_io as H  # noqa: E402
from cure_canonical_90200_whatchanged import CANONICAL, verify_fleet  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
SPEC_PATH = (
    Path(__file__).resolve().parent / "cure_specs" / "d1_whatchanged_2026_10_11.json"
)
CODE_FIELD = "kode_kbli_2025"
FIELD = "intel_2026.whatChanged"

EXIT_OK = 0
EXIT_REFUSED = 2

CureError = H.CureError


def plan_canonical(
    spec: dict, records: list[dict], edges: set[tuple[str, str]]
) -> dict[str, str]:
    """Pure. {code: new text} for the records still to cure; raises CureError on any drift or missing fact."""
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    todo: dict[str, str] = {}
    for entry in spec["canonical"]:
        code = entry["code"]
        rec = by_code.get(code)
        if rec is None:
            raise CureError(f"{code}: not in canonical")
        for path, want in entry["expect"].items():
            if not H.has_field(rec, path) or H.read_field(rec, path) != want:
                raise CureError(
                    f"{code}: expect[{path}]={want!r} but the record holds "
                    f"{H.read_field(rec, path) if H.has_field(rec, path) else 'nothing'!r} — refusing"
                )
        for a, b in entry.get("expect_bps_edges", []):
            if (a, b) not in edges:
                raise CureError(
                    f"{code}: the sentence rests on the BPS edge {a} -> {b}, absent from the edges file"
                )
        if set(entry["patch"]) != {FIELD}:
            raise CureError(
                f"{code}: the spec may patch {FIELD} only, not {sorted(entry['patch'])}"
            )
        if (
            H.judge_patch(rec, entry["old_sha256"], entry.get("new_sha256"), code=code)
            == "patch"
        ):
            if H.read_field(rec, FIELD) != entry["old_text"]:
                raise CureError(
                    f"{code}: hash matched old_sha256 but {FIELD} is not old_text — refusing"
                )
            todo[code] = entry["patch"][FIELD]
    return todo


def plan_gold(spec: dict, gold: dict) -> dict[str, str]:
    """Pure. {code: new text} for the gold entries still to cure; refuses a live text that is neither old nor new."""
    todo: dict[str, str] = {}
    for entry in spec["gold"]:
        code, field = entry["code"], entry["field"]
        live = (gold.get(code) or {}).get(field)
        if live == entry["new"]:
            continue
        if live != entry["old"]:
            raise CureError(
                f"gold {code}.{field}: the live text is neither the pinned old nor the new one — refusing"
            )
        todo[code] = entry["new"]
    return todo


def _edges(path: Path) -> set[tuple[str, str]]:
    return {
        (e["kbli_2020"], e["kbli_2025"])
        for e in json.loads(path.read_text(encoding="utf-8"))
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--dataset", default=str(CANONICAL))
    ap.add_argument("--gold", default=str(GOLD))
    ap.add_argument("--spec", default=str(SPEC_PATH))
    args = ap.parse_args(argv)

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    path, gold_path = Path(args.dataset), Path(args.gold)
    try:
        payload, records, original = H.load_dataset(path)
        canon_todo = plan_canonical(
            spec, records, _edges(REPO_ROOT / spec["edges_file"])
        )
        gold_text = gold_path.read_text(encoding="utf-8")
        gold = json.loads(gold_text)
        gold_todo = plan_gold(spec, gold)
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    for code, text in canon_todo.items():
        print(f"canonical {code}: {FIELD} -> {text!r}")
    for code, text in gold_todo.items():
        print(f"gold {code}: whatChanged -> {text!r}")
    if not canon_todo and not gold_todo:
        print("all nine already cured — no-op")
    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK

    if canon_todo:
        before = copy.deepcopy(records)
        by_code = {str(r.get(CODE_FIELD)): r for r in records}
        for code, text in canon_todo.items():
            H.write_field(by_code[code], FIELD, text)
        try:
            H.verify_untouched(
                before,
                records,
                CODE_FIELD,
                touched_codes=set(canon_todo),
                touched_field_paths={c: {FIELD} for c in canon_todo},
            )
        except CureError as exc:
            print(f"REFUSED (untouched_fields): {exc}")
            return EXIT_REFUSED
        H.atomic_write_text(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2)
            + ("\n" if original.endswith("\n") else ""),
        )
        fresh = {str(r.get(CODE_FIELD)): r for r in H.load_dataset(path)[1]}
        wrong = [c for c, t in canon_todo.items() if H.read_field(fresh[c], FIELD) != t]
        if wrong:
            print(f"canonical WROTE BUT READ BACK WRONG on: {wrong}")
            return EXIT_REFUSED

    if gold_todo:
        before_gold = copy.deepcopy(gold)
        for code, text in gold_todo.items():
            gold[code]["whatChanged"] = text
        moved = {
            c for c in set(before_gold) | set(gold) if before_gold.get(c) != gold.get(c)
        }
        stray = [
            c
            for c in moved
            if c not in gold_todo
            or {
                k
                for k in set(before_gold[c]) | set(gold[c])
                if before_gold[c].get(k) != gold[c].get(k)
            }
            != {"whatChanged"}
        ]
        if stray:
            print(f"REFUSED (gold untouched_fields): {sorted(stray)}")
            return EXIT_REFUSED
        H.atomic_write_text(
            gold_path,
            json.dumps(gold, ensure_ascii=False, indent=2)
            + ("\n" if gold_text.endswith("\n") else ""),
        )
        again = json.loads(gold_path.read_text(encoding="utf-8"))
        wrong = [c for c, t in gold_todo.items() if again[c].get("whatChanged") != t]
        if wrong:
            print(f"gold WROTE BUT READ BACK WRONG on: {wrong}")
            return EXIT_REFUSED

    print("\napplied and verified on re-read")
    if path.resolve() != CANONICAL.resolve():
        print(f"not canonical ({path}) — skipping consumer propagation")
        return EXIT_OK
    problems, repaired = verify_fleet(repair=True)
    for p in problems:
        print(f"  FLEET PROBLEM: {p}")
    if problems:
        return EXIT_REFUSED
    if repaired:
        print(f"repaired {repaired} stale fleet artifact(s)")
    print("consumer copies in sync with canonical")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
