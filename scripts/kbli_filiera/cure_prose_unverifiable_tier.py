#!/usr/bin/env python3
"""cure_prose_unverifiable_tier.py — remove the risk-tier claim a page asserts
while the same record declares that tier unverifiable.

WHY THIS EXISTS
---------------
`cure_l4bali_disclosure.py` cured the FIELD: 152 records whose Bali verdict was
derived from a risk tier we can no longer verify now say so on `l4_bali.reason`.
`cure_l3_prose_gap_disclosure.py` then carried that disclosure into the EDITORIAL
PROSE, on canonical and on gold. Both were right, and neither closed this:

    the disclosure was APPENDED. The sentence it contradicts was left standing.

So a page reads "In Bali it falls under a medium-high to high risk
classification, so registration will depend on the specific location and may
require additional compliance checks per address" — stated as settled fact — and
then, two lines below, "**Risk tier under review.** No KBLI-2025 risk scope for
this code could be retrieved…". The client gets a claim and its retraction in one
block, and the load-bearing sentence is the claim: it is the one that tells them
to expect extra scrutiny, higher capital, a harder registration.

That is W113 arriving in our own editorial layer — a correction written next to
the assertion instead of over it — and it is the expensive direction of the
error, because it turns away business on a tier nobody can produce.

WHY A COMPILER AND NOT A PATTERN
--------------------------------
The prose cure's own docstring settles this, and it is worth quoting rather than
re-deriving: two independent matchers were built for the asserting subset and
both failed in opposite directions — the emitter's `_TIER_CLAIM_RE` flags 152 of
152 (a discriminator that fires on everything discriminates nothing), a strict
hand-written one flags 19 and misses real assertions in phrasings it never
anticipated, and it scores the CURE as the DISEASE because the appended
paragraph itself contains the words "risk tier". `19 <= truth <= 152` and no
pattern closes the gap.

So membership is still structural (this cure only sees records the disclosure
lane marked), but WHICH sentence asserts, and what should stand in its place, is
a per-code READING. Every replacement is therefore a NEW claim, never a
softening of the old one — a weakened claim is still a claim — and each one was
graded by a seat from a different model family before it reached this spec.

WHAT IT WILL NOT DO
-------------------
It never authors a replacement: every `new` string comes from
`cure_specs/prose_unverifiable_tier.json`, which records who graded it. It never
touches `l4_bali`, `per_skala`, `pma_status` or `pma_max_asing` — restating a
settled verdict is how a correction becomes a new claim. It never touches the
appended disclosure paragraph: that is the cure, not the disease, and a spec
entry whose `old` contains it is refused.

TWO SURFACES, AND THE SECOND ONE IS THE ONE THAT SHOWS
------------------------------------------------------
`kbli-data.server.ts` renders the gold entry INSTEAD OF `intel_2026` whenever a
gold entry exists — a total mask, not a merge. 39 of the 152 carry gold prose.
A canonical-only cure would report every code cured while changing nothing a
reader sees on the worst-affected pages. So a spec entry names its surface, and
this script writes both.

THE PREMISE IS PINNED, AND A MOVED PREMISE IS A REFUSAL
-------------------------------------------------------
Each entry carries `expect_l4_status` / `expect_l4_blocked` as they stood when
the prose was read and graded, and this cure additionally requires the
`_l3_gap_disclosure` marker to still be present on the surface it is patching.
That marker is the whole reason the entry exists: if the disclosure lane's work
has since been re-derived away, the tier may be knowable again and the
replacement — which says it is not — would be the new lie.

FAIL-VISIBLE, NEVER A SILENT GUESS
----------------------------------
A patch applies only when `old` occurs EXACTLY ONCE in its field. Already-applied
is recognised (old absent AND new present) and skipped. Every other state — old
missing and new missing, old repeated, both present — is a CureError.

USAGE (dry-run is the default; nothing is written without --apply):
    python3 scripts/kbli_filiera/cure_prose_unverifiable_tier.py
    python3 scripts/kbli_filiera/cure_prose_unverifiable_tier.py --apply
    python3 scripts/kbli_filiera/cure_prose_unverifiable_tier.py --only 85581 --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("kbli_filiera.cure_prose_unverifiable_tier")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts/kbli_filiera/cure_specs/prose_unverifiable_tier.json"
DEFAULT_CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
GOLD_PATH = REPO_ROOT / "apps/mouth/data/kbli-gold-all.json"

# The sibling is reached by its PACKAGE path, and the repo root is put on
# sys.path so that path resolves whether this file is imported by the test suite
# or run as a script from an arbitrary cwd.
#
# This is not tidiness. `scripts/kbli_filiera/` sits on sys.path in script mode,
# so `import cure_l4_withdrawn_umkm_prose` and
# `import scripts.kbli_filiera.cure_l4_withdrawn_umkm_prose` load the same FILE
# into two distinct module objects — measured: `A is B` is False, and with it
# `CureError is CureError` is False. A test raising the package's CureError
# would then sail straight past this module's `except CureError`, and a refusal
# would surface as an uncaught traceback instead of the exit-1 the caller reads.
# Pinned by `test_the_sibling_engine_is_imported_once`.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Reuse, not re-implementation: the path resolver, the sync driver and the
# sidecar reconciler are the sibling compiler's, and two writers of one dataset
# must not each own a copy of the rule.
from scripts.kbli_filiera.cure_l4_withdrawn_umkm_prose import (  # noqa: E402
    CureError,
    _dig,
    reconcile_sidecar,
    run_sync_script,
)

MARKER_FIELD = "_l3_gap_disclosure"

# The appended disclosure paragraph opens with this. A spec entry whose `old`
# contains it would be deleting the cure while claiming to delete the disease,
# so it is refused by name rather than trusted to the author's discretion.
DISCLOSURE_OPENER = "**Risk tier under review.**"

# Layers this cure may never write. `l4_bali` is the settled verdict; the rest is
# government data. The spec is prose-only by construction, and this is the
# assertion of that, not a comment about it.
FORBIDDEN_ROOTS = frozenset(
    {"l4_bali", "per_skala", "pma_status", "pma_max_asing", "pp28_sources", "_l2_source"}
)


def load_gold(path: Path) -> dict[str, Any]:
    gold = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(gold, dict):
        raise CureError(f"unexpected gold shape in {path}: {type(gold).__name__}, expected object")
    return gold


def apply_patch(container: dict[str, Any], code: str, patch: dict[str, str]) -> bool:
    """Return True if the container changed, False if already applied."""
    field = patch["field"]
    root = field.split(".")[0].split("[")[0]
    if root in FORBIDDEN_ROOTS:
        raise CureError(
            f"{code}: spec targets {field!r}, and {root!r} is a verdict/government layer this "
            "cure may not write. Prose only."
        )
    owner, key = _dig(container, field)
    if key not in owner:
        raise CureError(f"{code}.{field}: field does not exist on this surface")
    text = owner[key]
    if not isinstance(text, str):
        raise CureError(f"{code}.{field}: holds {type(text).__name__}, not a string")

    old, new = patch["old"], patch["new"]
    if DISCLOSURE_OPENER in old:
        raise CureError(
            f"{code}.{field}: the `old` text contains the appended disclosure paragraph "
            f"({DISCLOSURE_OPENER!r}). That paragraph is the cure, not the claim — refusing to "
            "delete it."
        )
    if not old.strip():
        raise CureError(f"{code}.{field}: empty `old` — a patch must name the text it replaces")

    n_old, n_new = text.count(old), text.count(new)
    if n_old == 1:
        owner[key] = text.replace(old, new, 1)
        return True
    if n_old == 0 and n_new >= 1:
        logger.info("%s.%s: already applied — skipping", code, field)
        return False
    raise CureError(
        f"{code}.{field}: refusing — old occurs {n_old}x, new occurs {n_new}x. "
        "A patch applies only when the old text is present exactly once."
    )


def check_premise(record: dict[str, Any], code: str, entry: dict[str, Any]) -> None:
    l4 = record.get("l4_bali") or {}
    want_status, want_blocked = entry.get("expect_l4_status"), entry.get("expect_l4_blocked")
    got_status, got_blocked = l4.get("status"), l4.get("blocked")
    if got_status != want_status or got_blocked != want_blocked:
        raise CureError(
            f"{code}: premise moved — spec was written against status={want_status!r}/"
            f"blocked={want_blocked!r}, record now holds status={got_status!r}/"
            f"blocked={got_blocked!r}. Re-read and re-grade rather than writing prose onto a "
            "record it no longer describes."
        )


def check_disclosure_marker(container: dict[str, Any], code: str, surface: str) -> None:
    """The marker is why the entry exists. Gone marker = the tier may be knowable
    again, and the replacement (which says it is not) would be the new false claim."""
    if not isinstance(container.get(MARKER_FIELD), dict):
        raise CureError(
            f"{code}: the {surface} surface no longer carries {MARKER_FIELD!r}. This cure only "
            "removes a tier claim from a page that still declares the tier unverifiable — "
            "without that marker the premise is gone. Re-read this code."
        )


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
    touched_records, skipped = set(), 0

    for code, entry in codes.items():
        record = by_code[code]
        check_premise(record, code, entry)
        for patch in entry["patches"]:
            surface = patch["surface"]
            if surface == "canonical":
                container = record.get("intel_2026")
                if not isinstance(container, dict):
                    raise CureError(f"{code}: no intel_2026 object to patch")
            elif surface == "gold":
                container = gold.get(code)
                if not isinstance(container, dict):
                    raise CureError(
                        f"{code}: spec names a gold patch but no gold entry exists. The gold "
                        "entry was there when the prose was read — it has been removed since."
                    )
            else:
                raise CureError(f"{code}: unknown surface {surface!r}")
            check_disclosure_marker(container, code, surface)
            if apply_patch(container, code, patch):
                changed[surface] += 1
                touched_records.add(code)
            else:
                skipped += 1

    logger.info(
        "%s: %d record(s) touched — %d canonical patch(es), %d gold patch(es), %d already applied",
        "APPLY" if apply else "DRY-RUN",
        len(touched_records), changed["canonical"], changed["gold"], skipped,
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
        gold_path.write_text(
            json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
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
