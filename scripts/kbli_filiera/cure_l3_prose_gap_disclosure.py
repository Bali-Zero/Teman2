#!/usr/bin/env python3
"""cure_l3_prose_gap_disclosure.py — carry the l4_bali gap disclosure into the
EDITORIAL PROSE, on every surface a reader actually sees.

WHY THIS EXISTS
---------------
`cure_l4bali_disclosure.py` cured the FIELD: every record whose Bali verdict was
derived from a dead risk layer now carries `[derivation under review]` on
`l4_bali.reason`. Measured 2026-07-26, `emit_l4bali_gap_disclosure_spec.py
--census` reports **IN SCOPE 0 / already_disclosed 151** — that layer is done.

The prose was never touched, and the emitter's own docstring says so in its own
words: *"this spec does NOT touch editorial prose — it only discloses l4_bali"*,
with a `_meta.editorial_residue` counter for exactly this gap. So a page can show
a badge tooltip reading "derivation under review" directly above an editorial
paragraph that states a Bali risk tier as settled fact. Real examples from the
population: 72201 "Bali classifies it as medium-high to high risk", 79909 "its
OSS risk class at the large-enterprise (Besar) scale is medium-high or high".
This script closes that gap. It is the declared follow-up of that emitter, not a
new discovery.

SELECTION (structural — never prose)
------------------------------------
Population = every canonical record whose `l4_bali.reason` carries
`DISCLOSURE_PREFIX`. That is the same set the field cure wrote, seen from the
other side, and it is 152 records (disputed_key 97 / no_oss_scope 54 /
detached_tier 1) at the canonical of 2026-07-26.

**The asserting subset is NOT selectable, and this is load-bearing** (superscar
#3 arriving at the data layer). Two independent matchers were built and both
failed, in opposite directions:

  - The emitter's own `_TIER_CLAIM_RE`, run over all `intel_2026` fields, flags
    **152 of 152**. A discriminator that fires on the whole population
    discriminates nothing — its author knew, and commented the constant
    *"Bookkeeping only … NEVER used for selection"*.
  - A strict hand-written matcher over `whatYouNeed` flags **19**, and reading
    the 54 it rejected finds real assertions in phrasings it never anticipated
    ("Bali classifies it as", "has a … classification", "falls under higher-risk
    scrutiny"). It also scores the CURE as the DISEASE: the honest-gap sentence
    an earlier wave appended literally contains the words "risk tier".

  ⇒ 19 ≤ truth ≤ 152 and no pattern closes the gap, so this cure appends to ALL
  152 unconditionally. The asymmetry decides it: appending a true statement to a
  page that never asserted a tier is harmless, while failing to append it to one
  that did is the client-facing defect. Membership stays structural, which is
  the rule this whole programme exists to enforce.

TWO SURFACES, MEASURED BEFORE BUILDING
--------------------------------------
`kbli-data.server.ts` renders the gold entry INSTEAD OF `intel_2026` whenever a
gold entry exists (`goldEntry ? {…gold fields…} : {…canonical…}` — a total mask,
not a merge). **39 of the 152 have a non-empty `gold.whatYouNeed`**, and that
subset contains the worst offenders above (72201, 79909 are both in it). A
canonical-only cure would therefore have left the pages that most needed it
completely unchanged while reporting 152/152 cured — the "closed on 3 surfaces,
still lying on the 4th" lesson the /kbli-navigator corner already paid for.
So this script writes BOTH, and its census reports them separately.

IDEMPOTENCY
-----------
Nothing on a record says "this prose already carries the disclosure", and the
only alternative — grepping the prose to decide — is the leaking matcher above.
So the cure writes its OWN marker, `_l3_gap_disclosure`, next to the text it
appended, carrying the sha256 of the exact sentence. A re-run skips what it
already wrote; a change to the wording is visible as a sha mismatch rather than
silently double-appending.

This script writes canonical, so it lives under `scripts/kbli_filiera/` (the
data-plane guard's compiler glob) and syncs the dataset copies + vitest sidecar
exactly as its siblings do.
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

logger = logging.getLogger("kbli_filiera.cure_l3_prose_gap_disclosure")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
GOLD_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

from _prose_disclosure import DISCLOSURE_RE  # noqa: E402
from _l4bali_basis import (  # noqa: E402
    CODE_FIELD,
    DISCLOSURE_PREFIX,
    GAP_BASIS_DETACHED_TIER,
    GAP_BASIS_DISPUTED_KEY,
    GAP_BASIS_NO_OSS_SCOPE,
    gap_basis,
)

PROSE_FIELD = "whatYouNeed"
MARKER_FIELD = "_l3_gap_disclosure"
SPEC_ID = "l3_prose_gap_disclosure_2026_07_26"

# The appended paragraph. One per basis, each saying only what that basis
# supports — the same discipline as the field-layer suffixes, and the same
# refusal to name internal keys in reader-facing text (the catalogue already
# carries hundreds of codes whose prose narrates raw field names; this
# programme is paying that debt down, not adding to it).
#
# WORDING (F12): every clause speaks about OUR retrieval and OUR sources, never
# about what the regulator has or has not published. "Not verifiable in our
# sources" is a statement we can stand behind; "not published" is not.
_HEAD = "\n\n**Risk tier under review.** "
_TAIL = (
    " Where this page states a risk tier or a scale-based requirement, treat it as "
    "provisional pending re-derivation, and verify the current classification at oss.go.id "
    "before acting on it."
)
DISCLOSURE_BY_BASIS: dict[str, str] = {
    GAP_BASIS_DISPUTED_KEY: (
        _HEAD
        + "The licensing rows this code's risk tier was read from have since been set aside as "
        "unverifiable for KBLI 2025, so we cannot currently re-derive it."
        + _TAIL
    ),
    GAP_BASIS_NO_OSS_SCOPE: (
        _HEAD
        + "No KBLI-2025 risk scope for this code could be retrieved from the OSS API when this "
        "dataset was built, so we cannot currently verify the tier this page's assessment was "
        "derived from."
        + _TAIL
    ),
    GAP_BASIS_DETACHED_TIER: (
        _HEAD
        + "The risk tier this code's assessment cites is no longer among the licensing rows we "
        "can verify, so we cannot currently re-derive it."
        + _TAIL
    ),
}

# The anchored pattern is shared with the lot compilers via `_prose_disclosure` —
# two writers of one field must not each own a copy of the rule.
REWORD_RE = DISCLOSURE_RE



class CureError(RuntimeError):
    pass


def sentence_for(basis: str) -> str:
    try:
        return DISCLOSURE_BY_BASIS[basis]
    except KeyError:
        raise CureError(
            f"unknown gap_basis {basis!r} — no sentence defined for it; refusing to guess"
        ) from None


def sentence_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_marker(basis: str, text: str) -> dict[str, Any]:
    return {
        "spec": SPEC_ID,
        "basis": basis,
        "applied_on": date.today().isoformat(),
        "sentence_sha256": sentence_sha(text),
    }


def _load_records(path: Path) -> tuple[Any, list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    if not isinstance(records, list):
        raise CureError(f"unexpected canonical shape in {path}")
    return raw, records


def _detect_indent(raw_text: str) -> int:
    """Measure the file's own indent rather than assuming 2 (sibling convention)."""
    for line in raw_text.splitlines()[1:8]:
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        if leading > 0:
            return leading
    return 2


