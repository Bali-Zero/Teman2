#!/usr/bin/env python3
"""scripts/chore_dispatch.py — chore queue for cheap seats (receptor-live PART B).

Companion to the Armata H24 lanes (`scripts/army/jules_lane.py`,
`scripts/army/spark_lane.sh`, 2026-08-14/15) but one layer up: those two are
each a standing cron around ONE seat's own queue directory
(`infra/army/jules-queue/`, `infra/army/spark-queue/`). This file adds a
single GENERIC backlog — `infra/army/chore-queue/` — that a session (or a
daily cron tick) can point at any of the cheap seats without hand-rolling a
new queue format per seat. It does not replace either lane's own queue or
dispatch code; it REUSES it:

  seat=jules  -> shells out to `scripts/jules_dispatch.py new` directly
                 (the same script `jules_lane.py` itself calls). This tool
                 does the one-shot POST; `jules_lane.py --harvest` (or this
                 file's own `--harvest`) still owns polling to completion.
  seat=spark  -> writes the chore body into `infra/army/spark-queue/<id>.md`
                 in that lane's own file format, so `spark_lane.sh`'s
                 existing StartInterval tick picks it up on its own next
                 run. Spark's contract (read-only, never opens a PR) is
                 unchanged by going through this file.
  seat=haiku / seat=luna -> catalog entries only today. No cheap-seat CLI
                 for either is wired into this repo yet (see
                 scripts/arsenal_probe.py) — `--dispatch` on these seats is a
                 clean refusal (exit 3) naming that, not a silent no-op, so a
                 chore never LOOKS dispatched when nothing ran.

Contract, same as the Jules seat rules (CLAUDE.md §5): a cheap seat GENERATES,
it never lands anything. Every dispatched chore still needs an interactive
session's independent verification before it ships.

Schema (frontmatter block, two literal `---` lines — no yaml dependency,
matches the rest of this repo's hand-rolled key:value header convention):

    ---
    id: <slug, matches filename stem>
    title: <short imperative — becomes the session/report title>
    seat: jules | spark | haiku | luna
    scope: <paths the change may touch>
    acceptance: <exact command a verifier runs to call the diff correct>
    status: pending | dispatched | queued-spark | in-progress | completed | failed
    ---

    <task body — same authoring discipline as infra/army/jules-queue/README.md:
    where, what, why, scope fence, acceptance>

`session`/`dispatched_at` are added to the header by `--dispatch` itself —
never hand-authored.

Usage:
    python3 scripts/chore_dispatch.py --list
    python3 scripts/chore_dispatch.py --dispatch <id> --seat jules|spark [--dry-run]
    python3 scripts/chore_dispatch.py --harvest
    python3 scripts/chore_dispatch.py --dispatch-next [--dry-run]

Exit codes: 0 ok · 2 schema error · 3 usage/no-such-chore/unwired-seat ·
4 chore not in a dispatchable state (already dispatched/queued/closed) ·
75 lock busy (another dispatch/harvest mutation is in progress — EX_TEMPFAIL).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

VALID_SEATS = ("jules", "spark", "haiku", "luna")
VALID_STATUSES = (
    "pending", "dispatched", "queued-spark", "in-progress", "completed", "failed",
)
REQUIRED_FIELDS = ("id", "title", "seat", "scope", "acceptance", "status")

COMPLETED_RE = re.compile(r"complet", re.IGNORECASE)
FAILED_RE = re.compile(r"fail|error|cancel", re.IGNORECASE)

EXIT_LOCK_BUSY = 75


def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name, "").strip()
    return Path(val) if val else default


class Paths:
    """All paths env-overridable — same pattern as jules_lane.py's Paths,
    so tests fixture a fake world instead of touching the real repo/queue."""

    def __init__(self) -> None:
        self.repo = _env_path("CHORE_REPO", Path(__file__).resolve().parent.parent)
        self.queue_dir = _env_path(
            "CHORE_QUEUE_DIR", self.repo / "infra" / "army" / "chore-queue"
        )
        self.spark_queue_dir = _env_path(
            "CHORE_SPARK_QUEUE_DIR", self.repo / "infra" / "army" / "spark-queue"
        )
        self.jules_dispatch_script = _env_path(
            "CHORE_JULES_DISPATCH_SCRIPT", self.repo / "scripts" / "jules_dispatch.py"
        )


# --------------------------------------------------------------- chore I/O
def parse_chore(path: Path) -> tuple[dict[str, str], str]:
    """(fields, body) from a `---`-delimited key:value header. Raises
    ValueError (never crashes with a raw traceback) on a malformed file —
    the caller turns that into a schema-error exit, not a stack trace."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path.name}: missing opening '---' frontmatter delimiter")
    fields: dict[str, str] = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
        i += 1
    if i >= len(lines):
        raise ValueError(f"{path.name}: missing closing '---' frontmatter delimiter")
    body = "\n".join(lines[i + 1:]).lstrip("\n")
    return fields, body


