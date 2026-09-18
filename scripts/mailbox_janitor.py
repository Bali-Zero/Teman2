#!/usr/bin/env python3
"""mailbox_janitor.py — the ONLY deleter of ~/.nuzantara-mailbox.

Nothing else in this repo removes files or directories under the mailbox
root. `infra/claude-hooks/mailbox_inject.py` only ever RENAMES dead mail
(`<name>.md` -> `<name>.md.<tag>-<YYYYMMDDTHHMMSS>[Z]`, tags: delivered,
expired, superseded, skipped-oversize, unaddressed, retracted, muted) and
APPENDS seen broadcast names to `<session_dir>/.broadcast_seen`. Without a
janitor the root listing (one entry per session dir, plus `broadcast/`)
grows forever.

Invariants enforced here:

- Refuse to run (stderr + exit 1, nothing touched) if root is missing, not
  a directory, a symlink, or not owned by the current uid.
- Walk ONLY the root's direct children (session dirs and `broadcast/`) and
  their direct files — never deeper. A nested directory inside a session
  dir is left alone (kept, not descended).
- Never follow a symlink (file or dir); never delete one.
- A marked file (name matches the tag-timestamp suffix the hook writes) is
  pruned once it is older than `--marked-days`, in `broadcast/` and in
  session dirs alike. Age is computed from the tag's own UTC timestamp,
  falling back to mtime only if that timestamp fails to parse.
- `.broadcast_seen` in a session dir is pruned once the session dir is
  older than `--seen-days` AND none of the broadcast names it lists is
  still a live (regular, unmarked, unmarked-suffix) `.md` file in
  `broadcast/` — a still-referenced live broadcast keeps it, however old.
  An oversize `.broadcast_seen` (> 64 KiB) is never read, only kept.
- A session dir (never `broadcast/`, never the root itself) is rmdir'd once
  it is both empty and older than `--seen-days`.
- Every delete is re-checked for containment under root via realpath
  immediately before the syscall; anything that fails that check is
  counted as an error and left alone.
- Default is DRY-RUN: every counter reflects what WOULD happen; nothing on
  disk changes unless `--apply` is given.

Counter semantics: without --apply the removal counters (pruned_marked,
seen_removed, dirs_removed) count what is ELIGIBLE; with --apply they count what
was PERFORMED. They are equal on a run with errors=0; every attempt that
fails (EACCES, race, containment) lands in `errors` instead.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import pathlib
import re
import socket
import stat as stat_module
import sys
import time
from datetime import datetime, timezone

MARKER_RE = re.compile(
    r"\.(delivered|expired|superseded|skipped-oversize|unaddressed|muted|retracted)"
    r"-(\d{8}T\d{6})Z?$"
)

MAX_BROADCAST_SEEN_BYTES = 65536

COUNTER_KEYS = (
    "skipped_symlink",
    "pruned_marked",
    "pruned_bytes",
    "kept_marked_recent",
    "seen_removed",
    "seen_kept_live_ref",
    "seen_kept_recent",
    "dirs_removed",
    "dirs_kept_nonempty",
    "kept_live_md",
    "kept_unknown",
    "errors",
    "scanned_dirs",
    "scanned_files",
)


class MailboxJanitorRefusal(Exception):
    """Raised when the root fails a pre-flight safety check."""


def _refusal_reason(root: pathlib.Path):
    try:
        st = os.lstat(str(root))
    except FileNotFoundError:
        return "root missing: {}".format(root)
    except OSError as exc:
        return "cannot stat root {}: {}".format(root, exc)
    if stat_module.S_ISLNK(st.st_mode):
        return "root is a symlink: {}".format(root)
    if not stat_module.S_ISDIR(st.st_mode):
        return "root is not a directory: {}".format(root)
    if st.st_uid != os.getuid():
        return "root not owned by current uid: {}".format(root)
    return None


def _parse_tag_epoch(ts: str):
    try:
        return calendar.timegm(time.strptime(ts, "%Y%m%dT%H%M%S"))
    except ValueError:
        return None


def _is_live_broadcast(f: pathlib.Path) -> bool:
    return (not f.is_symlink()) and f.is_file() and f.suffix == ".md"


def _handle_marker_file(
    f: pathlib.Path,
    *,
    now: float,
    marked_cutoff: float,
    apply: bool,
    contained,
    counters: dict,
):
    match = MARKER_RE.search(f.name)
    if match is None:
        counters["kept_unknown"] += 1
        return
    ts_epoch = _parse_tag_epoch(match.group(2))
    if ts_epoch is None:
        try:
            age = now - f.stat().st_mtime
        except OSError:
            counters["errors"] += 1
            return
    else:
        age = now - ts_epoch

    if age <= marked_cutoff:
        counters["kept_marked_recent"] += 1
        return

    try:
        size = f.stat().st_size
    except OSError:
        size = 0

    if not apply:
        counters["pruned_marked"] += 1
        counters["pruned_bytes"] += size
        return

    if not contained(f):
        counters["errors"] += 1
        return
    try:
        f.unlink()
    except OSError:
        counters["errors"] += 1
        return
    counters["pruned_marked"] += 1
    counters["pruned_bytes"] += size


def _handle_broadcast_seen(
    marker: pathlib.Path,
    dir_age: float,
    *,
    live_broadcast_names: set,
    seen_cutoff: float,
    now: float,
    apply: bool,
    contained,
    counters: dict,
):
    try:
        st = marker.stat()
    except OSError:
        counters["errors"] += 1
        return
    size = st.st_size
    marker_age = now - st.st_mtime
    if size > MAX_BROADCAST_SEEN_BYTES:
        counters["kept_unknown"] += 1
        return
    try:
        text = marker.read_text(encoding="utf-8", errors="replace")
    except OSError:
        counters["errors"] += 1
        return
    names = [line.strip() for line in text.splitlines() if line.strip()]
    has_live_ref = any(n in live_broadcast_names for n in names)

    if has_live_ref:
        counters["seen_kept_live_ref"] += 1
        return

    # Two clocks, both must be stale: the dir (no entry created/removed) AND
    # the marker itself (the reader hook APPENDS to it without touching the dir
    # mtime, so a session that saw a broadcast yesterday keeps its marker even
    # inside a dir born weeks ago).
    if dir_age <= seen_cutoff or marker_age <= seen_cutoff:
        counters["seen_kept_recent"] += 1
        return

    if not apply:
        counters["seen_removed"] += 1
        return

    if not contained(marker):
        counters["errors"] += 1
        return
    # Last look before the unlink: a broadcast posted after the start-of-run
    # snapshot is live NOW, and a marker naming it must survive.
    broadcast_dir = marker.parent.parent / "broadcast"
    if any(_is_live_broadcast(broadcast_dir / n) for n in names):
        counters["seen_kept_live_ref"] += 1
        return
    try:
        marker.unlink()
    except OSError:
        counters["errors"] += 1
        return
    counters["seen_removed"] += 1


def run(root, *, marked_days=14, seen_days=3, apply=False, now=None):
    """Core: scan and (if apply) prune `root`. Returns the summary dict.

    Raises MailboxJanitorRefusal without touching anything if the root
    fails a safety check.
    """
    root = pathlib.Path(root)
    now = time.time() if now is None else now

    reason = _refusal_reason(root)
    if reason:
        raise MailboxJanitorRefusal(reason)

    root_real = os.path.realpath(str(root))

    def contained(target: pathlib.Path) -> bool:
        real = os.path.realpath(str(target))
        return real.startswith(root_real + os.sep)

    counters = {key: 0 for key in COUNTER_KEYS}
    marked_cutoff = marked_days * 86400
    seen_cutoff = seen_days * 86400

    top_entries = list(root.iterdir())
    root_entries_before = len(top_entries)

    broadcast_dir = root / "broadcast"
    live_broadcast_names = set()
    if broadcast_dir.is_dir() and not broadcast_dir.is_symlink():
        try:
            bcandidates = list(broadcast_dir.iterdir())
        except OSError:
            bcandidates = []
        for f in bcandidates:
            if _is_live_broadcast(f):
                live_broadcast_names.add(f.name)

    for entry in top_entries:
        if entry.is_symlink():
            counters["skipped_symlink"] += 1
            continue
        if not entry.is_dir():
            # Stray file directly at root level: not part of the contract.
            counters["kept_unknown"] += 1
            continue

        counters["scanned_dirs"] += 1
        is_broadcast_dir = entry.name == "broadcast"

        # Snapshot the dir mtime BEFORE touching its children: every unlink
        # below bumps it to wall-clock now, which would make a dir that just
        # lost its dead mail look "recent" and survive an extra seen_days.
        try:
            dir_age = now - entry.stat().st_mtime
            children = list(entry.iterdir())
        except OSError:
            counters["errors"] += 1
            continue

        remaining = 0
        for child in children:
            if child.is_symlink():
                counters["skipped_symlink"] += 1
                remaining += 1
                continue
            if child.is_dir():
                counters["kept_unknown"] += 1
                remaining += 1
                continue
            if not child.is_file():
                # fifo / socket / device: never ours, and it keeps the dir
                # non-empty — count it or rmdir fails ENOTEMPTY every night.
                counters["kept_unknown"] += 1
                remaining += 1
                continue

            counters["scanned_files"] += 1
            name = child.name

            if not is_broadcast_dir and name == ".broadcast_seen":
                before = counters["seen_removed"]
                _handle_broadcast_seen(
                    child,
                    dir_age,
                    live_broadcast_names=live_broadcast_names,
                    seen_cutoff=seen_cutoff,
                    now=now,
                    apply=apply,
                    contained=contained,
                    counters=counters,
                )
                if counters["seen_removed"] == before:
                    remaining += 1
                continue

            if MARKER_RE.search(name):
                before = counters["pruned_marked"]
                _handle_marker_file(
                    child,
                    now=now,
                    marked_cutoff=marked_cutoff,
                    apply=apply,
                    contained=contained,
                    counters=counters,
                )
                if counters["pruned_marked"] == before:
                    remaining += 1
                continue

            if child.suffix == ".md":
                counters["kept_live_md"] += 1
                remaining += 1
                continue

            counters["kept_unknown"] += 1
            remaining += 1

        if is_broadcast_dir:
            continue

        if remaining > 0:
            counters["dirs_kept_nonempty"] += 1
            continue

        if dir_age <= seen_cutoff:
            continue

        if not apply:
            counters["dirs_removed"] += 1
            continue

        if not contained(entry):
            counters["errors"] += 1
            continue
        try:
            entry.rmdir()
        except OSError:
            counters["errors"] += 1
            continue
        counters["dirs_removed"] += 1

    if apply:
        root_entries_after = len(list(root.iterdir()))
    else:
        root_entries_after = root_entries_before

    summary = {
        "ts": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "root": str(root),
        "apply": bool(apply),
        "marked_days": marked_days,
        "seen_days": seen_days,
        "root_entries_before": root_entries_before,
        "root_entries_after": root_entries_after,
    }
    summary.update(counters)
    return summary


def _format_line(summary: dict) -> str:
    mode = "APPLIED" if summary["apply"] else "DRY-RUN"
    kib = summary["pruned_bytes"] / 1024.0
    return (
        "mailbox-janitor: {mode} root_entries={before}->{after} "
        "pruned_marked={pruned} ({kib:.1f} KiB) seen_removed={seen} "
        "dirs_removed={dirs} kept_live_md={live} kept_marked_recent={recent} "
        "errors={errors}"
    ).format(
        mode=mode,
        before=summary["root_entries_before"],
        after=summary["root_entries_after"],
        pruned=summary["pruned_marked"],
        kib=kib,
        seen=summary["seen_removed"],
        dirs=summary["dirs_removed"],
        live=summary["kept_live_md"],
        recent=summary["kept_marked_recent"],
        errors=summary["errors"],
    )


def _append_receipt(path, summary: dict) -> None:
    flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, sort_keys=True) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prune dead mailbox artifacts. The only deleter of the mailbox root."
    )
    # Same override the hook and fleet_mail.sh honour, so a test fixture or a
    # relocated mailbox is seen by all three actors alike.
    parser.add_argument(
        "--root",
        default=os.environ.get("NUZ_MAILBOX_DIR") or "~/.nuzantara-mailbox",
    )
    parser.add_argument("--marked-days", type=int, default=14)
    parser.add_argument("--seen-days", type=int, default=3)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--receipt", default=None)
    parser.add_argument("--now-epoch", type=float, default=None)
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    root = pathlib.Path(args.root).expanduser()
    now = args.now_epoch if args.now_epoch is not None else time.time()

    try:
        summary = run(
            root,
            marked_days=args.marked_days,
            seen_days=args.seen_days,
            apply=args.apply,
            now=now,
        )
    except MailboxJanitorRefusal as exc:
        print("mailbox-janitor: refused: {}".format(exc), file=sys.stderr)
        return 1

    if args.receipt:
        _append_receipt(args.receipt, summary)

    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(_format_line(summary))

    return 2 if summary["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
