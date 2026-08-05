#!/usr/bin/env python3
"""cure_whatchanged_false_renumber.py — provenance claims `whatChanged` cannot show.

WHAT IT CURES, AND WHERE
------------------------
Three defects in one client-facing field, defined once in `_whatchanged_basis.py`
(read its docstring first — it holds the reasoning, this file holds the plumbing):

  A · `false_renumbering_claim`     — "Renumbered/adjusted from KBLI 2020." on a
                                      record with no predecessor in any layer
  B · `midword_truncation`          — exactly 216 chars, cut mid-word
  C · `contradicted_predecessor`    — names a "KBLI 2020: <code>" no layer holds

across the TWO in-repo surfaces that render it:

  canonical  data/source_documents/KBLI_2025_FINAL_CLEAN.json  (+ synced copies)
  gold       apps/mouth/data/kbli-gold-all.json  (428 codes) — **this one WINS
             on the page**: `kbli-data.server.ts::transformCode` takes
             `whatChanged` from gold whenever a gold entry exists, and
             `app/kbli/[code]/page.tsx:428` renders `gold.whatChanged` directly.
             Curing canonical alone would leave `/kbli/64995` still telling a
             client it was renumbered. This is the 4th-surface leak pattern the
             corner already records for `kbli_documents`, one surface over.

Measured 2026-07-25 (`--census` reproduces it):

              canonical      gold
  A                   4         1   (gold: 64995)
  B                  13         2   (gold: 64210, 64995)
  C                   4         1   (gold: 64210)

THE THIRD LIVE SURFACE IS NOT IN THIS REPO
------------------------------------------
`kg_nodes.properties.whatChanged` (1,554 nodes, read by `inspect_kbli` →
WhatsApp / webchat / kbli-explorer) carries the same defects in its own vintage
— 45 A-claims and 13 B-truncations, measured on prod. It is a database
mutation, not a file write, so it ships as `backend/scripts/kg_whatchanged_cure.py`
and is applied against Fly after this merges. Both callers import the SAME
`plan_text`, so the two surfaces cannot drift apart.

GOLD ENTRIES WITH NO CANONICAL RECORD
-------------------------------------
8 of the 428 gold codes (64921, 85300, 85491, 85499, 85600, 86903, 96120, 96130)
have no canonical record. They are INERT — `generateStaticParams` iterates
canonical and `dynamicParams = false`, so no page exists for them and
`assignTier` is only ever called with canonical codes — but they are exactly the
phantom class the corner warns about (a row that lives only downstream is
unreachable by every cure tool that keys off "a canonical record exists"). This
tool decides gold from the CANONICAL record, so it cannot judge them: they are
counted and named in the census, never silently skipped.

GUARD
-----
Every precondition is re-derived from the live record at apply time; nothing is
read from a spec file. A code that gained a predecessor since the census was
taken simply stops matching pass A — its sentence may now be true. That is not
hypothetical: an earlier census of this defect listed 8 codes, and after Batch-B's
`bps_2020_ancestors` populate landed (2026-07-24) four of them acquired a real
BPS ancestor with a lampiran locator. A census taken before a sibling lane lands
is stale by the time you cure it.

Sanctioned writer of both datasets under the data-plane registry. Dry-run by
default; `--apply` mutates, syncs the consumer copies, and bumps the sidecar.

Usage:
  python scripts/kbli_filiera/cure_whatchanged_false_renumber.py            # dry-run
  python scripts/kbli_filiera/cure_whatchanged_false_renumber.py --census   # report only
  python scripts/kbli_filiera/cure_whatchanged_false_renumber.py --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_FILIERA_DIR = str(Path(__file__).resolve().parent)
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

# Re-exported wholesale on purpose: callers (tests, the KG arm) must reach these
# through ONE module object. Importing `_whatchanged_basis` both as a bare
# sibling here and as `scripts.kbli_filiera._whatchanged_basis` elsewhere would
# create two distinct module objects — and two distinct `WhatChangedError`
# classes, so an `except` in one path would not catch the other's raise.
from _whatchanged_basis import (  # noqa: E402  (sibling-import idiom, see other compilers)
    ALL_PASSES,
    FALSE_CLAIM,
    HONEST_CLAIM,
    CURED_CONTINUITY_MARKER,
    PASS_CONTRADICTED_PREDECESSOR,
    PASS_FALSE_CLAIM,
    PASS_FALSE_CONTINUITY,
    PASS_RESIDUAL_CONTINUITY,
    PASS_TRUNCATED,
    TRUNCATION_LENGTH,
    WhatChangedError,
    claims_ambiguous_continuity,
    claims_number_unchanged,
    contradicted_continuity,
    contradicted_predecessors,
    contradicts_own_correction,
    drop_contradicted_predecessor,
    drop_false_continuity,
    drop_residual_continuity,
    has_no_recorded_predecessor,
    is_truncated_midword,
    number_is_discontinuous,
    plan_text,
    recorded_predecessors,
    swap_false_claim,
    trim_to_last_complete_sentence,
    unconfirmed_continuity_sentence,
)

# The re-exports above are unused *inside* this module by construction — they exist
# so callers reach the decision vocabulary through one module object. Declaring them
# in __all__ states that intent in the form the linter reads, instead of stamping
# eleven per-line suppressions onto the import block. The module's own public API is
# listed too, so adding __all__ does not silently narrow a future star-import.
__all__ = [
    # re-exported from _whatchanged_basis (single module object — see comment above)
    "ALL_PASSES",
    "CURED_CONTINUITY_MARKER",
    "FALSE_CLAIM",
    "HONEST_CLAIM",
    "PASS_CONTRADICTED_PREDECESSOR",
    "PASS_FALSE_CLAIM",
    "PASS_FALSE_CONTINUITY",
    "PASS_RESIDUAL_CONTINUITY",
    "PASS_TRUNCATED",
    "TRUNCATION_LENGTH",
    "WhatChangedError",
    "claims_ambiguous_continuity",
    "claims_number_unchanged",
    "contradicted_continuity",
    "contradicted_predecessors",
    "contradicts_own_correction",
    "drop_contradicted_predecessor",
    "drop_false_continuity",
    "drop_residual_continuity",
    "has_no_recorded_predecessor",
    "is_truncated_midword",
    "number_is_discontinuous",
    "plan_text",
    "recorded_predecessors",
    "swap_false_claim",
    "trim_to_last_complete_sentence",
    "unconfirmed_continuity_sentence",
    # this module's own surface
    "CODE_FIELD",
    "DEFAULT_CANONICAL",
    "DEFAULT_GOLD",
    "MIN_SURVIVING_BODY",
    "REPO_ROOT",
    "SIDECAR_DATASET_PATH",
    "SIDECAR_PATH",
    "SYNC_SCRIPT",
    "ambiguous_continuity_census",
    "canonical_index",
    "gold_entries",
    "main",
    "plan_canonical",
    "plan_gold",
    "plan_kg_spec",
    "render_spec_json",
    "run_sync_script",
    "thin_outcomes",
    "update_sidecar",
]

logger = logging.getLogger("kbli_filiera.cure_whatchanged_false_renumber")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
DEFAULT_GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"

CureError = WhatChangedError


def canonical_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r[CODE_FIELD]): r for r in records}


def gold_entries(raw: dict[str, Any]) -> dict[str, Any]:
    """Gold ships either bare or wrapped in `data` — both shapes are in the wild."""
    return raw.get("data", raw)


def plan_canonical(records: list[dict[str, Any]]) -> list[tuple[str, str, str, list[str]]]:
    """[(code, old, new, passes)] for every canonical record that needs a rewrite."""
    planned = []
    for record in records:
        text = str(((record.get("intel_2026") or {}).get("whatChanged") or ""))
        new_text, passes = plan_text(text, record)
        if passes:
            planned.append((str(record[CODE_FIELD]), text, new_text, passes))
    return planned


def plan_gold(
    gold: dict[str, Any], by_code: dict[str, dict[str, Any]]
) -> tuple[list[tuple[str, str, str, list[str]]], list[str]]:
    """[(code, old, new, passes)] plus the gold codes with NO canonical record.

    The second list is the point: an unjudgeable entry is REPORTED, never
    quietly dropped out of the loop.
    """
    planned, orphans = [], []
    for code, entry in gold.items():
        record = by_code.get(str(code))
        if record is None:
            orphans.append(str(code))
            continue
        if not isinstance(entry, dict):  # pragma: no cover - shape guard
            continue
        text = str(entry.get("whatChanged") or "")
        new_text, passes = plan_text(text, record)
        if passes:
            planned.append((str(code), text, new_text, passes))
    return planned, sorted(orphans)


def plan_kg_spec(pull: list[dict[str, Any]], by_code: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Turn a read-only pull of live KG texts into an applier spec.

    The KG lives in Postgres on Fly, where `_whatchanged_basis` is not
    importable, so the applier (`backend/scripts/kg_whatchanged_cure.py`) must
    be given the answers rather than compute them. Every entry pins `md5` of the
    text the decision was made against; the applier refuses to write when the
    live value no longer hashes to it. Same predicates, one implementation, and
    a content check at the boundary between them.
    """
    import hashlib

    entries = []
    for row in pull:
        entity_id = str(row["entity_id"])
        code = entity_id.split(":", 1)[-1]
        record = by_code.get(code)
        if record is None:
            continue  # reported by the caller, never silently cured
        text = str(row["text"])
        digest = hashlib.md5(text.encode("utf-8")).hexdigest()  # noqa: S324 - integrity pin
        if row.get("pin") and row["pin"] != digest:
            raise CureError(
                f"{entity_id}: the pulled text does not hash to its own pin — the pull is corrupt"
            )
        new_text, passes = plan_text(text, record)
        if not passes:
            continue
        entries.append(
            {
                "entity_id": entity_id,
                "code": code,
                "passes": passes,
                "md5": digest,
                "old": text,
                "new": new_text,
            }
        )
    return {
        "spec_id": "kg_whatchanged",
        "surface": "kg_nodes.properties.whatChanged",
        "applier": "backend/scripts/kg_whatchanged_cure.py",
        "entries": sorted(entries, key=lambda e: e["entity_id"]),
    }


