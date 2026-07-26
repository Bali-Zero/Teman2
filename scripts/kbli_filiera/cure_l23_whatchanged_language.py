#!/usr/bin/env python3
"""cure_l23_whatchanged_language.py — render the Italian machine templates in
`whatChanged` into English, on BOTH surfaces that serve it.

WHY THIS EXISTS
---------------
`intel_2026.whatChanged` is client-facing: `apps/mouth/src/app/kbli/[code]/page.tsx`
renders the gold copy at :428 and the canonical copy at :689, inside the
"2025 Transition" block of an otherwise-English regulatory page. The field is
composed by concatenating the record's `mapping_note` VERBATIM onto an English
lead sentence — and `mapping_note` is Italian machine output from the crosswalk
pipeline. So the page speaks English until the transition section, then Italian.

Measured on origin/main 2026-07-26: **346 of 1,559 records (22.2%)** carry at
least one of the six literal templates in the spec. Curled live on prod before
this cure ran, e.g. `/kbli/46442` served
"Il KBLI 2025 mantiene 46442 separato da 46441, rafforzando la distinzione
regolatorio-ministeriale ...".

WHY IT IS A TEMPLATE MAP AND NOT 346 TRANSLATIONS
-------------------------------------------------
Clustering the Italian-bearing sentences by normalised shape yields **17 shapes
for 354 sentences**, and the top two shapes alone are 314 of them. This is
machine output, so it is cured mechanically with zero editorial judgement. The
rule table lives in `cure_specs/l23_whatchanged_language.json` — spec-authored,
reviewable in one screen, never invented inline (same contract as
`cure_l4_editorial.py`: this script NEVER authors a replacement string).

BOTH SURFACES, AND GOLD IS THE ONE THAT MATTERS MOST
----------------------------------------------------
`gold` TOTALLY MASKS `intel_2026` in `kbli-data.server.ts` (`goldEntry ? {...} :
{...}` — a mask, not a merge), so a canonical-only cure reports success and
changes nothing on the pages that carry a gold body. That is the corner's rule
#2, already paid for once, and it bites here: gold carries **no Italian at all**
(428/428 records have whatChanged, 0 match any Italian template — its prose is
separately authored, e.g. "Unchanged from KBLI 2020 - direct match") but **111
of its 428 records leak a RAW ENUM** into that prose: "Direct match from KBLI
2020 (MATCH_LANGSUNG)." on a public page. Scanning gold for the Italian defect
alone would have declared it clean and left the enum leak live on precisely the
copy clients read. Two defects, two different distributions across the same two
surfaces — which is why each surface is measured for BOTH, not assumed to share
the other's diagnosis.

WHAT IT DOES NOT CLAIM
----------------------
It does not claim `whatChanged` ends up entirely English. A residue of
free-prose Italian matches no template (46442's hand-written clause is the
clearest case). The compiler COUNTS AND PRINTS that residue on every run — a
bounded cure that reports its own remainder, rather than a sweep that reads as
total. `346` is a FLOOR from literal matching; a looser word-list matcher scored
~353 and a looser matcher can also produce false positives. Neither number is
"the number of Italian records"; both are bounds from a form-matcher.

USAGE (dry-run is the default; nothing is written without --apply):
    python3 scripts/kbli_filiera/cure_l23_whatchanged_language.py
    python3 scripts/kbli_filiera/cure_l23_whatchanged_language.py --only 01279 10305
    python3 scripts/kbli_filiera/cure_l23_whatchanged_language.py --apply

AFTER --apply, IN THE SAME COMMIT (both are non-negotiable, both learned the hard way):
  * the sidecar pin is bumped here automatically (a REQUIRED check asserts it);
  * `python3 scripts/kbli_filiera/emit_batch_membership.py --apply` must be run
    as a SEPARATE, LATER commit — that emitter fences on "working canonical ==
    HEAD's blob", so it structurally cannot run while this cure holds the
    canonical dirty. Skipping it leaves the batch-A membership pin orphaned,
    which only a NON-required check notices — i.e. it ships.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("kbli_filiera.cure_l23_whatchanged_language")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "l23_whatchanged_language.json"
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
DEFAULT_GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"
FIELD = "whatChanged"

# Residue probe. Deliberately literal and deliberately NOT the cure's own rule
# set: if it reused the rules it would report zero by construction — a check
# that cannot fail. These are tokens that are unambiguously Italian IN THIS
# CORPUS; the count is reported as a bound, never as a truth.
_RESIDUE_MARKERS = (
    "mantiene", "separato", "rafforzando", "rinumerato", "aggregazione",
    "codici", "usa codice", "Dati da", "stabile", "confermato",
    "Verifica e aggiornamento",
)


class CureError(RuntimeError):
    """A spec/data mismatch severe enough to make the run's exit non-zero.

    Propagates uncaught out of main() — the fail-visible contract shared with
    cure_l4_editorial.py and cure_canonical_collisions.py.
    """


def _detect_indent(raw_text: str) -> int:
    """Measure the file's own indent rather than presuming 2."""
    for line in raw_text.splitlines()[1:8]:
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        if leading > 0:
            return leading
    return 2


