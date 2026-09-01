#!/usr/bin/env python3
"""queue_stall_notify.py — the delivery wire for scripts/queue_stall_classifier.py.

WHY THIS EXISTS: queue_stall_classifier.py is a deliberately pure reporter (see its own module
docstring) — zero disk writes, zero `os.environ` reads, read-only `gh api` GETs only, its own
test suite enforces that with a static AST proof. Nothing invokes it and nobody reads its
output: `git grep -l queue_stall_classifier origin/main` returns only the script itself, its
test, and evidence-pack references — no crontab entry anywhere in the fleet. A working alarm
that speaks to nobody is exactly scar family #2 (green != working, cron theater): the
classifier's OWN exit code is 0 whenever it ran cleanly, REGARDLESS of whether it found a single
stalled PR — so a naive cron wiring (`cron-runner.sh queue_stall_classifier.py`) would produce a
permanently green job, its stall table landing in a logfile nobody tails. This script is the
delivery wire: it runs the classifier, reads its report, and fleet-mails every row that names an
actual problem.

THIS SCRIPT DOES NOT TOUCH queue_stall_classifier.py. All side effects — the classifier
subprocess call, the fleet_mail.sh broadcasts — live HERE, in a separate, named, independently
testable module, so the classifier's own purity invariant (and its AST self-check) is never put
at risk by an edit to this file.

SUBPROCESS, NEVER IMPORT: queue_stall_classifier.py is run via `sys.executable
queue_stall_classifier.py --json`, not imported and called in-process. Importing it would still
be technically read-only, but it would blur the classifier's own "this script never mutates
anything" claim into "this script is never run in the same process as something that does" — a
materially weaker guarantee its own AST test cannot see across an import boundary. Team-lead
mandate, verbatim: "do NOT import it — subprocess keeps the purity boundary visible." A
consequence: this module cannot import CANNOT_VERIFY/STALL_CAUSES from the classifier either —
its cause vocabulary is duplicated below as literal strings (STANDALONE-by-design, the same
convention queue_stall_classifier.py itself uses for read_fable_gate_state vs
scripts/ci/harness_gate_read.py — see that module's docstring trap (e)). If the classifier's
cause vocabulary ever changes, this file's REAL_STALL_CAUSES/CANNOT_VERIFY must be updated by
hand; nothing across the subprocess boundary can catch that drift automatically.

CAUSE VOCABULARY: classify_stall()'s 5-bucket STALL_CAUSES set is NOT uniformly "a problem".
"queued-and-advancing" is its own documented default — "armed/queued, no known blocker; may
simply be slow" — the classifier's own way of saying nothing is actionably wrong. Fleet-mailing
that bucket every DEFAULT_MIN_AGE_MINUTES=30 tick would be noise-by-design, not signal, so
REAL_STALL_CAUSES below deliberately excludes it. The other 4 causes
(conflict/gate-verdict-missing/required-check-red/not-armed) each name something a human or the
next gate session should look at, and so does CANNOT-VERIFY — a row the classifier could not
read is news (its own instrument failed to measure), not silence.

DEDUP KEY ENCODES THE CAUSE, NOT JUST THE PR NUMBER: `queue_stall:<number>:<cause>`. The
classifier holds no state of its own (unlike queue_unstick.py, which fingerprints a DIRTY signal
on head-sha + conflict-digest across ticks) and the fleet mailbox reader
(infra/claude-hooks/mailbox_inject.py) keeps only the newest file per key, marking a broadcast
seen-once-per-session. A key of `queue_stall:<number>` alone would mean a PR whose stall CAUSE
changes (say, `not-armed` today, `required-check-red` tomorrow, after someone manually armed it
and CI then failed) never resurfaces once the first key's file already exists — the exact
silent-drop shape this module exists to avoid.

Kill switch: QUEUE_STALL_NOTIFY_ENABLED=false makes every invocation a no-op that still prints a
receipt line (superscar #2: a mute cron is a dead cron — silence must never be the only signal
that nothing happened). Checked BEFORE the classifier subprocess is even invoked.

--dry-run performs ZERO fleet-mail sends (and zero subprocess calls of any kind beyond the
classifier read itself) and prints exactly what it would have sent. This is how the conductor
verifies this script.

Env overrides:
  QUEUE_STALL_NOTIFY_ENABLED            "false"/"0"/"no"/"off" -> no-op (default: on)
  QUEUE_STALL_NOTIFY_REPO               default "Bali-Zero/Teman2"
  QUEUE_STALL_NOTIFY_MIN_AGE_MINUTES    default 30 (passed to the classifier as
                                         --min-age-minutes; duplicates
                                         queue_stall_classifier.py's own
                                         DEFAULT_MIN_AGE_MINUTES, STANDALONE-by-design)
  QUEUE_STALL_NOTIFY_CAP                default 5 (max fleet-mail sends per run; an UNMEASURED
                                         placeholder, same honesty as queue_unstick.py's own
                                         QUEUE_UNSTICK_CAP comment — chosen only because a bad
                                         night must not storm the fleet mailbox, not because 5
                                         was derived from anything)
  QUEUE_STALL_NOTIFY_FLEET_MAIL_HOST    default "pro" (host arg to fleet_mail.sh)
  QUEUE_STALL_NOTIFY_CLASSIFIER_TIMEOUT default 180 (seconds, subprocess timeout for the
                                         classifier call — it pages through every open PR and
                                         can legitimately take a while on a busy queue)

Exit codes: 0 = ran clean (the classifier ran clean AND every attempted send succeeded, whether
or not any PR was actually stalled); 1 = the classifier itself failed (non-zero rc — propagated
as a failure even if every row that DID parse was delivered successfully) OR at least one
fleet-mail send failed.

Tests: scripts/tests/test_queue_stall_notify.py.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
CLASSIFIER = SCRIPTS_DIR / "queue_stall_classifier.py"

REPO = os.environ.get("QUEUE_STALL_NOTIFY_REPO", "Bali-Zero/Teman2")
MIN_AGE_MINUTES = int(os.environ.get("QUEUE_STALL_NOTIFY_MIN_AGE_MINUTES", "30"))
# UNMEASURED placeholder — see module docstring env-override table. Deliberately small: the
# harm of under-sending (a stall waits one more 30-minute tick to resurface) is bounded and
# self-healing; the harm of over-sending (storming the fleet mailbox on a bad night) is not.
CAP = int(os.environ.get("QUEUE_STALL_NOTIFY_CAP", "5"))
FLEET_MAIL_HOST = os.environ.get("QUEUE_STALL_NOTIFY_FLEET_MAIL_HOST", "pro")
CLASSIFIER_TIMEOUT = int(os.environ.get("QUEUE_STALL_NOTIFY_CLASSIFIER_TIMEOUT", "180"))

# Duplicated from queue_stall_classifier.py's own CANNOT_VERIFY sentinel — see module docstring
# "SUBPROCESS, NEVER IMPORT" for why this is a literal, not an import.
CANNOT_VERIFY = "CANNOT-VERIFY"

# The 4 STALL_CAUSES that name an actual problem — see module docstring "CAUSE VOCABULARY" for
# why "queued-and-advancing" is deliberately excluded from this set.
REAL_STALL_CAUSES = frozenset(
    {
        "conflict",
        "gate-verdict-missing",
        "required-check-red",
        "not-armed",
    }
)


def _enabled() -> bool:
    return os.environ.get("QUEUE_STALL_NOTIFY_ENABLED", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command; never raises. Returns (rc, stdout, stderr). Duplicated boundary shape
    from queue_unstick.py::_run (STANDALONE-by-design, same convention as the rest of this
    family) — including `errors="replace"`, which is what makes "never raises" actually true:
    with the default strict decoding, `text=True` raises UnicodeDecodeError (a ValueError,
    caught by neither except arm) the moment a subprocess prints a non-UTF-8 byte."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Classifier invocation — subprocess only, see module docstring.
# ---------------------------------------------------------------------------


def run_classifier(
    *,
    repo: str,
    min_age_minutes: int,
    classifier_path: Path = CLASSIFIER,
    timeout: int = CLASSIFIER_TIMEOUT,
) -> tuple[int, dict[str, Any] | None, str, str]:
    """Invoke queue_stall_classifier.py as a SUBPROCESS with `--json`. Returns
    (rc, report_or_None, raw_stdout, raw_stderr).

    `report` is None ONLY when stdout could not be parsed as JSON at all (python itself failed
    to start, or crashed before printing anything) — never fabricated from a non-zero `rc`
    alone. The classifier's OWN contract (its module docstring, trap (g) and the CANNOT-VERIFY
    row shape) prints a full JSON report even on some of its rc=1 paths — a single CANNOT-VERIFY
    row among otherwise-fine rows, for instance — and this notifier must still be able to act on
    and report those rows precisely, not collapse "the classifier's rc was 1" into "there is
    nothing here to look at"."""
    argv = [
        sys.executable,
        str(classifier_path),
        "--repo",
        repo,
        "--min-age-minutes",
        str(min_age_minutes),
        "--json",
    ]
    rc, out, err = _run(argv, timeout=timeout)
    report: dict[str, Any] | None = None
    if out.strip():
        try:
            report = json.loads(out)
        except json.JSONDecodeError:
            report = None
    return rc, report, out, err


