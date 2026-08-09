#!/usr/bin/env python3
"""Write the declared sector-law carve-out list: the six insurance/reinsurance
codes Perpres 10/2021 Pasal 11 ayat (2) routes to their own sector law instead
of the Perpres's own regime.

WHY THIS EXISTS (2026-08-08 fix-pack, item G)
-----------------------------------------------
`perpres_body_default_relation.py` classifies every code that no restricting
annex names as RESIDUAL under Pasal 3 ayat (1) huruf d — "no annex names this
activity" — and that residual default is what `apps/mouth/data/
perpres-locators.json` renders as the "Basis:" line directly under a code's
PMA verdict. For `65111`/`65112`/`65121`/`65122`/`65201`/`65202`, that is
backwards: those six ARE absent from every Perpres annex, but the reason is
not "the residual-open default applies" — it is that Perpres 10/2021 Pasal 11
ayat (2) carves financial and banking bidang usaha OUT of the Perpres's own
regime entirely, routing them to sector law instead (PP 14/2018 Pasal 5(1)
jo. PP 3/2020, the instrument this PR's `cure_canonical_asuransi_pp14_cap.py`
already adjudicated the 80% cap against). Publishing "Perpres 10/2021 Pasal
3(1)(d)" as the basis for a TERBATAS/80 verdict cites the WRONG article for
the SAME reason the residual-open default is wrong for these six: Pasal 11(2)
means the Perpres was never the source of law here, in either direction.

WHY A SEPARATE FILE, NOT A HARDCODED SET IN THE COMPILER
-----------------------------------------------------------
`perpres_body_default_relation.py` already hardcodes two body-level lists
(`BODY_TERTUTUP`, `BODY_OTHER_REQUIREMENT`) as Python dicts, with a documented
reason: the source PDF's text layer is deterministically corrupted, so a
constant beats a regex over corrupted OCR. That reason does not apply here —
this list has six entries, verified against the SAME instrument's own text
(Pasal 11 ayat 2) and against UU 40/2014 Pasal 1 angka 14 (which names
`perusahaan reasuransi` and `perusahaan reasuransi syariah` explicitly, the
basis for treating 65201/65202 as certain rather than conditional — see
`cure_specs/canonical_asuransi_pp14_cap_2026_08_08.json::primary_sources`).
A DECLARED, versioned input file (the same shape as
`perpres-priority-codes.json` / `perpres-umkm-reservation.json` /
`perpres-foreign-caps.json`) keeps the provenance next to the codes it
justifies, inspectable and diffable on its own, rather than folded into the
relation module as an unlabelled constant.

WHAT THIS SCRIPT IS
--------------------
A one-shot WRITER, not a parser — there is no PDF to extract these six codes
from; they are the output of an adjudication this PR already made and primary-
sourced. Written via a script (not hand-edited) because `data/kbli-filiera/`
is a data-plane-guarded directory (`infra/claude-hooks/data-plane-registry.json`,
entry `kbli-filiera`, `compilers: "scripts/kbli_filiera/"`) — the guard blocks
interactive hand-edits of anything under it; this is the sanctioned writer.

Usage:
    python scripts/kbli_filiera/write_sector_law_carveout.py --check
    python scripts/kbli_filiera/write_sector_law_carveout.py --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "data" / "kbli-filiera" / "sector-law-carveout.json"

EXIT_OK, EXIT_DIFFERS = 0, 1


def _display(path: Path) -> str:
    """Repo-relative when it can be, absolute otherwise.

    Same fix as `perpres_body_default_relation.py::_display` (its docstring
    explains why): `Path.relative_to` RAISES for anything outside the repo, so
    a bare call turns a progress/error message into a crash the moment a test
    redirects `OUT_PATH` to a tmp dir — exactly the shape `test_sector_law_
    carveout.py::test_check_mode_matches_the_written_file_and_fails_on_drift`
    exercises. A status message must never be the thing that fails.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)

# The six codes this PR's cure_canonical_asuransi_pp14_cap.py adjudicated to
# TERBATAS/80 under PP 14/2018 Pasal 5(1) jo. PP 3/2020. Kept in step by
# test_sector_law_carveout.py, which asserts this set matches that spec's
# `codes` keys exactly — one adjudication, cited from two files, must not
# silently diverge into two populations.
CODES = ["65111", "65112", "65121", "65122", "65201", "65202"]


def build() -> dict:
    return {
        "instrument": "Perpres 10/2021 Pasal 11 ayat (2)",
        "basis": "Pasal 11 ayat (2)",
        "unit": "KBLI 2025 code (the six are unchanged 2020->2025; no crosswalk needed)",
        "note": (
            "These six codes are absent from every Perpres 10/2021/49/2021 "
            "annex, but NOT because the residual-open default (Pasal 3(1)(d)) "
            "applies to them — Pasal 11(2) routes financial/banking bidang "
            "usaha licensing and conduct to their own sector legislation "
            "instead, so the Perpres never governed the ownership question "
            "here in the first place. The sector law is PP 14/2018 Pasal "
            "5(1) jo. PP 3/2020 (80% foreign-ownership cap; listed insurers "
            "exempt; pre-2018 holdings above 80% grandfathered) — see "
            "scripts/kbli_filiera/cure_canonical_asuransi_pp14_cap.py and its "
            "spec for the full adjudication."
        ),
        "provenance": {
            "pasal_11_ayat_2_verbatim": (
                "Perizinan berusaha dan pelaksanaan kegiatan dalam rangka "
                "Penanaman Modal untuk Bidang Usaha keuangan dan Bidang "
                "Usaha perbankan dilaksanakan sesuai dengan ketentuan "
                "peraturan perundang-undangan di bidangnya masing-masing."
            ),
            "source": "peraturan.bpk.go.id Download/154474, Perpres 10/2021 body",
            "re_derived": "2026-08-08",
        },
        "codes": list(CODES),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the file (default: --check)")
    ap.add_argument("--check", action="store_true", help="verify the file on disk matches (default action)")
    args = ap.parse_args(argv)

    built = build()

    if args.write:
        OUT_PATH.write_text(json.dumps(built, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {_display(OUT_PATH)} ({len(built['codes'])} codes)")
        return EXIT_OK

    if not OUT_PATH.is_file():
        print(f"{_display(OUT_PATH)} missing — run with --write", file=sys.stderr)
        return EXIT_DIFFERS
    on_disk = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    if on_disk != built:
        print("DIFFERS from the declared list — re-run with --write", file=sys.stderr)
        return EXIT_DIFFERS
    print(f"{_display(OUT_PATH)} matches the declared list ({len(built['codes'])} codes)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
