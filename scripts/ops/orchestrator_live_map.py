#!/usr/bin/env python3
"""Read-only live map for Nuzantara agent orchestration.

The mapper turns the ad-hoc "who is working on what?" audit into a repeatable
artifact. It gathers active git worktrees, open PRs, relevant local processes,
and high-signal incomplete-code markers, then derives no-touch lanes and safe
candidate workstreams.

It is intentionally read-only: no branch switching, no cleanup, no process
signals, and no writes unless --output is explicitly provided.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_SCAN_ROOTS = (
    "apps/backend-rag/backend",
    "apps/mouth",
    "apps/admin-dashboard",
    "apps/web",
    "apps/webapp",
    "apps/nuzantara-mcp",
    "scripts",
)
SKIP_DIRS = {
    ".git",
    ".next",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "tests",
    "__tests__",
    "e2e",
}
SOURCE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".sh",
    ".md",
}
MAX_SCAN_BYTES = 512_000

MARKER_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("not_implemented_error", r"\bNotImplementedError\b", "high"),
    (
        "http_501",
        r"\bstatus_code\s*=\s*501\b|\bHTTP_501\b|\b501\b.*not implemented",
        "high",
    ),
    (
        "mock_result",
        r"\b(mock|placeholder|stub)\b.{0,80}\b(result|response|data)\b",
        "medium",
    ),
    (
        "returns_empty_placeholder",
        r"\breturn\s+(\[\]|\{\})\b.{0,80}\b(placeholder|stub|mock)\b",
        "medium",
    ),
    ("todo", r"\b(TODO|FIXME)\b", "low"),
    ("not_implemented_text", r"\bnot implemented\b", "medium"),
    ("placeholder_text", r"\bplaceholder\b|\bstub\b", "medium"),
)

LANE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("wr2", "wr2"),
    ("wr3", "wr3"),
    ("flowkit", "flowkit"),
    ("wa-mirror", "wa"),
    ("wacorpus", "wa"),
    ("wa-corpus", "wa"),
    ("whatsapp", "wa"),
    ("doc-intake", "doc-intake"),
    ("document-intake", "doc-intake"),
    ("olympus", "olympus"),
    ("router", "backend-router"),
    ("backend-rag", "backend-rag"),
    ("apps/mouth", "mouth"),
    ("mouth", "mouth"),
    ("palette", "mouth"),
    ("messagebubble", "mouth"),
    ("imagegenmodal", "mouth"),
    ("observatory", "observatory"),
    ("s13", "s13"),
    ("translation-drift", "translation"),
    ("crm_guardian", "crm-guardian"),
    ("crm-guardian", "crm-guardian"),
    ("workspace-event", "workspace-event-bridge"),
    ("intake", "doc-intake"),
)

PROCESS_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("claude", "claude"),
    ("codex", "codex"),
    ("gemini", "gemini"),
    ("flowkit", "flowkit"),
    ("wa-mirror", "wa"),
    ("openclaw_whatsapp", "wa"),
    ("crm_guardian", "crm-guardian"),
    ("workspace-event", "workspace-event-bridge"),
    ("uvicorn", "backend-runtime"),
    ("next dev", "frontend-runtime"),
)

AREA_BLOCK_ALIASES: dict[str, set[str]] = {
    "backend-rag": {"backend-rag", "backend-router", "backend-service"},
    "backend-router": {"backend-router"},
    "wa": {"wa"},
    "wr2": {"wr2"},
    "wr3": {"wr3"},
    "doc-intake": {"doc-intake"},
    "olympus": {"olympus"},
    "flowkit": {"flowkit", "wr2", "wr3"},
    "s13": {"s13"},
}

DEFAULT_REMOTE_TARGETS: dict[str, tuple[str, str]] = {
    "m5": ("m5", "/Users/balizero/nuzantara"),
    "air": ("air", "/Users/balizero/nuzantara"),
}


@dataclass(frozen=True)
class RemoteTarget:
    name: str
    host: str
    repo_root: str


@dataclass(frozen=True)
class MachineStatus:
    name: str
    host: str | None
    repo_root: str
    reachable: bool
    current_branch: str | None = None
    head: str | None = None
    origin_main: str | None = None
    identity: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class WorktreeInfo:
    path: str
    head: str | None = None
    branch: str | None = None
    detached: bool = False
    lane: str | None = None
    task_id: str | None = None
    machine: str = "local"


@dataclass(frozen=True)
class PullRequestInfo:
    number: int
    title: str
    head_ref: str
    base_ref: str
    state: str
    is_draft: bool
    merge_state_status: str | None
    updated_at: str | None
    author: str | None
    lane: str | None = None
    machine: str | None = None


@dataclass(frozen=True)
class ProcessSignal:
    pid: int | None
    category: str
    command: str
    machine: str = "local"


@dataclass(frozen=True)
class ComponentFinding:
    component_id: str
    area: str
    path: str
    line: int
    marker: str
    severity: str
    evidence: str


@dataclass(frozen=True)
class NoTouchLane:
    lane: str
    reason: str
    source: str
    reference: str
    machine: str = "local"


@dataclass(frozen=True)
class CandidateWorkstream:
    lane: str
    task_id: str
    area: str
    finding_count: int
    top_severity: str
    sample_paths: list[str]
    rationale: str


@dataclass(frozen=True)
class OrchestratorMap:
    generated_at: str
    repo_root: str
    current_branch: str | None
    machines: list[MachineStatus] = field(default_factory=list)
    worktrees: list[WorktreeInfo] = field(default_factory=list)
    pull_requests: list[PullRequestInfo] = field(default_factory=list)
    process_signals: list[ProcessSignal] = field(default_factory=list)
    findings: list[ComponentFinding] = field(default_factory=list)
    no_touch_lanes: list[NoTouchLane] = field(default_factory=list)
    candidate_workstreams: list[CandidateWorkstream] = field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_command(args: Sequence[str], cwd: Path, timeout_s: int = 15) -> str:
    try:
        proc = subprocess.run(
            list(args),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout


def _run_ssh_command(
    target: RemoteTarget, command: str, timeout_s: int = 15
) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                target.host,
                command,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except OSError as exc:
        return "", str(exc)
    except subprocess.TimeoutExpired:
        return "", f"timeout after {timeout_s}s"
    if proc.returncode != 0:
        return "", proc.stderr.strip() or f"ssh exited {proc.returncode}"
    return proc.stdout, ""


def _first_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def parse_remote_target(spec: str) -> RemoteTarget:
    trimmed = spec.strip()
    if not trimmed:
        raise ValueError("remote target cannot be empty")
    if trimmed in DEFAULT_REMOTE_TARGETS:
        host, repo_root = DEFAULT_REMOTE_TARGETS[trimmed]
        return RemoteTarget(name=trimmed, host=host, repo_root=repo_root)

    if "=" in trimmed:
        name, rest = trimmed.split("=", 1)
        name = name.strip()
        rest = rest.strip()
    else:
        rest = trimmed
        name = rest.split(":", 1)[0].strip()

    if ":" not in rest:
        raise ValueError(
            f"remote target must be name=host:/repo/path or host:/repo/path: {spec}"
        )
    host, repo_root = rest.split(":", 1)
    host = host.strip()
    repo_root = repo_root.strip()
    if not name or not host or not repo_root:
        raise ValueError(
            f"remote target must include name, host, and repo path: {spec}"
        )
    return RemoteTarget(name=name, host=host, repo_root=repo_root)


def _infer_lane(text: str) -> str | None:
    lowered = text.lower()
    for needle, lane in LANE_KEYWORDS:
        if needle in lowered:
            return lane
    return None


def _infer_machine(text: str) -> str | None:
    lowered = text.lower()
    if (
        "air-m5" in lowered
        or "air_m5" in lowered
        or "agent/m5/" in lowered
        or "agent/air/" in lowered
    ):
        return "m5"
    if "agent/pro/" in lowered or "agent/nuzantara/" in lowered:
        return "pro"
    return None


def _parse_branch_lane(branch: str | None) -> tuple[str | None, str | None]:
    if not branch:
        return None, None
    parts = branch.split("/")
    if len(parts) >= 4 and parts[0] == "agent":
        return parts[2], parts[3]
    lane = _infer_lane(branch)
    return lane, None


def parse_worktree_porcelain(
    text: str, *, machine: str = "local"
) -> list[WorktreeInfo]:
    worktrees: list[WorktreeInfo] = []
    current: dict[str, str] = {}

    def flush() -> None:
        if not current.get("worktree"):
            return
        branch_ref = current.get("branch")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
        lane, task_id = _parse_branch_lane(branch)
        worktrees.append(
            WorktreeInfo(
                path=current["worktree"],
                head=current.get("HEAD"),
                branch=branch,
                detached="detached" in current,
                lane=lane or _infer_lane(current["worktree"]),
                task_id=task_id,
                machine=machine,
            )
        )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    flush()
    return worktrees


def parse_pr_json(text: str) -> list[PullRequestInfo]:
    if not text.strip():
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    prs: list[PullRequestInfo] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        author = item.get("author")
        if isinstance(author, dict):
            author_login = author.get("login")
        else:
            author_login = None
        number = item.get("number")
        if not isinstance(number, int):
            continue
        head_ref = str(item.get("headRefName") or "")
        prs.append(
            PullRequestInfo(
                number=number,
                title=str(item.get("title") or ""),
                head_ref=head_ref,
                base_ref=str(item.get("baseRefName") or ""),
                state=str(item.get("state") or ""),
                is_draft=bool(item.get("isDraft")),
                merge_state_status=item.get("mergeStateStatus"),
                updated_at=item.get("updatedAt"),
                author=author_login,
                lane=_infer_lane(head_ref + " " + str(item.get("title") or "")),
                machine=_infer_machine(head_ref + " " + str(item.get("title") or "")),
            )
        )
    return prs


def parse_ps_aux(text: str, *, machine: str = "local") -> list[ProcessSignal]:
    signals: list[ProcessSignal] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        category = _infer_process_category(line)
        if category is None:
            continue
        parts = line.split(None, 10)
        pid: int | None = None
        if len(parts) > 1:
            try:
                pid = int(parts[1])
            except ValueError:
                pid = None
        command = parts[10] if len(parts) > 10 else line
        signals.append(
            ProcessSignal(pid=pid, category=category, command=command, machine=machine)
        )
    return signals


def _infer_process_category(line: str) -> str | None:
    lowered = line.lower()
    for needle, label in PROCESS_KEYWORDS:
        if needle == "flowkit":
            # Avoid false positives from Apple's WorkflowKit framework.
            if "/flowkit/" in lowered or "flowkit/venv" in lowered:
                return label
            continue
        if needle in lowered:
            return label
    return None


def collect_local_machine_status(repo_root: Path) -> MachineStatus:
    whoami = _first_line(_run_command(["whoami"], repo_root))
    hostname = _first_line(_run_command(["hostname"], repo_root))
    branch = _first_line(
        _run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    )
    head = _first_line(_run_command(["git", "rev-parse", "--short", "HEAD"], repo_root))
    origin_main = _first_line(
        _run_command(["git", "rev-parse", "--short", "origin/main"], repo_root)
    )
    identity = f"{whoami}@{hostname}" if whoami and hostname else None
    return MachineStatus(
        name="local",
        host=hostname,
        repo_root=str(repo_root),
        reachable=True,
        current_branch=branch,
        head=head,
        origin_main=origin_main,
        identity=identity,
    )


def _parse_status_lines(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key:
            values[key.strip()] = value.strip()
    return values


def collect_remote_machine(
    target: RemoteTarget,
) -> tuple[MachineStatus, list[WorktreeInfo], list[ProcessSignal]]:
    quoted_repo = shlex.quote(target.repo_root)
    status_command = (
        'printf "identity=%s@%s\\n" "$(whoami)" "$(hostname)"; '
        f"if git -C {quoted_repo} rev-parse --git-dir >/dev/null 2>&1; then "
        f'printf "branch="; git -C {quoted_repo} rev-parse --abbrev-ref HEAD 2>/dev/null || true; '
        f'printf "head="; git -C {quoted_repo} rev-parse --short HEAD 2>/dev/null || true; '
        f'printf "origin_main="; git -C {quoted_repo} rev-parse --short origin/main 2>/dev/null || true; '
        'else printf "error=repo_not_available\\n"; fi'
    )
    status_text, status_error = _run_ssh_command(target, status_command, timeout_s=15)
    if status_error:
        return (
            MachineStatus(
                name=target.name,
                host=target.host,
                repo_root=target.repo_root,
                reachable=False,
                error=status_error,
            ),
            [],
            [],
        )

    status_values = _parse_status_lines(status_text)
    status = MachineStatus(
        name=target.name,
        host=target.host,
        repo_root=target.repo_root,
        reachable=True,
        current_branch=status_values.get("branch") or None,
        head=status_values.get("head") or None,
        origin_main=status_values.get("origin_main") or None,
        identity=status_values.get("identity") or None,
        error=status_values.get("error") or None,
    )

    if status.error:
        return status, [], []

    worktree_text, _ = _run_ssh_command(
        target,
        f"git -C {quoted_repo} worktree list --porcelain 2>/dev/null || true",
        timeout_s=20,
    )
    ps_text, _ = _run_ssh_command(target, "ps aux 2>/dev/null || true", timeout_s=20)
    return (
        status,
        parse_worktree_porcelain(worktree_text, machine=target.name),
        parse_ps_aux(ps_text, machine=target.name),
    )


def component_area(path: str) -> str:
    normalized = path.replace(os.sep, "/")
    if normalized.startswith("apps/backend-rag/"):
        if "/routers/" in normalized or "router_registration" in normalized:
            return "backend-router"
        if "/services/" in normalized:
            return "backend-service"
        return "backend-rag"
    if normalized.startswith("apps/mouth/"):
        return "mouth"
    if normalized.startswith("apps/admin-dashboard/"):
        return "admin-dashboard"
    if normalized.startswith("apps/webapp/"):
        return "webapp"
    if normalized.startswith("apps/web/"):
        return "web"
    if normalized.startswith("apps/nuzantara-mcp/"):
        return "mcp"
    if normalized.startswith("scripts/wr2"):
        return "wr2"
    if normalized.startswith("scripts/wr3"):
        return "wr3"
    if "whatsapp" in normalized or "wa_" in normalized or "wa-" in normalized:
        return "wa"
    if normalized.startswith("scripts/"):
        return "ops-script"
    return normalized.split("/", 1)[0] if "/" in normalized else "repo"


def _iter_scan_files(repo_root: Path, scan_roots: Iterable[str]) -> Iterable[Path]:
    for rel_root in scan_roots:
        root = repo_root / rel_root
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix not in SOURCE_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_SCAN_BYTES:
                    continue
            except OSError:
                continue
            yield path


def scan_incomplete_markers(
    repo_root: Path,
    scan_roots: Iterable[str] = DEFAULT_SCAN_ROOTS,
    *,
    limit: int = 200,
    per_area_limit: int = 30,
) -> list[ComponentFinding]:
    compiled = [
        (name, re.compile(pattern, re.IGNORECASE), severity)
        for name, pattern, severity in MARKER_PATTERNS
    ]
    findings: list[ComponentFinding] = []
    seen: set[tuple[str, int, str]] = set()
    area_counts: dict[str, int] = {}

    for path in _iter_scan_files(repo_root, scan_roots):
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        area = component_area(rel_path)
        if area_counts.get(area, 0) >= per_area_limit:
            continue
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("# noqa"):
                continue
            for marker, regex, severity in compiled:
                if not regex.search(stripped):
                    continue
                key = (rel_path, line_no, marker)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    ComponentFinding(
                        component_id=area,
                        area=area,
                        path=rel_path,
                        line=line_no,
                        marker=marker,
                        severity=severity,
                        evidence=stripped[:180],
                    )
                )
                area_counts[area] = area_counts.get(area, 0) + 1
                break
            if len(findings) >= limit:
                return findings
            if area_counts.get(area, 0) >= per_area_limit:
                break
    return findings


def derive_no_touch_lanes(
    worktrees: Sequence[WorktreeInfo],
    prs: Sequence[PullRequestInfo],
    processes: Sequence[ProcessSignal],
) -> list[NoTouchLane]:
    lanes: dict[tuple[str, str, str, str], NoTouchLane] = {}

    def add(
        lane: str | None,
        reason: str,
        source: str,
        reference: str,
        *,
        machine: str = "local",
    ) -> None:
        if not lane:
            return
        key = (lane, source, reference, machine)
        lanes[key] = NoTouchLane(
            lane=lane,
            reason=reason,
            source=source,
            reference=reference,
            machine=machine,
        )

    for wt in worktrees:
        if wt.lane:
            add(
                wt.lane,
                "active git worktree exists",
                "worktree",
                wt.branch or wt.path,
                machine=wt.machine,
            )

    for pr in prs:
        if pr.state.upper() == "OPEN":
            machine = pr.machine or "github"
            add(
                pr.lane,
                f"open PR #{pr.number}: {pr.title}",
                "pull_request",
                pr.head_ref,
                machine=machine,
            )
            if pr.lane == "backend-router":
                add(
                    "backend-rag",
                    f"open PR #{pr.number} touches router wiring",
                    "pull_request",
                    pr.head_ref,
                    machine=machine,
                )

    process_seen: set[tuple[str, str]] = set()
    for proc in processes:
        process_key = (proc.machine, proc.category)
        if process_key in process_seen:
            continue
        process_seen.add(process_key)
        add(
            proc.category,
            f"process is running on {proc.machine}",
            "process",
            proc.command[:120],
            machine=proc.machine,
        )

    return sorted(
        lanes.values(),
        key=lambda item: (item.lane, item.machine, item.source, item.reference),
    )


def _severity_rank(severity: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(severity, 0)


def derive_candidate_workstreams(
    findings: Sequence[ComponentFinding],
    no_touch_lanes: Sequence[NoTouchLane],
    *,
    max_candidates: int = 8,
) -> list[CandidateWorkstream]:
    blocked_lanes = {lane.lane for lane in no_touch_lanes}
    blocked_areas = set(blocked_lanes)
    for lane in blocked_lanes:
        blocked_areas.update(AREA_BLOCK_ALIASES.get(lane, set()))
    grouped: dict[str, list[ComponentFinding]] = {}
    for finding in findings:
        if finding.area in blocked_areas or finding.component_id in blocked_areas:
            continue
        grouped.setdefault(finding.area, []).append(finding)

    candidates: list[CandidateWorkstream] = []
    for area, area_findings in grouped.items():
        sorted_findings = sorted(
            area_findings,
            key=lambda item: (-_severity_rank(item.severity), item.path, item.line),
        )
        top = sorted_findings[0]
        task_slug = (
            re.sub(r"[^a-z0-9]+", "-", area.lower()).strip("-")[:40] or "component"
        )
        sample_paths = []
        for finding in sorted_findings:
            if finding.path not in sample_paths:
                sample_paths.append(finding.path)
            if len(sample_paths) >= 3:
                break
        candidates.append(
            CandidateWorkstream(
                lane="ops" if area == "ops-script" else area,
                task_id=f"audit-{task_slug}-incomplete",
                area=area,
                finding_count=len(area_findings),
                top_severity=top.severity,
                sample_paths=sample_paths,
                rationale="Incomplete markers found and no active no-touch lane currently owns this area.",
            )
        )
    return sorted(
        candidates,
        key=lambda item: (
            -_severity_rank(item.top_severity),
            -item.finding_count,
            item.area,
        ),
    )[:max_candidates]


def collect_live_map(
    repo_root: Path,
    *,
    scan_roots: Iterable[str] = DEFAULT_SCAN_ROOTS,
    finding_limit: int = 200,
    per_area_limit: int = 30,
    remote_targets: Sequence[RemoteTarget] = (),
) -> OrchestratorMap:
    repo_root = repo_root.resolve()
    branch = (
        _run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root).strip()
        or None
    )
    machines = [collect_local_machine_status(repo_root)]
    worktrees = parse_worktree_porcelain(
        _run_command(["git", "worktree", "list", "--porcelain"], repo_root)
    )
    pr_json = _run_command(
        [
            "gh",
            "pr",
            "list",
            "--limit",
            "100",
            "--json",
            "number,title,headRefName,baseRefName,state,isDraft,mergeStateStatus,updatedAt,author",
        ],
        repo_root,
        timeout_s=30,
    )
    prs = parse_pr_json(pr_json)
    ps_text = _run_command(["ps", "aux"], repo_root)
    processes = parse_ps_aux(ps_text)
    for target in remote_targets:
        status, remote_worktrees, remote_processes = collect_remote_machine(target)
        machines.append(status)
        worktrees.extend(remote_worktrees)
        processes.extend(remote_processes)
    findings = scan_incomplete_markers(
        repo_root, scan_roots, limit=finding_limit, per_area_limit=per_area_limit
    )
    no_touch = derive_no_touch_lanes(worktrees, prs, processes)
    candidates = derive_candidate_workstreams(findings, no_touch)
    return OrchestratorMap(
        generated_at=_utc_now(),
        repo_root=str(repo_root),
        current_branch=branch,
        machines=machines,
        worktrees=worktrees,
        pull_requests=prs,
        process_signals=processes,
        findings=findings,
        no_touch_lanes=no_touch,
        candidate_workstreams=candidates,
    )


def render_markdown(report: OrchestratorMap) -> str:
    lines = [
        f"# Nuzantara Orchestrator Live Map - {report.generated_at}",
        "",
        f"- Repo: `{report.repo_root}`",
        f"- Branch: `{report.current_branch or 'unknown'}`",
        f"- Worktrees: {len(report.worktrees)}",
        f"- Open PRs observed: {len([pr for pr in report.pull_requests if pr.state.upper() == 'OPEN'])}",
        f"- Process signals: {len(report.process_signals)}",
        f"- Incomplete markers: {len(report.findings)}",
        "",
        "## Machines",
    ]
    if report.machines:
        for machine in report.machines:
            state = "reachable" if machine.reachable else "unreachable"
            details = [
                f"identity=`{machine.identity or 'unknown'}`",
                f"branch=`{machine.current_branch or 'unknown'}`",
                f"head=`{machine.head or 'unknown'}`",
                f"origin/main=`{machine.origin_main or 'unknown'}`",
            ]
            if machine.error:
                details.append(f"error=`{machine.error}`")
            lines.append(
                f"- `{machine.name}` via `{machine.host or 'local'}`: {state}; "
                + "; ".join(details)
            )
    else:
        lines.append("- None observed.")

    lines.extend(
        [
            "",
            "## No-Touch Lanes",
        ]
    )
    if report.no_touch_lanes:
        for lane in report.no_touch_lanes:
            lines.append(
                f"- [{lane.machine}] `{lane.lane}` ({lane.source}): {lane.reason} -> `{lane.reference}`"
            )
    else:
        lines.append("- None detected.")

    lines.extend(["", "## Candidate Workstreams"])
    if report.candidate_workstreams:
        for candidate in report.candidate_workstreams:
            paths = ", ".join(f"`{path}`" for path in candidate.sample_paths)
            lines.append(
                f"- `{candidate.lane}` / `{candidate.task_id}`: {candidate.finding_count} "
                f"markers, top severity `{candidate.top_severity}`. {paths}"
            )
    else:
        lines.append("- No safe candidates detected outside no-touch lanes.")

    lines.extend(["", "## High-Severity Findings"])
    high = [finding for finding in report.findings if finding.severity == "high"][:25]
    if high:
        for finding in high:
            lines.append(
                f"- `{finding.area}` `{finding.path}:{finding.line}` "
                f"{finding.marker}: {finding.evidence}"
            )
    else:
        lines.append("- None in scanned scope.")

    lines.append("")
    return "\n".join(lines)


def to_json(report: OrchestratorMap) -> str:
    return json.dumps(asdict(report), indent=2, sort_keys=True)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a read-only Nuzantara agent orchestration map."
    )
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect."
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument(
        "--output", type=Path, help="Optional output file. Stdout is used when omitted."
    )
    parser.add_argument(
        "--scan-root",
        action="append",
        dest="scan_roots",
        help="Relative path to scan for incomplete markers. Can be repeated.",
    )
    parser.add_argument("--finding-limit", type=int, default=200)
    parser.add_argument("--per-area-limit", type=int, default=30)
    parser.add_argument(
        "--remote",
        action="append",
        dest="remote_specs",
        help="Remote target as name=host:/abs/repo/path, host:/abs/repo/path, or default key m5/air.",
    )
    parser.add_argument(
        "--include-m5", action="store_true", help="Shortcut for --remote m5."
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    scan_roots = args.scan_roots or list(DEFAULT_SCAN_ROOTS)
    remote_specs = list(args.remote_specs or [])
    if args.include_m5:
        remote_specs.append("m5")
    try:
        remote_targets = [parse_remote_target(spec) for spec in remote_specs]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = collect_live_map(
        args.repo_root,
        scan_roots=scan_roots,
        finding_limit=args.finding_limit,
        per_area_limit=args.per_area_limit,
        remote_targets=remote_targets,
    )
    rendered = to_json(report) if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
        if not rendered.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
