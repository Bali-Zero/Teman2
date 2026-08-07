#!/usr/bin/env python3
"""One-shot: replace the 86101 gold card — it described the wrong hospital.

WHAT WAS WRONG
--------------
`apps/mouth/data/kbli-gold-all.json`'s entry for 86101 (Aktivitas Rumah Sakit
Pemerintah — canonical: TERTUTUP, `pma_max_asing` 0) narrated a PRIVATE general
hospital: "Terbuka — 100% foreign ownership", "IDR 100 billion minimum
investment", a nine-step PT PMA incorporation walkthrough, and it pointed the
reader at "86102 (Specialty Hospital)" as the easier PMA entry. Both premises
are wrong on the record: 86101 is government-operated and closed to PMA, and
86102 in KBLI 2025 is Puskesmas (a community health centre), not a specialty
hospital. A foreign investor reading this card would plan a company around a
code the record forbids them, then be misdirected to the wrong sibling code
for a second time.

SIX FIELDS, ONE SOURCE OF TRUTH
--------------------------------
The replacement text was adjudicated externally (cross-family review, then the
orchestrator's own final gate) and is implemented VERBATIM here — this module
does not author prose, it applies six pinned old->new pairs from
`cure_specs/gold_86101_government_hospital_2026_08_07.json`. Two claims the
reviewing pass proposed were REJECTED before this spec was written and are
deliberately absent from the new text: government hospitals' BLU/BLUD status,
and a Class C/D private-hospital prohibition — neither is sourced on this
record or anywhere in this repo's vaulted evidence. The old text's own IDR 100
billion figure is dropped for the identical reason: unsourced on this record.

`tkaInfo` and every field not named in the spec is left untouched — this is a
six-field replacement, not a record rewrite.

THE ARCHIVE
-----------
The spec file itself carries BOTH `old` and `new` for every field — it is the
archive, not a separate output this tool writes. The pre-cure prose is
therefore recoverable two ways: the spec file (which stays in the repo,
unlike a build artifact) and, once this commits, the pre-cure blob in git
history. Nothing here overwrites `cure_specs/*`; the spec is read-only input.

REFUSES, LOUDLY, RATHER THAN GUESSING
---------------------------------------
Aborts before writing anything if: the code is missing from gold; the spec
names a field the record does not carry; a field's LIVE text does not match
the spec's pinned `old` (someone else already touched it, or the world moved
under the adjudication) UNLESS it already reads as `new` (idempotent, not a
failure); or a field named in the spec is not a string.

THE FACTS-BASIS GUARD (round-4 review, 2026-08-07)
----------------------------------------------------
Everything above checks that gold's OWN text matches the spec's `old`/`new`
pins — it never checked the spec's premise: `facts_basis` names two live
canonical facts the whole card rests on (86101 government-operated/closed;
86103 the open private-hospital routing target), and neither was verified
against canonical before writing. A cure can be textually consistent with
its own spec while the spec's premise has quietly gone stale underneath it
— re-adjudication, a canonical fix, a later cure touching either code — and
this compiler would have applied 2026-08-07's adjudicated text over a world
that no longer matches it. `assert_facts_basis()` reads canonical directly
and refuses, naming the drifted fact, BEFORE `plan()` runs — so this also
gates the idempotent-noop path, not just a fresh write.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
CANONICAL_PATH = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC_PATH = Path(__file__).resolve().parent / "cure_specs" / "gold_86101_government_hospital_2026_08_07.json"

EXIT_OK = 0
EXIT_REFUSED = 2


class CureError(RuntimeError):
    """A refusal. Never downgraded to a warning."""


def load_gold(path: Path) -> tuple[dict, dict, str]:
    text = path.read_text(encoding="utf-8")
    raw = json.loads(text)
    data = raw.get("data", raw) if isinstance(raw, dict) else raw
    return raw, data, text


def load_canonical(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    if not isinstance(records, list):
        raise CureError(f"{path}: expected a canonical record list")
    return records


def assert_facts_basis(canonical_records: list[dict]) -> None:
    """The whole card rests on two live canonical facts, named verbatim in
    the spec's own `facts_basis.canonical_titles_and_verdicts`: 86101 is
    government-operated and closed to PMA; 86103 is the open private-hospital
    routing target. If either has drifted since the spec was adjudicated —
    re-adjudication, a canonical fix, an unrelated cure touching either code
    — this compiler must refuse rather than apply text written for a world
    that no longer exists. Runs before `plan()`, so it gates the
    idempotent-noop path too, not only a fresh write."""
    by_code = {str(r.get("kode_kbli_2025")): r for r in canonical_records}

    gov = by_code.get("86101")
    if gov is None:
        raise CureError("86101: not in canonical — the facts_basis premise cannot be checked")
    if gov.get("pma_status") != "TERTUTUP" or gov.get("pma_max_asing") != 0:
        raise CureError(
            "86101: facts_basis premise drifted — expected canonical "
            "pma_status='TERTUTUP'/pma_max_asing=0 (government-operated, closed "
            f"to PMA), found pma_status={gov.get('pma_status')!r}/"
            f"pma_max_asing={gov.get('pma_max_asing')!r}. The card's premises "
            "changed — re-adjudicate, do not apply."
        )

    priv = by_code.get("86103")
    if priv is None:
        raise CureError("86103: not in canonical — the facts_basis premise cannot be checked")
    if priv.get("pma_status") != "TERBUKA" or priv.get("pma_max_asing") != 100:
        raise CureError(
            "86103: facts_basis premise drifted — expected canonical "
            "pma_status='TERBUKA'/pma_max_asing=100 (the card's PMA routing "
            f"target), found pma_status={priv.get('pma_status')!r}/"
            f"pma_max_asing={priv.get('pma_max_asing')!r}. The card's premises "
            "changed — re-adjudicate, do not apply."
        )


def plan(spec: dict, gold: dict) -> dict:
    """Pure. Returns the per-field verdicts or raises CureError on a bad
    precondition. Every field is judged independently so a partial prior
    application (idempotent re-run) is distinguishable from real drift."""
    code = spec["code"]
    rec = gold.get(code)
    if rec is None:
        raise CureError(f"{code}: not in gold — nothing to replace")

    verdicts: dict[str, dict] = {}
    for field, pair in spec["fields"].items():
        if field not in rec:
            raise CureError(f"{code}.{field}: the spec names a field this record does not carry")
        live = rec[field]
        if not isinstance(live, str):
            raise CureError(f"{code}.{field}: not a string field — refusing to touch it")
        if live == pair["new"]:
            verdicts[field] = {"action": "noop", "reason": "already cured"}
        elif live == pair["old"]:
            verdicts[field] = {"action": "patch", "new": pair["new"]}
        else:
            raise CureError(
                f"{code}.{field}: live text matches neither the pinned `old` nor "
                f"the pinned `new` — it moved under the adjudication, re-derive "
                f"before writing"
            )
    return verdicts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--gold", default=str(GOLD_PATH))
    ap.add_argument("--spec", default=str(SPEC_PATH))
    ap.add_argument("--canonical", default=str(CANONICAL_PATH))
    args = ap.parse_args(argv)

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    gold_path = Path(args.gold)

    try:
        raw, gold, original = load_gold(gold_path)
        canonical_records = load_canonical(Path(args.canonical))
        assert_facts_basis(canonical_records)
        verdicts = plan(spec, gold)
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    code = spec["code"]
    to_patch = {f: v for f, v in verdicts.items() if v["action"] == "patch"}
    noop = [f for f, v in verdicts.items() if v["action"] == "noop"]
    print(f"{code}: {len(to_patch)} field(s) to patch, {len(noop)} already cured")
    for field in to_patch:
        print(f"  {field}: replaced ({len(spec['fields'][field]['old'])} chars -> {len(spec['fields'][field]['new'])} chars)")
    for field in noop:
        print(f"  {field}: already cured — no-op")

    if not to_patch:
        print("nothing to patch")
        return EXIT_OK

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK

    rec = gold[code]
    for field, v in to_patch.items():
        rec[field] = v["new"]

    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
        raw["data"] = gold
    else:
        raw = gold
    body = json.dumps(raw, ensure_ascii=False, indent=2)
    gold_path.write_text(body + ("\n" if original.endswith("\n") else ""), encoding="utf-8")

    # Read back and prove the write, rather than trusting that it happened.
    _, again, _ = load_gold(gold_path)
    after = again[code]
    wrong = [f for f in to_patch if after.get(f) != spec["fields"][f]["new"]]
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on: {wrong}")
        return EXIT_REFUSED
    print(f"\napplied and verified on re-read: {code} ({len(to_patch)} field(s))")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