_SHORT_ARRAY_RE = re.compile(r'"passes": \[\n\s+((?:"[a-z_]+",?\s*)+)\n\s+\]')


def render_spec_json(spec: dict[str, Any]) -> str:
    """Serialize the spec the way this repo formats JSON, deterministically.

    `json.dumps` puts every array element on its own line; prettier (which the
    pre-commit hook enforces on tracked JSON) collapses a short array onto one.
    Rather than let a committed compiler artifact be reformatted by hand after
    every emit — which would make the file's bytes depend on who ran it last —
    the compiler emits prettier's shape itself. The only arrays in this spec are
    `passes`, so the collapse is anchored to that key and nothing else.

    Same input => byte-identical output (G16), and a test pins that.
    """
    text = json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True)
    text = _SHORT_ARRAY_RE.sub(
        lambda m: '"passes": [' + " ".join(m.group(1).split()) + "]",
        text,
    )
    return text + "\n"


def _detect_indent(raw_text: str) -> int:
    for line in raw_text.splitlines()[1:8]:
        stripped = line.lstrip(" ")
        if stripped and stripped != line:
            return len(line) - len(stripped)
    return 2


def _write_json(path: Path, payload: Any, indent: int) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=indent)
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def run_sync_script() -> None:
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "sync"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise CureError(f"sync script failed with exit {result.returncode}")