# ---------------------------------------------------------------------------
# Pure planning — no I/O. What scripts/tests/test_queue_stall_notify.py exercises directly.
# ---------------------------------------------------------------------------


def plan_notifications(rows: list[dict[str, Any]], *, cap: int) -> dict[str, list]:
    """Pure: no I/O. Decides, for each classifier row (in the order given), whether it is
    notify-worthy, its fleet-mail dedup key, and whether the per-run cap suppresses it.

    See module docstring "DEDUP KEY ENCODES THE CAUSE" for why the key is
    `queue_stall:<number>:<cause>`, never `queue_stall:<number>` alone.

    Returns {
        "to_notify": [ {"number","cause","key","cannot_verify","detail"}, ... ]  (len <= cap,
                       in the SAME order `rows` arrived in — this function never reorders),
        "suppressed_by_cap": [ same shape, every notify-worthy row past the cap ],
        "skipped": [ (number, cause), ... ]  # not notify-worthy at all: "queued-and-advancing"
                                              # or any cause this module does not recognise
                                              # (never signalled, and never counted toward
                                              # `stalled` in the summary line)
    }
    """
    to_notify: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    skipped: list[tuple[Any, Any]] = []

    for row in rows:
        cause = row.get("cause")
        number = row.get("number")
        if cause == CANNOT_VERIFY:
            cannot_verify = True
        elif cause in REAL_STALL_CAUSES:
            cannot_verify = False
        else:
            skipped.append((number, cause))
            continue

        item = {
            "number": number,
            "cause": cause,
            "key": f"queue_stall:{number}:{cause}",
            "cannot_verify": cannot_verify,
            "detail": row.get("detail", ""),
        }
        if len(to_notify) < cap:
            to_notify.append(item)
        else:
            suppressed.append(item)

    return {"to_notify": to_notify, "suppressed_by_cap": suppressed, "skipped": skipped}


