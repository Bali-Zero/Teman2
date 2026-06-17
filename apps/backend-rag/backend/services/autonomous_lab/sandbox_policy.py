"""Sandbox policy contracts for Autonomous Lab experiments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

SANDBOX_POLICY_VERSION = "autonomous-lab-v1-sandbox-policy"


class SandboxNetworkMode(str, Enum):
    """Network behavior available to Lab sandbox runners."""

    DENY_ALL = "deny_all"
    ALLOWLIST_ONLY = "allowlist_only"


class SandboxFilesystemMode(str, Enum):
    """Filesystem behavior available to Lab sandbox runners."""

    WORKTREE_ONLY = "worktree_only"
    READ_ONLY_REPO_PLUS_ARTIFACTS = "read_only_repo_plus_artifacts"


@dataclass(frozen=True)
class SandboxFilesystemPolicy:
    """Filesystem contract for a prod-like isolated experiment."""

    mode: SandboxFilesystemMode
    repo_read_only: bool
    writable_roots: tuple[str, ...]
    forbidden_roots: tuple[str, ...]

    def to_receipt(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "repo_read_only": self.repo_read_only,
            "writable_roots": list(self.writable_roots),
            "forbidden_roots": list(self.forbidden_roots),
        }


@dataclass(frozen=True)
class SandboxNetworkPolicy:
    """Network contract for a prod-like isolated experiment."""

    mode: SandboxNetworkMode
    allowed_hosts: tuple[str, ...]
    allow_localhost: bool

    def to_receipt(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "allowed_hosts": list(self.allowed_hosts),
            "allow_localhost": self.allow_localhost,
        }


@dataclass(frozen=True)
class SandboxExecutionLimits:
    """Execution limits enforced before a sandbox runner can run commands."""

    timeout_seconds: int
    max_output_bytes: int
    max_artifact_bytes: int
    env_allowlist: tuple[str, ...]

    def to_receipt(self) -> dict[str, Any]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "max_artifact_bytes": self.max_artifact_bytes,
            "env_allowlist": list(self.env_allowlist),
        }


@dataclass(frozen=True)
class SandboxPolicy:
    """Receipt-safe policy required before any experiment execution."""

    version: str
    filesystem: SandboxFilesystemPolicy
    network: SandboxNetworkPolicy
    execution_limits: SandboxExecutionLimits
    require_policy_before_execution: bool
    production_writes_allowed: bool
    deploy_merge_push_allowed: bool
    raw_data_persistence_allowed: bool
    stdout_redaction_required: bool
    prod_like_input_contract: str

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "filesystem": self.filesystem.to_receipt(),
            "network": self.network.to_receipt(),
            "execution_limits": self.execution_limits.to_receipt(),
            "require_policy_before_execution": self.require_policy_before_execution,
            "production_writes_allowed": self.production_writes_allowed,
            "deploy_merge_push_allowed": self.deploy_merge_push_allowed,
            "raw_data_persistence_allowed": self.raw_data_persistence_allowed,
            "stdout_redaction_required": self.stdout_redaction_required,
            "prod_like_input_contract": self.prod_like_input_contract,
        }


def default_sandbox_policy() -> SandboxPolicy:
    """Return the fail-closed default sandbox policy."""
    return SandboxPolicy(
        version=SANDBOX_POLICY_VERSION,
        filesystem=SandboxFilesystemPolicy(
            mode=SandboxFilesystemMode.READ_ONLY_REPO_PLUS_ARTIFACTS,
            repo_read_only=True,
            writable_roots=(
                ".worktrees/<lane>-<task>/",
                "artifacts/autonomous_lab/",
                "tmp/autonomous_lab/",
            ),
            forbidden_roots=(
                "~/.ssh/",
                "~/.config/",
                "~/.claude/",
                "~/.codex/",
                "apps/backend-rag/.env",
                "apps/mouth/.env",
            ),
        ),
        network=SandboxNetworkPolicy(
            mode=SandboxNetworkMode.DENY_ALL,
            allowed_hosts=(),
            allow_localhost=False,
        ),
        execution_limits=SandboxExecutionLimits(
            timeout_seconds=600,
            max_output_bytes=1_000_000,
            max_artifact_bytes=10_000_000,
            env_allowlist=("CI", "NODE_ENV", "PATH", "PYTHONPATH"),
        ),
        require_policy_before_execution=True,
        production_writes_allowed=False,
        deploy_merge_push_allowed=False,
        raw_data_persistence_allowed=False,
        stdout_redaction_required=True,
        prod_like_input_contract="synthetic_or_redacted_fixtures_only",
    )


__all__ = [
    "SANDBOX_POLICY_VERSION",
    "SandboxExecutionLimits",
    "SandboxFilesystemMode",
    "SandboxFilesystemPolicy",
    "SandboxNetworkMode",
    "SandboxNetworkPolicy",
    "SandboxPolicy",
    "default_sandbox_policy",
]
