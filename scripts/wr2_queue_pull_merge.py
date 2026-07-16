#!/usr/bin/env python3
"""WR2 queue pull-merge — protect app-side publish transitions from the Pro pull.

WHY (Armate recon 2026-07-13, adversarially CONFIRMED): the WR2 Control app on
M5 writes publish transitions LOCALLY (QueueWriter.markPublished sets
state="published" in the local human-review-queue.json), while
wr2-queue-pull.sh blind-replaces that file with Pro's copy every 300s — the
operator marks a carousel published and minutes later it silently reverts to
"drafted" (split-brain, scar family #10). Pro stays the SSOT; this module makes
the pull a MERGE instead of a clobber, and emits the push-back list so the
wrapper can replay the protected transitions into Pro via the canonical
scripts/wr2_queue_writer.py mark-published (exact ref-code, validated IG URL).

Merge semantics (monotone state lattice — remote wins EXCEPT):
  - entry in both, LOCAL state is published* and REMOTE state is not:
    remote entry is kept as base, local publish fields overlaid
    (state, instagram_post_url, instagram_published_at, engagement_metrics,
    damar_action, damar_action_at, state_history) → also listed in push_back
    when its ref-code/IG-URL are shell-safe by construction (strict regex).
  - entry only in LOCAL (app-created: upload/auto-enqueue): kept, appended
    after remote entries, reported as local_only. Never pushed back.
    EXCEPTION (2026-07-17, archive-blind resurrect fix): if the entry's id
    is present in `remote_archive` (Pro's freshly-pulled queue-archive.json),
    Pro deliberately ARCHIVED it — it is dropped instead of resurrected, and
    reported under `archived_dropped`. Live case: a golden-visa entry
    archived on Pro kept reappearing on M5 every tick because the old code
    treated "gone from remote queue" as always meaning "new local entry".
    CRITICAL COUNTER-EXCEPTION (Codex red-team, 2026-07-17): a LOCAL entry
    that is itself published* is ALWAYS kept even when archived on Pro —
    kept in the merged output AND reported as local_only, plus flagged
    under `published_local_kept_despite_archive`. Rationale: push_back only
    fires from the REMOTE loop above, and once Pro archives the id it is no
    longer in the remote queue at all — if this loop dropped it too, a
    local publish transition that hadn't push-backed yet (race: M5
    publishes, Pro archives before the next tick's push-back lands) would
    lose its published state + instagram_post_url PERMANENTLY.
    Pathological case (present in BOTH remote queue and remote archive):
    the live queue wins — kept as a normal remote entry (not local_only, not
    dropped), with a warning in `queue_and_archive_conflict`.
  - everything else: remote wins verbatim.

CLI (used by infra/launchagents/wrappers/wr2-queue-pull.sh):
    python3 scripts/wr2_queue_pull_merge.py --remote R.json --local L.json \
        --out M.json [--remote-archive A.json]
prints a JSON report to stdout:
    {"protected": [ids], "local_only": [ids],
     "push_back": [{"id":..., "ref_code": "WR2-XXXXXX", "ig_url": ...}],
     "archived_dropped": [ids], "queue_and_archive_conflict": [ids],
     "published_local_kept_despite_archive": [ids]}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wr2_queue_writer import (  # noqa: E402 — same scripts/ dir
    PUBLISHED_STATES,
    compute_ref_code,
    item_id_of,
    validate_ig_url,
)

_REF_CODE_SAFE_RE = re.compile(r"^WR2-[0-9A-F]{6}$")

# Local fields overlaid onto the remote entry when protecting a publish.
_PUBLISH_FIELDS = (
    "state",
    "instagram_post_url",
    "instagram_published_at",
    "engagement_metrics",
    "damar_action",
    "damar_action_at",
    "state_history",
)


def _is_published(entry: dict[str, Any]) -> bool:
    return entry.get("state") in PUBLISHED_STATES


def merge_queues(
    remote: list[dict[str, Any]],
    local: list[dict[str, Any]],
    remote_archive: Optional[list[dict[str, Any]]] = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge Pro's queue (remote, SSOT) with the M5 local copy.

    `remote_archive` (2026-07-17): Pro's freshly-pulled queue-archive.json —
    entries Pro deliberately archived. Without this, an entry archived on Pro
    (removed from its live queue) looks identical, to this function, to a
    genuinely-new local-only entry — and gets resurrected into the merged
    output forever (live case: a golden-visa entry archived on Pro kept
    reappearing on M5 every pull). `None`/empty = old behavior (no archive
    cross-check), so callers that don't have an archive yet degrade safely.

    Returns (merged, report). Pure — no I/O.
    """
    local_by_id: dict[str, dict[str, Any]] = {}
    for e in local:
        if isinstance(e, dict):
            eid = item_id_of(e)
            if eid:
                local_by_id[eid] = e

    archived_ids: set[str] = set()
    for a in remote_archive or []:
        if isinstance(a, dict):
            aid = item_id_of(a)
            if aid:
                archived_ids.add(aid)

    merged: list[dict[str, Any]] = []
    protected: list[str] = []
    push_back: list[dict[str, str]] = []
    archived_dropped: list[str] = []
    queue_and_archive_conflict: list[str] = []
    seen: set[str] = set()

    for r in remote:
        if not isinstance(r, dict):
            merged.append(r)
            continue
        rid = item_id_of(r)
        if rid:
            seen.add(rid)
            if rid in archived_ids:
                # pathological: Pro's live queue AND its archive both carry
                # this id — the live queue wins (it's the more current SSOT
                # signal); just flag it, never drop a still-queued entry.
                queue_and_archive_conflict.append(str(rid))
        loc = local_by_id.get(rid) if rid else None
        if loc is not None and _is_published(loc) and not _is_published(r):
            out = dict(r)
            for k in _PUBLISH_FIELDS:
                if k in loc:
                    out[k] = loc[k]
            merged.append(out)
            protected.append(str(rid))
            ref = compute_ref_code(str(rid))
            url = str(loc.get("instagram_post_url") or "")
            # shell-safe by construction: strict ref shape + strict IG URL —
            # the wrapper interpolates these into an ssh command line.
            if _REF_CODE_SAFE_RE.match(ref) and validate_ig_url(url):
                push_back.append({"id": str(rid), "ref_code": ref, "ig_url": url.strip()})
        else:
            merged.append(r)

    local_only: list[str] = []
    published_local_kept_despite_archive: list[str] = []
    for e in local:
        if not isinstance(e, dict):
            continue
        eid = item_id_of(e)
        if not eid or eid in seen:
            continue
        if eid in archived_ids:
            if _is_published(e):
                # CRITICAL (Codex red-team, 2026-07-17): a local publish
                # transition survives an archive on Pro — dropping it here
                # (as a plain archived_dropped) would permanently lose the
                # published state + instagram_post_url with no recovery
                # path, since push_back only fires from the remote loop
                # above and this id is no longer in the remote queue at all.
                merged.append(e)
                local_only.append(str(eid))
                published_local_kept_despite_archive.append(str(eid))
                continue
            # archived on Pro, absent from Pro's live queue, NOT published
            # locally: Pro's decision, not a new local entry — drop instead
            # of resurrecting.
            archived_dropped.append(str(eid))
            continue
        merged.append(e)
        local_only.append(str(eid))

    return merged, {
        "protected": protected,
        "local_only": local_only,
        "push_back": push_back,
        "archived_dropped": archived_dropped,
        "queue_and_archive_conflict": queue_and_archive_conflict,
        "published_local_kept_despite_archive": published_local_kept_despite_archive,
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--remote", type=Path, required=True, help="freshly pulled Pro queue")
    ap.add_argument("--local", type=Path, required=True, help="current local queue")
    ap.add_argument("--out", type=Path, required=True, help="merged output path")
    ap.add_argument(
        "--remote-archive", type=Path, default=None,
        help="freshly pulled Pro queue-archive.json — cross-checked so an "
             "entry Pro archived is dropped instead of resurrected as local_only",
    )
    args = ap.parse_args(argv)

    remote = json.loads(args.remote.read_text(encoding="utf-8"))
    if not isinstance(remote, list):
        print(json.dumps({"error": "remote queue is not a list"}))
        return 2
    local: list = []
    if args.local.exists():
        try:
            parsed = json.loads(args.local.read_text(encoding="utf-8"))
            if isinstance(parsed, list):
                local = parsed
        except Exception:  # noqa: BLE001 — corrupt local: remote wins wholesale
            local = []

    remote_archive: Optional[list] = None
    if args.remote_archive is not None and args.remote_archive.exists():
        try:
            parsed_archive = json.loads(args.remote_archive.read_text(encoding="utf-8"))
            if isinstance(parsed_archive, list):
                remote_archive = parsed_archive
        except Exception:  # noqa: BLE001 — corrupt archive: skip the cross-check, don't fail the pull
            remote_archive = None

    merged, report = merge_queues(remote, local, remote_archive)
    args.out.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
