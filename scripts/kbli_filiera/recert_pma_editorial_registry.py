#!/usr/bin/env python3
"""recert_pma_editorial_registry.py — re-stamp the PMA editorial certification
registry's freshness pin after a canonical-only change that never moves
certified content's PMA-fingerprint-relevant fields.

WHY THIS EXISTS (2026-09-15, SAETTA-20260915 W-H, ported to W-J B1)
--------------------------------------------------------------------
`data/kbli-filiera/pma-editorial-certifications.json` pins `sourceDatasetSha256`
to the exact canonical bytes its 66 `pmaFingerprint`/`contentSha256` entries were
reviewed against (`apps/backend-rag/backend/services/kbli_editorial_certification.py`
enforces this at read time — `assert_certified_source_dataset`). Any PR that
writes canonical moves that hash, so `backend/tests/scripts/
test_kbli_qdrant_pma_sync.py` goes red in CI even when the local
`scripts/kbli_filiera/tests/` suite is clean (it never imports the backend
package). The registry lives under `data/kbli-filiera/**`, so the data-plane
guard refuses a hand-edit — this is the registered compiler that guard wants.

WHAT IT DOES, AND ONLY THIS
----------------------------
1. Diffs canonical between `HEAD^` and `HEAD` (or `--base`) to find exactly
   which `kode_kbli_2025` values changed — the same population a cure's own
   `verify_untouched` guard already proved is the complete touched set.
2. Reports (does NOT auto-refuse on) any overlap between the touched codes
   and the certified set — see "W-J B1 refinement" below for why this is a
   report, not a gate, on this branch.
3. Recomputes `pmaFingerprint` for all 66 certified codes against the NEW
   canonical via the real backend service (never re-derived) and refuses on
   ANY mismatch — this is the actual load-bearing gate: `pmaFingerprint`
   hashes only the `pma_*` national-disclosure fields (`disclose_pma`'s
   output), never `l4_bali.*`, so it is the exact invariant
   `matches_editorial_certification` enforces at read time.
4. Confirms the two external gold sources (`apps/mouth/data/
   kbli-gold-all.json`, `apps/kbli-navigator/lib/kbli-gold-content.ts`) are
   byte-identical to `--base` — the other content certified codes can draw
   from, and an l4_bali-only cure does not touch either.
5. Only if 3-4 hold: patches `sourceDatasetSha256` (to the new canonical's
   sha256) and `reviewedAt` (today), and NOTHING else — every per-code
   fingerprint is left byte-identical, because they did not move.

W-J B1 refinement vs the original W-H version
-----------------------------------------------
The W-H original (`5659ea41a4`) auto-REFUSED on any overlap between changed
and certified codes, because its own PR never had one. W-J B1's
`cure_l4bali_applied_closure.py` national-cap guard (finding 1, 2026-09-15
cure round) DOES touch 4 certified codes' records (10214, 16221, 95220,
95299) — but only their `l4_bali.*` fields (`touched_paths_for()` +
`H.verify_untouched()` refuse anything else repo-wide). `pmaFingerprint`
depends solely on `disclose_pma(record)`'s `pma_*` fields, which this cure
never writes — confirmed empirically (0/66 mismatches, including these 4)
before this refinement was written. Auto-refusing on raw-record overlap
would be a coarser PROXY for "content may have moved" than step 3's exact
fingerprint recomputation already is, so treating overlap as informational
and letting step 3 be the sole gate is a precision fix, not a loosening —
the enforcement code at read time was never checking record-equality, only
`pmaFingerprint`/`contentSha256` equality.

It never re-certifies a code, never edits a fingerprint, and never widens the
certified set — that is a human review, not a re-stamp.

Usage:
    PYTHONPATH=apps/backend-rag python3 scripts/kbli_filiera/recert_pma_editorial_registry.py --base HEAD
    PYTHONPATH=apps/backend-rag python3 scripts/kbli_filiera/recert_pma_editorial_registry.py --base HEAD --apply
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
REGISTRY = REPO_ROOT / "data" / "kbli-filiera" / "pma-editorial-certifications.json"
MOUTH_GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
STANDALONE_GOLD = REPO_ROOT / "apps" / "kbli-navigator" / "lib" / "kbli-gold-content.ts"
CODE_FIELD = "kode_kbli_2025"

EXIT_OK, EXIT_REFUSED = 0, 2


class RecertError(RuntimeError):
    pass


def _git_show(rev: str, rel_path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{rev}:{rel_path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def changed_codes(base: str) -> set[str]:
    """Every kode_kbli_2025 whose record differs between `base` and the
    working tree — computed by full-record comparison, not a line diff, so a
    key reordering that changes nothing is never reported as a change."""
    before_raw = _git_show(base, CANONICAL.relative_to(REPO_ROOT))
    if before_raw is None:
        raise RecertError(f"cannot read canonical at {base} — is it a valid ref?")
    before = {r[CODE_FIELD]: r for r in json.loads(before_raw)["data"]}
    after = {r[CODE_FIELD]: r for r in json.loads(CANONICAL.read_text(encoding="utf-8"))["data"]}
    codes = set(before) | set(after)
    return {c for c in codes if before.get(c) != after.get(c)}


def unchanged_since(base: str, path: Path) -> bool:
    before = _git_show(base, path.relative_to(REPO_ROOT))
    if before is None:
        return not path.exists()
    return path.exists() and path.read_text(encoding="utf-8") == before


def certified_codes(registry: dict) -> set[str]:
    out: set[str] = set()
    for section in ("canonicalIntel", "mouthGold", "standaloneGold"):
        out |= set((registry.get(section) or {}).keys())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the registry (default: dry-run)")
    ap.add_argument("--base", default="HEAD^", help="git ref to diff canonical/gold against")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))
    try:
        from backend.services.kbli_editorial_certification import (  # noqa: E402
            pma_editorial_fingerprint,
        )
    except ImportError as exc:
        print(f"CANNOT-VERIFY: {exc} — run with PYTHONPATH=apps/backend-rag", file=sys.stderr)
        return EXIT_REFUSED

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    certified = certified_codes(registry)

    try:
        touched = changed_codes(args.base)
    except RecertError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    overlap = touched & certified
    if overlap:
        print(
            f"NOTE: {sorted(overlap)} changed AND certified — proceeding only if "
            "their pmaFingerprint (step 3, the actual enforcement invariant) is "
            "unchanged; any mismatch below is a hard refusal.",
        )

    canonical = {r[CODE_FIELD]: r for r in json.loads(CANONICAL.read_text(encoding="utf-8"))["data"]}
    mismatches = []
    for section in ("canonicalIntel", "mouthGold", "standaloneGold"):
        for code, cert in (registry.get(section) or {}).items():
            record = canonical.get(code)
            if record is None:
                mismatches.append(f"{section}/{code}: not in canonical")
                continue
            fp = pma_editorial_fingerprint(record)
            if fp != cert.get("pmaFingerprint"):
                mismatches.append(f"{section}/{code}: pmaFingerprint moved")
    if mismatches:
        print("REFUSED — pmaFingerprint moved on a certified code:", file=sys.stderr)
        for m in mismatches:
            print(f"  {m}", file=sys.stderr)
        return EXIT_REFUSED

    for path in (MOUTH_GOLD, STANDALONE_GOLD):
        if not unchanged_since(args.base, path):
            print(f"REFUSED: {path} changed since {args.base} — content may have moved", file=sys.stderr)
            return EXIT_REFUSED

    new_sha = hashlib.sha256(CANONICAL.read_bytes()).hexdigest()
    old_sha = registry.get("sourceDatasetSha256")
    today = datetime.date.today().isoformat()

    print(f"{len(certified)} certified code(s), 0 pmaFingerprint mismatch, overlap {sorted(overlap)}")
    print(f"sourceDatasetSha256: {old_sha} -> {new_sha}")
    print(f"reviewedAt: {registry.get('reviewedAt')} -> {today}")

    if not args.apply:
        print("dry-run — rerun with --apply to write")
        return EXIT_OK

    registry["sourceDatasetSha256"] = new_sha
    registry["reviewedAt"] = today
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {REGISTRY}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
