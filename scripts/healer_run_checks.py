#!/usr/bin/env python3
"""Small testable checks used by infra/healer/healer-run.sh."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
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


class ProbeReportError(ValueError):
    """The proprioception report cannot be checked."""


CURE_VALUES = {"session", "owner", "pr"}
STRICT_ARSENAL_STATES = {"AUTH_DEAD", "BALANCE_DEAD", "MODEL_ERR", "UNKNOWN_ERR"}
_HOME_FORK_LIVE_RE = (
    re.compile(r"^DIVERGED: (.+?) != "),
    re.compile(r"^NO-REPO-TWIN: (.+?) executes live "),
)



def _probes(raw_json: str, *, strict: bool = False) -> list[dict[str, Any]]:
    """Load a non-empty proprioception probe list or reject the report."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ProbeReportError(f"malformed JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ProbeReportError("probe report must be a dict")
    probes = data.get("probes")
    if not isinstance(probes, list):
        raise ProbeReportError("probes must be a list")
    if not probes:
        raise ProbeReportError("probes must not be empty")
    if strict and not all(isinstance(probe, dict) for probe in probes):
        raise ProbeReportError("probes must all be objects")
    return [probe for probe in probes if isinstance(probe, dict)]


def count_diverged_probes(raw_json: str) -> int:
    """Count DIVERGED proprioception probes across current and legacy schemas."""
    count = 0
    for probe in _probes(raw_json):
        status = str(probe.get("status") or probe.get("verdict") or "").upper()
        if status == "DIVERGED":
            count += 1
    return count


def summarize_proprioception(raw_json: str) -> tuple[list[str], list[str]]:
    """Return (all diverged ids, P0/P1 session-curable ids)."""
    diverged: list[str] = []
    curable: list[str] = []
    for probe in _probes(raw_json, strict=True):
        status = str(probe.get("status") or probe.get("verdict") or "").upper()
        if status != "DIVERGED":
            continue
        probe_id = str(probe.get("id") or "(unknown)")
        cure = probe.get("cure", "session")
        if not isinstance(cure, str) or cure not in CURE_VALUES:  # exact: "Owner" is a foreign writer, not a quiet skip
            raise ProbeReportError(f"probe {probe_id}: invalid cure {cure!r}")
        severity = str(probe.get("severity") or "P1").upper()  # legacy reports were P1
        if len(severity) < 2 or severity[0] != "P" or not severity[1:].isdigit():
            raise ProbeReportError(f"probe {probe_id}: invalid severity {severity!r}")
        diverged.append(probe_id)
        if cure == "session" and int(severity[1:]) <= 1:
            curable.append(probe_id)
    return diverged, curable


def summarize_registry(raw_json: str) -> tuple[list[str], list[str]]:
    """Return (all dead ids, session-curable dead ids), rejecting foreign cures."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ProbeReportError(f"malformed registry JSON: {exc}") from exc
    dead = data.get("dead") if isinstance(data, dict) else None
    if not isinstance(dead, list) or not all(isinstance(item, dict) for item in dead):
        raise ProbeReportError("registry report must contain a dead object list")
    ids: list[str] = []
    curable: list[str] = []
    for item in dead:
        organ_id = str(item.get("id") or "(unknown)")
        cure = item.get("cure", "session")
        if not isinstance(cure, str) or cure not in {"session", "owner"}:
            raise ProbeReportError(f"dead organ {organ_id}: invalid cure {cure!r}")
        ids.append(organ_id)
        if cure == "session":
            curable.append(organ_id)
    return ids, curable


def summarize_home_fork(raw_json: str) -> tuple[list[str], list[str]]:
    """Return (all drifted live paths, paths writable by this healer session)."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ProbeReportError(f"malformed HOME-fork JSON: {exc}") from exc
    breaches = data.get("check_breaches") if isinstance(data, dict) else None
    if not isinstance(breaches, list) or not all(isinstance(item, str) for item in breaches):
        raise ProbeReportError("HOME-fork report must contain a check_breaches string list")
    paths: list[str] = []
    curable: list[str] = []
    for breach in breaches:
        match = next((rx.match(breach) for rx in _HOME_FORK_LIVE_RE if rx.match(breach)), None)
        if match is None:
            # No live path to judge (e.g. "DIVERGED: <repo> is absent from this
            # checkout"): unprovable owner cure, so it stays session-curable.
            paths.append(breach[:80])
            curable.append(breach[:80])
            continue
        path = Path(os.path.expanduser(match.group(1)))
        paths.append(str(path))
        try:
            owner_only = path.stat().st_uid == 0 or not os.access(path, os.W_OK)
        except OSError:
            owner_only = False  # fail open: an unprovable owner cure stays session-curable
        if not owner_only:
            curable.append(str(path))
    return paths, curable