def update_sidecar() -> None:
    import hashlib
    from datetime import date

    # Field name is "datasetSha256" — that is what the sidecar schema declares
    # and what apps/mouth/src/lib/kbli-dataset-version.test.ts reads. A run
    # that wrote a bare "sha256" key here (2026-07-25) left datasetSha256
    # stale while looking like it had updated the file: the vitest guard went
    # red on a merged PR because check≠action — the key existed, just under
    # the wrong name.
    digest = hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    before = sidecar.get("datasetSha256")
    sidecar["datasetSha256"] = f"sha256:{digest}"
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR_PATH.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("sidecar updated: %s -> sha256:%s", before, digest)


MIN_SURVIVING_BODY = 25


def thin_outcomes(planned: list[tuple[str, str, str, list[str]]]) -> list[str]:
    """Codes whose cured text keeps almost nothing beyond the opening sentence.

    The truncation pass can only drop the fragment; it cannot restore what was
    lost. On a text that was ONE long sentence cut mid-word, dropping the
    fragment leaves the template opener alone (46631). That is still better than
    publishing a sentence cut mid-word, but it is a real content loss and it is
    named here rather than discovered later on the page — restoring the prose is
    an editorial job, tracked in PENDING-ARMS, not something a compiler invents.
    """
    thin = []
    for code, _, new_text, _ in planned:
        body = new_text.replace(FALSE_CLAIM, "").replace(HONEST_CLAIM, "").strip()
        if len(body) < MIN_SURVIVING_BODY:
            thin.append(code)
    return sorted(thin)


