#!/usr/bin/env python3
"""emit_batch_membership.py — GARUDA-FILIERA Batch A membership compiler (P0).

Deterministic writer of the reason-coded member list for a Filiera batch, per
the pre-registered plan `research/operations/2026-07-18-kbli-batch-a-plan.md` §1.
Precondition P0: extraction lanes read THIS artifact (not an ad-hoc query) so
every lane operates on the identical, pinned member set.

Membership is by PREDICATE against the canonical, never by a hardcoded count
(plan §1). Each member carries a `reason_code`:

  A-serving/pp28    per_skala non-empty AND pp28_sources non-empty AND no _l2_source
  A-serving/orphan  per_skala non-empty AND pp28_sources empty     AND no _l2_source
  A-empty/gap       _l2_status == "no_oss_risk" AND per_skala == []

Batch A **scope** (what the lanes extract) = the two A-serving classes ONLY
(plan §1: A-empty is the standing no-scope watchlist, a follow-up batch — it is
recorded here for completeness with `in_scope: false`, never extracted in
Batch A).

Determinism (G16): the canonical git revision is pinned INTO the artifact; the
member list is sorted by code; dict key order is fixed. Same canonical revision
=> byte-identical artifact. The compiler refuses to run if the working canonical
differs from the pinned revision's canonical (fencing — a lane must not build a
member list against an unpinned/dirty dataset).

The artifact ALSO pins `canonical_sha256` — sha256 of the canonical file bytes,
alongside `canonical_revision` (a git commit SHA, kept for human readability).
Downstream consumers (e.g. emit_batch_calibration.py) MUST validate pins by
`canonical_sha256` content-equality, never by resolving `canonical_revision`
via git: a shallow CI checkout (depth=1) does not have historical commit
objects, so any git-history-based validation is environment-fragile. This is
the W88 scar discipline (verify state by CONTENT, never a SHA/ancestor/git
proxy) applied to a second fencing surface.

This is a `scripts/kbli_filiera/` compiler — the data-plane guard authorizes it
to write `data/kbli-filiera/**`. It NEVER writes the canonical dataset.

Usage:
    python scripts/kbli_filiera/emit_batch_membership.py            # dry-run (prints census)
    python scripts/kbli_filiera/emit_batch_membership.py --apply    # write the artifact
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
OUT_PATH = REPO_ROOT / "data/kbli-filiera/membership/batch-a-members.json"

REASON_SERVING_PP28 = "A-serving/pp28"
REASON_SERVING_ORPHAN = "A-serving/orphan"
REASON_EMPTY_GAP = "A-empty/gap"
IN_SCOPE_REASONS = {REASON_SERVING_PP28, REASON_SERVING_ORPHAN}


class MembershipError(RuntimeError):
    """Raised on any precondition/fencing violation — fail-visible, never silent."""


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _canonical_revision() -> str:
    """The git blob revision the canonical is pinned to. Fencing: the working
    canonical on disk MUST match HEAD's canonical, else a lane could build a
    member list against uncommitted drift."""
    head_blob = _git("rev-parse", "HEAD:data/source_documents/KBLI_2025_FINAL_CLEAN.json")
    work_blob = hashlib.sha1(
        b"blob " + str(CANONICAL.stat().st_size).encode() + b"\x00" + CANONICAL.read_bytes()
    ).hexdigest()
    if head_blob != work_blob:
        raise MembershipError(
            "canonical on disk differs from HEAD's canonical blob — commit or reset "
            f"before emitting membership (HEAD={head_blob[:12]} work={work_blob[:12]})"
        )
    return _git("rev-parse", "HEAD")


def _classify(record: dict[str, Any]) -> str | None:
    per_skala = record.get("per_skala")
    has_rows = bool(per_skala)
    empty = per_skala == []
    l2_source = record.get("_l2_source")
    l2_status = record.get("_l2_status")
    pp28 = bool(record.get("pp28_sources"))

    if has_rows and not l2_source:
        return REASON_SERVING_PP28 if pp28 else REASON_SERVING_ORPHAN
    if l2_status == "no_oss_risk" and empty:
        return REASON_EMPTY_GAP
    return None


def build_members(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    for r in records:
        code = r.get("kode_kbli_2025")
        if not code:
            continue
        reason = _classify(r)
        if reason is None:
            continue
        members.append(
            {
                "kode_kbli_2025": code,
                "reason_code": reason,
                "in_scope": reason in IN_SCOPE_REASONS,
                "sektor_id": r.get("sektor_id"),
                "judul": r.get("judul"),
                "pp28_sources": r.get("pp28_sources") or [],
            }
        )
    members.sort(key=lambda m: m["kode_kbli_2025"])
    return members


def census(members: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in members:
        out[m["reason_code"]] = out.get(m["reason_code"], 0) + 1
    out["_in_scope_total"] = sum(1 for m in members if m["in_scope"])
    out["_total"] = len(members)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the artifact (default: dry-run)")
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args(argv)

    if not CANONICAL.exists():
        raise MembershipError(f"canonical not found: {CANONICAL}")
    canonical_bytes = CANONICAL.read_bytes()
    records = json.loads(canonical_bytes.decode("utf-8"))["data"]
    revision = _canonical_revision()
    canonical_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
    members = build_members(records)
    cen = census(members)

    print(f"emit_batch_membership — canonical revision {revision[:12]} — mode="
          f"{'APPLY' if args.apply else 'DRY-RUN'}")
    for k in (REASON_SERVING_PP28, REASON_SERVING_ORPHAN, REASON_EMPTY_GAP):
        print(f"  {k}: {cen.get(k, 0)}")
    print(f"  in-scope (Batch A extraction set): {cen['_in_scope_total']}")
    print(f"  total no-scope population: {cen['_total']}")

    artifact = {
        "batch": "A",
        "plan": "research/operations/2026-07-18-kbli-batch-a-plan.md",
        "canonical_revision": revision,
        "canonical_sha256": canonical_sha256,
        "canonical_path": "data/source_documents/KBLI_2025_FINAL_CLEAN.json",
        "predicate_doc": {
            REASON_SERVING_PP28: "per_skala non-empty AND pp28_sources non-empty AND no _l2_source",
            REASON_SERVING_ORPHAN: "per_skala non-empty AND pp28_sources empty AND no _l2_source",
            REASON_EMPTY_GAP: "_l2_status == 'no_oss_risk' AND per_skala == []",
        },
        "census": cen,
        "members": members,
    }
    payload = json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"

    if not args.apply:
        print("DRY RUN — no file written. Re-run with --apply.")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    print(f"wrote {args.out.relative_to(REPO_ROOT)} ({len(members)} members, "
          f"sha256 {hashlib.sha256(payload.encode()).hexdigest()[:12]})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MembershipError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)
