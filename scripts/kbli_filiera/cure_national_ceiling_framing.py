#!/usr/bin/env python3
"""cure_national_ceiling_framing.py — stop telling a client a nationwide closure
is a Bali problem, and stop printing "100%" next to it.

WHAT IS WRONG
-------------
20 records hold an `l4_bali` verdict that CLOSES the activity while `pma_status`
is `TERBUKA` with `pma_max_asing: 100`. On six of them the closure names a
sectoral instrument at `confidence: HIGH` — `64110` is **Bank Sentral, i.e. Bank
Indonesia**; `86201`/`86202` are solo doctor and specialist practice, closed to
foreign nationals under Kemenkes health law; `38122` is radioactive-waste
collection, reserved to the State and BAPETEN.

The page renders that as two separate lies stacked on one screen:

  1. `intel_2026.editorial.byTheNumbers` — stat cards that live IN THE DATA, not
     in a component — prints `Foreign-ownership ceiling · 100%`. That number
     traces to `pma_source: "Perpres 10/2021, 49/2021"`, which is the
     ABSENCE-FROM-THE-ANNEX default fill, not a permission anybody granted. On
     the central bank it is an assertion nobody can stand behind.

  2. The prose scopes the ban to Bali. `86201` reads "Independent general medical
     care may be nationally foreign-open, but a foreign doctor cannot register a
     solo practice **in Bali**", while the record's own reason carries no
     geographic qualifier at all. A foreign doctor reads that and concludes
     "then I will open it in Jakarta".

The second one is the expensive direction: the first merely overstates, the
second actively routes a client toward a registration that will be refused.

WHY EVERY REPLACEMENT WAS RE-AUTHORED
-------------------------------------
A first authoring round was refuted by an independent cross-family seat on 16 of
18 codes, and most objections were real: replacements asserted "nationally" where
the reason gave no scope, strengthened "reserved to the State (BUMN) and BAPETEN"
into "State monopoly", deleted true zoning and licensing facts to fix an
ownership sentence, and — worst — left a numbered "1. PT PMA incorporation 2. NIB
via OSS" procedure standing directly beneath a sentence saying the activity is
closed to PMA. That last one is the disease reproducing inside its own cure.

Two of its objections were NOT real, and the difference matters, because both
were the grader correctly reading a packet that MY tooling had impoverished
(W107 — the probe can carry the disease it measures):

  * "the field `editorial.headline` does not exist" — it exists; the packet had
    FLATTENED it to `editorial_headline`. All 90 round-1 patches were then
    re-resolved against the real records on disk: 90 of 90 matched exactly once.
  * "the reason cites KBLI 96200, not this record's 96100" — the Perpres 49/2021
    annex is written against KBLI 2020 numbers. Checked against Peraturan BPS
    7/2025 Lampiran 5+10 (2,560 edges): 96200→96100, 96111→96210, 96112→96220,
    79921→79903, 55130→55201, 55193→55203 — every disputed attribution holds.

Two codes were DROPPED rather than cured and are named in the spec's `_meta`:
`86102` (the reason is a *klinik* cap of 67% and the record itself says Puskesmas
are government health posts where "private investment is not applicable" — the
proposed prose still offered a foreign route) and `47112` (the reason speaks of
minimarkets/supermarkets while this code is non-self-service mixed retail).

WHAT IT WILL NOT WRITE
----------------------
`pma_status` and `pma_max_asing` are government-data layers. They are wrong on
these records too, and fixing them is a SEPARATE decision with the four-store
propagation the corner documents (canonical → kbli_documents → Qdrant payload →
inspect cache). This compiler refuses them by name so that a prose lane can never
quietly become a data-layer lane. What ships here is what a reader sees on
`balizero.com/kbli/<code>`; the other surfaces stay wrong until that lane runs,
and that is stated rather than glossed.

FAIL-VISIBLE, NEVER A SILENT GUESS
----------------------------------
A patch applies only when `old` occurs EXACTLY ONCE. Already-applied is
recognised (old absent AND new present) and skipped. Every other state is a
CureError. Percentages in a replacement must be traceable to the record's own
`l4_reason` — an invented number is the failure mode this whole lane exists to
remove.

USAGE (dry-run is the default; nothing is written without --apply):
    python3 scripts/kbli_filiera/cure_national_ceiling_framing.py
    python3 scripts/kbli_filiera/cure_national_ceiling_framing.py --apply
    python3 scripts/kbli_filiera/cure_national_ceiling_framing.py --only 64110 --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("kbli_filiera.cure_national_ceiling_framing")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts/kbli_filiera/cure_specs/national_ceiling_framing.json"
DEFAULT_CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"

# The sibling engine is reached by its PACKAGE path, with the repo root on
# sys.path so that resolves whether this file is imported by the test suite or
# run as a script from an arbitrary cwd.
#
# `scripts/kbli_filiera/` sits on sys.path in script mode, so a flat import and a
# package import of the same FILE yield two distinct module objects — and with
# them two distinct `CureError` classes. A refusal raised through one and caught
# through the other escapes `main`'s `except` and surfaces as a traceback instead
# of the exit-1 a caller reads. Pinned by `test_the_sibling_engine_is_imported_once`.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.kbli_filiera.cure_l4_withdrawn_umkm_prose import (  # noqa: E402
    CureError,
    _dig,
    reconcile_sidecar,
    run_sync_script,
)

SURFACES = ("canonical", "gold")

# Layers this cure may never write: the settled verdict, and the government data
# whose correction is a different lane with a different propagation.
FORBIDDEN_ROOTS = frozenset(
    {
        "l4_bali",
        "per_skala",
        "pma_status",
        "pma_max_asing",
        "pma_source",
        "pp28_sources",
        "bps_2020_ancestors",
        "_l2_source",
    }
)

# A closure worded without a number. `0%` on a card is supportable only when the
# record's own reason says the activity is shut, not merely capped.
CLOSURE_RE = re.compile(
    r"tertutup|dialokasikan|structurally closed|closed to|cannot take|cannot open|"
    r"cannot register|reserved (?:to|for)|exclusive state|state monopoly|not applicable",
    re.IGNORECASE,
)
PCT_RE = re.compile(r"\b(\d{1,3})\s?%")


def split_field(code: str, field: str) -> tuple[str, str]:
    """`canonical:intel_2026.whatItMeans` -> ('canonical', 'intel_2026.whatItMeans').

    The surface lives IN the key rather than in a sibling attribute so that a
    patch cannot name one surface and address the other's field — the shape that
    let round 1's flattened names go unnoticed for a whole grading round.
    """
    surface, sep, path = field.partition(":")
    if not sep:
        raise CureError(
            f"{code}: field {field!r} has no surface prefix. Expected "
            f"'<surface>:<path>' with surface in {SURFACES}."
        )
    if surface not in SURFACES:
        raise CureError(f"{code}: unknown surface {surface!r} in field {field!r}")
    if not path:
        raise CureError(f"{code}: field {field!r} names a surface but no path")
    root = path.split(".")[0].split("[")[0]
    if root in FORBIDDEN_ROOTS:
        raise CureError(
            f"{code}: spec targets {field!r}, and {root!r} is a verdict/government layer this "
            "cure may not write. Prose only — the data layer is a separate lane."
        )
    if surface == "canonical" and not path.startswith("intel_2026."):
        raise CureError(
            f"{code}: canonical patches must address prose under 'intel_2026.', got {path!r}"
        )
    if path.endswith(".label"):
        raise CureError(
            f"{code}: {field!r} targets a stat-card LABEL. This cure corrects what a card "
            "CLAIMS (.value), never what it is called."
        )
    return surface, path


def check_new_percentages(record: dict[str, Any], code: str, patch: dict[str, str]) -> None:
    """Every percentage a replacement INTRODUCES must trace to the record's reason.

    Introduced, not merely present. The first draft convicted any figure in
    `new` and refused 95291, whose replacement copies the existing opening
    sentence — "Nationally, this activity is fully open (100%)" — verbatim and
    changes only what follows it. That is the guard judging the FORM (a digit in
    the new text) instead of the ENTITY (a figure this patch asserts for the
    first time), which is the same defect this whole lane exists to remove.

    A number carried over from `old` is the record's existing claim, and this
    lane deliberately does not touch the ownership DATA layer; a number that
    appears only in `new` is a new assertion and must be supported.

    LIMIT, stated rather than discovered later: this checks the numbers a
    replacement asserts, not whether the sentence around them is true. A cure
    that invents "49%" is caught here; one that misdescribes a real 67% is not,
    and that is what the adversarial grading round is for.
    """
    reason = ((record.get("l4_bali") or {}).get("reason")) or ""
    in_old = {m.group(1) for m in PCT_RE.finditer(patch["old"])}
    introduced = {m.group(1) for m in PCT_RE.finditer(patch["new"])} - in_old
    for num in introduced:
        # As a PERCENTAGE, not as a digit sequence. A bare `num in reason` reads
        # "49" out of "Perpres 49/2021" and lets a regulation number launder an
        # ownership cap — found by this file's own test, and the same form-not-
        # entity defect the lane exists to remove.
        if re.search(rf"\b{num}\s?%|\bmaks?(?:imal)?\.?\s+{num}\b", reason, re.IGNORECASE):
            continue
        if num == "0" and CLOSURE_RE.search(reason):
            continue
        raise CureError(
            f"{code}.{patch['field']}: replacement introduces {num}% but the record's l4_reason "
            "does not support that figure. A cure for invented ownership numbers may not invent "
            "one."
        )


def apply_patch(container: dict[str, Any], code: str, path: str, patch: dict[str, str]) -> bool:
    """Return True if the container changed, False if already applied."""
    # `_dig` always resolves to (owning DICT, final key) — a `name[i]` segment is
    # consumed on the way in, so `byTheNumbers[0].value` hands back the card dict
    # and the key "value". There is no list-owner case to branch on.
    owner, key = _dig(container, path)
    if key not in owner:
        raise CureError(f"{code}.{patch['field']}: field does not exist on this surface")
    text = owner[key]
    if not isinstance(text, str):
        raise CureError(f"{code}.{patch['field']}: holds {type(text).__name__}, not a string")

    old, new = patch["old"], patch["new"]
    if not old.strip():
        raise CureError(f"{code}.{patch['field']}: empty `old` — a patch must name what it replaces")

    n_old, n_new = text.count(old), text.count(new)
    if n_old == 1:
        owner[key] = text.replace(old, new, 1)
        return True
    if n_old == 0 and n_new >= 1:
        logger.info("%s.%s: already applied — skipping", code, patch["field"])
        return False
    raise CureError(
        f"{code}.{patch['field']}: refusing — old occurs {n_old}x, new occurs {n_new}x. "
        "A patch applies only when the old text is present exactly once."
    )


def check_premise(record: dict[str, Any], code: str, entry: dict[str, Any]) -> None:
    """All four pins, because the defect IS the disagreement between two of them.

    The verdict closes the activity while the ownership fields still say it is
    wide open. If either side has moved since the prose was read and graded, the
    replacement describes a record that no longer exists — most sharply if the
    DATA layer has since been corrected, because then a page saying "the national
    position is closed" would be arguing with a `pma_status` that already agrees.
    """
    l4 = record.get("l4_bali") or {}
    want = (
        entry.get("expect_l4_status"),
        entry.get("expect_l4_blocked"),
        entry.get("expect_pma_status"),
        entry.get("expect_pma_max_asing"),
    )
    got = (l4.get("status"), l4.get("blocked"), record.get("pma_status"), record.get("pma_max_asing"))
    if got != want:
        raise CureError(
            f"{code}: premise moved — spec was graded against "
            f"l4=({want[0]!r},{want[1]!r}) pma=({want[2]!r},{want[3]!r}), record now holds "
            f"l4=({got[0]!r},{got[1]!r}) pma=({got[2]!r},{got[3]!r}). Re-read and re-grade rather "
            "than writing prose onto a record it no longer describes."
        )


def load_gold(path: Path) -> dict[str, Any]:
    gold = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(gold, dict):
        raise CureError(f"unexpected gold shape in {path}: {type(gold).__name__}, expected object")
    return gold


def run(spec_path: Path, canonical_path: Path, gold_path: Path,
        only: list[str] | None, apply: bool) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    codes: dict[str, Any] = spec["codes"]
    if only:
        unknown = sorted(set(only) - set(codes))
        if unknown:
            raise CureError(f"--only names codes absent from the spec: {unknown}")
        codes = {c: codes[c] for c in only}

    doc = json.loads(canonical_path.read_text(encoding="utf-8"))
    by_code = {r["kode_kbli_2025"]: r for r in doc["data"]}
    gold = load_gold(gold_path)

    missing = sorted(set(codes) - set(by_code))
    if missing:
        raise CureError(f"spec names codes absent from canonical: {missing}")

    changed = {"canonical": 0, "gold": 0}
    touched, skipped = set(), 0

    for code, entry in codes.items():
        record = by_code[code]
        check_premise(record, code, entry)
        for patch in entry["patches"]:
            surface, path = split_field(code, patch["field"])
            check_new_percentages(record, code, patch)
            if surface == "canonical":
                container = record
            else:
                container = gold.get(code)
                if not isinstance(container, dict):
                    raise CureError(
                        f"{code}: spec names a gold patch but no gold entry exists. The gold "
                        "entry was there when the prose was read — it has been removed since."
                    )
            if apply_patch(container, code, path, patch):
                changed[surface] += 1
                touched.add(code)
            else:
                skipped += 1

    logger.info(
        "%s: %d record(s) touched — %d canonical patch(es), %d gold patch(es), %d already applied",
        "APPLY" if apply else "DRY-RUN",
        len(touched), changed["canonical"], changed["gold"], skipped,
    )
    if not apply:
        logger.info("nothing written — rerun with --apply")
        return 0

    if changed["canonical"]:
        canonical_path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        logger.info("canonical written: %s", canonical_path)
    if changed["gold"]:
        gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info("gold written: %s", gold_path)
    if changed["canonical"]:
        run_sync_script()
    # Keyed on the MISMATCH, not on whether this run changed anything — a no-op
    # run must still reconcile a sidecar that drifted.
    reconcile_sidecar(canonical_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    ap.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    ap.add_argument("--gold", type=Path, default=GOLD_PATH)
    ap.add_argument("--only", nargs="+", metavar="CODE")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run, writes nothing)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        return run(args.spec, args.canonical, args.gold, args.only, args.apply)
    except CureError as exc:
        logger.error("REFUSED: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