def validate_schema(fields: dict[str, str], name: str) -> list[str]:
    errors = []
    missing = [f for f in REQUIRED_FIELDS if not fields.get(f)]
    if missing:
        errors.append(f"{name}: missing/empty required field(s): {missing}")
    seat = fields.get("seat")
    if seat and seat not in VALID_SEATS:
        errors.append(f"{name}: seat={seat!r} not one of {list(VALID_SEATS)}")
    status = fields.get("status")
    if status and status not in VALID_STATUSES:
        errors.append(f"{name}: status={status!r} not one of {list(VALID_STATUSES)}")
    return errors


def write_chore(path: Path, fields: dict[str, str], body: str) -> None:
    """Atomic write-then-replace (matches jules_lane.py's save_jsonl
    convention) — a crash mid-write must never leave a half-written chore."""
    header = ["---"] + [f"{k}: {v}" for k, v in fields.items() if v != ""] + ["---"]
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text("\n".join(header) + "\n\n" + body.rstrip("\n") + "\n", encoding="utf-8")
    tmp.replace(path)


def load_chores(paths: Paths) -> list[tuple[Path, dict[str, str], str]]:
    out = []
    if not paths.queue_dir.is_dir():
        return out
    for f in sorted(paths.queue_dir.glob("*.md")):
        if f.name.lower() == "readme.md":
            continue
        try:
            fields, body = parse_chore(f)
        except ValueError as e:
            print(f"chore_dispatch: SKIP {f.name}: {e}", file=sys.stderr)
            continue
        out.append((f, fields, body))
    return out


def find_chore(paths: Paths, chore_id: str):
    for f, fields, body in load_chores(paths):
        if fields.get("id") == chore_id:
            return f, fields, body
    return None