def ambiguous_continuity_census(
    records: list[dict[str, Any]], gold: dict[str, Any], by_code: dict[str, dict[str, Any]]
) -> list[tuple[str, str]]:
    """[(code, surface)] the continuity pass deliberately DOES NOT cure.

    Pass D only fires on wordings that assert the NUMBER carried over. "Direct
    match from KBLI 2020" is ambiguous between that and a clean 1:1 ACTIVITY
    mapping onto a different number, so it is excluded — but excluding it
    silently would read as "there was nothing else", which is the failure mode
    a bounded sweep owes the reader a number for. These are the entries that a
    broader pattern WOULD have taken: ambiguous wording, on a record whose own
    code no crosswalk layer records.
    """
    found: list[tuple[str, str]] = []
    for record in records:
        text = str(((record.get("intel_2026") or {}).get("whatChanged") or ""))
        if (
            claims_ambiguous_continuity(text)
            and not claims_number_unchanged(text)
            and number_is_discontinuous(record)
        ):
            found.append((str(record[CODE_FIELD]), "canonical"))
    for code, entry in gold.items():
        record = by_code.get(str(code))
        if record is None:
            continue  # judged by the canonical record or not at all
        text = str((entry or {}).get("whatChanged") or "")
        if (
            claims_ambiguous_continuity(text)
            and not claims_number_unchanged(text)
            and number_is_discontinuous(record)
        ):
            found.append((str(code), "gold"))
    return sorted(found)


