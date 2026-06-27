#!/usr/bin/env python3
"""Nuzantara operations status and safe-fix command surface.

This is the source of truth for the native macOS dashboard. It intentionally
uses only the Python standard library so it can run from the main checkout,
from Xcode, and from GitHub Actions without backend dependencies.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_FLY_HEALTH_URL = "https://nuzantara-rag.fly.dev/health"
DEFAULT_DRIVE_STATUS_URL = "https://nuzantara-rag.fly.dev/api/admin/drive/poll/status"
DEFAULT_PEER_ALIAS = "pro"
DEFAULT_PEER_REPO = "~/Desktop/nuzantara"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 10,
) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return CommandResult(127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandResult(124, stdout, stderr or f"timeout after {timeout}s")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    current = here
    while True:
        if (current / ".git").exists() or (current / "scripts" / "nuz_status.py").exists():
            return current
        if current.parent == current:
            return here
        current = current.parent


def machine_role(hostname: str, username: str) -> str:
    if hostname in {"Nuzantara", "nuzantara"} and username == "nuzantara":
        return "Pro"
    if hostname in {"Mini-Pro2", "mini-pro2"}:
        return "Mini"
    if hostname in {"Air-M5", "air-m5"} or username == "balizero":
        return "Air-M5"
    return "Unknown"


def check_status(status: str, summary: str, **details: Any) -> dict[str, Any]:
    return {"status": status, "summary": summary, "details": details}


def git_status(path: Path, *, refresh: bool = False) -> dict[str, Any]:
    if refresh:
        run_command(["git", "fetch", "--quiet", "origin", "main"], cwd=path, timeout=20)

    branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    head = run_command(["git", "rev-parse", "--short=12", "HEAD"], cwd=path)
    head_full = run_command(["git", "rev-parse", "HEAD"], cwd=path)
    origin = run_command(["git", "rev-parse", "--short=12", "origin/main"], cwd=path)
    origin_full = run_command(["git", "rev-parse", "origin/main"], cwd=path)
    status = run_command(["git", "status", "--porcelain"], cwd=path)
    ahead = run_command(["git", "rev-list", "--count", "origin/main..HEAD"], cwd=path)
    behind = run_command(["git", "rev-list", "--count", "HEAD..origin/main"], cwd=path)

    dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else "unknown",
        "head": head.stdout.strip() if head.returncode == 0 else "",
        "head_full": head_full.stdout.strip() if head_full.returncode == 0 else "",
        "origin_main": origin.stdout.strip() if origin.returncode == 0 else "",
        "origin_main_full": origin_full.stdout.strip() if origin_full.returncode == 0 else "",
        "ahead": int(ahead.stdout.strip() or 0) if ahead.returncode == 0 else None,
        "behind": int(behind.stdout.strip() or 0) if behind.returncode == 0 else None,
        "dirty": bool(dirty_lines),
        "dirty_count": len(dirty_lines),
        "dirty_preview": dirty_lines[:8],
    }


def peer_git_status(peer: str, *, refresh: bool = False) -> dict[str, Any]:
    fetch = "git fetch --quiet origin main >/dev/null 2>&1; " if refresh else ""
    remote = (
        f"cd {DEFAULT_PEER_REPO} && {fetch}"
        "printf 'branch=%s\\n' \"$(git rev-parse --abbrev-ref HEAD 2>/dev/null)\" && "
        "printf 'head=%s\\n' \"$(git rev-parse --short=12 HEAD 2>/dev/null)\" && "
        "printf 'head_full=%s\\n' \"$(git rev-parse HEAD 2>/dev/null)\" && "
        "printf 'origin_main=%s\\n' \"$(git rev-parse --short=12 origin/main 2>/dev/null)\" && "
        "printf 'origin_main_full=%s\\n' \"$(git rev-parse origin/main 2>/dev/null)\" && "
        "printf 'ahead=%s\\n' \"$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)\" && "
        "printf 'behind=%s\\n' \"$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)\" && "
        "printf 'dirty_count=%s\\n' \"$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')\""
    )
    result = run_command(["ssh", "-o", "ConnectTimeout=3", peer, remote], timeout=12)
    if result.returncode != 0:
        return {
            "reachable": False,
            "error": (result.stderr or result.stdout).strip()[:300],
        }

    parsed: dict[str, Any] = {"reachable": True}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key] = value.strip()
    for key in ("ahead", "behind", "dirty_count"):
        try:
            parsed[key] = int(parsed.get(key, 0))
        except (TypeError, ValueError):
            parsed[key] = None
    parsed["dirty"] = bool(parsed.get("dirty_count"))
    return parsed


def http_json(
    url: str,
    *,
    timeout: int = 8,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {"User-Agent": "nuz-status/1.0"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read(256_000)
            body = json.loads(data.decode("utf-8"))
            return {"ok": True, "status_code": response.status, "body": body}
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        return {"ok": False, "status_code": exc.code, "error": body}
    except Exception as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            return curl_json(url, timeout=timeout, headers=headers)
        return {"ok": False, "status_code": None, "error": str(exc)}


def curl_json(
    url: str,
    *,
    timeout: int = 8,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Fetch JSON with curl as a macOS CA fallback for Python.org runtimes."""
    curl_args = [
        "curl",
        "-sS",
        "-L",
        "--max-time",
        str(timeout),
        "-H",
        "User-Agent: nuz-status/1.0",
    ]
    for key, value in (headers or {}).items():
        curl_args.extend(["-H", f"{key}: {value}"])
    curl_args.extend(["-w", "\n%{http_code}", url])
    result = run_command(
        curl_args,
        timeout=timeout + 3,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "status_code": None,
            "error": (result.stderr or result.stdout).strip()[:500],
        }

    body, separator, status_text = result.stdout.rpartition("\n")
    if not separator:
        body = result.stdout
        status_code = None
    else:
        try:
            status_code = int(status_text.strip())
        except ValueError:
            status_code = None

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = {"raw": body[:1000]}

    ok = status_code is not None and 200 <= status_code < 300
    payload: dict[str, Any] = {"ok": ok, "status_code": status_code}
    if ok:
        payload["body"] = parsed
    else:
        payload["error"] = parsed
    return payload


