#!/usr/bin/env python3
"""launchd_liveness_detector.py — the vaccine for W84 "green-but-TCC-dead" launchd jobs.

opus-mythos TAC of superscar #2 "Esiste ≠ Armato" (2026-06-16). The TAC found a
NEW vector of the family, not yet catalogued: a LaunchAgent whose wrapper lives
under a macOS TCC-protected location (`~/Desktop/...`) dies *silently* the moment
the launchd context loses its Full-Disk-Access grant — with NO change to the code,
the plist, or the Unix permissions. The proxy lies in the worst possible way:

    LastExitStatus = 0          ← launchd records a GREEN exit
    log content    = "Operation not permitted" / "getcwd: ... Operation not permitted"
    last stdout    = a STALE line from an old *interactive* (manual) run

So `launchctl list` is green, `job_health.py` (which reads structured JSONL the dead
job never wrote) sees nothing, and the guardian-of-guardians (`verify-connectome`)
is itself one of the corpses — green and dead together. Cross-machine proof: the
identical plist on Pro returns a HONEST exit (1 = real finding), on M5 returns 0
while never executing. The exit code alone is structurally incapable of telling
the difference; only correlating it with the LOG CONTENT can.

THIS DETECTOR is the structural antidote for the family applied to the new vector:
it reads the real end-to-end SIGNAL (does the log say the worker actually ran?), not
the proxy (the exit code). It judges a job DEAD-GREEN when:
    LastExitStatus == 0  AND  the job's log tail contains a launch-failure marker.
And DEAD-NONZERO when LastExitStatus != 0 (honest failure, still needs attention).
A non-zero exit with NO failure marker (e.g. Pro's verify-connectome exit 1 = a real
finding) is reported as FAILING-HONESTLY, distinct from DEAD-GREEN — no cry-wolf.

It does NOT fix anything (the cure — granting launchd Full-Disk-Access — is operator-
only, a click in System Settings). It DETECTS and ALARMS, which is exactly what was
missing: there was zero detector for this vector before.

Usage:
    python3 scripts/launchd_liveness_detector.py            # table, exit 1 if any dead-green
    python3 scripts/launchd_liveness_detector.py --json     # JSON (for MCP / cron)
    python3 scripts/launchd_liveness_detector.py --alert     # Telegram on dead-green/dead-nonzero
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
LAUNCHAGENTS = HOME / "Library" / "LaunchAgents"

# Markers that prove the WORKER never actually executed (launch-time denial),
# regardless of the exit code launchd recorded. TCC/Full-Disk-Access denial is the
# 2026-06-16 vector; the others are sibling launch-failures worth the same alarm.
# NOTE: these must be SPECIFIC to a launch failure of the WORKER, not generic shell
# noise. "command not found" (bare) was removed — it matched `.zshenv` startup chatter
# (`gh: command not found`) and cried wolf on a job that wasn't actually launch-failing.
# We require the failure to reference a script path or the bash/exec launcher itself.
LAUNCH_FAILURE_MARKERS = (
    "operation not permitted",
    "getcwd: cannot access parent directories",
    "bad interpreter",
)
# A "<launcher>: <path>: <reason>" failure line (the bash/sh refusing to exec the
# wrapper). This is the high-signal shape — it names the worker that didn't run.
_LAUNCHER_FAILURE_RE = re.compile(
    r"\b(?:/bin/)?(?:ba|z|d)?sh:\s+\S*/\S+:\s+"
    r"(operation not permitted|no such file or directory|permission denied|cannot execute)",
    re.IGNORECASE,
)

# Only audit OUR jobs (avoid noise from Apple/homebrew agents).
# liveness-detector-arm-0717: `matagaruda` added — a live audit while wiring this
# detector to a cron found 3 named-ambiguous jobs (redis-split-brain.check,
# pipeline-health.hourly, kg-query-api) silently invisible to `audit()` because
# their label is `com.matagaruda.*`, which matched neither prior branch. Mata
# Garuda is part of the same organism (same repo, same infra/launchagents/ dir,
# same "ours" intent as the comment states) — the gap was an oversight, not a
# deliberate exclusion. Without this fix, arming a cron for this detector would
# leave 3/10 of the jobs it was just tasked to disambiguate permanently unmonitored.
OURS_RE = re.compile(r"\b(nuzantara|balizero|matagaruda)\b", re.IGNORECASE)

# A stdout "green" line older than this (seconds) while the job claims to run more
# often is itself suspicious (the stale-interactive-run smell). 3 days default.
STALE_GREEN_SEC = 3 * 24 * 3600

# TAC-2 A2 (2026-07-05): a failure marker only counts if the log that carries it
# was written RECENTLY. Without this gate, an err-log never appended again after
# a TCC re-grant keeps its old "Operation not permitted" tail forever and the
# detector holds a CURED organ hostage as DEAD-* (the "stale W84 marker" bug —
# proprioception kept an already-cured M5 job sick for days). A job that is
# STILL failing re-appends the marker on every attempt, so its log mtime stays
# fresh and the gate never hides a live failure.
MARKER_FRESH_SEC = int(os.environ.get("W84_MARKER_FRESH_SEC", str(48 * 3600)))

# Healer tick 2026-07-10: LastExitStatus is STICKY — launchd keeps reporting the
# PREVIOUS incarnation's exit code for as long as the CURRENT incarnation keeps
# running (a SIGTERM at sleep/wake, or a crash years ago, never clears itself).
# A job that died once and has been alive+quiet ever since was reported
# FAILING-HONESTLY forever, off evidence that predates its current run. Live
# proof: mlx-server (4d11h uptime, serving /v1/models), fly-pg-tunnel.local
# (16d uptime, port 15432 accepting connections) — both FAILING-HONESTLY,
# both demonstrably alive and serving. RECOVERED requires a stable uptime
# (see _classify) so a job that JUST restarted (could still be crash-looping)
# is never masked.
#
# Healer tick 2026-07-10 (same day, second pass): the FIRST version of this
# fix additionally required `stale_green` (log quiet for STALE_GREEN_SEC) on
# the theory that "log actively re-writing" meant "actively re-writing fresh
# ERRORS". False: stale_green only measures ANY log write, not a failure one.
# local-livekit-server (16d uptime, port 7880 answering 200) logs benign
# periodic "high cpu load" INFO lines every few hours — its log is NEVER
# stale, so it stayed FAILING-HONESTLY forever despite being provably healthy.
# The real "no active failure" signal already exists: `marker is None`, which
# _log_has_failure_marker gates on its OWN freshness window (MARKER_FRESH_SEC,
# 48h) and only matches known launch-failure signatures. By the time
# `_classify` reaches the RECOVERED branch, marker is already guaranteed None
# (the marker-present branches return earlier) — stale_green added no real
# protection beyond that, only false negatives for chatty-but-healthy jobs.
UPTIME_STABLE_SEC = int(os.environ.get("W84_UPTIME_STABLE_SEC", str(STALE_GREEN_SEC)))


def _decode_wait_status(raw: int) -> int:
    """Decode the raw POSIX wait() status word `launchctl list <label>` reports
    for LastExitStatus into the human-legible exit code `launchctl print` and
    `subprocess` use (positive = normal exit code, negative = killed by that
    signal number).

    `launchctl list` emits the UNSHIFTED wait-status (a plain `exit 1` shows up
    as 256, since normal-exit codes are packed into the high byte), while a
    signal death (e.g. SIGKILL) shows up unshifted in the low bits (9, not
    2304). Left raw, two jobs both "failing" can show wildly different
    `last_exit` numbers for no operator-visible reason — confusing in the
    ledger/Telegram output even though `_classify()`'s zero/non-zero checks
    are unaffected either way (verified live 2026-07-12: overlap-detector.sh's
    designed `exit 1` on a real finding showed as `last_exit: 256`).
    """
    try:
        return os.waitstatus_to_exitcode(raw)
    except ValueError:
        return raw


def _launchctl_status(label: str) -> dict | None:
    """Return the parsed `launchctl list <label>` dict, or None if not loaded."""
    try:
        out = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if out.returncode != 0:
        return None
    d: dict = {}
    for line in out.stdout.splitlines():
        m = re.search(r'"(\w+)"\s*=\s*(-?\d+)', line)
        if m:
            d[m.group(1)] = int(m.group(2))
    if "LastExitStatus" in d:
        d["LastExitStatus"] = _decode_wait_status(d["LastExitStatus"])
    return d


def _parse_plist(plist: Path) -> dict:
    """Parse a plist, robust to MALFORMED XML (a real finding on M5: a plist with an
    unescaped token that plistlib's expat rejects). Fall back to `launchctl print`,
    which reads launchd's IN-MEMORY copy — immune to on-disk malformation."""
    try:
        with open(plist, "rb") as fh:
            return plistlib.load(fh)
    except Exception:
        # Fallback: scrape the paths out of `launchctl print` (authoritative).
        return _plist_from_launchctl(plist.stem)


def _plist_from_launchctl(label: str) -> dict:
    try:
        out = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return {}
    if out.returncode != 0:
        return {}
    d: dict = {}
    # `launchctl print` emits `stdout path = /...` / `stderr path = /...` / `path = /...plist`
    for line in out.stdout.splitlines():
        s = line.strip()
        m = re.match(r"stdout path\s*=\s*(\S.*)$", s)
        if m:
            d["StandardOutPath"] = m.group(1).strip()
        m = re.match(r"stderr path\s*=\s*(\S.*)$", s)
        if m:
            d["StandardErrorPath"] = m.group(1).strip()
        m = re.match(r"program\s*=\s*(\S.*)$", s)
        if m and "Program" not in d:
            d["Program"] = m.group(1).strip()
        m = re.match(r"(?:argument|arg)\s*\d*\s*=\s*(\S.*)$", s)
        if m:
            d.setdefault("ProgramArguments", []).append(m.group(1).strip())
    return d


def _log_paths(plist: Path) -> list[Path]:
    """Extract StandardOutPath / StandardErrorPath (robust to malformed plist)."""
    data = _parse_plist(plist)
    paths = []
    for key in ("StandardOutPath", "StandardErrorPath"):
        v = data.get(key)
        if v:
            paths.append(Path(os.path.expanduser(v)))
    # de-dup (a plist may point both streams at the same file, e.g. verify-connectome)
    seen, uniq = set(), []
    for p in paths:
        if str(p) not in seen:
            seen.add(str(p))
            uniq.append(p)
    return uniq


def _program_path(plist: Path) -> str | None:
    data = _parse_plist(plist)
    if data.get("Program"):
        return data["Program"]
    args = data.get("ProgramArguments") or []
    # The program is ALWAYS the first element of ProgramArguments (argv[0]); flags
    # like `-i` are later args, never the program. (Bug fix: a heuristic that skipped
    # argv[0] when it didn't end in .sh/.py fell through to args[1] = a flag.)
    return args[0] if args else None


def _log_has_failure_marker(paths: list[Path], now: float | None = None) -> str | None:
    """Return the matched line if any log tail proves the WORKER failed to launch.

    Two-tier: the high-signal launcher-failure shape (`/bin/bash: /path: reason`)
    OR a specific TCC/exec marker. Generic shell noise (`gh: command not found` from
    .zshenv) is deliberately NOT matched — that was the cry-wolf bug. We do NOT bare-
    except: an unreadable log is reported as no-marker, but the read error itself is
    not swallowed into a misleading 'healthy' (the irony the TAC caught in v1).

    Freshness gate (TAC-2 A2): a log whose mtime is older than MARKER_FRESH_SEC is
    archaeology, not evidence — its marker is ignored so a cured job stops being
    reported dead once its failure stops re-occurring."""
    now = time.time() if now is None else now
    for p in paths:
        if not p.exists():
            continue
        try:
            if (now - p.stat().st_mtime) > MARKER_FRESH_SEC:
                continue
            tail = p.read_text(errors="replace").splitlines()[-25:]
        except OSError:
            continue
        for line in reversed(tail):
            if _LAUNCHER_FAILURE_RE.search(line):
                return line.strip()[:160]
            low = line.lower()
            if any(mk in low for mk in LAUNCH_FAILURE_MARKERS):
                return line.strip()[:160]
    return None


def _newest_log_mtime(paths: list[Path]) -> float | None:
    mt = None
    for p in paths:
        try:
            if p.exists():
                mt = max(mt or 0, p.stat().st_mtime)
        except Exception:
            continue
    return mt


def _parse_etime(raw: str) -> float | None:
    """Parse `ps -o etime=` output: `[[DD-]HH:]MM:SS`. Pure, no subprocess."""
    raw = raw.strip()
    if not raw:
        return None
    days = 0
    if "-" in raw:
        day_part, raw = raw.split("-", 1)
        try:
            days = int(day_part)
        except ValueError:
            return None
    bits = raw.split(":")
    try:
        nums = [int(b) for b in bits]
    except ValueError:
        return None
    if len(nums) == 3:
        h, m, s = nums
    elif len(nums) == 2:
        h, m, s = 0, nums[0], nums[1]
    elif len(nums) == 1:
        h, m, s = 0, 0, nums[0]
    else:
        return None
    return float(days * 86400 + h * 3600 + m * 60 + s)


def _process_uptime_seconds(pid: int) -> float | None:
    """Seconds `pid` has been continuously running, via `ps -o etime=`.
    None if the PID doesn't exist or the output can't be parsed."""
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "etime="],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if out.returncode != 0:
        return None
    return _parse_etime(out.stdout)