# --------------------------------------------------------- subprocess seams
# Thin wrappers so tests monkeypatch exactly these two calls instead of
# `subprocess.run` globally — same isolation pattern as jules_lane.py's
# `run_jules_dispatch`. Never hits the network under test.
def _jules_new(paths: Paths, prompt: str, title: str, branch: str | None = None) -> tuple[int, str, str]:
    cmd = [sys.executable, str(paths.jules_dispatch_script), "new",
           "--prompt", prompt, "--title", title, "--json"]
    if branch:
        cmd += ["--branch", branch]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def _jules_status(paths: Paths, session: str) -> tuple[int, str, str]:
    cmd = [sys.executable, str(paths.jules_dispatch_script), "status", session, "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    return proc.returncode, proc.stdout, proc.stderr


# --------------------------------------------------------------- dispatch
def dispatch_jules(paths: Paths, path: Path, fields: dict, body: str, dry_run: bool) -> int:
    title = fields.get("title", fields["id"])
    prompt = f"# {title}\n\n{body}"
    branch = fields.get("branch", "").strip() or None
    if dry_run:
        print(f"[dry-run] would dispatch {fields['id']} to jules "
              f"(title={title!r}, branch={branch or 'main'!r}, prompt {len(prompt)} chars) — "
              f"no session created")
        return 0
    rc, out, err = _jules_new(paths, prompt, title, branch)
    if rc != 0:
        print(f"chore_dispatch: jules dispatch failed rc={rc}: {err[:400]}", file=sys.stderr)
        return rc or 1
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        print(f"chore_dispatch: jules_dispatch.py returned non-JSON: {out[:300]}", file=sys.stderr)
        return 1
    session = data.get("name", "")
    if not session:
        print(f"chore_dispatch: jules_dispatch.py returned no session name: {out[:300]}", file=sys.stderr)
        return 1
    fields["status"] = "dispatched"
    fields["session"] = session
    fields["dispatched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_chore(path, fields, body)
    print(f"dispatched {fields['id']} -> jules session {session}")
    return 0


def dispatch_spark(paths: Paths, path: Path, fields: dict, body: str, dry_run: bool) -> int:
    title = fields.get("title", fields["id"])
    content = f"# {title}\n\n{body}"
    target = paths.spark_queue_dir / f"{fields['id']}.md"
    if dry_run:
        print(f"[dry-run] would write {target} ({len(content)} chars) for "
              f"spark_lane.sh's next tick — read-only, no PR")
        return 0
    paths.spark_queue_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    fields["status"] = "queued-spark"
    fields["dispatched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_chore(path, fields, body)
    print(f"queued {fields['id']} -> {target} (spark_lane.sh, read-only, next tick)")
    return 0


DISPATCHERS = {"jules": dispatch_jules, "spark": dispatch_spark}


# ------------------------------------------------------------------- locking
def _lockfile_path(paths: Paths) -> Path:
    return paths.queue_dir / ".chore_dispatch.lock"


class ChoreLock:
    """Non-blocking exclusive flock guarding every mutation path (a real
    --dispatch, --harvest) — the daily plist tick and a manual invocation
    can otherwise race and double-dispatch the same chore into two live
    Jules sessions (refuter R1 finding 4). `with ChoreLock(paths) as ok:` —
    ok is False if another mutation currently holds the lock.

    Uses BSD flock() semantics (fcntl.flock, not POSIX fcntl record locks):
    the lock is bound to the OPEN FILE DESCRIPTION, not the owning process,
    so two independent opens of the same path genuinely conflict even from
    within the same process — this is what makes the lock test in
    scripts/tests/test_chore_dispatch.py deterministic without threads."""

    def __init__(self, paths: Paths) -> None:
        self.path = _lockfile_path(paths)
        self._fh = None

    def __enter__(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.close()
            return False
        self._fh = fh
        return True

    def __exit__(self, *exc_info) -> None:
        if self._fh is not None:
            try:
                fcntl.flock(self._fh, fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None


def cmd_dispatch(paths: Paths, chore_id: str, seat: str, dry_run: bool) -> int:
    if seat not in VALID_SEATS:
        print(f"chore_dispatch: --seat {seat!r} not one of {list(VALID_SEATS)}", file=sys.stderr)
        return 3
    found = find_chore(paths, chore_id)
    if found is None:
        print(f"chore_dispatch: no chore with id={chore_id!r} in {paths.queue_dir}", file=sys.stderr)
        return 3
    path, fields, body = found
    errors = validate_schema(fields, path.name)
    if errors:
        for e in errors:
            print(f"chore_dispatch: schema error: {e}", file=sys.stderr)
        return 2
    if fields.get("status") != "pending":
        print(f"chore_dispatch: {chore_id} status={fields.get('status')!r}, not 'pending' — "
              f"refusing to re-dispatch", file=sys.stderr)
        return 4
    if seat not in DISPATCHERS:
        print(f"chore_dispatch: no dispatch code wired for seat={seat!r} yet — "
              f"{seat} has no cheap-seat CLI in this repo (see scripts/arsenal_probe.py); "
              f"hand this chore to the matching Agent subagent instead", file=sys.stderr)
        return 3
    if dry_run:
        return DISPATCHERS[seat](paths, path, fields, body, dry_run)
    with ChoreLock(paths) as locked:
        if not locked:
            print(f"chore_dispatch: lock busy ({_lockfile_path(paths)}) — another dispatch/harvest "
                  f"is in progress, refusing to double-dispatch {chore_id}", file=sys.stderr)
            return EXIT_LOCK_BUSY
        return DISPATCHERS[seat](paths, path, fields, body, dry_run)


def cmd_dispatch_next(paths: Paths, dry_run: bool) -> int:
    unwired: list[str] = []
    for _, fields, _ in load_chores(paths):
        if fields.get("status") != "pending":
            continue
        seat = fields.get("seat", "")
        if seat not in DISPATCHERS:
            unwired.append(f"{fields.get('id', '?')} (seat={seat})")
            continue
        print(f"dispatch-next: picking {fields.get('id')} (seat={seat})")
        return cmd_dispatch(paths, fields.get("id", ""), seat, dry_run)
    if unwired:
        print(f"dispatch-next: skipped {len(unwired)} pending chore(s) with no wired dispatcher — "
              f"{', '.join(unwired)}", file=sys.stderr)
        print("dispatch-next: queue has only unwired-seat chores pending — nothing dispatched")
    else:
        print("dispatch-next: queue empty — no chore with status=pending")
    return 0


def cmd_list(paths: Paths) -> int:
    chores = load_chores(paths)
    if not chores:
        print(f"(no chores in {paths.queue_dir})")
        return 0
    for _, fields, _ in chores:
        print(f"{fields.get('id', '?'):42s} seat={fields.get('seat', '?'):6s} "
              f"status={fields.get('status', '?'):13s} {fields.get('title', '')}")
    return 0


HARVESTABLE_STATUSES = ("dispatched", "in-progress")


def cmd_harvest(paths: Paths) -> int:
    """Polls seat=jules chores currently status in {dispatched, in-progress}
    — spark chores are owned end-to-end by spark_lane.sh's own read-only
    report, there is nothing here to harvest for them. `in-progress` is
    included because harvest itself is what writes that status (a running
    session polled once): without it, a chore is polled exactly once, flips
    to in-progress, and is never looked at again for the rest of its run
    (refuter R1 finding 1)."""
    with ChoreLock(paths) as locked:
        if not locked:
            print(f"chore_dispatch: lock busy ({_lockfile_path(paths)}) — another dispatch/harvest "
                  f"is in progress, skipping this harvest tick", file=sys.stderr)
            return EXIT_LOCK_BUSY
        updated = 0
        for path, fields, body in load_chores(paths):
            if fields.get("seat") != "jules" or fields.get("status") not in HARVESTABLE_STATUSES:
                continue
            session = fields.get("session", "")
            if not session:
                continue
            rc, out, err = _jules_status(paths, session)
            if rc != 0:
                print(f"chore_dispatch: harvest status-check failed for {fields['id']} "
                      f"rc={rc}: {err[:200]}", file=sys.stderr)
                continue
            try:
                data = json.loads(out)
            except json.JSONDecodeError:
                print(f"chore_dispatch: non-JSON status response for {fields['id']}", file=sys.stderr)
                continue
            state = str(data.get("state", ""))
            if COMPLETED_RE.search(state):
                fields["status"] = "completed"
            elif FAILED_RE.search(state):
                fields["status"] = "failed"
            else:
                fields["status"] = "in-progress"
            write_chore(path, fields, body)
            updated += 1
            print(f"harvested {fields['id']}: status={fields['status']} (session {session}, state={state!r})")
        if not updated:
            print("harvest: nothing to update")
        return 0


# --------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dispatch", metavar="ID")
    parser.add_argument("--seat", choices=VALID_SEATS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--harvest", action="store_true")
    parser.add_argument("--dispatch-next", action="store_true")
    args = parser.parse_args(argv)

    paths = Paths()

    if args.list:
        return cmd_list(paths)
    if args.dispatch:
        if not args.seat:
            print("chore_dispatch: --dispatch requires --seat", file=sys.stderr)
            return 3
        return cmd_dispatch(paths, args.dispatch, args.seat, args.dry_run)
    if args.harvest:
        return cmd_harvest(paths)
    if args.dispatch_next:
        return cmd_dispatch_next(paths, args.dry_run)

    parser.print_help()
    return 3


if __name__ == "__main__":
    sys.exit(main())