def load_rules(spec_path: Path) -> list[dict[str, Any]]:
    """Compile the spec's rules. A spec with no rules is an ERROR, not a no-op:
    a cure that silently cures nothing is indistinguishable from a cure that
    worked, which is precisely how a broken gate ships (W102)."""
    if not spec_path.exists():
        raise CureError(f"spec not found: {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    rules = spec.get("rules") or []
    if not rules:
        raise CureError(f"spec {spec_path} declares no rules — refusing to run a no-op sweep")
    compiled = []
    for r in rules:
        for key in ("id", "pattern", "replacement"):
            if key not in r:
                raise CureError(f"spec rule missing '{key}': {r}")
        compiled.append({**r, "regex": re.compile(r["pattern"])})
    return compiled


def cure_text(text: str, rules: list[dict[str, Any]], hits: Counter) -> str:
    """Apply every rule in order. Records per-rule hit counts in `hits`.

    Each rule is anchored on its full template context, so none can fire inside
    a quoted historical label — see the spec's `_the_trap_guarded_here`.
    """
    out = text
    for rule in rules:
        if rule.get("uppercase_first_group"):
            # A regex replacement cannot change case, and stripping a leading
            # token ("MATCH_LANGSUNG — direct match…") would otherwise leave a
            # sentence starting lowercase. The flag is explicit per-rule rather
            # than a blanket post-pass: a blanket "uppercase after ." would also
            # rewrite prose this cure has no business touching.
            repl = lambda mm: mm.group(1).upper() + mm.group(2)  # noqa: E731
        else:
            repl = rule["replacement"]
        out, n = rule["regex"].subn(repl, out)
        if n:
            hits[rule["id"]] += n
    # Collapse whitespace the deletion rule may have doubled, without touching
    # newlines (the field is rendered with whitespace-pre-line in places).
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def residue_markers(text: str) -> list[str]:
    """Which residue markers survive in `text`. A bound, not a verdict.

    QUOTED SPANS ARE STRIPPED FIRST, and that is the whole subtlety. One record
    carries an English audit note that CITES the old Italian label as history:
    "the previous 'match con aggregazione' status_mapping/label was stale".
    That citation is text this cure deliberately preserves — rewriting it would
    corrupt an audit trail. A probe that counted it would report ~54 records of
    "residue" that are in fact correctly cured, i.e. the probe would be
    over-matching in exactly the way the cure is built not to. Measured: 54
    flagged before this strip, 5 after, and the 49 difference was entirely that
    one quoted label. A guard and its own success-metric must both match the
    ENTITY, never the bare substring (superscar #3).
    """
    scannable = re.sub(r"'[^']*'", " ", text)
    low = scannable.lower()
    return [m for m in _RESIDUE_MARKERS if m.lower() in low]


def _iter_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    for key in ("data", "codes", "records"):
        if isinstance(payload, dict) and isinstance(payload.get(key), list):
            return payload[key]
    raise CureError("could not locate the record list in the dataset payload")


def canonical_pairs(payload: Any) -> list[tuple[str, Any]]:
    """(code, intel_2026) for the canonical — a LIST of records."""
    pairs = []
    for rec in _iter_records(payload):
        code = str(rec.get(CODE_FIELD) or rec.get("kode_kbli") or rec.get("code") or "")
        pairs.append((code, rec.get("intel_2026")))
    return pairs


def gold_pairs(payload: Any) -> list[tuple[str, Any]]:
    """(code, intel) for the gold — a DICT KEYED BY CODE whose values hold the
    intel fields at top level. A different shape from the canonical's list, and
    worth stating rather than papering over: an earlier version of this script
    assumed one shape for both and raised instead of silently curing nothing —
    which is the behaviour we want and why the shapes get separate functions."""
    if not isinstance(payload, dict):
        raise CureError(f"gold dataset is {type(payload).__name__}, expected a code-keyed dict")
    return [(str(code), intel) for code, intel in payload.items()]


def cure_dataset(
    pairs: list[tuple[str, Any]],
    rules: list[dict[str, Any]],
    only: set[str] | None,
    label: str,
) -> tuple[int, Counter, list[tuple[str, list[str]]]]:
    """Cure `FIELD` in every (code, container) pair. Returns (changed, hits, residues)."""
    changed = 0
    hits: Counter = Counter()
    residues: list[tuple[str, list[str]]] = []
    for code, container in pairs:
        if only and code not in only:
            continue
        if not isinstance(container, dict):
            continue
        before = container.get(FIELD)
        if not isinstance(before, str) or not before:
            continue
        after = cure_text(before, rules, hits)
        if after != before:
            container[FIELD] = after
            changed += 1
        left = residue_markers(after)
        if left:
            residues.append((code, left))
    logger.info("%s: %d record(s) rewritten", label, changed)
    return changed, hits, residues


def run_sync_script() -> None:
    logger.info("running %s sync", SYNC_SCRIPT)
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "sync"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise CureError(f"sync_kbli_dataset.sh sync failed with exit {result.returncode}")


def update_sidecar() -> None:
    if not SIDECAR_DATASET_PATH.exists():
        raise CureError(f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH} (sync must run first)")
    digest = hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    before = sidecar.get("datasetSha256")
    # The `sha256:` prefix is load-bearing, not decoration: a BARE hex string in
    # committed data trips `Detect Secrets`, a REQUIRED check, as a "Hex High
    # Entropy String" — and which hashes trip it is a dice roll re-rolled every
    # run, so auditing today's offenders prevents nothing.
    sidecar["datasetSha256"] = f"sha256:{digest}"
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR_PATH.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("sidecar updated: %s -> %s", before, sidecar["datasetSha256"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    ap.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    ap.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    ap.add_argument("--only", nargs="+", default=None, help="restrict to these KBLI codes")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run, writes nothing)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    rules = load_rules(args.spec)
    only = set(args.only) if args.only else None

    raw = args.canonical.read_text(encoding="utf-8")
    indent = _detect_indent(raw)
    payload = json.loads(raw)

    c_changed, c_hits, c_residue = cure_dataset(
        canonical_pairs(payload), rules, only, "canonical"
    )

    gold_payload = json.loads(args.gold.read_text(encoding="utf-8"))
    g_changed, g_hits, g_residue = cure_dataset(
        gold_pairs(gold_payload), rules, only, "gold"
    )

    total_hits = c_hits + g_hits
    print()
    print("  per-rule replacements (canonical + gold):")
    for rule in rules:
        print(f"    {total_hits.get(rule['id'], 0):>5}  {rule['id']}")
    print(f"    {sum(total_hits.values()):>5}  TOTAL")

    # No silent caps: the remainder this cure does NOT cover is printed, always.
    residue = {c for c, _ in c_residue} | {c for c, _ in g_residue}
    print()
    print(f"  residue after cure: {len(residue)} record(s) still match >=1 Italian marker")
    print("    (a BOUND from a form-matcher, not a verdict — free-prose Italian")
    print("     matches no template and is deliberately out of this cure's scope)")
    for code, markers in sorted(c_residue + g_residue)[:8]:
        print(f"      {code}: {','.join(markers)}")

    if not args.apply:
        print()
        logger.info(
            "DRY-RUN — canonical=%d gold=%d record(s) would change; rerun with --apply",
            c_changed, g_changed,
        )
        return 0

    if g_changed:
        args.gold.write_text(
            json.dumps(gold_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if c_changed:
        with args.canonical.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=indent)
            f.write("\n")
        run_sync_script()
        update_sidecar()

    logger.info("APPLIED — canonical=%d gold=%d record(s) rewritten", c_changed, g_changed)
    logger.info(
        "NEXT, as a SEPARATE later commit: python3 scripts/kbli_filiera/emit_batch_membership.py --apply"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
