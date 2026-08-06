#!/usr/bin/env python3
"""cure_prose_national_openness.py — replace prose that tells a client an
activity is nationally open when the record says its foreign-ownership ceiling
is zero.

WHAT IS BEING REPLACED, AND WHY IT IS NOT A SOFTENING
------------------------------------------------------
`editorial_record_conformance.py` reports the codes whose authored prose
asserts national openness against their own record. The six in the first spec
share one record fact: the bidang usaha is allocated to Koperasi and UMKM by
Perpres 49/2021 Lampiran II, so `pma_max_asing` is 0 and a PT PMA cannot hold
it anywhere in Indonesia.

Four of them carry a sentence that contradicts ITSELF:

    "nationally open to full foreign ownership, but a PT PMA cannot register
     this activity anywhere in Indonesia"

If it were nationally open to full foreign ownership, a PT PMA could hold it.
The reservation IS the national position, not something a separate rule then
blocks — and a reader of the first half goes looking for the structure that
unlocks the second. The other two (`95220`, `95299`) are worse: their bodies
still tell the whole story as a BALI problem, which sends a client to register
in Jakarta, where it is refused too.

WHOLE FIELDS, NEVER SENTENCES
-----------------------------
A cross-family review refuted the sentence-level version of this cure:
`95220`'s body carries the false premise in four separate places, so patching
one leaves the paragraph contradicting itself. Every replacement here is a
WHOLE field. Where a body holds true facts unrelated to ownership — `95299`'s
scope and exclusion list, `95220`'s scope paragraph — those paragraphs are
carried into the replacement verbatim, because the previous spec's failure mode
was deleting true licensing and zoning facts while fixing an ownership one.

THE OLD TEXT IS IDENTIFIED BY HASH, NOT BY MATCHING
----------------------------------------------------
Each field carries the sha256 of the text it was written against. A field that
moved since the spec was graded is a REFUSAL, not a re-match: the replacement
was authored and graded against a specific paragraph, and silently overwriting
a different one is how a cure becomes an author.

FOUR REFUSALS BEFORE IT WRITES
------------------------------
1. The record's `pma_max_asing` / `pma_status` / `pma_kondisi` must still match
   what the spec was graded against.
2. Every field's live text must hash to `old_sha256`.
3. No replacement may state a percentage that is not the record's own cap —
   the one machine-checkable property of an authored sentence.
4. After patching IN MEMORY, the detector must report zero remaining openness
   assertions on the cured codes AND an unchanged verdict on every other code.
   The second half matters more than the first: a cure that alters a record it
   was not asked to touch is the failure this directory keeps rediscovering.

WHAT IT DOES NOT WRITE
----------------------
Canonical only. `apps/mouth/data/kbli-gold-all.json` takes precedence on the
website for the fields it carries, and it is already clean — measured, zero
openness assertions across all 428 gold codes. Gold carries no `editorial.*`
keys at all, so the headline, standfirst, body and pull quote come from
canonical on every code, and Qdrant is built from canonical on every field.
Writing gold here would overwrite correct, independently authored text.

USAGE (dry-run is the default; nothing is written without --apply):

    python3 scripts/kbli_filiera/cure_prose_national_openness.py
    python3 scripts/kbli_filiera/cure_prose_national_openness.py --apply
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_FILIERA = str(Path(__file__).resolve().parent)
if _FILIERA not in sys.path:
    sys.path.insert(0, _FILIERA)

import editorial_record_conformance as E  # noqa: E402

from scripts.kbli_filiera.cure_l4_withdrawn_umkm_prose import (  # noqa: E402
    reconcile_sidecar,
    run_sync_script,
)

CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC = (
    Path(__file__).resolve().parent
    / "cure_specs"
    / "prose_umkm_reserved_openness_2026_08_06.json"
)

logger = logging.getLogger("cure_prose_national_openness")

_PERCENT = re.compile(r"(\d+)\s*%")


class CureError(RuntimeError):
    """Raised when a premise the spec rests on is no longer true."""


def read_field(record: dict[str, Any], path: str) -> Any:
    cur: Any = record.get("intel_2026") or {}
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def write_field(record: dict[str, Any], path: str, value: str) -> None:
    cur = record["intel_2026"]
    keys = path.split(".")
    for key in keys[:-1]:
        cur = cur[key]
    cur[keys[-1]] = value


def check_premise(record: dict[str, Any], code: str, expect: dict[str, Any]) -> None:
    """Has the record moved under the graded text?"""
    for key in ("pma_max_asing", "pma_status"):
        want, got = expect.get(key), record.get(key)
        if want != got:
            raise CureError(
                f"{code}: premise moved — spec graded against {key}={want!r}, record now "
                f"holds {got!r}. Re-read and re-grade rather than writing prose onto a "
                "record it no longer describes."
            )
    needle = expect.get("pma_kondisi_contains")
    if needle and needle not in (record.get("pma_kondisi") or ""):
        raise CureError(
            f"{code}: `pma_kondisi` no longer contains {needle!r}. Every replacement in "
            "this spec names the Koperasi/UMKM allocation as the REASON the ceiling is "
            "zero; without it on the record the sentences would assert their own basis."
        )


def plan_for(record: dict[str, Any], code: str, entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Which fields to replace on ONE record, refusing anything ambiguous."""
    cap = record.get("pma_max_asing")
    edits: list[dict[str, Any]] = []

    for path, patch in entry["fields"].items():
        live = read_field(record, path)
        if not isinstance(live, str) or not live.strip():
            raise CureError(
                f"{code}.{path}: field is {type(live).__name__}, not prose. The spec was "
                "written against a string; something restructured this record."
            )
        digest = hashlib.sha256(live.encode("utf-8")).hexdigest()
        if digest != patch["old_sha256"]:
            raise CureError(
                f"{code}.{path}: text moved since the spec was graded "
                f"(sha256 {digest[:12]} != {patch['old_sha256'][:12]}). The replacement was "
                "authored against a specific paragraph and refuted against that one; "
                "overwriting a different paragraph with it would be authoring blind."
            )
        for stated in _PERCENT.findall(patch["new"]):
            if not isinstance(cap, int) or int(stated) != cap:
                raise CureError(
                    f"{code}.{path}: replacement states {stated}% but the record's cap is "
                    f"{cap!r}. A percentage is the one part of an authored sentence a "
                    "machine can check, and it does not get to disagree with the field."
                )
        edits.append({"code": code, "field": path, "was": live, "now": patch["new"]})

    return edits


