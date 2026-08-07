#!/usr/bin/env python3
"""One-shot: 90200's gold whatChanged said "new code, no 2020 equivalent" —
canonical's own bps_2020_ancestors field says otherwise.

WHAT WAS WRONG
--------------
`apps/mouth/data/kbli-gold-all.json`'s entry for `90200` (Aktivitas Seni
Pertunjukan) carried `whatChanged`: "New in KBLI 2025 — no equivalent in
KBLI 2020. Register fresh on OSS." Canonical's own `bps_2020_ancestors` field
for this record names FOUR 2020 ancestor codes (`90011`, `90021`, `90022`,
`90024` — performing-arts activities and venues), so the card asserted the
opposite of what the structured data already records. A holder of any of
those four 2020 codes reading this card would conclude nothing carries
forward, instead of being told this IS their code now (a merge, KBLI 2025
"MATCH_CON_AGGREGAZIONE" shape). Same class of defect as the 86101 cure
(`cure_gold_86101_government_hospital.py`): editorial prose contradicting a
structured field on the SAME record.

ONE FIELD, ONE SOURCE OF TRUTH
--------------------------------
Spec-driven, same pattern as the 86101 cure: the replacement text is pinned
verbatim in `cure_specs/gold_90200_whatchanged_merged_2026_08_07.json` — this
module applies the pinned old->new pair, it does not author prose. Every
other field on the record (`whatItMeans`, `whatYouNeed`, `zantaraOpener`,
`baliContext`, `youllAlsoNeed`, `tkaInfo`) is untouched.

THE FACTS-BASIS GUARD
------------------------
`assert_facts_basis()` reads canonical directly and refuses if 90200's
`bps_2020_ancestors.codes` no longer names exactly those four codes — a
re-adjudication or a canonical fix could otherwise leave this cure applying
2026-08-07's premise over a world that has moved. Runs before `plan()`, so it
also gates the idempotent-noop path, not just a fresh write.

REFUSES, LOUDLY, RATHER THAN GUESSING
----------------------------------------
Aborts before writing anything if: the code is missing from gold; the spec
names a field the record does not carry; the field's LIVE text does not
match the spec's pinned `old` (unless it already reads as `new` —
idempotent, not a failure); or the field is not a string.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
CANONICAL_PATH = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC_PATH = (
    Path(__file__).resolve().parent
    / "cure_specs"
    / "gold_90200_whatchanged_merged_2026_08_07.json"
)

EXIT_OK = 0
EXIT_REFUSED = 2

EXPECTED_ANCESTORS = ["90011", "90021", "90022", "90024"]


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
    """The card's premise is canonical's own `bps_2020_ancestors.codes` for
    90200. If it has drifted from the four codes this cure names, the
    adjudicated text no longer describes the record — refuse rather than
    apply stale prose."""
    by_code = {str(r.get("kode_kbli_2025")): r for r in canonical_records}
    rec = by_code.get("90200")
    if rec is None:
        raise CureError("90200: not in canonical — the facts_basis premise cannot be checked")
    ancestors = rec.get("bps_2020_ancestors") or {}
    codes = [str(c) for c in (ancestors.get("codes") or [])]
    if codes != EXPECTED_ANCESTORS:
        raise CureError(
            "90200: facts_basis premise drifted — expected "
            f"bps_2020_ancestors.codes == {EXPECTED_ANCESTORS}, found "
            f"{codes!r}. The card's premise changed — re-adjudicate, do not "
            "apply."
        )


def plan(spec: dict, gold: dict) -> dict:
    """Pure. Returns the per-field verdicts or raises CureError on a bad
    precondition."""
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
                f"{code}.{field}: live text matches neither the pinned `old` "
                f"nor the pinned `new` — it moved under the adjudication, "
                f"re-derive before writing"
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
