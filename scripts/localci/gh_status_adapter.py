#!/usr/bin/env python3
"""INERT adapter: local-CI ``status.json`` -> GitHub commit-status payload.

Context ``pro/local-ci`` is NON-required and comparison-only: it lets a human set the
local verdict beside the hosted checks, and never replaces one of them. In this phase
the adapter only BUILDS the payload and the ``gh api`` argv; the only posting path (behind --post + LOCALCI_ADAPTER_ARMED=1 + LOCALCI_ADAPTER_PHASE=live) is refused in this phase and never reached by tests.

Verdict mapping (``overall`` -> GitHub ``state``):

    PASS                              -> success
    FAIL, ERROR                       -> failure
    BLOCKED, STALE, INTERRUPTED       -> error
    SUBSET_PASS                       -> pending  ("SUBSET (not parity)" — a subset run
                                          is never parity with the hosted gate, so it can
                                          never read as green)
    anything else / missing           -> error

Posting needs ``--post`` AND ``LOCALCI_ADAPTER_ARMED=1`` AND ``LOCALCI_ADAPTER_PHASE=live``.
Missing any of the three the run is refused (exit 3) after printing the argv it would have
used. No HTTP client is imported; a future live phase shells out to ``gh api``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONTEXT = "pro/local-ci"
DEFAULT_REPO = "Bali-Zero/Teman2"
DESCRIPTION_MAX = 140
SUBSET_PREFIX = "SUBSET (not parity)"

STATE_BY_OVERALL = {
    "PASS": "success",
    "FAIL": "failure",
    "ERROR": "failure",
    "BLOCKED": "error",
    "STALE": "error",
    "INTERRUPTED": "error",
    "SUBSET_PASS": "pending",
}
FAIL_STATUSES = frozenset({"FAIL", "ERROR"})

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_POST_REFUSED = 3

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class AdapterError(ValueError):
    """The status.json cannot be turned into a payload — refuse rather than guess."""


def state_for(overall: object) -> str:
    return STATE_BY_OVERALL.get(overall, "error") if isinstance(overall, str) else "error"


def count_checks(checks: object) -> tuple[int, int, int]:
    """(pass, fail, other). ``fail`` is FAIL+ERROR; NOT_APPLICABLE and the rest are other."""
    passed = failed = other = 0
    if isinstance(checks, dict):
        for entry in checks.values():
            status = entry.get("status") if isinstance(entry, dict) else None
            if status == "PASS":
                passed += 1
            elif status in FAIL_STATUSES:
                failed += 1
            else:
                other += 1
    return passed, failed, other


def build_description(overall: object, run_id: str, passed: int, failed: int, other: int) -> str:
    label = SUBSET_PREFIX if overall == "SUBSET_PASS" else str(overall)
    head = f"{label}: run "
    tail = f" | PASS {passed} FAIL {failed} other {other}"
    room = DESCRIPTION_MAX - len(head) - len(tail)
    rid = run_id if len(run_id) <= room else run_id[: max(room - 1, 1)] + "~"
    return (head + rid + tail)[:DESCRIPTION_MAX]


def build_payload(status: dict, target_url: str | None = None) -> dict:
    run_id = status.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise AdapterError("status.json has no run_id")
    overall = status.get("overall")
    passed, failed, other = count_checks(status.get("checks"))
    payload = {
        "state": state_for(overall),
        "context": CONTEXT,
        "description": build_description(overall, run_id, passed, failed, other),
    }
    if target_url:
        payload["target_url"] = target_url
    return payload


def build_url(repo: str, sha: object) -> str:
    if not isinstance(repo, str) or not _REPO_RE.match(repo):
        raise AdapterError(f"repo {repo!r} is not owner/name")
    if not isinstance(sha, str) or not _SHA_RE.match(sha):
        raise AdapterError("candidate_sha is missing or not a full 40-hex sha")
    return f"repos/{repo}/statuses/{sha}"


def build_gh_argv(url: str, payload: dict) -> list[str]:
    argv = ["gh", "api", "--method", "POST", url]
    for key, value in payload.items():
        argv += ["-f", f"{key}={value}"]
    return argv


def _armed() -> bool:
    return os.environ.get("LOCALCI_ADAPTER_ARMED") == "1"


def _live() -> bool:
    return os.environ.get("LOCALCI_ADAPTER_PHASE") == "live"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("status", type=Path, help="path to a local-CI status.json")
    ap.add_argument("--out", type=Path, default=None,
                    help="directory for adapter_dryrun.json (default: the status.json's directory)")
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name (default {DEFAULT_REPO})")
    ap.add_argument("--target-url", default=None, help="optional link to the run's evidence")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="post", action="store_false", default=False,
                      help="build and write the payload, post nothing (default)")
    mode.add_argument("--post", dest="post", action="store_true",
                      help="post via `gh api` — refused unless armed and in the live phase")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        status = json.loads(args.status.read_text())
        if not isinstance(status, dict):
            raise AdapterError("status.json is not a JSON object")
        payload = build_payload(status, args.target_url)
        url = build_url(args.repo, status.get("candidate_sha"))
    except (OSError, json.JSONDecodeError, AdapterError) as exc:
        print(f"gh_status_adapter: refusing — {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    gh_argv = build_gh_argv(url, payload)

    if args.post:
        if not (_armed() and _live()):
            missing = [name for name, ok in (("LOCALCI_ADAPTER_ARMED=1", _armed()),
                                             ("LOCALCI_ADAPTER_PHASE=live", _live())) if not ok]
            print("gh_status_adapter: --post REFUSED — this phase is comparison-only and "
                  f"inert; needs {' and '.join(missing)} (both, plus --post).", file=sys.stderr)
            print("would-be argv (not executed): " + json.dumps(gh_argv))
            return EXIT_POST_REFUSED
        result = subprocess.run(gh_argv, capture_output=True, text=True)
        print(json.dumps({"payload": payload, "url": url, "posted": result.returncode == 0}))
        return EXIT_OK if result.returncode == 0 else result.returncode

    record = {"payload": payload, "url": url, "would_post": False}
    out_dir = args.out if args.out is not None else args.status.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "adapter_dryrun.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
