#!/usr/bin/env python3
"""Small testable checks used by infra/healer/healer-run.sh."""

from __future__ import annotations

import json
import sys
from typing import Any

RATE_OR_QUOTA_MARKERS: tuple[str, ...] = (
    "hit your weekly limit",
    "hit your usage limit",
    "usage limit",
    "weekly limit",
    "rate limit",
    "rate.limit",
    "out of extra usage",
    "quota exceeded",
    "quota_exceeded",
    "resource_exhausted",
    "429",
    "exhausted",
)

AUTH_REQUIRED_MARKERS: tuple[str, ...] = (
    "auth required",
    "authentication required",
    "login required",
    "not logged in",
    "oauth",
    "token_revoked",
    "refresh_token",
    "unauthorized",
    "401",
)


def count_diverged_probes(raw_json: str) -> int:
    """Count DIVERGED proprioception probes across current and legacy schemas."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return 0

    probes = data.get("probes")
    if not isinstance(probes, list):
        return 0

    count = 0
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        status = str(probe.get("status") or probe.get("verdict") or "").upper()
        if status == "DIVERGED":
            count += 1
    return count


def classify_session_tail(text: str) -> str:
    """Classify known operator-gated CLI failures; generic errors stay generic."""
    lowered = text.lower()
    if any(marker in lowered for marker in RATE_OR_QUOTA_MARKERS):
        return "rate_or_quota_limit"
    if any(marker in lowered for marker in AUTH_REQUIRED_MARKERS):
        return "auth_required"
    return "session_error"


def _read_stdin() -> str:
    return sys.stdin.read()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: healer_run_checks.py <count-diverged|classify-session-tail>\n")
        return 2

    command = argv[1]
    payload = _read_stdin()
    if command == "count-diverged":
        sys.stdout.write(f"{count_diverged_probes(payload)}\n")
        return 0
    if command == "classify-session-tail":
        sys.stdout.write(f"{classify_session_tail(payload)}\n")
        return 0

    sys.stderr.write(f"unknown command: {command}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