def in_population(record: dict[str, Any]) -> bool:
    """Structural membership: the FIELD cure already disclosed this record."""
    l4 = record.get("l4_bali")
    if not isinstance(l4, dict):
        return False
    return str(l4.get("reason", "")).startswith(DISCLOSURE_PREFIX)


def plan(
    records: list[dict[str, Any]],
    gold: dict[str, Any],
    only: set[str] | None,
) -> tuple[list[dict[str, Any]], Counter]:
    """Decide, per code, what each surface needs. Writes nothing."""
    plans: list[dict[str, Any]] = []
    stats: Counter = Counter()

    for record in records:
        code = record.get(CODE_FIELD)
        if not code or not in_population(record):
            continue
        if only and code not in only:
            continue
        stats["population"] += 1

        basis = gap_basis(record)
        if basis is None:
            # The field cure disclosed it, so a basis existed when that ran. If it
            # is gone now the record changed underneath us: report, never guess.
            stats["skipped_basis_vanished"] += 1
            logger.warning("%s: disclosed on l4_bali but no gap_basis today — skipped", code)
            continue
        text = sentence_for(basis)
        marker = build_marker(basis, text)

        intel = record.get("intel_2026")
        canonical_action = "missing_prose"
        if isinstance(intel, dict) and isinstance(intel.get(PROSE_FIELD), str) and intel[PROSE_FIELD].strip():
            existing = intel.get(MARKER_FIELD)
            if isinstance(existing, dict) and existing.get("sentence_sha256") == marker["sentence_sha256"]:
                canonical_action = "already_disclosed"
            elif isinstance(existing, dict):
                canonical_action = "reword" if REWORD_RE.search(intel[PROSE_FIELD].rstrip()) else "wording_drift_unanchored"
            else:
                canonical_action = "append"
        stats[f"canonical_{canonical_action}"] += 1

        gold_entry = gold.get(code)
        gold_action = "not_in_gold"
        if isinstance(gold_entry, dict) and isinstance(gold_entry.get(PROSE_FIELD), str) and gold_entry[PROSE_FIELD].strip():
            existing = gold_entry.get(MARKER_FIELD)
            if isinstance(existing, dict) and existing.get("sentence_sha256") == marker["sentence_sha256"]:
                gold_action = "already_disclosed"
            elif isinstance(existing, dict):
                gold_action = "reword" if REWORD_RE.search(gold_entry[PROSE_FIELD].rstrip()) else "wording_drift_unanchored"
            else:
                gold_action = "append"
        elif isinstance(gold_entry, dict):
            # A gold entry with no prose does NOT mask: the renderer takes
            # `goldEntry.whatYouNeed || ""`, so an empty one blanks the section
            # regardless of what canonical holds. Report it rather than write into it.
            gold_action = "gold_prose_empty"
        stats[f"gold_{gold_action}"] += 1

        plans.append(
            {
                "code": code,
                "basis": basis,
                "text": text,
                "marker": marker,
                "canonical_action": canonical_action,
                "gold_action": gold_action,
                "record": record,
                "gold_entry": gold_entry if isinstance(gold_entry, dict) else None,
            }
        )
    return plans, stats


