#!/usr/bin/env python3
"""lint_plist_daemon_cron_xor.py — Linux port of the catB LaunchAgent
daemon|cron XOR + W67 crash-loop guard.

WHY THIS EXISTS (Day-1 CI honesty pass, 2026-07-20): the original
`.github/workflows/catB-daemon-cron-xor.yml` job ran on `macos-latest` and
shelled out to `/usr/libexec/PlistBuddy` (a genuinely macOS-only binary) to
read three keys — `KeepAlive`, `StartInterval`, `StartCalendarInterval` —
out of each committed `.plist`. macOS runners are ~10x the ubuntu-latest
minute-cost on GitHub-hosted infra and slower to schedule, for a job that is
pure data extraction from an Apple plist (binary or XML) — a format Python's
stdlib `plistlib` module parses natively, with zero macOS dependency. This
script replicates the PlistBuddy-based classification EXACTLY (same
ambiguous/W67 semantics, same messages) so the GitHub Actions job/step names
and behavior stay identical, just on `ubuntu-latest`.

CLASSIFICATION (verbatim from the shell version this replaces):
  - "ambiguous" = the plist has a `KeepAlive` key (ANY form — bool or dict)
    AND a schedule key (`StartInterval` or `StartCalendarInterval`).
    Structurally ambiguous: daemon-vs-cron cannot be told apart from the
    plist alone. Informational only — never fails the build.
  - "W67 crash-loop class" = `KeepAlive` is the BARE boolean `true` (not a
    dict like `{SuccessfulExit: false}`, which is a legitimate crash-restart
    daemon) AND a schedule key is present. This is the exact W67 signature
    (2026-06-07): a cron job wearing a daemon's unconditional-restart flag —
    launchd SIGTERM-kills the spawned children every restart tick. HARD-FAILS
    the build (exit 1) if any committed plist matches.

PlistBuddy `Print :Key` semantics this script reproduces: a key that exists
(any type, any value) makes the check "present" (`-n "$ka"` in the original
shell); a key that doesn't exist maps to PlistBuddy printing nothing to
stdout (swallowed via `2>/dev/null`) — i.e. "not present". `plistlib`'s
`"KeepAlive" in data` / `"StartInterval" in data` mirrors this exactly:
presence, not truthiness (a `<false/>` KeepAlive still counts as
"KeepAlive present" for ambiguity purposes, same as PlistBuddy printing the
literal string "false").
"""

from __future__ import annotations

import glob
import os
import plistlib
import sys

PLIST_GLOBS = ["infra/launchagents/*.plist", "infra/launchd/*.plist"]


def classify(paths: list[str]) -> tuple[int, int, int, list[str], list[str], list[str]]:
    """Returns (total, ambiguous, w67, ambig_list, w67_list, parse_warnings)."""
    total = 0
    ambiguous = 0
    w67 = 0
    ambig_list: list[str] = []
    w67_list: list[str] = []
    parse_warnings: list[str] = []

    for f in paths:
        total += 1
        try:
            with open(f, "rb") as fh:
                data = plistlib.load(fh)
        except Exception as exc:  # noqa: BLE001 — best-effort, never crash the lint
            parse_warnings.append(f"{f}: {exc}")
            continue

        if not isinstance(data, dict):
            parse_warnings.append(f"{f}: top-level plist is not a dict ({type(data).__name__})")
            continue

        has_ka = "KeepAlive" in data
        has_sched = ("StartInterval" in data) or ("StartCalendarInterval" in data)

        # Ambiguous = KeepAlive (any form) AND a schedule present.
        if has_ka and has_sched:
            ambiguous += 1
            ambig_list.append(os.path.basename(f))

        # W67 crash-loop class = BARE boolean KeepAlive=true AND a schedule.
        # (A cron job wearing a daemon's unconditional-restart flag: launchd
        #  will SIGTERM-kill its spawned children every restart tick.)
        if data.get("KeepAlive") is True and has_sched:
            w67 += 1
            w67_list.append(os.path.basename(f))

    return total, ambiguous, w67, ambig_list, w67_list, parse_warnings


def main() -> int:
    paths = sorted(
        p for pattern in PLIST_GLOBS for p in glob.glob(pattern) if os.path.isfile(p)
    )
    total, ambiguous, w67, ambig_list, w67_list, parse_warnings = classify(paths)

    for warning in parse_warnings:
        print(f"::warning title=plist parse error::{warning}")

    print(f"committed plist        : {total}")
    print(f"ambiguous (KA+schedule): {ambiguous}")
    print(f"W67 crash-loop class   : {w67}")
    if ambig_list:
        print(f"::notice title=daemon|cron ambiguous (informational)::{' '.join(ambig_list)}")

    if w67 != 0:
        offenders = " ".join(w67_list)
        print(
            "::error title=W67 crash-loop regression::These committed plist have bare "
            "KeepAlive=true AND a schedule — the exact W67 SIGTERM-every-restart "
            "signature. Make it a true daemon (KeepAlive only, no schedule) OR a true "
            f"cron (schedule only, no KeepAlive). Offenders: {offenders}"
        )
        return 1

    print(
        "OK: zero W67 crash-loop-class committed plist (KeepAlive=true + schedule). "
        "Ambiguous backlog is informational and lives mostly in the live home — sweep "
        "on the Pro."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