def _format_message(item: dict[str, Any]) -> str:
    """Pure: the fleet-mail body text. CANNOT-VERIFY gets a DISTINCT wording — "an instrument
    that could not read is news, not silence" (team-lead mandate, verbatim) — never the same
    sentence shape as a real stall cause, so a reader of the mailbox can tell the two apart at a
    glance without opening the classifier report."""
    number = item["number"]
    cause = item["cause"]
    detail = item.get("detail", "")
    if item["cannot_verify"]:
        return (
            f"queue_stall: PR #{number} — the classifier COULD NOT VERIFY this PR's stall state "
            f"({detail}). An instrument that could not read is news, not silence — this is not "
            "the same as 'no stall found'."
        )
    return f"queue_stall: PR #{number} is stalled ({cause}): {detail}"


# ---------------------------------------------------------------------------
# Delivery — side-effecting.
# ---------------------------------------------------------------------------


def send_notification(
    item: dict[str, Any], *, dry_run: bool, repo_root: Path = REPO_ROOT
) -> tuple[bool, str]:
    """Mirrors queue_unstick.py::send_dirty_signal's shape (team-lead mandate: "Copy the exact
    invocation shape used by scripts/queue_unstick.py around lines 632 and 647-651") — same
    fleet_mail.sh argv shape, same dry-run / missing-file / non-zero-rc handling. Returns
    (ok, detail_line_for_the_log)."""
    msg = _format_message(item)
    number = item["number"]

    if dry_run:
        return True, (
            f"[dry-run] would signal PR #{number} ({item['cause']}) via fleet_mail.sh "
            f"{FLEET_MAIL_HOST} broadcast --key {item['key']}: {msg}"
        )

    fleet_mail = repo_root / "scripts" / "fleet_mail.sh"
    if not fleet_mail.is_file():
        return False, f"signal FAILED PR #{number}: fleet_mail.sh not found at {fleet_mail}"
    rc, out, err = _run(
        ["bash", str(fleet_mail), FLEET_MAIL_HOST, "broadcast", "--key", item["key"], msg],
        timeout=30,
    )
    if rc != 0:
        return False, f"signal FAILED PR #{number} rc={rc}: {err.strip()[:300]}"
    return True, f"signal OK PR #{number}: {out.strip() or 'sent'}"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else "queue_stall_notify"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="perform zero fleet-mail sends; print exactly what would be sent",
    )
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--min-age-minutes", type=int, default=MIN_AGE_MINUTES)
    parser.add_argument(
        "--cap", type=int, default=CAP,
        help="max fleet-mail sends per run (default %(default)s)",
    )
    parser.add_argument(
        "--classifier-path", default=str(CLASSIFIER),
        help="override queue_stall_classifier.py location (tests only)",
    )
    parser.add_argument("--classifier-timeout", type=int, default=CLASSIFIER_TIMEOUT)
    args = parser.parse_args(argv)

    # Kill switch checked FIRST — before the classifier subprocess ever runs (module docstring:
    # "Checked BEFORE the classifier subprocess is even invoked").
    if not _enabled():
        print(
            "QUEUE_STALL_NOTIFY_SUMMARY disabled=true examined=0 stalled=0 sent=0 "
            f"send_failed=0 suppressed_by_cap=0 dry_run={str(args.dry_run).lower()}"
        )
        return 0

    rc, report, out, err = run_classifier(
        repo=args.repo,
        min_age_minutes=args.min_age_minutes,
        classifier_path=Path(args.classifier_path),
        timeout=args.classifier_timeout,
    )
    classifier_failed = rc != 0

    if report is None:
        # The classifier's stdout could not be parsed as JSON at all — nothing to plan over.
        # Still a structured, loud receipt (superscar #2), never a silent return.
        detail = (err or out or "no output").strip()[:300]
        print(
            f"QUEUE_STALL_NOTIFY_SUMMARY classifier_rc={rc} classifier_failed=true "
            "examined=0 stalled=0 sent=0 send_failed=0 suppressed_by_cap=0 "
            f"dry_run={str(args.dry_run).lower()} error={detail!r}"
        )
        return 1

    rows = report.get("rows") or []
    plan = plan_notifications(rows, cap=args.cap)

    sent = 0
    send_failed = 0
    for item in plan["to_notify"]:
        ok, detail_line = send_notification(item, dry_run=args.dry_run)
        print(detail_line)
        if ok:
            sent += 1
        else:
            send_failed += 1

    stalled = len(plan["to_notify"]) + len(plan["suppressed_by_cap"])
    summary = (
        f"QUEUE_STALL_NOTIFY_SUMMARY classifier_rc={rc} "
        f"examined={report.get('examined_total', 0)} stalled={stalled} sent={sent} "
        f"send_failed={send_failed} suppressed_by_cap={len(plan['suppressed_by_cap'])} "
        f"cap={args.cap} dry_run={str(args.dry_run).lower()}"
    )
    print(summary)

    # Exit codes — module docstring: the classifier's own failure propagates as a failure here
    # EVEN IF every row that did parse was delivered successfully, and a send failure is its own
    # independent reason to be non-zero. A clean run (classifier rc=0, all sends ok) is 0
    # regardless of whether any PR was actually stalled.
    return 1 if (classifier_failed or send_failed) else 0


if __name__ == "__main__":
    sys.exit(main())