def _classify(
    *,
    status: dict | None,
    marker: str | None,
    prog_exists: bool,
    uptime_sec: float | None,
) -> str:
    """Pure classification — exit-code x log-content x process-uptime.

    RECOVERED fires when the process has been alive longer than
    UPTIME_STABLE_SEC with NO failure marker. Marker is already guaranteed
    None by the time we reach this branch (the marker-present branches above
    return first), and `_log_has_failure_marker` has its own freshness gate
    (MARKER_FRESH_SEC) — so "no marker" already means "no known launch-failure
    signature in the recent log", independent of how chatty the log is.
    Short uptime alone still blocks RECOVERED: a job that just restarted
    could still be crash-looping regardless of log content.
    """
    if status is None:
        return "NOT-LOADED"
    exit_code = status.get("LastExitStatus")
    pid = status.get("PID")
    if marker and exit_code == 0:
        return "DEAD-GREEN"          # the W84 vector: green lies
    if marker and exit_code not in (0, None):
        return "DEAD-NONZERO"        # honest non-zero + proven launch failure
    if exit_code not in (0, None):
        if (
            pid is not None
            and uptime_sec is not None
            and uptime_sec > UPTIME_STABLE_SEC
        ):
            return "RECOVERED"       # sticky exit code, provably alive since
        return "FAILING-HONESTLY"    # non-zero, no marker, no recovery proof
    if not prog_exists:
        return "ARMED-TO-NOTHING"    # plist points at a missing script
    return "OK"