def _report(label: str, planned: list[tuple[str, str, str, list[str]]]) -> None:
    print(f"\n{label}: {len(planned)} record(s) to rewrite")
    for name in ALL_PASSES:
        hit = [code for code, _, _, passes in planned if name in passes]
        print(f"  {name}: {len(hit)} {sorted(hit)}")
    thin = thin_outcomes(planned)
    print(f"  …of which left with <{MIN_SURVIVING_BODY} chars of body (editorial restore): {len(thin)} {thin}")
    for code, old, new, passes in planned:
        print(f"\n  {code} {passes}")
        print(f"    OLD: {old[:150]}")
        print(f"    NEW: {new[:150]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--census", action="store_true", help="report the population, write nothing")
    parser.add_argument("--apply", action="store_true", help="mutate both surfaces (default: dry-run)")
    parser.add_argument(
        "--kg-pull",
        type=Path,
        help="read-only pull of live kg_nodes texts ([{entity_id,text,pin}]) to turn into a spec",
    )
    parser.add_argument(
        "--kg-spec-out",
        type=Path,
        default=REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "kg_whatchanged.json",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stdout
    )

    canonical_raw = args.canonical.read_text(encoding="utf-8")
    canonical_indent = _detect_indent(canonical_raw)
    dataset = json.loads(canonical_raw)
    records: list[dict[str, Any]] = dataset["data"]
    by_code = canonical_index(records)

    gold_raw = args.gold.read_text(encoding="utf-8")
    gold_indent = _detect_indent(gold_raw)
    gold_doc = json.loads(gold_raw)
    gold = gold_entries(gold_doc)

    canonical_plan = plan_canonical(records)
    gold_plan, gold_orphans = plan_gold(gold, by_code)

    print(f"canonical records: {len(records)}   gold entries: {len(gold)}")
    _report("CANONICAL", canonical_plan)
    _report("GOLD (renders in preference to canonical)", gold_plan)
    print(
        f"\ngold entries with NO canonical record (unjudgeable, left untouched): "
        f"{len(gold_orphans)} {gold_orphans}"
    )

    ambiguous = ambiguous_continuity_census(records, gold, by_code)
    print(
        f"\nambiguous continuity wording, REPORTED not cured "
        f"(\"direct match from KBLI 2020\" — could mean the same number or a 1:1 "
        f"activity mapping; the record's own code is in no crosswalk layer): "
        f"{len(ambiguous)} {ambiguous}"
    )

    if args.kg_pull:
        pull = json.loads(args.kg_pull.read_text(encoding="utf-8"))
        spec = plan_kg_spec(pull, by_code)
        pulled_codes = {str(r["entity_id"]).split(":", 1)[-1] for r in pull}
        unknown = sorted(pulled_codes - set(by_code))
        print(
            f"\nKG: {len(pull)} node(s) pulled → {len(spec['entries'])} rewrite(s); "
            f"{len(unknown)} pulled node(s) have no canonical record and were left alone: {unknown}"
        )
        for entry in spec["entries"]:
            print(f"  {entry['entity_id']} {entry['passes']}")
        if args.apply:
            args.kg_spec_out.parent.mkdir(parents=True, exist_ok=True)
            args.kg_spec_out.write_text(render_spec_json(spec), encoding="utf-8")
            logger.info("wrote KG cure spec: %s", args.kg_spec_out)

    if args.census or not args.apply:
        print("\nDRY RUN — no files written." if not args.census else "\nCENSUS ONLY.")
        return 0

    if not canonical_plan and not gold_plan:
        logger.info("nothing to cure")
        return 0

    for code, _, new_text, _ in canonical_plan:
        by_code[code]["intel_2026"]["whatChanged"] = new_text
    for code, _, new_text, _ in gold_plan:
        gold[code]["whatChanged"] = new_text

    # A surface with nothing to rewrite is not written AT ALL. Re-serialising it
    # is not a no-op: on 2026-08-05 a run that reported "wrote 0 gold entry(ies)"
    # still stripped the trailing newline from `kbli-gold-all.json`, so the diff
    # carried a file the run had just declared untouched — and `prettier --check`
    # then failed on a change nobody made. A tool that says it wrote nothing must
    # leave the bytes alone.
    if canonical_plan:
        _write_json(args.canonical, dataset, canonical_indent)
    logger.info(
        "wrote %d canonical record(s) to %s",
        len(canonical_plan),
        args.canonical if canonical_plan else "(nothing to write — file untouched)",
    )
    if gold_plan:
        _write_json(args.gold, gold_doc, gold_indent)
    logger.info(
        "wrote %d gold entry(ies) to %s",
        len(gold_plan),
        args.gold if gold_plan else "(nothing to write — file untouched)",
    )

    run_sync_script()
    update_sidecar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
