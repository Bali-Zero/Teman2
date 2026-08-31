#!/usr/bin/env python3
"""Alert when Bali Zero's own price sheet is past its review interval.

Scope, fixed by the mandate (Zero, 2026-08-31, verbatim: "per il prtezzo che
si controlli solo il nostro pricing tool"): this sentinel looks ONLY at Bali
Zero's own price sheet — the file `pricing_service.py` actually loads. It does
not consult NB-2, the web, or any government fee schedule. Government PNBP is
a different question with a different owner; conflating the two is how a
"prices changed" alert ends up meaning nothing anybody can act on.

WHY THIS IS NOT A ONE-LINE DATE COMPARISON
------------------------------------------
The sheet carries `metadata.last_updated`. On 2026-08-31 that field said
`2026-05-06` while the file's content had last changed on 2026-08-26 (git) and
carried entries stamped `verified_on: 2026-08-25`. The field is therefore NOT
maintained: it is a literal somebody wrote once, not a review date. Measured,
not assumed — see the tests.

That has one hard consequence, and it is the whole design:

    `last_updated` can prove the sheet is OVERDUE. It can never prove the
    sheet is FRESH.

So this sentinel refuses to report OK on the strength of that field alone. OK
requires the field to be inside the review interval AND corroborated: at least
one independent trace of the file changing must exist, and none may be newer
than the field. The two traces, both LOWER bounds on when the content moved:

  1. the last git commit touching the file;
  2. the newest per-entry `verified_on` in the sheet.

Every way that conjunction can fail has its own loud outcome, and none of them
is a quiet pass:

  ATTESTATION_UNMAINTAINED  a trace is newer than the field — the review date
                            is not tracking edits, so the freshness question
                            cannot be answered in either direction.
  ANOMALY                   a date in the sheet has not happened yet. A future
                            date is trivially "inside the interval" and no real
                            trace can ever be newer than it, so this shape slips
                            past every other check.
  CANNOT_VERIFY             no trace exists at all (git could not answer and no
                            entry carries verified_on), so the contradiction
                            check would pass VACUOUSLY rather than on evidence;
                            or the sheet is malformed or unreadable.

The asymmetry is preserved throughout: REVIEW_DUE is decided BEFORE the
corroboration gate, because "overdue" is provable from the field alone.

The last three outcomes were added after the kimi-code/k3 council seat found
each as a reachable FALSE OK on the first draft, all reproduced here before
being adopted.

A commit that only reformatted the file would also trip this. That direction
is deliberate: the error it produces is a loud false ATTESTATION_UNMAINTAINED,
never a quiet false OK. A sentinel that errs must err toward noise.

Only 2 of 113 priced entries carry `verified_on` at all. The other 111 are
UNKNOWN, not fresh — that count travels in the alert body, because it is the
reason the file-level date is the only signal there is.

Usage:
    python3 scripts/price_review_sentinel.py
    python3 scripts/price_review_sentinel.py --dry-run
    python3 scripts/price_review_sentinel.py --now 2026-08-31T00:00:00Z  # TEST-ONLY

Exit codes (house contract, `visa_freshness_sentinel.py`):
    0 — OK or APPROACHING (nothing to do, or a heads-up delivered)
    1 — REVIEW_DUE, ATTESTATION_UNMAINTAINED or ANOMALY (an actionable finding)
    2 — CANNOT_VERIFY (unreadable, malformed, uncorroborated, or crashed)

rc=1 means a finding was COMPUTED AND DELIVERED, and the wrapper reads it that
way — so a crash must never be able to exit 1. Every unexpected exception is
caught and turned into rc=2, in classify()'s caller and again around main().

A gateway failure NEVER raises — logged and swallowed, matching the house
contract that `tg_notify.py` never fails its caller.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("price-review-sentinel")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / "apps" / "backend-rag"
TG_NOTIFY = PROJECT_ROOT / "scripts" / "tg_notify.py"

# Ratified by Zero, 2026-08-31 ("va bene 90 giorni").
PRICE_REVIEW_INTERVAL_DAYS = 90
# Heads-up window before the interval expires.
DEFAULT_WARN_DAYS = 14
# One day of slack between writing the review date and the commit landing.
#
# The first version of this comment blamed the UTC/WITA offset, and that was
# backwards: UTC is BEHIND WITA, so a commit's UTC date can never run ahead of
# the WITA date a reviewer would have typed. The real reason is merge lag — a
# reviewer stamps today's date, the PR lands tomorrow, and git honestly reports
# the later day. Corrected after the kimi-code/k3 council seat called the
# justification inverted; the value stays 1, only the reason is now true.
#
# The cost, stated rather than smoothed over: a genuine price edit made exactly
# one day after a genuine review is absorbed and reads as OK. Widening the
# grace buys nothing and hides more; narrowing it to zero makes every ordinary
# same-PR lag look like a broken attestation.
ATTESTATION_GRACE_DAYS = 1

OUTCOME_OK = "OK"
OUTCOME_APPROACHING = "APPROACHING"
OUTCOME_REVIEW_DUE = "REVIEW_DUE"
OUTCOME_UNMAINTAINED = "ATTESTATION_UNMAINTAINED"
OUTCOME_ANOMALY = "ANOMALY"
OUTCOME_CANNOT_VERIFY = "CANNOT_VERIFY"

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_CANNOT_VERIFY = 2
# A finding was computed but the alert did NOT go out. Distinct from both a
# delivered finding and a malfunction: an undelivered p0 must never be
# representable as a successful delivery (codex-gpt-5.6-sol).
EXIT_UNDELIVERED = 3

# End-anchored on the date, or on a full ISO-8601 instant. Unanchored, this
# accepted "2026-05-06-whatever" and silently used the leading date — a
# malformed field must be UNKNOWN, not partially believed (codex-gpt-5.6-sol).
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ][0-9:.+Z-]+)?$")


# ---------------------------------------------------------------------------
# Locating the sheet the LIVE service loads (never a name typed twice)
# ---------------------------------------------------------------------------


def resolve_price_sheet(backend_root: Path = BACKEND_ROOT) -> Path:
    """Return the path of the price sheet `pricing_service` itself loads.

    The filename is imported from the service, never restated here. A sheet
    renamed to a 2027 edition must not leave this sentinel watching a dead
    file and reporting green — the classic proxy failure. Raises on failure;
    the caller turns that into CANNOT_VERIFY rather than guessing a name.
    """
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    from backend.services.pricing.pricing_service import (  # noqa: PLC0415
        _PRICING_FILENAME,
    )

    return backend_root / "backend" / "data" / _PRICING_FILENAME


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def parse_date(raw: Any) -> dt.date | None:
    """Parse a leading ISO-8601 date. Returns None for anything unparseable —
    absence is UNKNOWN, and the caller must never read it as 'today'."""
    if not isinstance(raw, str):
        return None
    match = _ISO_DATE.match(raw.strip())
    if match is None:
        return None
    try:
        return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def iter_priced_entries(sheet: dict) -> list[tuple[str, dict]]:
    """Every leaf that carries a price. Mirrors how the catalogue is shaped:
    a priced leaf has `price` or `tier_range` and is not descended into."""
    found: list[tuple[str, dict]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if "price" in node or "tier_range" in node:
                found.append((path, node))
                return
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(sheet.get("services", {}), "services")
    return found


def git_worktree_dirty(path: Path, repo_root: Path = PROJECT_ROOT) -> bool:
    """True when `path` has uncommitted changes.

    Not theoretical: the Pro checkout routinely carries uncommitted files, and
    a price edited in the working tree leaves git history untouched — so
    `git_last_change` would report an old date and the sentinel would call an
    edited sheet current (codex-gpt-5.6-sol). A dirty file is a change that
    happened at some unknown time no earlier than the last commit, so it counts
    as a trace dated today.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--", str(path)],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("git status failed: %s", exc)
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


