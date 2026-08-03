#!/usr/bin/env python3
"""cure_l4_withdrawn_umkm_prose.py — retire the withdrawn UMKM inference from the
EDITORIAL PROSE, one spec-authored sentence at a time.

WHY THIS EXISTS
---------------
On 2026-08-03 Permeninves/BKPM 5/2025 Pasal 26(1) withdrew the inference that had
closed codes on the ground that OSS shows them no *Usaha Besar* scale row: being
Usaha Besar is a CONSEQUENCE of holding PMA status, not a precondition for
registering, so the absence of that row says nothing about foreign ownership. The
VERDICT layer was cured that day and the 1,559 code pages with it. The prose that
EXPLAINS each verdict was not, and 34 canonical records still argue the withdrawn
claim in fluent English.

This compiler cures the first and most expensive slice of that backlog: the 13
records whose Bali verdict is `NON_CLASSIFICABILE` — "we hold no verified
licensing rows, so no Bali position can be stated" — while their prose tells the
reader a PT PMA *cannot register* the activity. The page contradicts its own
badge, and it errs toward turning away business we could take.

WHAT IT WILL NOT DO
-------------------
It never authors a replacement. Every `new` string comes from
`cure_specs/l4_withdrawn_umkm_prose.json`, which records who graded it. It never
touches `l4_bali` — that layer is already correct and restating a settled verdict
is how a correction becomes a new claim (W113). It never touches gold: measured
before writing this, `apps/mouth/data/kbli-gold-all.json` holds no editorial prose
for these codes (0 pattern hits, no `editorial` key, and 7 of the 13 are absent
from gold entirely), so a gold path here would be a limb with no blood in it.

THE PREMISE IS PINNED, AND A MOVED PREMISE IS A REFUSAL
-------------------------------------------------------
Each spec entry carries `expect_l4_status` / `expect_l4_blocked` as they stood
when the prose was authored and graded. If a record's verdict has since moved,
the replacement was written about a world that no longer exists, and this script
REFUSES that code rather than writing prose graded against a stale premise. That
is not defensive dressing: the whole reason this backlog exists is that a verdict
changed and the prose explaining it did not.

FAIL-VISIBLE, NEVER A SILENT GUESS
----------------------------------
A patch applies only when `old` occurs EXACTLY ONCE in its field. Already-applied
is recognised (old absent AND new present) and skipped. Every other state — old
missing and new missing, old repeated, both present — is a CureError. A cure that
guesses at ambiguity is worse than one that stops.

USAGE (dry-run is the default; nothing is written without --apply):
    python3 scripts/kbli_filiera/cure_l4_withdrawn_umkm_prose.py
    python3 scripts/kbli_filiera/cure_l4_withdrawn_umkm_prose.py --apply
    python3 scripts/kbli_filiera/cure_l4_withdrawn_umkm_prose.py --only 70100 93199 --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("kbli_filiera.cure_l4_withdrawn_umkm_prose")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts/kbli_filiera/cure_specs/l4_withdrawn_umkm_prose.json"
DEFAULT_CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
SYNC_SCRIPT = REPO_ROOT / "scripts/sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps/mouth/data/kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"


class CureError(RuntimeError):
    """A state the spec does not describe. Always fatal, never a guess."""


def _dig(container: dict[str, Any], dotted: str) -> tuple[dict[str, Any], str]:
    """Resolve `a.b.c` to (owning dict, final key). Missing parents are an error,
    not a silently-created path: this cure edits prose that already exists."""
    parts = dotted.split(".")
    node: Any = container
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            raise CureError(f"field path {dotted!r} does not exist (stopped at {part!r})")
        node = node[part]
    if not isinstance(node, dict):
        raise CureError(f"field path {dotted!r} does not resolve to an object")
    return node, parts[-1]


def apply_patch(record: dict[str, Any], code: str, patch: dict[str, str]) -> bool:
    """Return True if the record changed, False if the patch was already applied."""
    intel = record.get("intel_2026")
    if not isinstance(intel, dict):
        raise CureError(f"{code}: no intel_2026 object to patch")
    owner, key = _dig(intel, patch["field"])
    if key not in owner:
        # Distinguished from the type error below on purpose: an ABSENT field and
        # a field holding the wrong type send a reader to different places, and a
        # diagnosis that names the wrong cause costs more than no diagnosis (W106).
        raise CureError(f"{code}.{patch['field']}: field does not exist on this record")
    text = owner[key]
    if not isinstance(text, str):
        raise CureError(
            f"{code}.{patch['field']}: exists but holds {type(text).__name__}, not a string"
        )

    old, new = patch["old"], patch["new"]
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
    l4 = record.get("l4_bali") or {}
    want_status = entry.get("expect_l4_status")
    want_blocked = entry.get("expect_l4_blocked")
    got_status, got_blocked = l4.get("status"), l4.get("blocked")
    if got_status != want_status or got_blocked != want_blocked:
        raise CureError(
            f"{code}: premise moved — spec was written against "
            f"status={want_status!r}/blocked={want_blocked!r}, record now holds "
            f"status={got_status!r}/blocked={got_blocked!r}. The replacement prose was "
            "graded against the old verdict; re-author and re-grade it rather than "
            "writing it onto a record it no longer describes."
        )


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


def reconcile_sidecar(canonical: Path) -> bool:
    """Keyed on the MISMATCH, not on whether this run changed anything — a no-op
    run must still reconcile a sidecar that drifted (the l23 compiler learned this
    the hard way: hung off `if changed`, it was unreachable exactly when wrong)."""
    if not SIDECAR_DATASET_PATH.exists():
        raise CureError(f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH} (sync must run first)")
    if SIDECAR_DATASET_PATH.read_bytes() != canonical.read_bytes():
        logger.info("sidecar dataset copy differs from canonical — syncing before hashing")
        run_sync_script()
    digest = hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    before = sidecar.get("datasetSha256")
    if before == f"sha256:{digest}":
        logger.info("sidecar already current (%s) — no write", before)
        return False
    # The `sha256:` prefix is load-bearing: a bare hex string in committed data
    # trips `Detect Secrets` (a REQUIRED check) as a high-entropy string.
    sidecar["datasetSha256"] = f"sha256:{digest}"
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR_PATH.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("sidecar updated: %s -> %s", before, sidecar["datasetSha256"])
    return True


def run(spec_path: Path, canonical_path: Path, only: list[str] | None, apply: bool) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    codes: dict[str, Any] = spec["codes"]
    if only:
        unknown = sorted(set(only) - set(codes))
        if unknown:
            raise CureError(f"--only names codes absent from the spec: {unknown}")
        codes = {c: codes[c] for c in only}

    doc = json.loads(canonical_path.read_text(encoding="utf-8"))
    by_code = {r["kode_kbli_2025"]: r for r in doc["data"]}

    missing = sorted(set(codes) - set(by_code))
    if missing:
        raise CureError(f"spec names codes absent from canonical: {missing}")

    changed_records, changed_patches, skipped = 0, 0, 0
    for code, entry in codes.items():
        record = by_code[code]
        check_premise(record, code, entry)
        touched = False
        for patch in entry["patches"]:
            if apply_patch(record, code, patch):
                changed_patches += 1
                touched = True
            else:
                skipped += 1
        if touched:
            changed_records += 1
            logger.info("%s — %s", code, entry.get("judul", ""))

    logger.info(
        "%s: %d record(s), %d patch(es) rewritten, %d already applied",
        "APPLY" if apply else "DRY-RUN", changed_records, changed_patches, skipped,
    )
    if not apply:
        logger.info("nothing written — rerun with --apply")
        return 0

    if changed_patches:
        canonical_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info("canonical written: %s", canonical_path)
        run_sync_script()
    reconcile_sidecar(canonical_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    ap.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    ap.add_argument("--only", nargs="+", metavar="CODE")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run, writes nothing)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        return run(args.spec, args.canonical, args.only, args.apply)
    except CureError as exc:
        logger.error("REFUSED: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
