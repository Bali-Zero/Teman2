#!/usr/bin/env python3
"""WR2 publish-feedback writer — close the IG-metrics feedback loop.

The WR2 carousel pipeline leaves caroselli in `human-review-queue.json` with
state `applied_ready_for_damar`. Damar then publishes them to Instagram BY HAND
(Law 5 — Zero/Damar publish manually, no autonomous IG API). Until now there was
no way to feed the published IG URL back into the queue, so the IG-metrics
scraper (`~/.claude/skills/bali-zero-brand/_ig-metrics-scraper.py`) had nothing
to scrape and the weekly analyst stayed blocked on "insufficient data".

This module is the missing writer. It is the COMMON core for every feedback
channel (manual CLI now, WhatsApp ingest in STRATO 2): given a short, stable
`ref_code` and an IG post URL, it finds the matching queue item and normalizes
it to the exact shape the scraper consumes:

    state                  -> "published"
    instagram_post_url     -> <url>
    instagram_published_at -> <iso utc>
    engagement_metrics     -> None        (cleared; a dict of Nones is TRUTHY and
                                           the scraper SKIPS truthy em — verified
                                           against _ig-metrics-scraper.py:46)
    damar_action           -> "published"
    damar_action_at        -> <iso utc>

Ref-code design (anti-fragility for the WhatsApp channel): the code is a pure
deterministic function of the item id (`WR2-` + 6 hex of sha1). No extra state to
keep in sync, and Damar can be told the exact code to quote back. Matching is
EXACT on the ref-code — never fuzzy, never "the only pending one". The writer
NEVER writes on an ambiguous/absent match: it returns a structured outcome the
caller routes to a human-disambiguation queue instead.

The queue is heterogeneous (two historical schemas coexist): the 43 ready items
use `item_id`/`topic`, the newer drafts use `id`/`topic_slug`. `item_id_of`
handles both.

CLI:
    python scripts/wr2_queue_writer.py list-ready
    python scripts/wr2_queue_writer.py ref-code <item_id>
    python scripts/wr2_queue_writer.py mark-published <ref_code> <ig_url> [--at ISO]
    python scripts/wr2_queue_writer.py ingest-external <ig_url> [--topic T] [--at ISO]
    python scripts/wr2_queue_writer.py add-external '<json payload>'

Side-effect free functions (pure, unit-tested) are separated from the two I/O
functions (`load_queue`, `write_queue_atomic`) so the matching/normalization
logic is testable without touching disk.

DOCUMENTED LIMITATION (external-post feature, §B, 2026-07-17): `add-external`
lands the QUEUE ENTRY only — it never receives or writes the entry's images.
When the WR2 Control app (M5) registers an external post WITH images, those
PNGs stay local to M5's `carousel/external-<date>-<slug>/slides/` directory;
this writer's Pro-side counterpart has no rsync/copy step for them, and Pro
(the queue's SSOT) renders nothing for that carousel_path. Acceptable for v1
because Pro's queue-consuming surfaces (scraper, analyst, mark-published) only
need instagram_post_url/state/metrics, never the local slide PNGs — but a
future viewer that expects Pro to render the carousel for an image-bearing
external post will find the directory missing there.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# ── Constants ──────────────────────────────────────────────────────────────

DEFAULT_QUEUE_PATH = (
    Path.home() / "nuzantara/apps/war-room/output/queue/human-review-queue.json"
)

# States from which an item may legitimately transition to `published`.
PUBLISHABLE_STATES = ("applied_ready_for_damar", "approved", "reviewed")
PUBLISHED_STATES = ("published", "published_with_edits")

REF_CODE_PREFIX = "WR2-"
REF_CODE_HEX_LEN = 6

# IG post / reel URL. Accepts optional www, trailing slash, query string.
_IG_URL_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?(?:\?\S*)?$"
)


# ── Pure functions (no I/O) ────────────────────────────────────────────────


def item_id_of(item: dict[str, Any]) -> Optional[str]:
    """Return the canonical id of a queue item, across both historical schemas.

    Old (ready_for_damar) schema uses `item_id`; newer drafts use `id`.
    """
    return item.get("item_id") or item.get("id")


def topic_of(item: dict[str, Any]) -> str:
    """Human label for an item, across both schemas (best-effort)."""
    return item.get("topic") or item.get("topic_slug") or "(no topic)"


def compute_ref_code(item_id: str) -> str:
    """Deterministic short ref-code for an item id.

    `WR2-` + first 6 uppercase hex of sha1(item_id). Stable across runs, no
    stored state. Collisions are detectable at list-ready time.
    """
    digest = hashlib.sha1(item_id.encode("utf-8")).hexdigest()
    return f"{REF_CODE_PREFIX}{digest[:REF_CODE_HEX_LEN].upper()}"


def normalize_ref_code(raw: str) -> str:
    """Canonicalize a user-supplied ref-code for exact comparison.

    Uppercases, strips whitespace, and tolerates a missing `WR2-` prefix
    (Damar might type just the 6 hex). Does NOT validate length.
    """
    s = raw.strip().upper()
    if not s.startswith(REF_CODE_PREFIX) and re.fullmatch(r"[0-9A-F]{1,}", s):
        s = REF_CODE_PREFIX + s
    return s


def validate_ig_url(url: str) -> bool:
    """True iff `url` looks like a real instagram post/reel/tv permalink."""
    return bool(_IG_URL_RE.match(url.strip()))


_IG_SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", re.IGNORECASE
)


def extract_ig_shortcode(url: str) -> Optional[str]:
    """Return the IG shortcode (the /p/<code>/ segment) of a permalink, else None."""
    m = _IG_SHORTCODE_RE.search(url.strip())
    return m.group(1) if m else None


def build_external_item(
    ig_url: str, published_at_iso: str, topic: Optional[str] = None
) -> dict[str, Any]:
    """Build a fresh, published queue item for an EXTERNALLY-published IG post.

    Used for posts published by hand (e.g. by Zero) that never went through the
    WR2 pipeline — there is no pre-existing queue item to advance, so we mint
    one already in the scraper-consumable `published` shape. The id is
    `ig-<shortcode>` (deterministic from the URL → idempotent). `external=True`
    and `source="manual_external"` flag it so the IG analyst knows it lacks the
    full WR2 attributes (archetype/domain/audience).
    """
    url = ig_url.strip()
    shortcode = extract_ig_shortcode(url) or hashlib.sha1(url.encode()).hexdigest()[:8]
    return {
        "item_id": f"ig-{shortcode}",
        "topic": topic or f"(external IG post {shortcode})",
        "state": "published",
        "instagram_post_url": url,
        "instagram_published_at": published_at_iso,
        "engagement_metrics": None,
        "damar_action": "published",
        "damar_action_at": published_at_iso,
        "external": True,
        "source": "manual_external",
        "created_at": published_at_iso,
    }


REQUIRED_EXTERNAL_PAYLOAD_FIELDS = (
    "item_id",
    "state",
    "instagram_post_url",
    "source",
    "topic_slug",
)
EXTERNAL_MANUAL_SOURCE = "external_manual"


def validate_external_payload(payload: dict[str, Any]) -> Optional[str]:
    """Return an error string if `payload` is not a valid add-external entry, else None.

    Distinct from `validate_ig_url` (URL shape only): this checks the FULL contract
    the WR2 Control app (M5) is expected to build (`ExternalPostRegistration.swift`,
    §A) before pushing it here for propagation to Pro (§B) — required fields present,
    `state` must already be "published" (this writer never transitions state, only
    lands an already-published entry), `source` must be the exact literal
    `"external_manual"` (not the older `ingest_external_post`/`build_external_item`
    convention `"manual_external"` — the two call sites mint entries for different
    origins: that one is Zero pasting a bare URL on Pro directly, this one is the app
    replaying a fully-formed entry it already built on M5).
    """
    for field in REQUIRED_EXTERNAL_PAYLOAD_FIELDS:
        if not payload.get(field):
            return f"missing required field: {field!r}"
    if payload.get("state") != "published":
        return f"state must be 'published', got {payload.get('state')!r}"
    if payload.get("source") != EXTERNAL_MANUAL_SOURCE:
        return f"source must be {EXTERNAL_MANUAL_SOURCE!r}, got {payload.get('source')!r}"
    if not validate_ig_url(str(payload["instagram_post_url"])):
        return f"instagram_post_url is not a valid IG permalink: {payload['instagram_post_url']!r}"
    return None


def find_by_ref_code(
    items: list[dict[str, Any]], ref_code: str
) -> tuple[Optional[int], Optional[dict[str, Any]]]:
    """Return (index, item) of the unique item whose ref-code matches, else (None, None).

    Exact, case-insensitive match on the ref-code derived from the item id.
    """
    target = normalize_ref_code(ref_code)
    for idx, item in enumerate(items):
        iid = item_id_of(item)
        if iid and compute_ref_code(iid) == target:
            return idx, item
    return None, None


def apply_publish(
    item: dict[str, Any], ig_url: str, published_at_iso: str
) -> dict[str, Any]:
    """Return a COPY of `item` normalized to the scraper-consumable published shape.

    Pure: does not mutate the input. Clears `engagement_metrics` to None so the
    scraper (which skips truthy em) will pick the item up after the 24h window.
    """
    updated = dict(item)
    updated["state"] = "published"
    updated["instagram_post_url"] = ig_url.strip()
    updated["instagram_published_at"] = published_at_iso
    updated["engagement_metrics"] = None
    updated["damar_action"] = "published"
    updated["damar_action_at"] = published_at_iso
    # Append to state_history if the item tracks one (newer schema); leave absent otherwise.
    history = updated.get("state_history")
    if isinstance(history, list):
        updated["state_history"] = history + [
            {"state": "published", "at": published_at_iso, "via": "wr2_queue_writer"}
        ]
    return updated


# ── Outcome type ───────────────────────────────────────────────────────────


@dataclass
class PublishResult:
    """Structured outcome of mark_published. `ok` distinguishes success from no-op/error."""

    status: str  # published | already_published | conflict | not_found | invalid_url | wrong_state
    ok: bool
    ref_code: str
    item_id: Optional[str] = None
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ok": self.ok,
            "ref_code": self.ref_code,
            "item_id": self.item_id,
            "detail": self.detail,
        }


# ── I/O functions ──────────────────────────────────────────────────────────


def load_queue(path: Path) -> list[dict[str, Any]]:
    """Load the queue list. Raises FileNotFoundError if absent (caller decides)."""
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):  # tolerate {"items": [...]} wrapper
        data = data.get("items", [])
    if not isinstance(data, list):
        raise ValueError(f"queue at {path} is not a list")
    return data


def write_queue_atomic(path: Path, items: list[dict[str, Any]]) -> None:
    """Write the queue list atomically (tmp file in same dir + os.replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".queue-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)  # atomic on POSIX
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


@contextmanager
def queue_lock(path: Path):
    """Serialize read-modify-write against the other queue writers.

    Same lock file and protocol as wr2_html_render_apply._append_review_queue
    and _damar-queue-server (fcntl EX on human-review-queue.lock) — an atomic
    replace alone does not prevent two writers from both loading the same
    baseline and the second replace erasing the first one's mutation."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with open(lock_path, "w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


# ── Orchestration ──────────────────────────────────────────────────────────


def mark_published(
    path: Path,
    ref_code: str,
    ig_url: str,
    published_at: Optional[str] = None,
    now: Optional[datetime] = None,
) -> PublishResult:
    """Find the item by ref-code and mark it published with the IG URL.

    Idempotent and safe:
      * not_found     — no item matches the ref-code  -> NO write
      * invalid_url   — url is not an instagram permalink -> NO write
      * already_published — already published with the SAME url -> NO write (success no-op)
      * conflict      — already published with a DIFFERENT url -> NO write (needs human)
      * wrong_state   — item exists but is not in a publishable state -> NO write
      * published     — applied + written atomically -> WRITE
    """
    ref = normalize_ref_code(ref_code)

    if not validate_ig_url(ig_url):
        return PublishResult("invalid_url", False, ref, detail=f"not an IG permalink: {ig_url!r}")

    with queue_lock(path):
        items = load_queue(path)
        idx, item = find_by_ref_code(items, ref)
        if item is None:
            return PublishResult("not_found", False, ref, detail="no queue item matches this ref-code")

        iid = item_id_of(item)
        state = item.get("state")
        existing_url = (item.get("instagram_post_url") or "").strip()
        new_url = ig_url.strip()

        if state in PUBLISHED_STATES:
            if existing_url == new_url:
                return PublishResult("already_published", True, ref, iid, "no-op: same URL already recorded")
            return PublishResult(
                "conflict", False, ref, iid,
                f"already published with a different URL ({existing_url!r}); refusing to overwrite",
            )

        if state not in PUBLISHABLE_STATES:
            return PublishResult(
                "wrong_state", False, ref, iid,
                f"state {state!r} is not publishable (expected one of {PUBLISHABLE_STATES})",
            )

        published_iso = published_at or (now or datetime.now(timezone.utc)).isoformat()
        items[idx] = apply_publish(item, new_url, published_iso)
        write_queue_atomic(path, items)
        return PublishResult("published", True, ref, iid, f"published at {published_iso}")


def ingest_external_post(
    path: Path,
    ig_url: str,
    topic: Optional[str] = None,
    published_at: Optional[str] = None,
    now: Optional[datetime] = None,
) -> PublishResult:
    """Register an externally-published IG post (no pre-existing queue item).

    For posts published by hand (e.g. by Zero) that bypassed the WR2 pipeline.
    Mints a fresh `published` item (id `ig-<shortcode>`) so the scraper collects
    its metrics. Idempotent on the IG URL: re-ingesting the same post is a no-op.

    Default `published_at` is 25h in the past so the post is IMMEDIATELY eligible
    for the scraper (which skips items <24h old) — these posts are already live,
    we are not waiting for a fresh-publish window. Pass `--at` with the real
    publication date when known.

    Returns PublishResult with ref_code = compute_ref_code of the minted id.
      * invalid_url     — not an IG permalink -> NO write
      * already_present — a published item with the SAME url already exists -> no-op
      * ingested        — minted + written atomically -> WRITE
    """
    url = ig_url.strip()
    if not validate_ig_url(url):
        return PublishResult("invalid_url", False, "", detail=f"not an IG permalink: {ig_url!r}")

    with queue_lock(path):
        items = load_queue(path)
        for existing in items:
            if (existing.get("instagram_post_url") or "").strip() == url:
                iid = item_id_of(existing)
                return PublishResult(
                    "already_present", True, compute_ref_code(iid or url), iid,
                    "no-op: this IG URL is already registered",
                )

        published_iso = published_at or (
            (now or datetime.now(timezone.utc)) - timedelta(hours=25)
        ).isoformat()
        new_item = build_external_item(url, published_iso, topic=topic)
        items.append(new_item)
        write_queue_atomic(path, items)
        iid = new_item["item_id"]
        return PublishResult("ingested", True, compute_ref_code(iid), iid, f"registered external post {iid}")


def add_external(path: Path, payload: dict[str, Any]) -> PublishResult:
    """Append a FULLY-FORMED external-manual queue entry (M5->Pro propagation, §B).

    Distinct from `ingest_external_post` above (which MINTS a minimal item from a
    bare URL for Zero's manual CLI use, id `ig-<shortcode>`, source
    `"manual_external"`): this accepts a payload the WR2 Control app already built
    end-to-end (item_id `external_<date>T<time>_<slug>`, topic_slug, slide_count,
    carousel_path, source `"external_manual"`, ...) and appends it VERBATIM after
    validation — the app is the author, this call is only the sync landing point.

    Refuses a duplicate on EITHER the same `instagram_post_url` OR the same
    `item_id` already present (idempotency requirement, §B acceptance #2): the
    M5->Pro push-back loop may retry after a flaky ssh, and a real duplicate post
    submitted twice by the operator must be refused, not double-enqueued.

      * invalid_payload  — missing/wrong-shaped field -> NO write
      * already_present  — same item_id or instagram_post_url already in queue -> NO write (no-op)
      * added            — appended + written atomically -> WRITE
    """
    err = validate_external_payload(payload)
    if err:
        return PublishResult("invalid_payload", False, "", detail=err)

    new_id = str(payload["item_id"])
    new_url = str(payload["instagram_post_url"]).strip()

    with queue_lock(path):
        items = load_queue(path)
        for existing in items:
            eid = item_id_of(existing)
            existing_url = (existing.get("instagram_post_url") or "").strip()
            if eid == new_id or (existing_url and existing_url == new_url):
                return PublishResult(
                    "already_present", True, compute_ref_code(new_id), eid,
                    "no-op: an entry with this item_id or instagram_post_url already exists",
                )
        items.append(dict(payload))
        write_queue_atomic(path, items)
        return PublishResult("added", True, compute_ref_code(new_id), new_id,
                              f"registered external post {new_id}")


# ── CLI ────────────────────────────────────────────────────────────────────


def _resolve_queue_path(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("WR2_QUEUE_PATH")
    return Path(env) if env else DEFAULT_QUEUE_PATH


def _cmd_list_ready(args: argparse.Namespace) -> int:
    path = _resolve_queue_path(args.queue)
    items = load_queue(path)
    seen: dict[str, str] = {}
    rows = []
    for item in items:
        state = item.get("state")
        if not args.all and state not in PUBLISHABLE_STATES:
            continue
        iid = item_id_of(item)
        if not iid:
            continue
        ref = compute_ref_code(iid)
        collision = " ⚠️COLLISION" if ref in seen and seen[ref] != iid else ""
        seen[ref] = iid
        rows.append((ref, state, iid, topic_of(item), collision))
    if not rows:
        print("(no items)")
        return 0
    print(f"{'REF-CODE':<12} {'STATE':<24} {'ITEM_ID':<40} TOPIC")
    for ref, state, iid, topic, coll in rows:
        print(f"{ref:<12} {state:<24} {iid:<40} {topic[:50]}{coll}")
    print(f"\n{len(rows)} item(s).")
    return 0


def _cmd_ref_code(args: argparse.Namespace) -> int:
    print(compute_ref_code(args.item_id))
    return 0


def _cmd_mark_published(args: argparse.Namespace) -> int:
    path = _resolve_queue_path(args.queue)
    result = mark_published(path, args.ref_code, args.ig_url, published_at=args.at)
    print(json.dumps(result.as_dict(), ensure_ascii=False))
    return 0 if result.ok else 1


def _cmd_ingest_external(args: argparse.Namespace) -> int:
    path = _resolve_queue_path(args.queue)
    result = ingest_external_post(path, args.ig_url, topic=args.topic, published_at=args.at)
    print(json.dumps(result.as_dict(), ensure_ascii=False))
    return 0 if result.ok else 1


def _cmd_add_external(args: argparse.Namespace) -> int:
    path = _resolve_queue_path(args.queue)
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "invalid_json", "ok": False, "detail": str(e)}, ensure_ascii=False))
        return 1
    if not isinstance(payload, dict):
        print(json.dumps({"status": "invalid_json", "ok": False, "detail": "payload is not a JSON object"}))
        return 1
    result = add_external(path, payload)
    print(json.dumps(result.as_dict(), ensure_ascii=False))
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="WR2 publish-feedback queue writer")
    p.add_argument("--queue", help="path to human-review-queue.json (default: env WR2_QUEUE_PATH or standard)")
    sub = p.add_subparsers(dest="cmd", required=True)

    lr = sub.add_parser("list-ready", help="list items awaiting publish with their ref-code")
    lr.add_argument("--all", action="store_true", help="show all items, not only publishable")
    lr.set_defaults(func=_cmd_list_ready)

    rc = sub.add_parser("ref-code", help="print the ref-code for a given item id")
    rc.add_argument("item_id")
    rc.set_defaults(func=_cmd_ref_code)

    mp = sub.add_parser("mark-published", help="mark an item published with its IG URL")
    mp.add_argument("ref_code")
    mp.add_argument("ig_url")
    mp.add_argument("--at", help="ISO timestamp of publication (default: now UTC)")
    mp.set_defaults(func=_cmd_mark_published)

    ie = sub.add_parser(
        "ingest-external",
        help="register an externally-published IG post (no pre-existing queue item)",
    )
    ie.add_argument("ig_url")
    ie.add_argument("--topic", help="human label for the post (default: auto from shortcode)")
    ie.add_argument("--at", help="ISO publication date (default: 25h ago, so it's immediately scraper-eligible)")
    ie.set_defaults(func=_cmd_ingest_external)

    ae = sub.add_parser(
        "add-external",
        help="append a fully-formed external_manual entry built by the WR2 Control app (M5->Pro sync, §B)",
    )
    ae.add_argument("payload", help="JSON object: item_id/state/instagram_post_url/source/topic_slug/...")
    ae.set_defaults(func=_cmd_add_external)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
