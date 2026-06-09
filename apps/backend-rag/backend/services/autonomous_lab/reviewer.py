"""Deterministic review guardrails for autonomous lab run receipts."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from backend.services.autonomous_lab.command_policy import (
    ALLOWED_VERIFICATION_COMMANDS,
    is_allowed_lab_command,
    is_allowed_verification_command,
    is_allowed_worktree_command,
)
from backend.services.autonomous_lab.planner import GateSeverity, LabRun
from backend.services.autonomous_lab.receipt_safety import (
    receipt_safe_evidence,
    shorten_receipt_value,
)

DEFAULT_ALLOWED_TARGET_PREFIXES = (
    "apps/backend-rag/backend/services/autonomous_lab/",
    "apps/backend-rag/backend/tests/unit/services/autonomous_lab/",
    "research/operations/autonomous-lab/",
)
DEFAULT_ALLOWED_TARGET_PATHS = (
    "scripts/autonomous_lab_draft.py",
    "scripts/autonomous_lab_run.py",
)
DEFAULT_ALLOWED_VERIFICATION_COMMANDS = ALLOWED_VERIFICATION_COMMANDS

_RAW_FIELD_NAMES = {"body", "content", "full_text", "raw", "raw_text", "text", "transcript"}
_RAW_MARKER_RE = re.compile(
    r"\b(?:RAW(?:_[A-Z0-9]+){1,}|[A-Z0-9]+_(?:MUST_NOT_LEAK|SHOULD_NOT_APPEAR))\b"
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"<>,;]{12,}"
)
_SECRET_QUERY_KEY_RE = re.compile(
    r"(?i)(?:^|[?&])(?:access[_-]?token|api[_-]?key|key|password|secret|signature|sig|token)="
)
_GOOGLE_WORKSPACE_WRITE_RE = re.compile(
    r"(?i)\b(?:google\s+(?:workspace|drive|docs|sheets)|gdrive|gam|clasp)\b"
    r".{0,80}\b(?:append|batchupdate|create|delete|insert|patch|update|write)\b"
)
_COMMAND_SEGMENT_RE = r"[^\n;&|]*"
_COMMAND_BLOCK_PATTERNS = (
    (
        "deploy_command",
        re.compile(
            rf"(?i)\b(?:fly|flyctl)\b(?={_COMMAND_SEGMENT_RE}\bdeploy\b)"
            rf"|\bvercel\b(?={_COMMAND_SEGMENT_RE}(?:\bdeploy\b|--prod\b))"
            rf"|\b(?:npm|pnpm|yarn)\b(?={_COMMAND_SEGMENT_RE}\bdeploy\b)"
            rf"|\bdocker\b(?={_COMMAND_SEGMENT_RE}\bpush\b)"
            rf"|\bkubectl\b(?={_COMMAND_SEGMENT_RE}\b(?:apply|rollout|set)\b)"
            rf"|\bgcloud\b(?={_COMMAND_SEGMENT_RE}\brun\b{_COMMAND_SEGMENT_RE}\bdeploy\b)"
            rf"|\bterraform\b(?={_COMMAND_SEGMENT_RE}\bapply\b)"
        ),
        "deployment commands are not allowed in lab receipts",
    ),
    (
        "push_command",
        re.compile(rf"(?i)\bgit\b(?={_COMMAND_SEGMENT_RE}\bpush\b)"),
        "git push is not allowed",
    ),
    (
        "merge_command",
        re.compile(
            rf"(?i)\bgit\b(?={_COMMAND_SEGMENT_RE}\b(?:merge|rebase)\b)"
            rf"|\bgh\b(?={_COMMAND_SEGMENT_RE}\bpr\b{_COMMAND_SEGMENT_RE}\bmerge\b)"
        ),
        "merge or rebase commands are not allowed",
    ),
    (
        "unsafe_command",
        re.compile(
            r"(?i)\brm\s+-[A-Za-z]*r[A-Za-z]*f\b"
            r"|\brm\s+-[A-Za-z]*f[A-Za-z]*r\b"
            r"|\bsudo\b"
            r"|\bchmod\s+777\b"
            r"|\bchown\b"
            r"|\b(?:curl|wget)\b[^|]{0,200}\|\s*(?:bash|sh|zsh)\b"
            r"|\blaunchctl\s+(?:bootstrap|kickstart|load)\b"
            r"|\bfly\s+ssh\b"
        ),
        "unsafe shell command is not allowed in lab receipts",
    ),
)


@dataclass(frozen=True)
class LabReviewFinding:
    """One deterministic reviewer finding."""

    rule_id: str
    severity: GateSeverity
    message: str
    location: str
    evidence: str | None = None

    def to_receipt(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "location": self.location,
        }
        if self.evidence is not None:
            payload["evidence"] = self.evidence
        return payload


@dataclass(frozen=True)
class LabReviewDecision:
    """Approve/block decision for a lab receipt review."""

    approved: bool
    blocked: bool
    findings: tuple[LabReviewFinding, ...]

    @property
    def blockers(self) -> tuple[LabReviewFinding, ...]:
        return tuple(
            finding for finding in self.findings if finding.severity == GateSeverity.BLOCKER
        )

    @property
    def warnings(self) -> tuple[LabReviewFinding, ...]:
        return tuple(
            finding for finding in self.findings if finding.severity == GateSeverity.WARNING
        )

    def to_receipt(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "blocked": self.blocked,
            "findings": [finding.to_receipt() for finding in self.findings],
            "blocker_count": len(self.blockers),
            "warning_count": len(self.warnings),
        }


class AutonomousLabReviewer:
    """Review a LabRun receipt without mutating repo state or executing commands."""

    def __init__(
        self,
        *,
        allowed_target_prefixes: Iterable[str] = DEFAULT_ALLOWED_TARGET_PREFIXES,
        allowed_target_paths: Iterable[str] = DEFAULT_ALLOWED_TARGET_PATHS,
        allowed_verification_commands: Iterable[str] = DEFAULT_ALLOWED_VERIFICATION_COMMANDS,
    ) -> None:
        self.allowed_target_prefixes = tuple(
            _normalize_prefix(prefix) for prefix in allowed_target_prefixes
        )
        self.allowed_target_paths = frozenset(
            _normalize_path(target_path) for target_path in allowed_target_paths
        )
        self.allowed_verification_commands = frozenset(
            command.strip() for command in allowed_verification_commands
        )

    def review(self, run_or_receipt: LabRun | Mapping[str, Any]) -> LabReviewDecision:
        if isinstance(run_or_receipt, LabRun):
            return self.review_receipt(run_or_receipt.to_receipt())
        return self.review_receipt(run_or_receipt)

    def review_receipt(self, receipt: Mapping[str, Any]) -> LabReviewDecision:
        findings: list[LabReviewFinding] = []
        findings.extend(self._review_planner_gates(receipt))
        findings.extend(self._review_target_paths(receipt))
        findings.extend(self._review_commands(receipt))
        findings.extend(self._review_workspace_writes(receipt))
        findings.extend(self._review_raw_leakage(receipt))
        findings.extend(self._review_verification(receipt))

        deduped = tuple(_dedupe_findings(findings))
        blocked = any(finding.severity == GateSeverity.BLOCKER for finding in deduped)
        return LabReviewDecision(approved=not blocked, blocked=blocked, findings=deduped)

    def _review_planner_gates(self, receipt: Mapping[str, Any]) -> list[LabReviewFinding]:
        gates = _run_scope(receipt).get("safety_gates", [])
        if not isinstance(gates, list):
            return [
                LabReviewFinding(
                    "malformed_safety_gates",
                    GateSeverity.BLOCKER,
                    "safety_gates must be a list",
                    "safety_gates",
                    type(gates).__name__,
                )
            ]

        findings: list[LabReviewFinding] = []
        for index, gate in enumerate(gates):
            if not isinstance(gate, Mapping):
                findings.append(
                    LabReviewFinding(
                        "malformed_safety_gate",
                        GateSeverity.BLOCKER,
                        "safety gate must be an object",
                        f"safety_gates[{index}]",
                        type(gate).__name__,
                    )
                )
                continue
            if gate.get("passed") is not False:
                continue
            name = str(gate.get("name", "unnamed_gate"))
            safe_name = _receipt_safe_evidence(name)
            findings.append(
                LabReviewFinding(
                    "google_workspace_write_request"
                    if name == "google_workspace_write_block"
                    else "failed_planner_gate",
                    _severity_from_value(gate.get("severity")),
                    f"planner safety gate failed: {safe_name}",
                    f"safety_gates[{index}]",
                    _receipt_safe_evidence(str(gate.get("detail", ""))),
                )
            )
        return findings

    def _review_target_paths(self, receipt: Mapping[str, Any]) -> list[LabReviewFinding]:
        plan = _simulation_plan(receipt)
        target_paths = plan.get("target_paths")
        if not isinstance(target_paths, list):
            return [
                LabReviewFinding(
                    "malformed_target_paths",
                    GateSeverity.BLOCKER,
                    "simulation_plan.target_paths must be a list",
                    "simulation_plan.target_paths",
                    type(target_paths).__name__,
                )
            ]

        findings: list[LabReviewFinding] = []
        for index, target_path in enumerate(target_paths):
            location = f"simulation_plan.target_paths[{index}]"
            if not isinstance(target_path, str):
                findings.append(
                    LabReviewFinding(
                        "unsafe_target_path",
                        GateSeverity.BLOCKER,
                        "target path must be a string",
                        location,
                        type(target_path).__name__,
                    )
                )
                continue
            reason = invalid_autonomous_lab_target_path_reason(
                target_path,
                allowed_target_prefixes=self.allowed_target_prefixes,
                allowed_target_paths=self.allowed_target_paths,
            )
            if reason:
                findings.append(
                    LabReviewFinding(
                        "unsafe_target_path",
                        GateSeverity.BLOCKER,
                        reason,
                        location,
                        _shorten(target_path),
                    )
                )
        return findings

    def _review_commands(self, receipt: Mapping[str, Any]) -> list[LabReviewFinding]:
        findings: list[LabReviewFinding] = []
        worktree_command = _simulation_plan(receipt).get("worktree_command")
        if not isinstance(worktree_command, str) or not worktree_command.strip():
            findings.append(
                LabReviewFinding(
                    "missing_worktree_command",
                    GateSeverity.BLOCKER,
                    "simulation_plan.worktree_command must be a non-empty string",
                    "simulation_plan.worktree_command",
                    type(worktree_command).__name__,
                )
            )

        for location, command in _command_strings(receipt):
            if (
                location == "simulation_plan.worktree_command"
                and not is_allowed_worktree_command(command)
            ):
                findings.append(
                    LabReviewFinding(
                        "worktree_command_not_allowlisted",
                        GateSeverity.BLOCKER,
                        "worktree command is not in the autonomous lab allowlist",
                        location,
                        _receipt_safe_evidence(command),
                    )
                )
            elif not is_allowed_lab_command(command):
                findings.append(
                    LabReviewFinding(
                        "command_not_allowlisted",
                        GateSeverity.BLOCKER,
                        "lab command is not in the autonomous lab allowlist",
                        location,
                        _receipt_safe_evidence(command),
                    )
                )
            for rule_id, pattern, message in _COMMAND_BLOCK_PATTERNS:
                if pattern.search(command):
                    findings.append(
                        LabReviewFinding(
                            rule_id,
                            GateSeverity.BLOCKER,
                            message,
                            location,
                            _receipt_safe_evidence(command),
                        )
                    )
        return findings

    def _review_workspace_writes(self, receipt: Mapping[str, Any]) -> list[LabReviewFinding]:
        findings: list[LabReviewFinding] = []
        for location, key, value in _walk_strings(receipt):
            if value == "workspace_write_requested" or key == "requires_google_workspace_write":
                findings.append(
                    LabReviewFinding(
                        "google_workspace_write_request",
                        GateSeverity.BLOCKER,
                        "Google Workspace write request is not allowed in lab receipts",
                        location,
                        _receipt_safe_evidence(value),
                    )
                )
            elif _GOOGLE_WORKSPACE_WRITE_RE.search(value):
                findings.append(
                    LabReviewFinding(
                        "google_workspace_write_request",
                        GateSeverity.BLOCKER,
                        "Google Workspace write request is not allowed in lab receipts",
                        location,
                        _receipt_safe_evidence(value),
                    )
                )
        return findings

    def _review_raw_leakage(self, receipt: Mapping[str, Any]) -> list[LabReviewFinding]:
        findings: list[LabReviewFinding] = []
        for location, key, value in _walk_strings(receipt):
            normalized_key = key.lower()
            if normalized_key in _RAW_FIELD_NAMES and _looks_like_raw_text(value):
                findings.append(
                    LabReviewFinding(
                        "raw_text_leakage",
                        GateSeverity.BLOCKER,
                        "receipt contains a raw-text-like field",
                        location,
                        _receipt_safe_evidence(value, force_fingerprint=True),
                    )
                )
            elif _RAW_MARKER_RE.search(value) or _SECRET_ASSIGNMENT_RE.search(value):
                findings.append(
                    LabReviewFinding(
                        "raw_text_leakage",
                        GateSeverity.BLOCKER,
                        "receipt contains raw-text-like leakage signal",
                        location,
                        _receipt_safe_evidence(value, force_fingerprint=True),
                    )
                )
        return findings

    def _review_verification(self, receipt: Mapping[str, Any]) -> list[LabReviewFinding]:
        plan = _simulation_plan(receipt)
        verification_commands = plan.get("verification_commands")
        target_paths = plan.get("target_paths")
        if not isinstance(verification_commands, list):
            return [
                LabReviewFinding(
                    "missing_verification",
                    GateSeverity.BLOCKER,
                    "simulation_plan.verification_commands must be a non-empty list",
                    "simulation_plan.verification_commands",
                    type(verification_commands).__name__,
                )
            ]

        findings: list[LabReviewFinding] = []
        for index, command in enumerate(verification_commands):
            if not isinstance(command, str) or not command.strip():
                continue
            normalized_command = command.strip()
            if (
                normalized_command not in self.allowed_verification_commands
                or not is_allowed_verification_command(normalized_command)
            ):
                findings.append(
                    LabReviewFinding(
                        "verification_command_not_allowlisted",
                        GateSeverity.BLOCKER,
                        "verification command is not in the autonomous lab allowlist",
                        f"simulation_plan.verification_commands[{index}]",
                        _receipt_safe_evidence(normalized_command),
                    )
                )
        if findings:
            return findings
        if any(isinstance(command, str) and command.strip() for command in verification_commands):
            return []
        has_targets = isinstance(target_paths, list) and any(
            isinstance(path, str) and path.strip() for path in target_paths
        )
        return [
            LabReviewFinding(
                "missing_verification",
                GateSeverity.BLOCKER if has_targets else GateSeverity.WARNING,
                "lab run must include verification commands before approval",
                "simulation_plan.verification_commands",
                "[]",
            )
        ]


def review_lab_run(run: LabRun) -> LabReviewDecision:
    return AutonomousLabReviewer().review(run)


def _normalize_prefix(prefix: str) -> str:
    normalized = PurePosixPath(prefix.strip()).as_posix().lstrip("./")
    return normalized if normalized.endswith("/") else f"{normalized}/"


def _normalize_path(target_path: str) -> str:
    return PurePosixPath(target_path.strip()).as_posix().lstrip("./")


def invalid_autonomous_lab_target_path_reason(
    target_path: str,
    *,
    allowed_target_prefixes: Iterable[str] = DEFAULT_ALLOWED_TARGET_PREFIXES,
    allowed_target_paths: Iterable[str] = DEFAULT_ALLOWED_TARGET_PATHS,
) -> str | None:
    """Return why a Lab target path is unsafe, or None when it is allowed."""
    candidate = target_path.strip()
    if not candidate:
        return "target path is empty"
    if "\x00" in candidate:
        return "target path contains a null byte"
    if "\\" in candidate:
        return "target path must use POSIX separators"
    if "://" in candidate:
        return "target path must be repository-relative, not a URI"
    if candidate.startswith("~"):
        return "target path must not be home-relative"

    path = PurePosixPath(candidate)
    if path.is_absolute():
        return "target path must be repository-relative"
    if ".." in path.parts:
        return "target path must not contain path traversal"

    normalized = path.as_posix().lstrip("./")
    allowed_paths = frozenset(_normalize_path(path_value) for path_value in allowed_target_paths)
    if normalized in allowed_paths:
        return None

    allowed_prefixes = tuple(_normalize_prefix(prefix) for prefix in allowed_target_prefixes)
    if not any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in allowed_prefixes
    ):
        return "target path is outside the autonomous lab write set"
    return None


def _simulation_plan(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    plan = _run_scope(receipt).get("simulation_plan", {})
    return plan if isinstance(plan, Mapping) else {}


def _command_strings(receipt: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    plan = _simulation_plan(receipt)
    worktree_command = plan.get("worktree_command")
    if isinstance(worktree_command, str):
        yield "simulation_plan.worktree_command", worktree_command

    verification_commands = plan.get("verification_commands")
    if isinstance(verification_commands, list):
        for index, command in enumerate(verification_commands):
            if isinstance(command, str):
                yield f"simulation_plan.verification_commands[{index}]", command

    yield from _extra_command_strings(receipt)
    run_scope = _run_scope(receipt)
    if run_scope is not receipt:
        yield from _extra_command_strings(run_scope, location_prefix="run.")


def _extra_command_strings(
    scope: Mapping[str, Any], *, location_prefix: str = ""
) -> Iterator[tuple[str, str]]:
    planned_only_commands = scope.get("planned_only_commands")
    if isinstance(planned_only_commands, list):
        for index, command in enumerate(planned_only_commands):
            if isinstance(command, str):
                yield f"{location_prefix}planned_only_commands[{index}]", command

    stage_results = scope.get("stage_results")
    if isinstance(stage_results, list):
        for stage_index, stage in enumerate(stage_results):
            if not isinstance(stage, Mapping):
                continue
            stage_commands = stage.get("planned_only_commands")
            if not isinstance(stage_commands, list):
                continue
            for command_index, command in enumerate(stage_commands):
                if isinstance(command, str):
                    yield (
                        f"{location_prefix}stage_results[{stage_index}]"
                        f".planned_only_commands[{command_index}]",
                        command,
                    )


def _run_scope(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    run = receipt.get("run")
    return run if isinstance(run, Mapping) else receipt


def _walk_strings(value: Any, path: str = "$", key: str = "") -> Iterator[tuple[str, str, str]]:
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            child_key_text = str(child_key)
            yield from _walk_strings(
                child_value,
                path=f"{path}.{child_key_text}",
                key=child_key_text,
            )
    elif isinstance(value, list):
        for index, child_value in enumerate(value):
            yield from _walk_strings(child_value, path=f"{path}[{index}]", key=key)
    elif isinstance(value, str):
        yield path, key, value


def _looks_like_raw_text(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if _RAW_MARKER_RE.search(stripped) or _SECRET_ASSIGNMENT_RE.search(stripped):
        return True
    words = re.findall(r"\w+", stripped)
    return len(words) >= 24 or stripped.count("\n") >= 2


def _receipt_safe_evidence(value: str, *, force_fingerprint: bool = False) -> str:
    return receipt_safe_evidence(value, force_fingerprint=force_fingerprint)


def _severity_from_value(value: Any) -> GateSeverity:
    try:
        return GateSeverity(str(value))
    except ValueError:
        return GateSeverity.BLOCKER


def _dedupe_findings(findings: Iterable[LabReviewFinding]) -> Iterator[LabReviewFinding]:
    seen: set[tuple[str, str, str | None]] = set()
    for finding in findings:
        key = (finding.rule_id, finding.location, finding.evidence)
        if key in seen:
            continue
        seen.add(key)
        yield finding


def _shorten(value: str, limit: int = 180) -> str:
    return shorten_receipt_value(value, limit=limit)


__all__ = [
    "DEFAULT_ALLOWED_TARGET_PATHS",
    "DEFAULT_ALLOWED_TARGET_PREFIXES",
    "DEFAULT_ALLOWED_VERIFICATION_COMMANDS",
    "AutonomousLabReviewer",
    "LabReviewDecision",
    "LabReviewFinding",
    "review_lab_run",
]