def audit() -> list[dict]:
    findings: list[dict] = []
    if not LAUNCHAGENTS.exists():
        return findings
    now = time.time()
    for plist in sorted(LAUNCHAGENTS.glob("*.plist")):
        label = plist.stem
        if not OURS_RE.search(label):
            continue
        status = _launchctl_status(label)
        logs = _log_paths(plist)
        marker = _log_has_failure_marker(logs)
        prog = _program_path(plist)
        prog_exists = bool(prog and Path(os.path.expanduser(prog)).exists())
        newest = _newest_log_mtime(logs)
        stale_green = newest is not None and (now - newest) > STALE_GREEN_SEC
        pid = (status or {}).get("PID")
        uptime_sec = _process_uptime_seconds(pid) if pid is not None else None

        # Classification — the whole point: cross exit-code with log content
        # AND (2026-07-10) process uptime, so a sticky historical exit code
        # doesn't outlive the incarnation that produced it. See _classify.
        verdict = _classify(
            status=status, marker=marker, prog_exists=prog_exists,
            uptime_sec=uptime_sec,
        )

        findings.append({
            "label": label,
            "verdict": verdict,
            "last_exit": (status or {}).get("LastExitStatus"),
            "program": prog,
            "program_exists": prog_exists,
            "log_marker": marker,
            "stale_green": stale_green,
        })
    return findings