def _rewrite(body: str, item: dict[str, Any]) -> str:
    """Append the paragraph, replacing an earlier wording of it if one is there."""
    stripped = REWORD_RE.sub("", body.rstrip())
    return stripped.rstrip() + item["text"]


def apply_plan(plans: list[dict[str, Any]]) -> tuple[int, int]:
    canonical_writes = gold_writes = 0
    for item in plans:
        if item["canonical_action"] in ("append", "reword"):
            intel = item["record"]["intel_2026"]
            intel[PROSE_FIELD] = _rewrite(intel[PROSE_FIELD], item)
            intel[MARKER_FIELD] = item["marker"]
            canonical_writes += 1
        if item["gold_action"] in ("append", "reword"):
            entry = item["gold_entry"]
            entry[PROSE_FIELD] = _rewrite(entry[PROSE_FIELD], item)
            entry[MARKER_FIELD] = item["marker"]
            gold_writes += 1
    return canonical_writes, gold_writes


def run_sync_script() -> None:
    if not SYNC_SCRIPT.exists():
        raise CureError(f"sync script missing: {SYNC_SCRIPT}")
    logger.info("running %s", SYNC_SCRIPT)
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT)], cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise CureError(f"sync script failed ({result.returncode}): {result.stderr[-2000:]}")


def update_sidecar() -> None:
    if not SIDECAR_DATASET_PATH.exists():
        raise CureError(f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH} (sync must run first)")
    digest = hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    before = dict(sidecar)
    sidecar["datasetSha256"] = f"sha256:{digest}"
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR_PATH.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("sidecar: %s -> %s", before.get("datasetSha256"), sidecar["datasetSha256"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--gold", type=Path, default=GOLD_PATH)
    parser.add_argument("--only", nargs="*", help="restrict to these codes")
    parser.add_argument("--census", action="store_true", help="report and write nothing")
    parser.add_argument(
        "--emit-spec", type=Path, default=None,
        help="write the coverage manifest (the codes this cure touched) and exit",
    )
    parser.add_argument("--apply", action="store_true", help="write (default is dry-run)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    canonical_text = args.canonical.read_text(encoding="utf-8")
    raw, records = _load_records(args.canonical)
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    if not isinstance(gold, dict):
        raise CureError(f"unexpected gold shape in {args.gold}: {type(gold).__name__}")

    only = set(args.only) if args.only else None
    plans, stats = plan(records, gold, only)

    print(f"canonical records: {len(records)}")
    for key in sorted(stats):
        print(f"  {key:34s} {stats[key]}")
    if args.emit_spec:
        # A RECORD of what the structural selector chose — never an input to it.
        # Selection stays `l4_bali.reason` carrying the disclosure prefix; this file
        # exists so the canonical-diff innocence checks can account for every changed
        # record ("no cure spec claims this code" is how they catch a stray mutation),
        # and so coverage is auditable without re-running the tool.
        payload = {
            "_spec_id": SPEC_ID,
            "_generated_by": "scripts/kbli_filiera/cure_l3_prose_gap_disclosure.py --emit-spec",
            "_selection": "structural: l4_bali.reason startswith the l4bali disclosure prefix",
            "_note": (
                "Descriptive, not prescriptive. Editing this file does NOT change which "
                "records the cure touches — re-run --emit-spec to regenerate it."
            ),
            "codes": [{"code": p["code"], "gap_basis": p["basis"]} for p in plans],
        }
        args.emit_spec.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.emit_spec} ({len(plans)} codes)")
        return 0
    if args.census:
        return 0

    actionable = {"append", "reword"}
    to_write = [p for p in plans if actionable & {p["canonical_action"], p["gold_action"]}]
    print(
        f"\n{'APPLY' if args.apply else 'DRY-RUN'}: "
        f"{sum(1 for p in plans if p['canonical_action'] in actionable)} canonical + "
        f"{sum(1 for p in plans if p['gold_action'] in actionable)} gold writes"
    )
    if not args.apply:
        for item in to_write[:3]:
            print(f"\n--- {item['code']} ({item['basis']}) would append:\n{item['text'].strip()}")
        return 0
    if not to_write:
        logger.info("nothing to apply — skipping write, sync and sidecar")
        return 0

    canonical_writes, gold_writes = apply_plan(plans)
    if canonical_writes:
        indent = _detect_indent(canonical_text)
        with args.canonical.open("w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False, indent=indent)
            fh.write("\n")
        logger.info("canonical written: %d records", canonical_writes)
    if gold_writes:
        args.gold.write_text(
            json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        logger.info("gold written: %d entries", gold_writes)
    if canonical_writes:
        run_sync_script()
        update_sidecar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
