#!/usr/bin/env python3
"""The restricted SLICE hiding inside a "100% open" code.

WHAT THIS IS
------------
12 codes adjudicated `BROADER` in `apply_perpres_foreign_caps.ADJUDICATION`
render "100% Open" on `/kbli/<code>` — correctly, on the WHOLE code — while a
NARROWER bidang usaha inside them carries a Perpres 10/2021 (as amended by
49/2021) foreign-ownership condition. `13133` (Industri Kain Batik) is 100%
open as a whole code; "batik cap" (stamped batik) specifically is reserved to
domestic capital. A client filing under 13133 for stamped-batik production
would file "100% open" and be wrong about the one activity they are actually
doing. This module discloses the slice — never re-derives the BROADER verdict
itself, which is `apply_perpres_foreign_caps.ADJUDICATION`'s call and stays
there (one SSOT, W105).

Five of those 12 — `20235`, `30303`, `51103`, `60103` and `60203` — are
excluded (see `ADJACENT_NOT_CONTAINED`): their OWN `ADJUDICATION` reason says
the annex activity is a NEIGHBOUR in the same ancestor family, not something
actually inside the code (bespoke perfume is not traditional cosmetics; a
spacecraft is not a military aircraft; space transport is not air transport;
on-demand streaming is not an institutional broadcaster). Publishing a slice
notice on those pages would assert a containment the adjudication itself denies.
That leaves 7 codes reached by the general derivation.

Plus the two hand-adjudicated `30111`/`30113` rows (see `MANUAL_SLICE_ROWS`):
these two are `AMBIGUOUS`, not `DISAGREE`, in `perpres_foreign_cap_relation`'s
own join — the law gives KBLI-2020 code `30111` TWO different caps depending
on bidang usaha (warship yard 49%, traditional wooden vessel 0%), so a
single-cap patch was never possible for either 2025 descendant. That is
exactly the shape a slice disclosure exists for, and it needed a human read of
each code's own `uraian` to resolve: 30111's uraian literally lists "kapal
perang" among its manned-vessel examples (both slices apply), while 30113's
lists "operasi militer" among its unmanned-vessel use-cases but never mentions
Pinisi/Cadik/traditional construction (only the defence slice applies — a
traditional wooden Pinisi is not an unmanned vehicle).

WHY THE GENERAL DERIVATION EXCLUDES 30111/30113
--------------------------------------------------
The general loop below assigns EVERY (entry, cap, condition) tuple under a
KBLI-2020 ancestor to EVERY 2025 code descending from it — safe for the other
12 BROADER codes because each of their ancestors carries exactly ONE tuple.
`30111` carries TWO (entries 7 and 8), and BOTH `30111` and `30113` descend
from it: an unscoped cross-product would give `30113` the Pinisi/Cadik row too
— an unmanned vehicle cannot be a traditional wooden vessel. `MANUAL_SLICE_ROWS`
is the adjudicated, per-code answer; the general loop explicitly skips both
codes rather than silently producing the wrong cross-product.

REFUSES, LOUDLY (never guesses, never silently drops a row)
-------------------------------------------------------------
* a BROADER-adjudicated code (excluding the two hand-authored ones and the two
  adjacent-not-contained exclusions) has no matching row in the join — the
  derivation that is supposed to explain WHY it is BROADER found nothing to
  disclose, which means either the ADJUDICATION entry or the join itself has
  drifted;
* an `ADJACENT_NOT_CONTAINED` code's `ADJUDICATION` verdict or reason text has
  moved since the exclusion was written — a stale exclusion is exactly the
  double-speak this module exists to prevent, just inverted (a slice that
  SHOULD be disclosed silently isn't);
* any row's `foreignCapPct` is not 0 or 49 — the only two values Lampiran III
  actually uses; a third value would be a transcription or a join defect;
* the code's OWN catalogue `pma_status` is not `TERBUKA` — a slice disclosure
  on an already-restricted code would double-speak (the 50113-class case: a
  code with a verified, code-wide TERBATAS/49 cap needs no slice notice, it
  IS the restriction). This is what keeps `21021`/`21022` out of this artifact
  once their ADJUDICATION verdict flips `RENAMED -> PLAIN` and their whole
  code is patched to TERBATAS: they simply never reach the BROADER filter.

IT REPORTS AND EMITS; IT DOES NOT DECIDE. `--check` exits 0 (the population is
the designed disclosure, not a failure). `--check-artifact` exits 1 when the
emitted artifact no longer matches a recomputation from canonical + the
ADJUDICATION dict — the same freshness contract `gold_risk_dispute_relation.py`
uses, so a future ADJUDICATION edit cannot drift silently from the page.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
ARTIFACT = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-perpres-slice-disclosures.json"

# Sibling-module import: same sys.path pattern every compiler in this
# directory uses (works whether this file is executed directly or imported by
# a test that already inserted this directory).
_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

from perpres_foreign_cap_relation import (  # noqa: E402
    INSTRUMENT,
    RELATION,
    VINTAGE,
    ancestors_of,
    caps_by_code,
)
from apply_perpres_foreign_caps import ADJUDICATION, BROADER  # noqa: E402

VALID_CAPS = {0, 49}

# The 2 hand-adjudicated rows the general ancestor-join derivation cannot
# produce safely (see module docstring). `(entry, bidang_usaha, cap,
# condition)` — the SAME shape `caps_by_code(RELATION)` groups tuples into,
# and the SAME literal annex text `RELATION` already carries for entries 7/8
# (kbli_2020 "30111"), so this is not new prose: it is the existing annex
# text, hand-assigned to the correct 2025 descendant(s) instead of the
# cross-product every other descendant would get.
MANUAL_SLICE_ROWS: dict[str, list[tuple[int, str, int, str | None]]] = {
    "30111": [
        (7, "Industri kapal perang", 49, "may exceed 49% with Menteri Pertahanan approval"),
        (8, "Industri kapal: Pinisi, Cadik, kapal dari kayu lainnya dengan desain khas tradisional", 0, None),
    ],
    "30113": [
        (7, "Industri kapal perang", 49, "may exceed 49% with Menteri Pertahanan approval"),
    ],
}

# Five BROADER-adjudicated codes whose OWN adjudication reason (see ADJUDICATION
# in apply_perpres_foreign_caps.py) says the annex activity is not actually
# INSIDE the 2025 code — it is a neighbour in the same ancestor family, not a
# narrower slice of it. `20235` (bespoke perfume) shares ancestor "20232" with
# `20232` (traditional cosmetics) but the annex restricts traditional
# cosmetics, not bespoke perfume; `30303` (spacecraft) shares ancestor "30300"
# with `30301`/`30302` (manned/unmanned military aircraft) but the annex
# restricts military AIRCRAFT, not spacecraft; `51103` (space transport) shares
# ancestor "51109" with `51101`/`51102` (passenger/cargo air transport) but
# entry 31 restricts air transport, not space transport; `60103` and `60203`
# (on-demand audio/video streaming) descend from broadcasting ancestors but
# entries 34/35 restrict institutional broadcaster status, not streaming.
# Publishing "one specific activity inside this code carries a condition" on
# these pages would assert a containment `ADJUDICATION` itself denies — the
# general ancestor-join below would otherwise include them (same ancestor, same
# annex row) exactly like their siblings that DO stay. Reasons pulled verbatim
# from `ADJUDICATION` at import time (never re-typed) so the texts can never
# drift from each other; `compute_disclosures()` re-checks every excluded code
# is still BROADER with the SAME reason before every run.
ADJACENT_NOT_CONTAINED: dict[str, str] = {
    "20235": ADJUDICATION["20235"][1],
    "30303": ADJUDICATION["30303"][1],
    "51103": ADJUDICATION["51103"][1],
    "60103": ADJUDICATION["60103"][1],
    "60203": ADJUDICATION["60203"][1],
}


class SliceDisclosureError(RuntimeError):
    """A refusal. Never downgraded to a warning, never silently dropped."""


def load_canonical(path: Path = CANONICAL) -> list[dict[str, Any]]:
    return json.loads(path.read_text())["data"]


def broader_codes(adjudication: dict[str, tuple[str, str]]) -> set[str]:
    return {code for code, (verdict, _) in adjudication.items() if verdict == BROADER}


def _row(entry: int, bidang: str, cap: int, cond: str | None) -> dict[str, Any]:
    return {
        "bidangUsaha": bidang,
        "foreignCapPct": cap,
        "condition": cond,
        "locator": f"{INSTRUMENT} entry #{entry}",
    }


def general_rows(
    canonical: list[dict[str, Any]],
    adjudication: dict[str, tuple[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    """The 10-code population reached by a single ancestor -> annex-row join.

    Excludes `MANUAL_SLICE_ROWS`' codes explicitly (see module docstring for
    why an unscoped cross-product would be wrong for them) and
    `ADJACENT_NOT_CONTAINED`'s codes (the annex activity is a neighbour, not a
    slice inside them — see that dict's own comment). Refuses loudly if a
    BROADER-adjudicated code (outside both exclusion sets) has no row here —
    the derivation that explains WHY it is BROADER found nothing.
    """
    targets = broader_codes(adjudication) - set(MANUAL_SLICE_ROWS) - set(ADJACENT_NOT_CONTAINED)
    by_code = caps_by_code(RELATION)
    reverse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in canonical:
        for ancestor in ancestors_of(rec):
            reverse[ancestor].append(rec)

    out: dict[str, list[dict[str, Any]]] = {}
    for code_2020, entries in by_code.items():
        for rec in reverse.get(code_2020, []):
            code_2025 = str(rec.get("kode_kbli_2025"))
            if code_2025 not in targets:
                continue
            for entry, bidang, cap, cond in entries:
                out.setdefault(code_2025, []).append(_row(entry, bidang, cap, cond))

    missing = sorted(targets - out.keys())
    if missing:
        raise SliceDisclosureError(
            f"BROADER-adjudicated code(s) missing from the ancestor join, "
            f"nothing to disclose for: {missing} — the ADJUDICATION entry or "
            f"the join has drifted from each other"
        )
    return out


def manual_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        code: [_row(entry, bidang, cap, cond) for entry, bidang, cap, cond in rows]
        for code, rows in MANUAL_SLICE_ROWS.items()
    }


def compute_disclosures(
    canonical: list[dict[str, Any]],
    adjudication: dict[str, tuple[str, str]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Pure. Raises `SliceDisclosureError` on any of the three refusal
    conditions named in the module docstring — never emits a partial or
    guessed artifact."""
    adjudication = ADJUDICATION if adjudication is None else adjudication
    records_by_code = {str(r.get("kode_kbli_2025")): r for r in canonical}

    disclosures: dict[str, list[dict[str, Any]]] = {}
    disclosures.update(general_rows(canonical, adjudication))
    disclosures.update(manual_rows())

    # The two hand-authored codes must ALSO be BROADER-adjudicated — a
    # guilt/innocence pin against ADJUDICATION drifting out from under them,
    # not a live legal check (§ the module docstring: they are `ambiguous`,
    # not `disagree`, so `broader_codes()` alone would never have found them).
    for code in MANUAL_SLICE_ROWS:
        verdict, _ = adjudication.get(code, (None, ""))
        if verdict != BROADER:
            raise SliceDisclosureError(
                f"{code}: hand-authored slice rows exist but ADJUDICATION no "
                f"longer marks it BROADER (found {verdict!r}) — the "
                f"adjudication moved out from under the disclosure"
            )

    # ADJACENT_NOT_CONTAINED's exclusion is only valid for as long as its own
    # premise holds: same verdict (BROADER), same reason text. If either
    # drifts, the exclusion needs a human to re-derive it — silently keeping
    # a stale exclusion (or a stale reason) is exactly the double-speak this
    # module exists to prevent, just inverted.
    for code, reason in ADJACENT_NOT_CONTAINED.items():
        verdict, live_reason = adjudication.get(code, (None, ""))
        if verdict != BROADER:
            raise SliceDisclosureError(
                f"{code}: excluded as adjacent-not-contained but ADJUDICATION "
                f"no longer marks it BROADER (found {verdict!r}) — re-derive "
                f"whether the exclusion still applies"
            )
        if live_reason != reason:
            raise SliceDisclosureError(
                f"{code}: ADJUDICATION's reason changed since the exclusion "
                f"was written ({live_reason!r} != {reason!r}) — re-read it "
                f"before trusting the exclusion still holds"
            )

    for code, rows in sorted(disclosures.items()):
        record = records_by_code.get(code)
        if record is None:
            raise SliceDisclosureError(f"{code}: not in canonical — cannot verify pma_status")
        status = record.get("pma_status")
        if status != "TERBUKA":
            raise SliceDisclosureError(
                f"{code}: a slice disclosure would double-speak — the whole "
                f"code's own pma_status is {status!r}, not TERBUKA (the "
                f"50113-class case: an already-restricted code needs no "
                f"slice notice, it IS the restriction)"
            )
        for row in rows:
            cap = row["foreignCapPct"]
            if cap not in VALID_CAPS:
                raise SliceDisclosureError(
                    f"{code}: row foreignCapPct={cap!r} is not one of "
                    f"{sorted(VALID_CAPS)} — Lampiran III only ever uses "
                    f"these two values"
                )

    return disclosures