def git_last_change(path: Path, repo_root: Path = PROJECT_ROOT) -> dt.date | None:
    """Date of the last commit touching `path`, or None if git cannot say.

    None is UNKNOWN — with git unavailable the attestation check simply loses
    one of its two traces; it never becomes a pass.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--format=%cI", "--", str(path)],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # noqa: BLE001 — git absence must not crash the sentinel
        logger.warning("git log failed: %s", exc)
        return None
    if proc.returncode != 0:
        logger.warning("git log rc=%s: %s", proc.returncode, proc.stderr.strip())
        return None
    return parse_date(proc.stdout.strip())


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Verdict:
    outcome: str
    reason: str
    last_updated: dt.date | None = None
    age_days: int | None = None
    interval_days: int = PRICE_REVIEW_INTERVAL_DAYS
    worktree_dirty: bool = False
    priced_entries: int = 0
    entries_with_attestation: int = 0
    newest_verified_on: dt.date | None = None
    git_last_change: dt.date | None = None
    sheet_path: str | None = None

    def to_dict(self) -> dict:
        out = dataclasses.asdict(self)
        for key in ("last_updated", "newest_verified_on", "git_last_change"):
            value = out[key]
            out[key] = value.isoformat() if isinstance(value, dt.date) else None
        return out

    @property
    def entries_without_attestation(self) -> int:
        return self.priced_entries - self.entries_with_attestation


def classify(
    sheet: dict,
    *,
    today: dt.date,
    git_date: dt.date | None,
    worktree_dirty: bool = False,
    sheet_path: Path | None = None,
    interval_days: int = PRICE_REVIEW_INTERVAL_DAYS,
    warn_days: int = DEFAULT_WARN_DAYS,
) -> Verdict:
    """Decide the outcome. OK requires BOTH that the attestation is inside the
    interval AND that nothing shows the file moved after it was written."""
    priced = iter_priced_entries(sheet)
    attested = [
        d for d in (parse_date(entry.get("verified_on")) for _, entry in priced) if d
    ]
    newest_verified = max(attested) if attested else None
    common = {
        "worktree_dirty": worktree_dirty,
        "priced_entries": len(priced),
        "entries_with_attestation": len(attested),
        "newest_verified_on": newest_verified,
        "git_last_change": git_date,
        "interval_days": interval_days,
        "sheet_path": str(sheet_path) if sheet_path else None,
    }

    if not priced:
        return Verdict(
            outcome=OUTCOME_CANNOT_VERIFY,
            reason=(
                "the sheet contains no priced entries at all — an empty or "
                "structurally broken catalogue cannot be reported as current. "
                "There is nothing here whose freshness could be assessed."
            ),
            **common,
        )

    metadata = sheet.get("metadata")
    if not isinstance(metadata, dict):
        return Verdict(
            outcome=OUTCOME_CANNOT_VERIFY,
            reason=(
                f"metadata is {type(metadata).__name__}, not an object — the "
                "sheet is malformed and carries no readable review date."
            ),
            **common,
        )

    last_updated = parse_date(metadata.get("last_updated"))
    if last_updated is None:
        return Verdict(
            outcome=OUTCOME_CANNOT_VERIFY,
            reason="metadata.last_updated is missing or unparseable — the sheet "
                   "carries no review date at all, so its age is UNKNOWN.",
            **common,
        )

    age_days = (today - last_updated).days
    common["last_updated"] = last_updated
    common["age_days"] = age_days

    # A date that has not happened yet is not a fresh review, it is a broken
    # one — and it is the shape that slips past every other check here, since
    # a negative age is trivially "inside the interval" and no real trace can
    # ever be newer than a future date. Found by the kimi-code/k3 council seat
    # and reproduced before adoption: last_updated=2027-01-01 with today
    # 2026-08-31 returned OK, reason "reviewed -123 days ago".
    future = [
        (label, value)
        for label, value in (
            ("metadata.last_updated", last_updated),
            ("the newest verified_on", newest_verified),
        )
        if value is not None and value > today
    ]
    if future:
        detail = "; ".join(f"{label} is {value.isoformat()}" for label, value in future)
        return Verdict(
            outcome=OUTCOME_ANOMALY,
            reason=(
                f"a date in the sheet has not happened yet ({detail}, today is "
                f"{today.isoformat()}). A review cannot be dated in the future, "
                "so the attestation is not trustworthy and no freshness claim "
                "can rest on it."
            ),
            **common,
        )

    # The attestation is only worth reading if nothing contradicts it.
    traces = [d for d in (git_date, newest_verified) if d is not None]
    if worktree_dirty:
        # An uncommitted edit happened at an unknown time, no earlier than the
        # last commit. Dating it today is the conservative reading: it makes
        # the sheet look changed-since-review, never fresher than it is.
        traces.append(today)
    contradicting = [d for d in traces if (d - last_updated).days > ATTESTATION_GRACE_DAYS]
    if contradicting:
        newest_trace = max(contradicting)
        return Verdict(
            outcome=OUTCOME_UNMAINTAINED,
            reason=(
                f"metadata.last_updated says {last_updated.isoformat()} but the "
                f"sheet demonstrably changed on {newest_trace.isoformat()}. The "
                "field is not tracking edits, so it cannot answer the freshness "
                "question in either direction."
            ),
            **common,
        )

    # >= not >: at day 90 a 90-day interval HAS elapsed. The strict form
    # delayed the verdict to day 91 and printed the absurd "due in 0
    # day(s)" on day 90 (codex-gpt-5.6-sol).
    if age_days >= interval_days:
        return Verdict(
            outcome=OUTCOME_REVIEW_DUE,
            reason=(
                f"the price sheet was last reviewed {age_days} days ago "
                f"({last_updated.isoformat()}), past the {interval_days}-day "
                "review interval."
            ),
            **common,
        )

    # Past this point the answer would be OK or APPROACHING — both of which
    # claim the sheet is current. That claim needs corroboration, and with no
    # trace at all there is none: the contradiction check above passed
    # VACUOUSLY, not on evidence. Reported by the kimi-code/k3 council seat and
    # reproduced: git unavailable plus zero verified_on entries returned OK
    # with the reason "nothing shows the sheet changed after that date", when
    # in fact nothing COULD have shown it. Reachable in production — the whole
    # sheet carries two verified_on stamps, and git_last_change() returns None
    # on any git failure. Note the asymmetry is preserved: REVIEW_DUE above is
    # provable from the field alone, so it is returned before this gate.
    if not traces:
        return Verdict(
            outcome=OUTCOME_CANNOT_VERIFY,
            reason=(
                f"metadata.last_updated says {last_updated.isoformat()}, inside "
                f"the {interval_days}-day interval, but there is no independent "
                "trace to corroborate it — git could not answer and no entry "
                "carries verified_on. The field alone cannot establish freshness."
            ),
            **common,
        )

    if age_days > interval_days - warn_days:
        return Verdict(
            outcome=OUTCOME_APPROACHING,
            reason=(
                f"the price sheet is {age_days} days old; the {interval_days}-day "
                f"review is due in {interval_days - age_days} day(s)."
            ),
            **common,
        )

    return Verdict(
        outcome=OUTCOME_OK,
        reason=(
            f"reviewed {age_days} days ago ({last_updated.isoformat()}), inside "
            f"the {interval_days}-day interval, and nothing shows the sheet "
            "changed after that date."
        ),
        **common,
    )


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------


def dedup_key(verdict: Verdict) -> str:
    stamp = verdict.last_updated.isoformat() if verdict.last_updated else "no-date"
    return f"price-review:{verdict.outcome}:{stamp}"


def format_alert_text(verdict: Verdict) -> str:
    heads = {
        OUTCOME_REVIEW_DUE: "💰 Price sheet REVIEW DUE",
        OUTCOME_APPROACHING: "💰 Price sheet review approaching",
        OUTCOME_UNMAINTAINED: "🕳️ Price sheet review date UNMAINTAINED",
        OUTCOME_ANOMALY: "🛑 Price sheet date ANOMALY",
        OUTCOME_CANNOT_VERIFY: "❓ Price sheet CANNOT VERIFY",
        OUTCOME_OK: "✅ Price sheet OK",
    }
    lines = [heads.get(verdict.outcome, verdict.outcome), "", verdict.reason]

    if verdict.priced_entries:
        missing = verdict.entries_without_attestation
        lines.append("")
        lines.append(
            f"{missing} of {verdict.priced_entries} priced entries carry no "
            "verified_on — those are UNKNOWN, not fresh."
        )
    if verdict.outcome in (OUTCOME_UNMAINTAINED, OUTCOME_ANOMALY):
        lines.append("")
        lines.append(
            "Fix: bump metadata.last_updated when the sheet is reviewed, or the "
            "only freshness signal this sentinel has stays broken."
        )
    return "\n".join(lines)


def extract_gateway_verdict(stderr: str) -> str | None:
    for line in reversed((stderr or "").splitlines()):
        stripped = line.strip()
        if stripped.startswith("VERDICT:"):
            return stripped
    return None


@dataclasses.dataclass
class Delivery:
    """What actually happened to the alert — separate from what was decided.

    The first draft returned only the gateway's verdict string and `main()`
    ignored it, so a missing or failing `tg_notify.py` still exited 1 and the
    wrapper wrote "finding delivered". Classification status and delivery
    status are two facts and now travel as two fields.
    """
    attempted: bool = False
    delivered: bool = False
    gateway_verdict: str | None = None

    @property
    def label(self) -> str:
        if not self.attempted:
            return "skipped"
        return "sent" if self.delivered else "FAILED"


def send_alert(verdict: Verdict, gateway_path: Path | None = None) -> Delivery:
    """Route through `scripts/tg_notify.py`. NEVER raises.

    `gateway_path` resolves at CALL time, not at import. As a default argument
    it froze the module constant, so a test that patched `TG_NOTIFY` silently
    reached the REAL gateway instead — which is how a unit test came within one
    missing token of firing a p0 to Zero's phone. Caught here; the shape is
    worth remembering wherever a module constant is used as a default.
    """
    if gateway_path is None:
        gateway_path = TG_NOTIFY
    if verdict.outcome == OUTCOME_OK:
        return Delivery(attempted=False)

    # UNMAINTAINED is p0 alongside REVIEW_DUE: a broken review date means every
    # future run of this sentinel is blind, which outranks a housekeeping note.
    tier = (
        "p0"
        if verdict.outcome in (OUTCOME_REVIEW_DUE, OUTCOME_UNMAINTAINED, OUTCOME_ANOMALY)
        else "digest"
    )
    text = format_alert_text(verdict)
    key = dedup_key(verdict)

    if not gateway_path.is_file():
        logger.warning("tg_notify.py not found at %s — alert NOT sent: %s", gateway_path, key)
        return Delivery(attempted=True, delivered=False)

    try:
        proc = subprocess.run(
            [
                sys.executable, str(gateway_path),
                "--tier", tier,
                "--source", "price-review-sentinel",
                "--dedup-key", key,
                "--", text,
            ],
            capture_output=True, text=True, timeout=30,
        )
        gateway_verdict = extract_gateway_verdict(proc.stderr)
        logger.info(
            "tg_notify: %s (rc=%s, tier=%s, key=%s)",
            gateway_verdict or "NO VERDICT", proc.returncode, tier, key,
        )
        # The gateway printing "VERDICT: SENT" is not delivery — its RETURN
        # CODE is. The first draft believed the printed line and would have
        # called a gateway that exited 3 a success.
        return Delivery(
            attempted=True,
            delivered=proc.returncode == 0,
            gateway_verdict=gateway_verdict,
        )
    except Exception as exc:  # noqa: BLE001 — gateway failure must NEVER crash the sentinel
        logger.warning("tg_notify invocation failed: %s", exc)
        return Delivery(attempted=True, delivered=False)


EXIT_BY_OUTCOME = {
    OUTCOME_OK: EXIT_OK,
    OUTCOME_APPROACHING: EXIT_OK,
    OUTCOME_REVIEW_DUE: EXIT_FINDING,
    OUTCOME_UNMAINTAINED: EXIT_FINDING,
    OUTCOME_ANOMALY: EXIT_FINDING,
    OUTCOME_CANNOT_VERIFY: EXIT_CANNOT_VERIFY,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Alert when Bali Zero's own price sheet is past its review interval."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the verdict, never send Telegram.")
    parser.add_argument("--now", default=None, help="ISO-8601 date override — TEST-ONLY, never for cron.")
    parser.add_argument("--interval-days", type=int, default=PRICE_REVIEW_INTERVAL_DAYS)
    parser.add_argument("--warn-days", type=int, default=DEFAULT_WARN_DAYS)
    parser.add_argument("--json", action="store_true", help="Emit the verdict as JSON.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[price-review-sentinel] %(message)s",
    )

    if args.now:
        today = parse_date(args.now)
        if today is None:
            parser.error(f"--now: unparseable ISO-8601 date: {args.now!r}")
    else:
        today = dt.datetime.now(dt.timezone.utc).date()

    try:
        sheet_path = resolve_price_sheet()
    except Exception as exc:  # noqa: BLE001
        verdict = Verdict(
            outcome=OUTCOME_CANNOT_VERIFY,
            reason=f"could not resolve the price sheet the service loads: {exc}",
        )
    else:
        try:
            sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            verdict = Verdict(
                outcome=OUTCOME_CANNOT_VERIFY,
                reason=f"could not read {sheet_path}: {exc}",
                sheet_path=str(sheet_path),
            )
        else:
            # Anything unexpected in here must land on CANNOT_VERIFY, never on
            # an uncaught exception. Python exits 1 on a traceback, the wrapper
            # reads rc=1 as "finding delivered", and the organism would then see
            # a healthy organ that reported a finding it never computed. Found
            # by the kimi-code/k3 council seat on a malformed `metadata`, and
            # the laundering is general: this catch closes the class, the
            # isinstance guard in classify() closes that particular instance.
            try:
                verdict = classify(
                    sheet,
                    today=today,
                    git_date=git_last_change(sheet_path),
                    worktree_dirty=git_worktree_dirty(sheet_path),
                    sheet_path=sheet_path,
                    interval_days=args.interval_days,
                    warn_days=args.warn_days,
                )
            except Exception as exc:  # noqa: BLE001 — see above: never exit 1 on a crash
                logger.exception("classification crashed")
                verdict = Verdict(
                    outcome=OUTCOME_CANNOT_VERIFY,
                    reason=f"classification crashed on {sheet_path}: "
                           f"{type(exc).__name__}: {exc}",
                    sheet_path=str(sheet_path),
                )

    if args.json:
        print(json.dumps(verdict.to_dict(), indent=2))
    else:
        print(format_alert_text(verdict))

    delivery = Delivery(attempted=False)
    if not args.dry_run:
        delivery = send_alert(verdict)

    rc = EXIT_BY_OUTCOME.get(verdict.outcome, EXIT_CANNOT_VERIFY)
    if delivery.attempted and not delivery.delivered:
        rc = EXIT_UNDELIVERED

    # One machine-readable last line so the wrapper can put the CONDITION in
    # the organism sidecar, not merely "a finding happened". A sheet overdue
    # for four months must not look identical to a clean run in the heartbeat
    # (codex-gpt-5.6-sol).
    print(
        f"SENTINEL-STATE outcome={verdict.outcome} "
        f"delivery={delivery.label} rc={rc}"
    )
    return rc


if __name__ == "__main__":
    # Last line of defence for the same laundering: rc=1 must mean "a finding
    # was computed and delivered", never "the process died". Anything that
    # escapes main() exits 2 (CANNOT_VERIFY), which the wrapper reads as an
    # organ malfunction — the truthful reading.
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 — a crash must not be readable as a finding
        logging.getLogger("price-review-sentinel").exception("sentinel crashed")
        sys.exit(EXIT_CANNOT_VERIFY)
