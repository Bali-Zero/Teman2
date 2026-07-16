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

`push_back_external` (§A/§B, 2026-07-17): a SEPARATE, read-only pass over
`local` (see `external_push_candidates`) — entries the WR2 Control app
registered via the external-post feature that are not yet confirmed synced
to Pro. Orthogonal to the merge loop above: it never changes what lands in
`merged`/`local_only`, it only surfaces what the wrapper should replay onto
Pro via `wr2_queue_writer.py add-external`.

CLI (used by infra/launchagents/wrappers/wr2-queue-pull.sh):
    python3 scripts/wr2_queue_pull_merge.py --remote R.json --local L.json \
        --out M.json [--remote-archive A.json]
prints a JSON report to stdout:
    {"protected": [ids], "local_only": [ids],
     "push_back": [{"id":..., "ref_code": "WR2-XXXXXX", "ig_url": ...}],
     "archived_dropped": [ids], "queue_and_archive_conflict": [ids],
     "published_local_kept_despite_archive": [ids],
     "push_back_external": [{"item_id":..., ...full payload}]}

Secondary CLI mode (§B, standalone — does not need --remote/--local/--out):
    python3 scripts/wr2_queue_pull_merge.py --mark-synced-item-id ID \
        --mark-synced-file L.json
marks the matching entry `synced_to_pro: true` on L.json after the wrapper
confirms a `push_back_external` entry landed on Pro, and prints
`{"ok": true, "marked": ID}`.
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
    EXTERNAL_MANUAL_SOURCE,
    PUBLISHED_STATES,
    compute_ref_code,
    item_id_of,
    validate_external_payload,
    validate_ig_url,
    write_queue_atomic,
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


def external_push_candidates(local: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Local entries the WR2 Control app registered via the external-post feature
    (§A, 2026-07-17) that have NOT yet been confirmed synced to Pro. Pure — no I/O,
    no ssh; the wrapper (wr2-queue-pull.sh) replays each one via
    `scripts/wr2_queue_writer.py add-external` and then calls `mark_synced_to_pro`
    below on confirmed success.

    An entry qualifies when ALL of:
      - `source == EXTERNAL_MANUAL_SOURCE` — only the app's own external-post writes
        carry this exact marker, never a WR2-pipeline entry (never confuse this with
        `ingest_external_post`'s `"manual_external"`, a DIFFERENT origin/convention);
      - `synced_to_pro` is not already truthy — idempotent: a confirmed push must
        never be replayed forever (the local entry gets marked after success);
      - the payload passes `validate_external_payload` — a malformed/partial local
        entry (e.g. a write that raced a crash) must never be shipped over ssh as a
        broken CLI argument; it stays local-only, unsynced, until it's fixed.
    """
    out: list[dict[str, Any]] = []
    for e in local:
        if not isinstance(e, dict):
            continue
        if e.get("source") != EXTERNAL_MANUAL_SOURCE:
            continue
        if e.get("synced_to_pro"):
            continue
        if validate_external_payload(e) is not None:
            continue
        out.append(e)
    return out


def mark_synced_to_pro(items: list[dict[str, Any]], item_id: str) -> list[dict[str, Any]]:
    """Pure: return a COPY of `items` with the entry matching `item_id` marked
    `synced_to_pro: true`, so `external_push_candidates` never re-offers a
    confirmed push. No-op (items returned unchanged, by value) if no entry matches
    — the wrapper calling this after a successful ssh push always has a real id,
    but a stale/raced call must never crash or silently invent an entry."""
    out: list[dict[str, Any]] = []
    for it in items:
        if isinstance(it, dict) and item_id_of(it) == item_id:
            it = dict(it)
            it["synced_to_pro"] = True
        out.append(it)
    return out


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
        "push_back_external": external_push_candidates(local),
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # --remote/--local/--out are NOT required at the argparse level (only
    # enforced below, ap.error) because the secondary --mark-synced-item-id
    # mode (§B) is a standalone invocation that needs none of them.
    ap.add_argument("--remote", type=Path, help="freshly pulled Pro queue")
    ap.add_argument("--local", type=Path, help="current local queue")
    ap.add_argument("--out", type=Path, help="merged output path")
    ap.add_argument(
        "--remote-archive", type=Path, default=None,
        help="freshly pulled Pro queue-archive.json — cross-checked so an "
             "entry Pro archived is dropped instead of resurrected as local_only",
    )
    # Secondary mode (§B): after the wrapper successfully replays a push_back_external
    # entry into Pro via `wr2_queue_writer.py add-external`, it calls back into THIS
    # script to mark that entry `synced_to_pro: true` on the LOCAL file — so the next
    # merge's `external_push_candidates` never re-offers it. Kept in this module
    # (not a new script) because it operates on the same local-queue shape and reuses
    # `mark_synced_to_pro` directly.
    ap.add_argument("--mark-synced-item-id", help="mark this item_id synced_to_pro=true on --mark-synced-file")
    ap.add_argument("--mark-synced-file", type=Path, help="local queue file to mutate (used with --mark-synced-item-id)")
    args = ap.parse_args(argv)

    if args.mark_synced_item_id:
        if not args.mark_synced_file:
            print(json.dumps({"ok": False, "error": "--mark-synced-file is required with --mark-synced-item-id"}))
            return 2
        items = json.loads(args.mark_synced_file.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            print(json.dumps({"ok": False, "error": "--mark-synced-file is not a list"}))
            return 2
        updated = mark_synced_to_pro(items, args.mark_synced_item_id)
        write_queue_atomic(args.mark_synced_file, updated)
        print(json.dumps({"ok": True, "marked": args.mark_synced_item_id}))
        return 0

    if not (args.remote and args.local and args.out):
        ap.error("--remote, --local and --out are all required unless --mark-synced-item-id is given")

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
