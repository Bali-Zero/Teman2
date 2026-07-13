#!/usr/bin/env python3
"""WR2 review-queue hygiene — quarantine malformed entries, purge junk artifact dirs.

WHY (W96, 2026-07-13): unit tests that exercised `_apply_one` of
scripts/wr2_html_render_apply.py without patching `_publish_visibility` leaked
fixture entries into the PRODUCTION human-review-queue.json (topic "", slug
"carousel", slide_count 1, drive_url "https://drive/x") plus one junk carousel
dir per run — 24 phantom "micro carousels" visible as undisplayable drafts in
the WR2 Control app, 131 junk dirs on M5. The test-isolation conftest fixture
kills the *source*; this module is the *immune organ*: any malformed entry that
still reaches the queue (future writers, partial failures) gets quarantined on
the next reconciler tick instead of rotting in the operator's review list.

CONTRACT (entity-based, not substring — scar family #3 discipline):
a queue entry is JUNK iff ALL of:
  - state == "drafted"           (never touch published/reviewed history)
  - topic is empty/whitespace    (every legitimate writer passes the draft topic;
                                  an empty topic violates the queue-entry contract)
  - instagram_post_url is falsy  (belt: anything already published is history)

A junk artifact DIR is purged iff ALL of (verified by CONTENT, W88):
  - basename matches ^\\d{4}-\\d{2}-\\d{2}-carousel-[0-9a-f]{8}$
    (slug exactly "carousel" == the empty-topic slugification)
  - meta.json has empty topic OR the test placeholder drive_url
  - slides/ holds <= 1 PNG

Quarantined entries are MOVED (atomically, under the same fcntl lock the
writers use) to queue-quarantine.json next to the queue — auditable, never
silently destroyed.

CLI (dry-run by default; --apply to mutate):
    python scripts/wr2_queue_hygiene.py                  # report only
    python scripts/wr2_queue_hygiene.py --apply          # quarantine entries
    python scripts/wr2_queue_hygiene.py --apply --purge-dirs  # also delete junk dirs

Env: WR2_OUTPUT_ROOT overrides the default output root (same knob as
wr2_html_render_apply._default_output_root).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("wr2.queue_hygiene")

_JUNK_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-carousel-[0-9a-f]{8}$")
_PLACEHOLDER_DRIVE_URLS = ("https://drive/x",)


def _default_output_root() -> Path:
    """Same convention as wr2_html_render_apply._default_output_root."""
    return Path(
        os.environ.get(
            "WR2_OUTPUT_ROOT",
            str(Path.home() / "Desktop" / "nuzantara" / "apps" / "war-room" / "output"),
        )
    )


def is_junk_entry(entry: object) -> bool:
    """True iff `entry` matches the junk contract (see module docstring)."""
    if not isinstance(entry, dict):
        return False
    if entry.get("state") != "drafted":
        return False
    if entry.get("instagram_post_url"):
        return False
    topic = entry.get("topic")
    # Old-schema items (published era) have no "topic" key at all — absence is
    # NOT emptiness; only an explicitly blank topic violates the writer contract.
    if "topic" not in entry:
        return False
    return not str(topic or "").strip()


@dataclass
class SweepReport:
    moved: list[str] = field(default_factory=list)
    kept: int = 0
    dry_run: bool = True


def sweep_queue(
    queue_path: Path | None = None,
    quarantine_path: Path | None = None,
    *,
    dry_run: bool = True,
) -> SweepReport:
    """Move junk entries from the review queue into the quarantine ledger.

    Atomic (tmp+rename) under an fcntl lock on the queue file — the same
    protocol wr2_html_render_apply._append_review_queue uses, so a concurrent
    render cannot interleave with the sweep.
    """
    qp = queue_path or (_default_output_root() / "queue" / "human-review-queue.json")
    quarantine = quarantine_path or qp.with_name("queue-quarantine.json")
    report = SweepReport(dry_run=dry_run)
    if not qp.exists():
        logger.info("queue %s does not exist — nothing to sweep", qp)
        return report

    with open(qp, "r+", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            queue = json.loads(lock_fh.read() or "[]")
            if not isinstance(queue, list):
                logger.error("queue %s is not a JSON list — refusing to sweep", qp)
                return report
            junk = [e for e in queue if is_junk_entry(e)]
            keep = [e for e in queue if not is_junk_entry(e)]
            report.moved = [str(e.get("id", "?")) for e in junk]
            report.kept = len(keep)
            if not junk or dry_run:
                return report

            existing: list = []
            if quarantine.exists():
                try:
                    existing = json.loads(quarantine.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001 — corrupt quarantine: start fresh, keep old aside
                    corrupt = quarantine.with_suffix(".corrupt")
                    shutil.copy2(quarantine, corrupt)
                    logger.warning("quarantine file corrupt — preserved at %s", corrupt)
                    existing = []
            if not isinstance(existing, list):
                existing = [existing]
            existing.extend(junk)

            qtmp = quarantine.with_suffix(f".tmp.{os.getpid()}")
            qtmp.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(qtmp, quarantine)

            tmp = qp.with_suffix(f".tmp.{os.getpid()}")
            tmp.write_text(json.dumps(keep, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, qp)
            logger.info(
                "quarantined %d junk entries -> %s (queue keeps %d)",
                len(junk), quarantine, len(keep),
            )
            return report
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def is_junk_dir(car_dir: Path) -> bool:
    """True iff `car_dir` matches the junk artifact-dir contract by CONTENT."""
    if not car_dir.is_dir() or not _JUNK_DIR_RE.match(car_dir.name):
        return False
    meta_path = car_dir / "meta.json"
    topic_empty = False
    placeholder = False
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            topic_empty = not str(meta.get("topic") or "").strip()
            placeholder = meta.get("drive_url") in _PLACEHOLDER_DRIVE_URLS
        except Exception:  # noqa: BLE001 — unreadable meta on a junk-named dir: still gated by PNG count
            topic_empty = True
    else:
        topic_empty = True  # junk-named dir without meta: writer never finished
    if not (topic_empty or placeholder):
        return False
    pngs = list((car_dir / "slides").glob("*.png")) if (car_dir / "slides").is_dir() else []
    return len(pngs) <= 1


def purge_junk_dirs(output_root: Path | None = None, *, dry_run: bool = True) -> list[str]:
    """Delete junk carousel dirs under <output_root>/carousel. Returns their names."""
    root = (output_root or _default_output_root()) / "carousel"
    if not root.is_dir():
        return []
    victims = [d for d in sorted(root.iterdir()) if is_junk_dir(d)]
    for d in victims:
        if dry_run:
            logger.info("DRY-RUN would purge %s", d)
        else:
            shutil.rmtree(d)
            logger.info("purged junk dir %s", d)
    return [d.name for d in victims]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--queue", type=Path, default=None, help="queue path override")
    ap.add_argument("--output-root", type=Path, default=None, help="output root override")
    ap.add_argument("--apply", action="store_true", help="mutate (default: dry-run report)")
    ap.add_argument("--purge-dirs", action="store_true", help="also purge junk carousel dirs")
    args = ap.parse_args(argv)

    root = args.output_root or _default_output_root()
    qp = args.queue or (root / "queue" / "human-review-queue.json")
    report = sweep_queue(qp, dry_run=not args.apply)
    print(json.dumps({
        "dry_run": report.dry_run,
        "quarantined": report.moved,
        "kept": report.kept,
    }, indent=2))
    if args.purge_dirs:
        purged = purge_junk_dirs(root, dry_run=not args.apply)
        print(json.dumps({"purged_dirs": purged, "dry_run": not args.apply}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
