#!/usr/bin/env python3
"""Repo-wide: backfill `new_sha256` into a cure spec, after its patch has
landed on canonical (item J, 2026-08-08 fix-pack hardening).

WHY THIS EXISTS
----------------
`H.judge_patch(rec, old_sha256, new_sha256)` classifies a live record as
either "patch" (hashes to `old_sha256`, apply) or "noop" (hashes to
`new_sha256`, already cured) — never the per-key "already carries the
target values" guess the earlier hardened compilers used, which is blind to
drift on any field the patch never named (see `_hardened_cure_io.judge_
patch`'s own docstring for the blind spot this closes). That means every
spec needs BOTH pins, but `old_sha256` is naturally available when the spec
is AUTHORED (a snapshot of the live record before writing the patch) while
`new_sha256` can only be known AFTER the patch has actually landed — and
for a record more than one cure touches on DIFFERENT fields (this fix-pack's
41011 / 47221 / 90200 / the six asuransi codes each carry two: their own
named cure PLUS `cure_canonical_sector_law_prosepack.py`), only after the
LAST cure in the sequence has landed, or an earlier cure's `new_sha256`
would pin a state a later, legitimate cure immediately invalidates.

So this is a SEPARATE, repo-wide tool, run once near the end of a fix-pack's
data-mutating steps — not folded into any one compiler, because no single
compiler knows whether it is the last one to touch a given record.

WHAT IT DOES
------------
For every code a spec names (either shape this codebase uses: a top-level
`code` + `old_sha256`, as in `cure_canonical_47221_kondisi.py` / `cure_
canonical_90200_whatchanged.py`; or a `codes: {code: {old_sha256, ...}}` map,
as in `cure_canonical_asuransi_pp14_cap.py` / `cure_canonical_sector_law_
prosepack.py`), reads the CURRENT canonical record and:

  * if it still hashes to `old_sha256` — REFUSES. Backfilling now would pin
    the UNPATCHED state as "new", defeating the entire idempotency check;
    apply the cure first.
  * if `new_sha256` is already set and matches the current hash — no-op,
    already backfilled correctly.
  * if `new_sha256` is already set and does NOT match — REFUSES (something
    moved the record again since the last backfill); rerun with `--force`
    only after confirming that move was legitimate.
  * otherwise — writes the current hash as `new_sha256` and reports it.

`--check` (the default) is dry-run; nothing is written without `--write`.
The spec file itself is not in the data-plane registry (only `data/kbli-
filiera/**` and the emitted canonical/gold artifacts are), so a direct write
is the sanctioned path here, same as every other cure spec edit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parent)
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import _hardened_cure_io as H  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
CODE_FIELD = "kode_kbli_2025"

EXIT_OK, EXIT_REFUSED = 0, 2


def _entries(spec: dict) -> dict[str, dict]:
    """Normalize both spec shapes this codebase uses to {code: entry}.

    The single-code shape's "entry" IS the spec itself (aliased, not
    copied) — writing `entry["new_sha256"]` on it sets the spec's own
    top-level key, which is exactly where that shape expects it.
    """
    if "codes" in spec:
        return spec["codes"]
    if "code" in spec:
        return {spec["code"]: spec}
    raise SystemExit(f"spec has neither 'codes' nor 'code' — unrecognised shape: {sorted(spec)}")


def plan(spec: dict, records: list[dict], force: bool) -> dict[str, dict]:
    """Pure. {code: {"action": "backfill"|"noop"|"refuse", ...}}."""
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    out: dict[str, dict] = {}
    for code, entry in _entries(spec).items():
        rec = by_code.get(code)
        if rec is None:
            out[code] = {"action": "refuse", "reason": "not in canonical"}
            continue

        current = H.sha256_of(rec)
        old = entry.get("old_sha256")
        existing_new = entry.get("new_sha256")

        if current == old:
            out[code] = {
                "action": "refuse",
                "reason": (
                    "record still hashes to old_sha256 — not yet patched; "
                    "apply the cure with --apply first"
                ),
            }
            continue
        if existing_new is not None and current == existing_new:
            out[code] = {"action": "noop", "reason": "already backfilled"}
            continue
        if existing_new is not None and current != existing_new and not force:
            out[code] = {
                "action": "refuse",
                "reason": (
                    f"new_sha256 already pinned to {existing_new!r} but the live "
                    f"record now hashes to {current!r} — something moved this "
                    "record again since the last backfill; re-run with --force "
                    "only after confirming that move was legitimate"
                ),
            }
            continue
        out[code] = {"action": "backfill", "sha256": current}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="path to the cure spec JSON to backfill")
    ap.add_argument("--dataset", default=str(CANONICAL))
    ap.add_argument("--write", action="store_true", help="write the spec (default: --check, dry-run)")
    ap.add_argument("--force", action="store_true", help="overwrite a new_sha256 pin that no longer matches")
    args = ap.parse_args(argv)

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    _, records, _ = H.load_dataset(Path(args.dataset))

    verdicts = plan(spec, records, force=args.force)

    refused = {c: v for c, v in verdicts.items() if v["action"] == "refuse"}
    for code, v in refused.items():
        print(f"REFUSED {code}: {v['reason']}")
    if refused:
        return EXIT_REFUSED

    noop = [c for c, v in verdicts.items() if v["action"] == "noop"]
    to_backfill = {c: v for c, v in verdicts.items() if v["action"] == "backfill"}
    for code in noop:
        print(f"{code}: already backfilled — no-op")
    for code, v in to_backfill.items():
        print(f"{code}: new_sha256 -> {v['sha256']}")

    if not to_backfill:
        print("nothing to backfill")
        return EXIT_OK
    if not args.write:
        print("\ndry-run — rerun with --write to persist")
        return EXIT_OK

    entries = _entries(spec)
    for code, v in to_backfill.items():
        entries[code]["new_sha256"] = v["sha256"]

    body = json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
    H.atomic_write_text(spec_path, body)
    print(f"\nwrote {len(to_backfill)} new_sha256 pin(s) to {spec_path}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
