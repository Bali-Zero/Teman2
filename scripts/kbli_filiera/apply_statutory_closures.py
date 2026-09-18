#!/usr/bin/env python3
"""Relabel the statutory closures from ``declared_gap`` to ``located``.

WHAT THIS CHANGES, AND WHAT IT DOES NOT
----------------------------------------
59 canonical records are published ``TERTUTUP`` / 0% and were, until this
compiler, ``declared_gap``: the page said "foreign ownership not yet verified"
about a code the statute closes by name or by kind. The 2026-09-18 dossier
(``research/kbli/2026-09-18-kbli-codes-closed-to-pma-tier1-tier2-dossier.md``
§3.1-3.2) traced every one of them to an instrument, and Zero ruled the label
``located`` for every class. This compiler writes that label and the basis.

It changes NO verdict and NO cap. A record that is not already ``TERTUTUP``/0
is REFUSED, never flipped: 87101, 88101, 88901 carry «Pemerintah» in their
title and are published TERBUKA 100%, and 11030 is the 2025 heir of the
Perpres-named 11031 and is published TERBUKA 100% — each is a Legge 5 decision,
named in the spec's ``excluded`` and left untouched here.

ONE MECHANICAL LEG PER CLASS, RE-DERIVED FROM THE CANONICAL
-----------------------------------------------------------
* ``instrument_names_code`` — the Perpres names a 2020 code; the record's sole
  ``bps_2020_ancestors`` entry must be that code with ``sebagian`` false.
* ``statute_item_by_title`` — the statute item's operative noun must be in the
  record's title.
* ``government_activity`` — the code sits under 84 or the title carries
  «Pemerintah» as a whole word; AND the rule's whole canonical population must
  be either an item or a named exclusion (both directions), so a code the rule
  reaches cannot be silently left out, and an exclusion cannot hide a code that
  should have been an item.
* ``non_commercial_institutional`` — the title names the class.

The basis string states the derivation. For the title-derived classes it says
so in words — «no instrument maps the 5-digit code» — because a reader who
takes «located» to mean «named by an instrument» would be misled otherwise.

Usage (dry-run is the default; nothing is written without --apply):
  python3 scripts/kbli_filiera/apply_statutory_closures.py
  python3 scripts/kbli_filiera/apply_statutory_closures.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

from apply_umkm_reservations import (  # noqa: E402
    CANONICAL,
    CURE_SPECS,
    EXIT_OK,
    EXIT_REFUSED,
    load,
    propagate,
)

SPEC = CURE_SPECS / "statutory_closures_naso_2026_09_18.json"
CLASSES = (
    "instrument_names_code",
    "statute_item_by_title",
    "government_activity",
    "non_commercial_institutional",
)
TITLE_DERIVED = "title-derived: no instrument maps the 5-digit code"


def _title(record: dict[str, Any]) -> str:
    return str(record.get("judul") or "")


def basis_for(cls: str, item: dict[str, Any], record: dict[str, Any]) -> str:
    title = _title(record)
    if cls == "instrument_names_code":
        return (
            f"Perpres 10/2021 Pasal 2(2)(b) (as amended by Perpres 49/2021) names "
            f'"{item["named_as"]}" among the Bidang Usaha tertutup; KBLI-2025 '
            f"{item['code']} inherits KBLI-2020 {item['named_2020_code']} whole "
            f"(sole BPS ancestor, not partial), so the closure is the whole code; "
            f"closed to all Penanaman Modal, max foreign 0%."
        )
    if cls == "statute_item_by_title":
        return (
            f"UU 25/2007 Pasal 12(2) as replaced by UU 6/2023 Pasal 77 item 2, "
            f"{item['statute_item']}, incorporated by Perpres 10/2021 Pasal 2(2)(a) — "
            f'matched by the record\'s title "{title}" ({TITLE_DERIVED}); '
            f"closed to all Penanaman Modal, max foreign 0%."
        )
    if cls == "government_activity":
        leg = (
            "the code sits under KBLI 84 (Administrasi Pemerintahan, Pertahanan dan "
            "Jaminan Sosial Wajib)"
            if item["leg"] == "prefix_84"
            else f'the title "{title}" names the activity as carried out by the Pemerintah'
        )
        return (
            f"Perpres 10/2021 Pasal 2(1)(b) + 2(3) (as amended by Perpres 49/2021): "
            f"activities of the Pemerintah Pusat are outside the open fields, and "
            f"Pasal 2(1a) confines the open fields to Bidang Usaha yang bersifat "
            f"komersial — {leg} ({TITLE_DERIVED}); not an investable field, "
            f"max foreign 0%."
        )
    return (
        f"Perpres 10/2021 Pasal 2(1a) (as amended by Perpres 49/2021): the open "
        f'fields are Bidang Usaha yang bersifat komersial, and "{title}" is the '
        f"activity of international and extraterritorial bodies, not a commercial "
        f"field ({TITLE_DERIVED}); not an investable field, max foreign 0%."
    )


def patch_for(
    cls: str, spec: dict[str, Any], item: dict[str, Any], record: dict
) -> dict:
    return {
        "pma_status": "TERTUTUP",
        "pma_max_asing": 0,
        "pma_verification_status": "located",
        "pma_official_basis": basis_for(cls, item, record),
        "pma_source_vintage": spec["vintage"],
        "pma_cap_verified": True,
        "pma_kondisi": spec["classes"][cls]["kondisi"],
    }


def _leg_holds(
    cls: str, item: dict[str, Any], record: dict[str, Any], rule: dict
) -> str | None:
    title = _title(record)
    if cls == "instrument_names_code":
        if f"(KBLI {item['named_2020_code']})" not in item["named_as"]:
            return f"spec names {item['named_as']!r} but claims 2020 code {item['named_2020_code']}"
        anc = record.get("bps_2020_ancestors") or {}
        codes = list(anc.get("codes") or [])
        partial = list(anc.get("sebagian") or [])
        if codes != [item["named_2020_code"]] or partial != [False]:
            return f"2020 ancestry is {codes}/{partial}, not sole whole {item['named_2020_code']}"
        return None
    if cls in ("statute_item_by_title", "non_commercial_institutional"):
        missing = [t for t in item["title_terms"] if t.lower() not in title.lower()]
        if missing:
            return f"title {title!r} lacks {missing}"
        return None
    if cls == "government_activity":
        if item["leg"] == "prefix_84":
            if not item["code"].startswith(rule["prefix"]):
                return f"leg prefix_84 but code does not start with {rule['prefix']}"
        elif item["leg"] == "title_pemerintah":
            if not re.search(rule["title_regex"], title):
                return f"leg title_pemerintah but title {title!r} does not match"
        else:
            return f"unknown leg {item['leg']!r}"
        return None
    return f"unknown class {cls!r}"


def _population(rule: dict[str, Any], records: list[dict[str, Any]]) -> set[str]:
    rx = re.compile(rule["title_regex"])
    return {
        str(r["kode_kbli_2025"])
        for r in records
        if str(r["kode_kbli_2025"]).startswith(rule["prefix"]) or rx.search(_title(r))
    }


def check(
    spec: dict[str, Any], records: list[dict[str, Any]]
) -> tuple[list[tuple[str, dict]], list[str]]:
    """Return (todo as (class, item), refusals). Any refusal blocks the write."""
    by_code = {str(r["kode_kbli_2025"]): r for r in records}
    todo: list[tuple[str, dict]] = []
    refusals: list[str] = []
    seen: set[str] = set()

    for cls in CLASSES:
        block = spec["classes"][cls]
        rule = block.get("rule", {})
        for item in block["items"]:
            code = str(item["code"])
            if code in seen:
                refusals.append(f"{code}: listed twice")
                continue
            seen.add(code)
            record = by_code.get(code)
            if record is None:
                refusals.append(f"{code}: not in canonical")
                continue
            if (
                record.get("pma_status") != "TERTUTUP"
                or record.get("pma_max_asing") != 0
            ):
                refusals.append(
                    f"{code}: published {record.get('pma_status')}/"
                    f"{record.get('pma_max_asing')} — this compiler relabels, it never flips"
                )
                continue
            why = _leg_holds(cls, item, record, rule)
            if why:
                refusals.append(f"{code}: {why}")
                continue
            want = patch_for(cls, spec, item, record)
            state = record.get("pma_verification_status")
            if state == "located":
                if record.get("pma_official_basis") != want["pma_official_basis"]:
                    refusals.append(f"{code}: already located under a different basis")
                continue
            if state != "declared_gap":
                refusals.append(
                    f"{code}: verification state {state!r} is neither known value"
                )
                continue
            todo.append((cls, item))

        excluded = set(block.get("excluded", {}))
        for code in excluded & {str(i["code"]) for i in block["items"]}:
            refusals.append(f"{code}: both an item and an exclusion of {cls}")
        if rule:
            population = _population(rule, records)
            listed = {str(i["code"]) for i in block["items"]}
            for code in sorted(population - listed - excluded):
                refusals.append(
                    f"{code}: reached by the {cls} rule but neither item nor exclusion"
                )
            for code in sorted((listed | excluded) - population):
                refusals.append(
                    f"{code}: listed under {cls} but the rule does not reach it"
                )
            for code in sorted(excluded & population):
                r = by_code[code]
                if r.get("pma_status") == "TERTUTUP" and r.get("pma_max_asing") == 0:
                    refusals.append(
                        f"{code}: excluded from {cls} yet already TERTUTUP/0 — an eligible "
                        f"code needs a reason the spec does not give"
                    )
    return todo, refusals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--dataset", default=str(CANONICAL))
    ap.add_argument("--spec", default=str(SPEC))
    args = ap.parse_args(argv)

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    path = Path(args.dataset)
    payload, records, original = load(path)

    todo, refusals = check(spec, records)
    total = sum(len(spec["classes"][c]["items"]) for c in CLASSES)
    already = total - len(todo) - len(refusals)
    print(
        f"spec items {total} · applicable {len(todo)} · already applied {already} · "
        f"refused {len(refusals)}"
    )
    for cls in CLASSES:
        print(
            f"  excluded by {cls}: {sorted(spec['classes'][cls].get('excluded', {}))}"
        )
    for r in refusals:
        print(f"  REFUSE {r}")
    if refusals:
        print(
            "\nrefusing to write: a spec wrong about one code is not trusted for the rest"
        )
        return EXIT_REFUSED

    for cls, item in todo:
        print(
            f"  {item['code']} [{cls}]: declared_gap -> located (TERTUTUP/0 unchanged)"
        )

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK
    if not todo:
        print("\nalready applied — clean no-op; nothing written or propagated")
        return EXIT_OK

    by_code = {str(r["kode_kbli_2025"]): r for r in records}
    for cls, item in todo:
        record = by_code[str(item["code"])]
        record.update(patch_for(cls, spec, item, record))

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(body + ("\n" if original.endswith("\n") else ""), encoding="utf-8")

    _, again, _ = load(path)
    fresh = {str(r["kode_kbli_2025"]): r for r in again}
    wrong = [
        i["code"]
        for _, i in todo
        if fresh[str(i["code"])].get("pma_verification_status") != "located"
        or fresh[str(i["code"])].get("pma_status") != "TERTUTUP"
        or fresh[str(i["code"])].get("pma_max_asing") != 0
    ]
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on {len(wrong)}: {wrong[:10]}")
        return EXIT_REFUSED
    print(f"\napplied and verified on re-read: {len(todo)} code(s)")

    if path.resolve() != CANONICAL.resolve():
        print(f"not canonical ({path}) — skipping consumer propagation")
        return EXIT_OK

    problems = propagate()
    for p in problems:
        print(f"  PROPAGATION FAILED: {p}")
    if problems:
        return EXIT_REFUSED
    print("consumer copies in sync with canonical")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