def _report_time(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ProbeReportError("arsenal report has no timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProbeReportError(f"invalid arsenal report timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ProbeReportError("arsenal report timestamp must include a timezone")
    return parsed


def _load_last_acted(state_path: Path) -> dict[tuple[str, str], str]:
    """A corrupt state reads as never-acted, loudly: one repeat alert beats a mute receptor."""
    if not state_path.exists():
        return {}
    try:
        items = json.loads(state_path.read_text(encoding="utf-8"))["last_acted"]
        if not isinstance(items, list):
            raise TypeError("last_acted is not a list")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        sys.stderr.write(f"arsenal state unreadable ({type(exc).__name__}), treated as never acted\n")
        return {}
    acted: dict[tuple[str, str], str] = {}
    for item in items:
        try:
            _report_time(item["report_ts"])
            acted[(str(item["seat"]), str(item["state"]))] = item["report_ts"]
        except (TypeError, KeyError, ProbeReportError):
            sys.stderr.write("arsenal state entry unreadable, treated as never acted\n")
    return acted


def gate_arsenal_transitions(raw_json: str, state_path: Path) -> tuple[list[str], list[str], str]:
    """Deduplicate strict seat transitions by their report's own timestamp."""
    try:
        report = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ProbeReportError(f"malformed arsenal JSON: {exc}") from exc
    if not isinstance(report, dict) or not isinstance(report.get("transitions"), list):
        raise ProbeReportError("arsenal report must contain a transitions list")
    report_ts = report.get("ts")
    current_time = _report_time(report_ts)
    acted = _load_last_acted(state_path)

    new: list[str] = []
    skipped: list[str] = []
    for transition in report["transitions"]:
        if not isinstance(transition, dict):
            raise ProbeReportError("arsenal transitions must all be objects")
        seat = str(transition.get("seat") or "")
        status = str(transition.get("to") or "")
        if not seat or status not in STRICT_ARSENAL_STATES:
            continue
        key = (seat, status)
        previous = acted.get(key)
        label = f"{seat}:{status}"
        if previous is not None and current_time <= _report_time(previous):
            skipped.append(label)
            continue
        new.append(label)
        acted[key] = str(report_ts)

    if new:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": 1,
            "last_acted": [
                {"seat": seat, "state": status, "report_ts": ts}
                for (seat, status), ts in sorted(acted.items())
            ],
        }
        tmp = state_path.with_suffix(state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        tmp.replace(state_path)
    return new, skipped, str(report_ts)


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
    if len(argv) < 2:
        sys.stderr.write("usage: healer_run_checks.py <command>\n")
        return 2

    command = argv[1]
    payload = _read_stdin()
    if command == "count-diverged":
        try:
            count = count_diverged_probes(payload)
        except ProbeReportError as exc:
            sys.stderr.write(f"{exc}\n")
            return 3
        sys.stdout.write(f"{count}\n")
        return 0
    if command == "proprioception-summary" and len(argv) == 2:
        try:
            diverged, curable = summarize_proprioception(payload)
        except ProbeReportError as exc:
            sys.stderr.write(f"{exc}\n")
            return 3
        sys.stdout.write(f"{len(diverged)}\n{len(curable)}\n{','.join(diverged)}\n")
        return 0
    if command == "registry-summary" and len(argv) == 2:
        try:
            dead, curable = summarize_registry(payload)
        except ProbeReportError as exc:
            sys.stderr.write(f"{exc}\n")
            return 3
        sys.stdout.write(f"{len(dead)}\n{len(curable)}\n{','.join(dead)}\n")
        return 0
    if command == "home-fork-summary" and len(argv) == 2:
        try:
            drifted, curable = summarize_home_fork(payload)
        except ProbeReportError as exc:
            sys.stderr.write(f"{exc}\n")
            return 3
        sys.stdout.write(
            f"{len(drifted)}\n{len(curable)}\n{','.join(drifted)}\n{','.join(curable)}\n"
        )
        return 0
    if command == "arsenal-transitions" and len(argv) == 4 and argv[2] == "--state":
        try:
            new, skipped, report_ts = gate_arsenal_transitions(payload, Path(argv[3]))
        except ProbeReportError as exc:
            sys.stderr.write(f"{exc}\n")
            return 3
        sys.stdout.write(f"{','.join(new)}\n{','.join(skipped)}\n{report_ts}\n")
        return 0
    if command == "classify-session-tail":
        sys.stdout.write(f"{classify_session_tail(payload)}\n")
        return 0

    sys.stderr.write(f"unknown command: {command}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