# Verdicts that warrant an alarm (the silent killers + the missing arms).
ALARM_VERDICTS = {"DEAD-GREEN", "DEAD-NONZERO", "ARMED-TO-NOTHING", "NOT-LOADED"}


def _send_telegram(text: str) -> bool:
    """Best-effort Telegram alert; never raises (and never logs the token)."""
    secrets = HOME / ".nuzantara-secrets.env"
    token = chat = None
    try:
        for line in secrets.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("TELEGRAM_OWNER_CHAT_ID="):
                chat = line.split("=", 1)[1].strip().strip('"')
    except Exception:
        return False
    if not (token and chat):
        return False
    import urllib.parse
    import urllib.request
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--alert", action="store_true")
    args = ap.parse_args()

    findings = audit()
    alarms = [f for f in findings if f["verdict"] in ALARM_VERDICTS]

    if args.json:
        print(json.dumps({"findings": findings, "alarms": len(alarms)}, indent=2))
    else:
        if not findings:
            print("launchd liveness: no nuzantara/balizero LaunchAgents found.")
        else:
            print(f"launchd liveness detector — {len(findings)} job(s), {len(alarms)} alarm(s):\n")
            for f in findings:
                flag = (
                    "🚨" if f["verdict"] in ALARM_VERDICTS
                    else "⚠️ " if f["verdict"] == "FAILING-HONESTLY"
                    else "♻️ " if f["verdict"] == "RECOVERED"
                    else "✓ "
                )
                print(f"  {flag} {f['verdict']:<17} {f['label']}  (exit={f['last_exit']})")
                if f["log_marker"]:
                    print(f"        ↳ log proves launch failure: {f['log_marker']}")
                if f["verdict"] == "ARMED-TO-NOTHING":
                    print(f"        ↳ program missing: {f['program']}")
            print("\nDEAD-GREEN = launchd exit 0 but the log proves the worker never ran")
            print("(the W84 TCC vector). Cure is OPERATOR-ONLY: grant the launchd context")
            print("Full Disk Access in System Settings, OR relocate the wrapper outside ~/Desktop.")

    if args.alert and alarms:
        lines = [f"🚨 launchd liveness ({len(alarms)} dead/suspended):"]
        for f in alarms:
            lines.append(f"• {f['verdict']}: {f['label']} (exit={f['last_exit']})")
        _send_telegram("\n".join(lines))

    return 1 if alarms else 0


if __name__ == "__main__":
    sys.exit(main())