def build_artifact(disclosures: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "_meta": {
            "generated_by": "scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit",
            "instrument": INSTRUMENT,
            "vintage": VINTAGE,
            "note": (
                "Codes whose WHOLE-CODE pma_status is TERBUKA (100% open) while a "
                "NARROWER bidang usaha inside them carries a Perpres foreign-cap "
                "condition (see apply_perpres_foreign_caps.ADJUDICATION for the "
                "BROADER verdict, and MANUAL_SLICE_ROWS for the two "
                "hand-adjudicated 30111/30113 rows). Multi-row per code is allowed. "
                "excluded_adjacent_not_contained lists BROADER codes deliberately "
                "left OUT of `disclosures` because their own ADJUDICATION reason "
                "says the annex activity is a neighbour, not something inside the "
                "code — publishing a slice notice there would assert a containment "
                "the adjudication itself denies."
            ),
            "count": len(disclosures),
            "excluded_adjacent_not_contained": dict(sorted(ADJACENT_NOT_CONTAINED.items())),
        },
        "disclosures": disclosures,
    }


def _serialize(artifact: dict[str, Any]) -> str:
    return json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--emit", action="store_true", help=f"write {ARTIFACT}")
    parser.add_argument(
        "--check-artifact",
        action="store_true",
        help="exit 1 when the emitted artifact no longer matches a recomputation",
    )
    parser.add_argument("--canonical", type=Path, default=CANONICAL)
    parser.add_argument("--artifact", type=Path, default=ARTIFACT)
    args = parser.parse_args(argv)

    try:
        disclosures = compute_disclosures(load_canonical(args.canonical))
    except SliceDisclosureError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    artifact = build_artifact(disclosures)

    if args.check_artifact:
        if not args.artifact.exists():
            print(f"ARTIFACT MISSING: {args.artifact}", file=sys.stderr)
            return 1
        on_disk = args.artifact.read_text()
        if on_disk != _serialize(artifact):
            print(
                "ARTIFACT STALE: recomputation differs — re-run "
                "perpres_slice_disclosure_relation.py --emit and commit the "
                "result in the SAME change that touched canonical/ADJUDICATION",
                file=sys.stderr,
            )
            return 1
        print(f"artifact fresh: {len(disclosures)} codes disclosed")
        return 0

    if args.emit:
        args.artifact.write_text(_serialize(artifact))
        total_rows = sum(len(rows) for rows in disclosures.values())
        print(f"wrote {args.artifact} ({len(disclosures)} codes, {total_rows} rows)")
        return 0

    if args.json:
        print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    total_rows = sum(len(rows) for rows in disclosures.values())
    print(f"perpres slice disclosures: {len(disclosures)} codes, {total_rows} rows")
    for code, rows in sorted(disclosures.items()):
        for row in rows:
            cond = f" ({row['condition']})" if row["condition"] else ""
            print(f"  {code}: «{row['bidangUsaha']}» {row['foreignCapPct']}%{cond}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
