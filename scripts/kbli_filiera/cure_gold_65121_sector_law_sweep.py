#!/usr/bin/env python3
"""One-shot: sweep unverified capital figures out of 65121's WHOLE gold entry
and align its acquisition-only PMA framing with the corrected sector-law cap.

WHAT WAS WRONG
--------------
65121 (Asuransi Jiwa Konvensional) named specific capital figures — "IDR 100
billion" OJK paid-up capital, "IDR 10B" PT PMA stated capital — across THREE
gold fields (zantaraOpener, whatYouNeed, baliContext), nine occurrences
total. `cure_gold_paidup_capital.py` deliberately EXCLUDES 65121
(`REFUSAL_NOTE["65121"]`: "OJK paid-up + PT PMA STATED capital — the two are
already separated") because its automatic mechanism cannot safely
distinguish the two capital concepts here — that exclusion means the figures
were never machine-verified, not that they were confirmed correct. POJK
23/2023 (OJK's minimum-capital schedule for insurers) has not been
primary-fetched in this session or, so far as this cure can tell, any prior
one. The hard rule (2026-08-08 sector-law brief, item 2): NO capital figures
anywhere in cards without a verified primary source — soften to "confirm
with OJK" language, keep the substance (there IS a high capital bar, an OJK
license gate, and a lower-capital agency alternative), drop the number.

`baliContext`'s acquisition line also still framed the 80% cap as
"historically ... for acquisitions" — pre-dating this PR's
`cure_canonical_asuransi_pp14_cap.py` cure, which established the cap is
GENERAL (PP 14/2018 Pasal 5(1)), not acquisition-specific. That line is
corrected here too. (The closing "**PMA:**" sentence in whatYouNeed itself
was already corrected by `cure_gold_pma_line.py::AUTHORED_SENTENCES["65121"]`
— a disjoint substring; this sweep never touches it.)

HARDENING (item 6, 2026-08-08 ledger)
--------------------------------------
The spec pins `old_sha256` against the WHOLE 65121 gold record (all six
fields) as observed when this cure was authored, so any drift anywhere in
the record — including a field this sweep does not edit — is refused rather
than silently overwritten. Atomic write (tmp+rename). After patching in
memory, every OTHER code in the gold file is asserted byte-identical, and
65121 itself is asserted to differ ONLY on the fields the spec's edits name.

Each edit is an exact-substring old/new pair, applied like
`cure_gold_pma_line.py::AUTHORED_SENTENCES` — idempotent per edit (already
applied = skip, not failure) and refuses loudly if an edit's `old` text is
gone from the live field without the `new` text having taken its place
(someone already rewrote that sentence differently).

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

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
SPEC_PATH = (
    Path(__file__).resolve().parent
    / "cure_specs"
    / "gold_65121_sector_law_sweep_2026_08_08.json"
)

EXIT_OK = 0
EXIT_REFUSED = 2

CureError = H.CureError


def load_gold(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise CureError(f"{path}: expected a dict keyed by KBLI code")
    return payload, text


def plan(spec: dict, gold: dict) -> dict:
    """Pure. {"action": "patch"|"noop", "fields": {field: new_text}} or
    raises CureError. Judges the record's full-body hash first (drift
    anywhere in the record refuses), then walks each edit independently."""
    code = spec["code"]
    rec = gold.get(code)
    if rec is None:
        raise CureError(f"{code}: not in gold — nothing to sweep")

    current_hash = H.sha256_of(rec)
    if current_hash != spec["old_sha256"]:
        # Could still be a partial-apply (idempotent resume) — check whether
        # every edit's `new` text is already present; if so, treat as noop
        # rather than guessing at a drift that is actually just "done".
        if all(
            e["new"] in (rec.get(e["field"]) or "") for e in spec["edits"]
        ):
            return {"action": "noop", "reason": "already cured (all edits present)"}
        raise CureError(
            f"{code}: live record hashes to {current_hash!r}, not the pinned "
            f"old_sha256 {spec['old_sha256']!r} — the record drifted under "
            "this adjudication; re-derive before writing, do not overwrite blind"
        )

    fields: dict[str, str] = {}
    for edit in spec["edits"]:
        field = edit["field"]
        live = fields.get(field, rec.get(field))
        if live is None:
            raise CureError(f"{code}.{field}: field is gone — the pin is stale")
        if edit["old"] not in live:
            if edit["new"] in live:
                continue  # this edit already applied — idempotent, not a failure
            raise CureError(
                f"{code}.{field}: the pinned sentence is not in the live text "
                "— it was authored against a paragraph that has since moved; "
                "re-read it before re-pinning:\n  " + edit["old"][:120]
            )
        fields[field] = live.replace(edit["old"], edit["new"], 1)

    if not fields:
        return {"action": "noop", "reason": "already cured (all edits present)"}
    return {"action": "patch", "fields": fields}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--dataset", default=str(GOLD_PATH))
    ap.add_argument("--spec", default=str(SPEC_PATH))
    args = ap.parse_args(argv)

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    path = Path(args.dataset)
    code = spec["code"]

    try:
        gold, original = load_gold(path)
        verdict = plan(spec, gold)
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    if verdict["action"] == "noop":
        print(f"{code}: already cured — no-op")
        return EXIT_OK

    for field in sorted(verdict["fields"]):
        print(f"{code}.{field}: {len([e for e in spec['edits'] if e['field'] == field])} edit(s)")

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK

    before = copy.deepcopy(gold)
    for field, new_text in verdict["fields"].items():
        gold[code][field] = new_text

    # untouched_fields: every OTHER code byte-identical; 65121 itself may
    # differ only on the fields this plan actually touched.
    if set(before) != set(gold):
        raise CureError("untouched_fields: the code population itself changed")
    for other_code, before_rec in before.items():
        if other_code == code:
            continue
        if H.sha256_of(before_rec) != H.sha256_of(gold[other_code]):
            print(f"REFUSED (untouched_fields): {other_code!r} changed and was never named")
            return EXIT_REFUSED
    changed_fields = {
        k for k in before[code] if before[code].get(k) != gold[code].get(k)
    }
    extra = changed_fields - set(verdict["fields"])
    if extra:
        print(f"REFUSED (untouched_fields): 65121 changed undeclared field(s) {sorted(extra)}")
        return EXIT_REFUSED

    body = json.dumps(gold, ensure_ascii=False, indent=2)
    H.atomic_write_text(path, body + ("\n" if original.endswith("\n") else ""))

    fresh, _ = load_gold(path)
    wrong = [f for f, v in verdict["fields"].items() if fresh[code].get(f) != v]
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on: {wrong}")
        return EXIT_REFUSED
    print("\napplied and verified on re-read")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