def run(spec_path: Path, canonical_path: Path, only: list[str] | None, apply: bool) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    wanted: dict[str, Any] = spec["codes"]
    if only:
        unknown = sorted(set(only) - set(wanted))
        if unknown:
            raise CureError(f"--only names codes absent from the spec: {unknown}")
        wanted = {c: wanted[c] for c in only}

    doc = json.loads(canonical_path.read_text(encoding="utf-8"))
    records = doc["data"]
    by_code = {r.get("kode_kbli_2025"): r for r in records}

    missing = sorted(set(wanted) - set(by_code))
    if missing:
        raise CureError(f"spec names codes absent from canonical: {missing}")

    before = {r.get("kode_kbli_2025"): E.classify(r)["body_asserts_national_openness"]
              for r in records}
    logger.info(
        "before: %d code(s) assert a national openness their record denies; this spec "
        "covers %d of them",
        sum(before.values()),
        len(wanted),
    )

    patched = copy.deepcopy(records)
    patched_by_code = {r.get("kode_kbli_2025"): r for r in patched}

    edits: list[dict[str, Any]] = []
    for code, entry in wanted.items():
        record = patched_by_code[code]
        check_premise(record, code, entry["expect"])
        edits.extend(plan_for(record, code, entry))

    for edit in edits:
        write_field(patched_by_code[edit["code"]], edit["field"], edit["now"])

    for edit in edits:
        logger.info("  %s  %-24s %d -> %d chars", edit["code"], edit["field"],
                    len(edit["was"]), len(edit["now"]))

    after = {r.get("kode_kbli_2025"): E.classify(r)["body_asserts_national_openness"]
             for r in patched}

    # The two refusals that make this safe to write, checked on the PATCHED
    # document rather than hoped for.
    still_lying = sorted(c for c in wanted if after.get(c))
    if still_lying:
        logger.error(
            "refusing to write: %s still assert national openness after the replacement. "
            "A half-cure leaves a page consistent enough to be believed and wrong where "
            "it counts.",
            still_lying,
        )
        return 1

    collateral = sorted(c for c in before if c not in wanted and before[c] != after.get(c))
    if collateral:
        logger.error(
            "refusing to write: the verdict changed on %d code(s) this spec never named "
            "(%s). A cure that alters a record it was not asked to touch is the failure "
            "this directory keeps rediscovering.",
            len(collateral),
            collateral[:10],
        )
        return 1

    logger.info(
        "%s: %d field(s) on %d code(s); codes still asserting openness overall: %d -> %d",
        "APPLY" if apply else "DRY-RUN",
        len(edits),
        len({e["code"] for e in edits}),
        sum(before.values()),
        sum(after.values()),
    )

    if not apply:
        logger.info("nothing written — rerun with --apply")
        return 0
    if not edits:
        logger.info("nothing to write")
        return 0

    doc["data"] = patched
    canonical_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("canonical written: %s", canonical_path)
    run_sync_script()
    reconcile_sidecar(canonical_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", type=Path, default=SPEC)
    ap.add_argument("--canonical", type=Path, default=CANONICAL)
    ap.add_argument("--only", nargs="*", help="restrict to these codes")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        return run(args.spec, args.canonical, args.only, args.apply)
    except CureError as exc:
        logger.error("REFUSED: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
