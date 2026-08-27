#!/usr/bin/env python3
"""wa_codex_seat_sentinel.py — S3 seat-death sentinel (Piece B), reader half
of the seat sentinel pair for the wa-codex broker's OpenAI/Codex leg.

Runs as `nuzantara` via cron-runner.sh — a DIFFERENT user from the probe
(Piece A, scripts/wa_codex_seat_probe.py, runs as the login-less
zantara-codex whose home is unreadable cross-user). This organ reads TWO
independent sources and never trusts either one alone:

1. The probe's status file — the ONLY channel that crosses the user
   boundary from zantara-codex's sandbox. A `verdict=auth_death` here is a
   direct, job-traffic-independent signal: the probe checks even when the
   lane is flag-OFF and zero jobs flow.
2. The prod `wa_broker_gauge` row (server-side, via `scripts/pg.sh`) — the
   admission/liveness gauge every `/claim` poll upserts. Catches the case
   the probe cannot see at all: the daemon itself silently stopped polling
   (crash, version-pin pause, host down) even though its OWN auth is fine.

Neither source alone is sufficient (scar family #2, "esiste ≠ armato"): a
probe that never ran again would sit at a stale timestamp forever unless
something ELSE notices the silence, and a gauge read alone cannot name
"auth" as the cause — the daemon logs that, in a file this user cannot
read. Two guardians, two blind spots each; together they cover the pair.

W104 discipline (`redis-cli` exits 0 with `NOAUTH` on stdout — the twin
lesson generalizes to any CLI): the gauge query is JUDGED BY ITS OUTPUT, not
its exit code alone — empty stdout or a shape that does not parse into
exactly 4 fields is CANNOT-VERIFY, never read as "clean".

EXIT: 0 = both sources were read (verdicts, if any, travel via Telegram
alert — same convention as wa_session_liveness.py, not via exit code). 2 =
the gauge could not be read/parsed at all — CANNOT-VERIFY, never a silent 0
(the cron-runner.sh receipt alarm, the W107 cure, picks up non-zero exits).
A probe file that is simply MISSING is deliberately NOT a CANNOT-VERIFY
here: it is itself a RED verdict ("probe silent") — an unarmed probe is a
finding this organ can and must name, not a reason to give up looking at
the gauge.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional, Sequence

logger = logging.getLogger("wa_codex_seat_sentinel")

REPO: Final[Path] = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.tg_gateway_verdict import extract_gateway_verdict  # noqa: E402

# S1.5 addendum (2026-08-26, team-lead review of PR #5028): the WRITE side
# (scripts/wa_codex_seat_probe.py) emits `verdict` via named `Final[str]`
# constants; this reader used to compare against bare string literals
# (`"auth_death"`, `"quota_exhausted"`, `"ok"`) instead of importing those
# same constants — the identical protocol-drift shape as the private-symbol
# import that started this whole PR, one layer up (a rename on the write
# side would silently stop matching here, degrading a RED seat-death alarm
# to a WARN "other_failure" with zero visible signal that anything broke).
# Importing the probe module is safe at IMPORT time — the user-boundary
# concern in the probe's own docstring is about RUNTIME execution
# (`codex login status` runs as zantara-codex), not about reading its
# Final[str] constants, which are plain module attributes with no I/O.
#
# Note 2 (team-lead review of PR #5028, 2026-08-26): this import reads
# the REPO CHECKOUT's copy of wa_codex_seat_probe.py — but the thing that
# ACTUALLY WRITES `verdict` into seat-status.json at runtime is the
# DEPLOYED copy at /usr/local/lib/wa-codex-broker/seat_probe.py, a
# different path under a different user (zantara-codex). This import
# being SAFE — i.e. these constants matching whatever string the deployed
# probe actually emits — depends on those two copies not drifting. That
# dependency is not an accident: `scripts/wa_codex_seat_probe.py` <->
# `/usr/local/lib/wa-codex-broker/seat_probe.py` IS a declared pair in
# infra/home-fork/declared-pairs.json (verified: repo="scripts/
# wa_codex_seat_probe.py", live="/usr/local/lib/wa-codex-broker/
# seat_probe.py"), so `lint_home_fork.py` DOES watch this specific pair
# for drift. If that declaration is ever removed, this import stops being
# safe by construction and starts being safe only by accident.
from scripts.wa_codex_seat_probe import (  # noqa: E402
    VERDICT_AUTH_DEATH,
    VERDICT_OK,
    VERDICT_QUOTA_EXHAUSTED,
)

_ENV_STATUS_FILE: Final[str] = "WA_CODEX_SEAT_STATUS_FILE"
_DEFAULT_STATUS_FILE: Final[str] = "/usr/local/var/wa-codex-broker/seat-status.json"
_ENV_PROBE_INTERVAL_S: Final[str] = "WA_CODEX_PROBE_INTERVAL_S"
DEFAULT_PROBE_INTERVAL_S: Final[float] = 21600.0  # 6h — matches the probe plist's StartInterval.

_GAUGE_STALENESS_LIMIT_S: Final[float] = 600.0
_BREAKER_FAILURE_LIMIT: Final[int] = 3
_GAUGE_QUERY_TIMEOUT_S: Final[int] = 30

RED: Final[str] = "RED"
WARN: Final[str] = "WARN"

EXIT_OK: Final[int] = 0
EXIT_CANNOT_VERIFY: Final[int] = 2

AUTH_DEATH_MSG: Final[str] = (
    "codex seat AUTH DEAD — operator: sudo -u zantara-codex "
    "CODEX_HOME=/Users/zantara-codex/.codex HOME=/Users/zantara-codex "
    "/opt/homebrew/bin/codex login"
)
PROBE_SILENT_MSG: Final[str] = "seat probe silent (not armed, or its daemon died)"
BREAKER_MSG: Final[str] = (
    "codex leg failing — cause is named only in the daemon log: "
    "sudo grep 'AUTH DEATH' /Users/zantara-codex/logs/wa-codex-broker.err"
)
DAEMON_SILENT_MSG: Final[str] = "daemon silent (dead / version-pin pause / host down)"
# S1.5 (2026-08-26), owner packet item 13 — twin of AUTH_DEATH_MSG for the
# probe's `quota_exhausted` verdict (scripts/wa_codex_seat_probe.py). The
# remedy differs (wait, or switch seats — never "re-login"), which is
# exactly why this is its own message and its own dedup condition rather
# than reusing AUTH_DEATH_MSG's wording or BREAKER_MSG's sudo-grep hint (the
# daemon's own AUTH DEATH/QUOTA EXHAUSTED log lines live in the same
# cron-unreadable file — see wa_codex_daemon.py's B2b arm — so this message
# does not point there either; the probe's own status file already carries
# the actionable verdict without needing that file read).
QUOTA_EXHAUSTED_MSG: Final[str] = (
    "codex seat QUOTA EXHAUSTED — wait for the usage window to reset, or "
    "switch seats (this is not an auth failure — do not re-login)"
)


@dataclass(frozen=True)
class Verdict:
    level: str  # RED | WARN
    condition: str  # stable per-condition dedup component (never the measurement)
    message: str


# ---------------------------------------------------------------------------
# Pure logic — no I/O, this is where the tests live.
# ---------------------------------------------------------------------------


def _probe_side(
    probe_status: Optional[dict],
    probe_age_s: Optional[float],
    probe_interval_s: float,
) -> list[Verdict]:
    """Verdicts from the probe status file ALONE — split out so `run()` can
    still emit an in-hand `auth_death` when the gauge is unreadable (Kimi r1
    M1: the CANNOT-VERIFY path must never swallow a verdict already in
    hand — the operator would be paged 'could not read gauge' while the
    actionable re-login command sits in the status file unread)."""
    verdicts: list[Verdict] = []
    stale = probe_age_s is None or probe_age_s >= 2 * probe_interval_s
    if probe_status is None or stale:
        verdicts.append(Verdict(RED, "probe_silent", PROBE_SILENT_MSG))
    else:
        probe_verdict = probe_status.get("verdict")
        if probe_verdict == VERDICT_AUTH_DEATH:
            verdicts.append(Verdict(RED, VERDICT_AUTH_DEATH, AUTH_DEATH_MSG))
        elif probe_verdict == VERDICT_QUOTA_EXHAUSTED:
            # S1.5 (2026-08-26): distinct from auth_death (fix = re-login)
            # and from the generic other_failure bucket below (fix = wait /
            # switch seats) — twin, on the read side, of the daemon's own
            # CodexExecQuotaError arm (wa_codex_daemon.py B2b). RED, same
            # severity as auth_death: either way the OpenAI/Codex leg is
            # fully blocked for every subsequent job, even though the
            # remedy differs.
            verdicts.append(Verdict(RED, VERDICT_QUOTA_EXHAUSTED, QUOTA_EXHAUSTED_MSG))
        elif probe_verdict != VERDICT_OK:
            # other_failure, probe_error, AND any vocabulary this reader does
            # not know yet (e.g. a future probe adding a POLICY_BLOCKED
            # verdict) must fall somewhere VISIBLE, never into silence —
            # W116: an unmapped finale that lands in the healthy bucket is
            # how the next real signal gets lost. "quota_exhausted" used to
            # be the example named here; it graduated to its own branch
            # above (S1.5) and no longer reaches this one.
            verdicts.append(
                Verdict(
                    WARN,
                    "other_failure",
                    "seat probe reports {0} (rc login={1} rc exec={2})".format(
                        probe_verdict,
                        probe_status.get("login_status_rc"),
                        probe_status.get("exec_rc"),
                    ),
                )
            )
        # probe_verdict == VERDICT_OK ("ok"): the only value that produces
        # no verdict.
    return verdicts


def _gauge_side(gauge_row: tuple[str, str, int, float]) -> list[Verdict]:
    # The gauge row is single-row by CHECK (id = 1); the query pins WHERE
    # id = 1 anyway, like every other reader (Kimi r1 m10).
    _last_seen_raw, breaker_state, consecutive_failures, staleness_s = gauge_row
    verdicts: list[Verdict] = []
    if breaker_state != "closed" or consecutive_failures >= _BREAKER_FAILURE_LIMIT:
        verdicts.append(Verdict(RED, "breaker_open", BREAKER_MSG))
    if staleness_s > _GAUGE_STALENESS_LIMIT_S:
        verdicts.append(Verdict(RED, "daemon_silent", DAEMON_SILENT_MSG))
    return verdicts


def evaluate(
    probe_status: Optional[dict],
    probe_age_s: Optional[float],
    gauge_row: Optional[tuple[str, str, int, float]],
    now: datetime,
    probe_interval_s: float = DEFAULT_PROBE_INTERVAL_S,
) -> list[Verdict]:
    """Pure classification over both sources. `now` is a parameter, not
    `datetime.now()` read internally, so a test controls freshness exactly.

    `gauge_row=None` is REFUSED, not silently absorbed into an empty verdict
    list: a gauge the caller could not read is a CANNOT-VERIFY case that
    must be handled BEFORE this function runs (see `run()`) — an unread
    gauge is not the same fact as "the gauge says everything is fine", and
    this function must never let the two collapse into the same empty
    return value (that would read as a clean pass on a source we never
    looked at).
    """
    if gauge_row is None:
        raise ValueError(
            "evaluate() requires an already-resolved gauge_row — a gauge "
            "that could not be read/parsed is CANNOT-VERIFY and must be "
            "handled by the caller before this function runs, never "
            "silently folded into an empty (= healthy-looking) verdict list."
        )
    return _probe_side(probe_status, probe_age_s, probe_interval_s) + _gauge_side(gauge_row)


# ---------------------------------------------------------------------------
# I/O — readers. Each ALWAYS returns a value (never raises on the ordinary
# "not there"/"unreadable" cases); `run()` decides what that means.
# ---------------------------------------------------------------------------


def _status_file_path() -> Path:
    return Path(os.environ.get(_ENV_STATUS_FILE, _DEFAULT_STATUS_FILE))


def _probe_interval_s() -> float:
    try:
        return float(os.environ.get(_ENV_PROBE_INTERVAL_S, DEFAULT_PROBE_INTERVAL_S))
    except ValueError:
        return DEFAULT_PROBE_INTERVAL_S


def _read_probe_status() -> tuple[Optional[dict], Optional[float]]:
    """(status_dict, age_seconds) — (None, None) for BOTH "file missing" and
    "file present but unreadable/corrupt/malformed": `evaluate()` treats
    both identically as "probe silent", since neither lets us trust a
    verdict inside it."""
    path = _status_file_path()
    try:
        raw = path.read_text()
    except OSError:
        return None, None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("probe status file is not valid JSON: %s", path)
        return None, None
    checked_at_raw = data.get("checked_at")
    if not isinstance(checked_at_raw, str):
        logger.warning("probe status file missing/malformed checked_at: %s", path)
        return None, None
    try:
        checked_at = datetime.strptime(checked_at_raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        logger.warning("probe status checked_at unparseable: %r", checked_at_raw)
        return None, None
    age_s = (datetime.now(timezone.utc) - checked_at).total_seconds()
    return data, age_s


def _read_gauge() -> Optional[tuple[str, str, int, float]]:
    """Runs the gauge query via scripts/pg.sh and JUDGES THE OUTPUT (W104):
    empty stdout, or a shape that does not split into exactly 4 fields, or
    a field that does not convert — all return None (CANNOT-VERIFY), never
    a guessed/default row."""
    pg_sh = REPO / "scripts" / "pg.sh"
    query = (
        "SELECT broker_last_seen_at, breaker_state, consecutive_failures, "
        "EXTRACT(EPOCH FROM (now() - broker_last_seen_at)) FROM wa_broker_gauge "
        "WHERE id = 1"
    )
    try:
        proc = subprocess.run(
            ["bash", str(pg_sh), "-A", "-t", "-c", query],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=_GAUGE_QUERY_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("gauge query failed to run: %s", type(exc).__name__)
        return None

    line = next((ln for ln in reversed(proc.stdout.splitlines()) if ln.strip()), "")
    if not line:
        logger.warning(
            "gauge query returned no output (rc=%s): %s",
            proc.returncode,
            (proc.stderr or "").strip()[:200],
        )
        return None

    fields = [f.strip() for f in line.split("|")]
    if len(fields) != 4:
        logger.warning("gauge query output unparseable (expected 4 fields, got %d): %r", len(fields), line)
        return None

    _last_seen_raw, breaker_state, consecutive_failures_raw, staleness_raw = fields
    if not breaker_state:
        logger.warning("gauge query returned an empty breaker_state: %r", line)
        return None
    try:
        consecutive_failures = int(consecutive_failures_raw)
        # broker_last_seen_at is NULL until the daemon's FIRST poll ever —
        # psql -A -t renders NULL as an empty field. That is not an
        # unparseable row (CANNOT-VERIFY); it is the honest fact "the daemon
        # has never been seen", i.e. infinite staleness → daemon_silent RED.
        staleness_s = float("inf") if staleness_raw == "" else float(staleness_raw)
    except ValueError:
        logger.warning("gauge query numeric fields unparseable: %r", line)
        return None

    return (_last_seen_raw, breaker_state, consecutive_failures, staleness_s)


def hostname() -> str:
    return socket.gethostname().split(".")[0]


# ---------------------------------------------------------------------------
# Alerting — same chain as wa_session_liveness.py::send_to_gateway.
# ---------------------------------------------------------------------------


def send_to_gateway(message: str, host: str, level: str, condition: str) -> bool:
    """alerter (dedup) -> tg_notify, same chain as every other sentinel in
    this tree. RED -> alerter level CRITICAL / gateway tier p0. WARN ->
    alerter level WARNING / gateway tier digest (alerter.send_alert's own
    tier mapping: CRITICAL/DEADMAN -> p0, WARNING/INFO -> digest)."""
    alerter_level = "CRITICAL" if level == RED else "WARNING"
    try:
        sys.path.insert(0, str(REPO / "scripts"))
        from sentinel_lib import alerter  # noqa: PLC0415

        return bool(alerter.send_alert(message, level=alerter_level, condition=condition))
    except Exception:  # noqa: BLE001 — fallback diretto al gateway
        gateway = REPO / "scripts" / "tg_notify.py"
        if not gateway.exists():
            return False
        tier = "p0" if level == RED else "digest"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dedup_key = f"wa-codex-seat-{condition}-{today}"
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(gateway),
                    "--tier",
                    tier,
                    "--source",
                    "wa-codex-seat-sentinel",
                    "--dedup-key",
                    dedup_key,
                    message,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as exc:  # noqa: BLE001 — notification failure is fail-closed
            print(f"tg_notify: ERRORE subprocess ({type(exc).__name__})", file=sys.stderr)
            return False
        verdict = extract_gateway_verdict(proc.stderr)
        print(f"tg_notify: {verdict or f'NESSUN verdetto rc={proc.returncode}'}", file=sys.stderr)
        # Kimi r2 #2: mirror the alerter's OWN responsibility bar (alerter.py:207
        # counts every canonical verdict — spooled/deduped/logged mean the gateway
        # durably owns the news), not the stricter gateway_delivered()=="sent".
        # With M4 giving False teeth (exit 2 -> receipt page), judging a spooled
        # RED as "failed" would manufacture a false CANNOT-VERIFY during a mere
        # rate-limit spool. A canonical verdict on rc 0 = responsibility taken.
        return proc.returncode == 0 and verdict is not None


def _emit_cannot_verify(host: str) -> bool:
    message = (
        f"wa-codex-seat-sentinel [{host}] — CANNOT-VERIFY: could not read/parse "
        "the wa_broker_gauge row (pg.sh query failed, returned no output, or an "
        "unparseable shape).\n\nNo verdict was reached: this is NOT a health verdict."
    )
    return send_to_gateway(message, host, RED, "gauge_cannot_verify")


def _emit(verdicts: Sequence[Verdict], host: str) -> bool:
    """Sends every verdict; returns False if any RED failed to deliver.
    A lost RED is fail-open on the exact path this organ exists for (Kimi
    r1 M4): the caller must then exit non-zero so the cron-runner receipt
    alarm — the W107 backup channel that fires only on non-zero exits —
    gets its chance. WARN deliveries are best-effort (digest tier)."""
    all_red_delivered = True
    for v in verdicts:
        sent = send_to_gateway(f"{v.level} wa-codex-seat [{host}]: {v.message}", host, v.level, v.condition)
        print(f"{v.level} {v.condition}: alert {'inviato' if sent else 'FALLITO'} — {v.message}")
        if not sent and v.level == RED:
            all_red_delivered = False
    return all_red_delivered


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    host = hostname()

    probe_status, probe_age_s = _read_probe_status()
    gauge_row = _read_gauge()

    if gauge_row is None:
        # In-hand probe verdicts still travel (Kimi r1 M1): a dead seat AND
        # an unreadable gauge tend to co-occur in a degraded moment, and the
        # actionable auth_death must not hide behind a generic CANNOT-VERIFY.
        _emit(_probe_side(probe_status, probe_age_s, _probe_interval_s()), host)
        _emit_cannot_verify(host)
        print(
            "wa-codex-seat-sentinel: CANNOT-VERIFY — could not read/parse the "
            "broker gauge; gauge-side verdicts not reached",
            file=sys.stderr,
        )
        return EXIT_CANNOT_VERIFY

    verdicts = evaluate(probe_status, probe_age_s, gauge_row, now, _probe_interval_s())

    if not verdicts:
        print(f"wa-codex-seat-sentinel [{host}]: all conditions healthy")
        return EXIT_OK

    all_red_delivered = _emit(verdicts, host)
    if not all_red_delivered:
        # Fail-open guard (Kimi r1 M4): a RED that could not be delivered —
        # gateway down, spool refused — must surface through the ONE channel
        # left, the cron-runner receipt alarm on non-zero exit.
        print(
            "wa-codex-seat-sentinel: RED alert delivery FAILED — exiting "
            "non-zero so the receipt alarm fires",
            file=sys.stderr,
        )
        return EXIT_CANNOT_VERIFY
    # Delivered verdicts travel via the Telegram alert above, not the exit
    # code — same convention as wa_session_liveness.py: the sentinel SAW the
    # problem and DELIVERED it, which is a successful run, not a failure.
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="wa_codex_seat_sentinel: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.parse_args(argv)
    return run()


if __name__ == "__main__":
    sys.exit(main())