def gh_latest_run(workflow: str, *, commit: str | None = None) -> dict[str, Any]:
    command = [
        "gh",
        "run",
        "list",
        "--workflow",
        workflow,
        "--limit",
        "1",
        "--json",
        "status,conclusion,createdAt,updatedAt,url,headSha",
    ]
    if commit:
        command.extend(["--commit", commit])
    result = run_command(command, timeout=12)
    if result.returncode != 0:
        return {"available": False, "error": (result.stderr or result.stdout).strip()[:300]}
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {"available": False, "error": str(exc)}
    return {"available": True, "latest": rows[0] if rows else None}


def build_checks(
    *,
    root: Path,
    refresh: bool,
    offline: bool,
    peer: str,
    fly_health_url: str,
    drive_status_url: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    local_git = git_status(root, refresh=refresh)
    local_status = "ok"
    local_summary = f"{local_git['branch']} @ {local_git['head']}"
    if local_git["dirty"]:
        local_status = "warn"
        local_summary += f" with {local_git['dirty_count']} dirty files"
    if local_git["behind"]:
        local_status = "warn"
        local_summary += f", {local_git['behind']} behind origin/main"
    checks.append({"id": "git_local", **check_status(local_status, local_summary, **local_git)})

    if offline:
        checks.append(
            {
                "id": "git_peer",
                **check_status("unknown", "offline mode: peer Git not checked"),
            },
        )
    else:
        peer_git = peer_git_status(peer, refresh=refresh)
        if not peer_git.get("reachable"):
            checks.append(
                {
                    "id": "git_peer",
                    **check_status("fail", "Pro peer unreachable", **peer_git),
                },
            )
        else:
            peer_state = "ok"
            peer_summary = f"{peer_git.get('branch', 'unknown')} @ {peer_git.get('head', '')}"
            if peer_git.get("dirty"):
                peer_state = "fail"
                peer_summary += f" with {peer_git.get('dirty_count')} dirty files"
            elif peer_git.get("behind"):
                peer_state = "warn"
                peer_summary += f", {peer_git.get('behind')} behind origin/main"
            checks.append(
                {
                    "id": "git_peer",
                    **check_status(peer_state, peer_summary, **peer_git),
                },
            )
            actions.append(
                {
                    "id": "sync_pro_main",
                    "label": "Sync Pro main",
                    "enabled": (
                        peer_git.get("branch") == "main"
                        and not peer_git.get("dirty")
                        and bool(peer_git.get("behind"))
                        and not peer_git.get("ahead")
                    ),
                    "target": "pro-main",
                },
            )
            actions.append(
                {
                    "id": "stash_and_sync_pro_main",
                    "label": "Stash + sync Pro main",
                    "enabled": (
                        peer_git.get("branch") == "main"
                        and bool(peer_git.get("dirty"))
                        and bool(peer_git.get("behind"))
                        and not peer_git.get("ahead")
                    ),
                    "target": "pro-main-autostash",
                },
            )

    if offline:
        checks.append({"id": "fly_health", **check_status("unknown", "offline mode")})
        checks.append({"id": "drive_worker", **check_status("unknown", "offline mode")})
    else:
        fly = http_json(fly_health_url)
        fly_body = fly.get("body") if isinstance(fly.get("body"), dict) else {}
        fly_ok = bool(fly.get("ok") and fly_body.get("status") in {"healthy", "ok"})
        checks.append(
            {
                "id": "fly_health",
                **check_status(
                    "ok" if fly_ok else "fail",
                    f"HTTP {fly.get('status_code')}: {fly_body.get('status', fly.get('error', 'unknown'))}",
                    **fly,
                ),
            },
        )

        drive_headers: dict[str, str] = {}
        drive_api_key = os.getenv("NUZANTARA_API_KEY", "").strip()
        if drive_api_key:
            drive_headers["X-API-Key"] = drive_api_key
        drive = http_json(drive_status_url, headers=drive_headers)
        drive_body = drive.get("body") if isinstance(drive.get("body"), dict) else {}
        drive_status = drive_body.get("status", "unknown")
        summary = f"worker endpoint={drive_status}"
        if not drive.get("ok") and drive.get("status_code") == 401 and not drive_api_key:
            state = "warn"
            summary = "worker auth required: set NUZANTARA_API_KEY"
        elif not drive.get("ok"):
            state = "fail"
        elif drive_status == "stale":
            state = "fail"
        elif drive_status == "ok":
            state = "ok"
        else:
            state = "warn"
        checks.append(
            {
                "id": "drive_worker",
                **check_status(
                    state,
                    summary,
                    **drive,
                ),
            },
        )

    if offline:
        checks.append({"id": "github_tests", **check_status("unknown", "offline mode")})
    else:
        tests = gh_latest_run("Tests & Coverage", commit=local_git.get("origin_main_full") or None)
        if not tests.get("available"):
            checks.append(
                {
                    "id": "github_tests",
                    **check_status("unknown", "gh unavailable", **tests),
                },
            )
        else:
            latest = tests.get("latest") or {}
            conclusion = latest.get("conclusion")
            status = latest.get("status")
            state = "ok" if status == "completed" and conclusion == "success" else "warn"
            checks.append(
                {
                    "id": "github_tests",
                    **check_status(state, f"{status}/{conclusion}", **tests),
                },
            )

    return checks, actions


def collect_status(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root(Path.cwd())
    username = getpass.getuser()
    hostname = socket.gethostname().split(".")[0]
    checks, actions = build_checks(
        root=root,
        refresh=bool(args.refresh),
        offline=bool(args.offline),
        peer=args.peer,
        fly_health_url=args.fly_health_url,
        drive_status_url=args.drive_status_url,
    )
    failing = sum(1 for check in checks if check["status"] == "fail")
    warning = sum(1 for check in checks if check["status"] == "warn")
    unknown = sum(1 for check in checks if check["status"] == "unknown")
    overall = "ok"
    if failing:
        overall = "fail"
    elif warning:
        overall = "warn"
    elif unknown:
        overall = "unknown"
    return {
        "generated_at": utc_now(),
        "overall": overall,
        "machine": {
            "user": username,
            "hostname": hostname,
            "role": machine_role(hostname, username),
        },
        "repo_root": str(root),
        "checks": checks,
        "actions": actions,
    }


def safe_fix(target: str, *, peer: str) -> dict[str, Any]:
    if target == "pro-main":
        remote = (
            f"cd {DEFAULT_PEER_REPO} && "
            "git fetch --quiet origin main && "
            "test \"$(git rev-parse --abbrev-ref HEAD)\" = main && "
            "test -z \"$(git status --porcelain)\" && "
            "git merge --ff-only origin/main"
        )
        result = run_command(["ssh", "-o", "ConnectTimeout=3", peer, remote], timeout=60)
        return {
            "target": target,
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        }

    if target == "pro-main-autostash":
        stash_name = f"nuz-status-auto-stash-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        remote = (
            f"cd {DEFAULT_PEER_REPO} && "
            "test \"$(git rev-parse --abbrev-ref HEAD)\" = main && "
            "git fetch --quiet origin main && "
            "test \"$(git rev-list --count origin/main..HEAD)\" = 0 && "
            f"git stash push -u -m {stash_name!r} && "
            "git merge --ff-only origin/main && "
            "git status --short --branch"
        )
        result = run_command(["ssh", "-o", "ConnectTimeout=3", peer, remote], timeout=120)
        return {
            "target": target,
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        }

    if target == "local-main":
        root = repo_root(Path.cwd())
        guard_branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
        guard_dirty = run_command(["git", "status", "--porcelain"], cwd=root)
        if guard_branch.stdout.strip() != "main" or guard_dirty.stdout.strip():
            return {
                "target": target,
                "ok": False,
                "returncode": 2,
                "stdout": "",
                "stderr": "local checkout is not clean main",
            }
        fetch = run_command(["git", "fetch", "--quiet", "origin", "main"], cwd=root, timeout=30)
        if fetch.returncode != 0:
            return {
                "target": target,
                "ok": False,
                "returncode": fetch.returncode,
                "stdout": fetch.stdout,
                "stderr": fetch.stderr,
            }
        merge = run_command(["git", "merge", "--ff-only", "origin/main"], cwd=root, timeout=60)
        return {
            "target": target,
            "ok": merge.returncode == 0,
            "returncode": merge.returncode,
            "stdout": merge.stdout[-4000:],
            "stderr": merge.stderr[-4000:],
        }

    return {
        "target": target,
        "ok": False,
        "returncode": 64,
        "stdout": "",
        "stderr": f"unknown safe-fix target: {target}",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nuzantara status dashboard backend")
    sub = parser.add_subparsers(dest="command")

    status = sub.add_parser("status", help="Collect status")
    status.add_argument("--json", action="store_true", help="Emit JSON")
    status.add_argument("--refresh", action="store_true", help="Fetch fresh Git refs")
    status.add_argument("--offline", action="store_true", help="Skip network and SSH checks")
    status.add_argument("--peer", default=DEFAULT_PEER_ALIAS)
    status.add_argument("--fly-health-url", default=DEFAULT_FLY_HEALTH_URL)
    status.add_argument("--drive-status-url", default=DEFAULT_DRIVE_STATUS_URL)

    fix = sub.add_parser("fix", help="Run a safe automated fix")
    fix.add_argument(
        "--target",
        required=True,
        choices=["pro-main", "pro-main-autostash", "local-main"],
    )
    fix.add_argument("--peer", default=DEFAULT_PEER_ALIAS)
    fix.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in {None, "status"}:
        if args.command is None:
            args.command = "status"
            args.json = False
            args.refresh = False
            args.offline = False
            args.peer = DEFAULT_PEER_ALIAS
            args.fly_health_url = DEFAULT_FLY_HEALTH_URL
            args.drive_status_url = DEFAULT_DRIVE_STATUS_URL
        payload = collect_status(args)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Nuzantara status: {payload['overall']}")
            for check in payload["checks"]:
                print(f"- {check['id']}: {check['status']} - {check['summary']}")
        return 0 if payload["overall"] in {"ok", "unknown", "warn"} else 1

    if args.command == "fix":
        payload = safe_fix(args.target, peer=args.peer)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"{args.target}: {'ok' if payload['ok'] else 'failed'}")
            if payload["stdout"]:
                print(payload["stdout"])
            if payload["stderr"]:
                print(payload["stderr"], file=sys.stderr)
        return 0 if payload["ok"] else 1

    parser.print_help()
    return 64


if __name__ == "__main__":
    sys.exit(main())
