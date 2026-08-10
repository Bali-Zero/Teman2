#!/usr/bin/env python3
"""Read-only LLM client drift audit for the Pro/M5 fleet.

The release lock and placement policy live in ``infra/fleet/llm-clients.json``.
This program only resolves executables and invokes declared ``--version``-style
commands.  It never installs, updates, logs in, reads credential files, or
prints command output that might contain account data.

``--fleet`` ships this same stdlib-only probe to the selected SSH peers over
stdin.  It does not require the peer checkout to already contain this version
of the script, which is important when the audit is being used to diagnose
repository drift in the first place.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import socket
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "infra" / "fleet" / "llm-clients.json"
DEFAULT_NODES = REPO_ROOT / "infra" / "fleet" / "nodes.json"

AUDIT_SCHEMA_VERSION = 1
MAX_PROBE_WORKERS = 4
DEFAULT_COMMAND_TIMEOUT = 30.0
DEFAULT_SSH_TIMEOUT = 240.0
VALID_PRESENCE = {"required", "allowed", "forbidden"}
VALID_SCOPES = {"pro-m5", "host-specific"}
VALID_ROLLOUTS = {"tracked", "canary_required"}
VALID_HOST_ROLES = {"pro", "m5", "mini"}
VERSION_RE = re.compile(r"(?<![0-9])([0-9]+(?:\.[0-9]+){1,3}(?:[-+][0-9A-Za-z.-]+)?)")
SAFE_ROLE_RE = re.compile(r"^[a-z0-9_-]+$")
SAFE_SSH_ALIAS_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.@-]*$")
SAFE_HOME_RE = re.compile(r"^/Users/[A-Za-z0-9._-]+$")
MISE_SYMLINK_TARGETS = (
    "~/.local/bin/mise",
    "~/.local/share/mise/installs/mise/*/bin/mise",
    "/opt/homebrew/Cellar/mise/*/bin/mise",
    "/usr/local/Cellar/mise/*/bin/mise",
)

# The manifest is data, not an extension mechanism.  Every executable probe is
# reviewed here so a manifest-only change cannot turn this observational tool
# into an arbitrary command runner.
SAFE_CLIENT_PROBES: dict[str, dict[str, Any]] = {
    "codex": {
        "binary": "codex",
        "version": ("--version",),
        "auth": ("login", "status"),
        # Codex may use a reviewed dispatcher plus an npm install and fallback.
        # Treat them as equivalent only while every concrete path is healthy
        # and reports the exact same version; any divergence remains a collision.
        "allow_equivalent_install_paths": True,
        "symlink_targets": (
            "~/.local/share/mise/installs/node/*/lib/node_modules/@openai/codex/bin/codex.js",
            "/opt/homebrew/lib/node_modules/@openai/codex/bin/codex.js",
            "/usr/local/lib/node_modules/@openai/codex/bin/codex.js",
        ),
    },
    "claude": {
        "binary": "claude",
        "version": ("--version",),
        "auth": ("auth", "status"),
        "symlink_targets": (
            "~/.local/share/claude/versions/*",
            "~/.local/share/mise/installs/node/*/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe",
        ),
    },
    "agy": {"binary": "agy", "version": ("--version",)},
    "kimi": {
        "binary": "kimi",
        "version": ("--version",),
        "extra_paths": ("~/.kimi-code/bin/kimi",),
        "symlink_targets": ("~/.kimi-code/bin/kimi",),
    },
    "nlm": {
        "binary": "nlm",
        "version": ("--version",),
        "auth": ("login", "--check"),
        "symlink_targets": ("~/.local/share/uv/tools/notebooklm-mcp-cli/bin/nlm",),
    },
    "gemini": {
        "binary": "gemini",
        "version": ("--version",),
        "symlink_targets": (
            "~/.local/share/mise/installs/node/*/lib/node_modules/@google/gemini-cli/bundle/gemini.js",
            "/opt/homebrew/lib/node_modules/@google/gemini-cli/bundle/gemini.js",
            "/usr/local/lib/node_modules/@google/gemini-cli/bundle/gemini.js",
        ),
    },
    "grok": {
        "binary": "grok",
        "version": ("--version",),
        "extra_paths": ("~/.grok/bin/grok",),
        "symlink_targets": ("~/.grok/downloads/grok-*-macos-aarch64",),
    },
    "opencode": {
        "binary": "opencode",
        "version": ("--version",),
        "symlink_targets": (
            "~/.local/share/mise/installs/node/*/lib/node_modules/opencode-ai/bin/opencode.exe",
            "/opt/homebrew/lib/node_modules/opencode-ai/bin/opencode.exe",
            "/usr/local/lib/node_modules/opencode-ai/bin/opencode.exe",
        ),
    },
    "qwen": {
        "binary": "qwen",
        "version": ("--version",),
        "symlink_targets": (
            "~/.local/share/mise/installs/node/*/lib/node_modules/@qwen-code/qwen-code/cli-entry.js",
            "/opt/homebrew/lib/node_modules/@qwen-code/qwen-code/cli-entry.js",
            "/usr/local/lib/node_modules/@qwen-code/qwen-code/cli-entry.js",
        ),
    },
    "jules": {"binary": "jules", "version": ("version",)},
    "pi": {
        "binary": "pi",
        "version": ("--version",),
        "symlink_targets": (
            "~/.local/share/mise/installs/node/*/lib/node_modules/@mariozechner/pi-coding-agent/dist/cli.js",
            "/opt/homebrew/lib/node_modules/@mariozechner/pi-coding-agent/dist/cli.js",
            "/usr/local/lib/node_modules/@mariozechner/pi-coding-agent/dist/cli.js",
        ),
    },
    "aider": {
        "binary": "aider",
        "version": ("--version",),
        "symlink_targets": ("~/.local/share/uv/tools/aider-chat/bin/aider",),
    },
    "cline": {
        "binary": "cline",
        "version": ("--version",),
        "symlink_targets": (
            "/opt/homebrew/lib/node_modules/cline/dist/cli.mjs",
            "/usr/local/lib/node_modules/cline/dist/cli.mjs",
        ),
    },
    "ollama": {
        "binary": "ollama",
        "version": ("--version",),
        "symlink_targets": (
            "/opt/homebrew/Cellar/ollama/*/bin/ollama",
            "/usr/local/Cellar/ollama/*/bin/ollama",
        ),
    },
    "openclaw": {
        "binary": "openclaw",
        "version": ("--version",),
        "symlink_targets": (
            "/opt/homebrew/lib/node_modules/openclaw/openclaw.mjs",
            "/usr/local/lib/node_modules/openclaw/openclaw.mjs",
        ),
    },
}


class AuditConfigError(ValueError):
    """The checked-in manifest or fleet roster is not safe to execute."""


@dataclass(frozen=True)
class CommandResult:
    """Small subprocess result that is easy to fake without leaking output."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[Sequence[str], float], CommandResult]
RemoteRunner = Callable[[Sequence[str], str, float], CommandResult]


def subprocess_runner(argv: Sequence[str], timeout: float) -> CommandResult:
    """Run a bounded local observation command and capture its output."""

    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return CommandResult(returncode=124)
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def subprocess_remote_runner(
    argv: Sequence[str], script_source: str, timeout: float
) -> CommandResult:
    """Run the in-memory probe on a peer; no peer-side files are written."""

    try:
        completed = subprocess.run(
            list(argv),
            input=script_source,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return CommandResult(returncode=124)
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object with a configuration-oriented error."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditConfigError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditConfigError(f"{path} must contain a JSON object")
    return value


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Fail closed before any manifest-provided command is invoked."""

    if manifest.get("schema_version") != AUDIT_SCHEMA_VERSION:
        raise AuditConfigError(
            f"unsupported manifest schema_version={manifest.get('schema_version')!r}"
        )
    version_policy = manifest.get("version_policy")
    if (
        not isinstance(version_policy, dict)
        or version_policy.get("mode") != "latest-stable"
    ):
        raise AuditConfigError("version_policy.mode must be latest-stable")
    if not version_policy.get("lock_refreshed_at"):
        raise AuditConfigError("version_policy.lock_refreshed_at is required")

    clients = manifest.get("clients")
    if not isinstance(clients, list) or not clients:
        raise AuditConfigError("manifest.clients must be a non-empty list")

    seen: set[str] = set()
    for index, raw_client in enumerate(clients):
        if not isinstance(raw_client, dict):
            raise AuditConfigError(f"clients[{index}] must be an object")
        client_id = raw_client.get("id")
        if not isinstance(client_id, str) or not SAFE_ROLE_RE.fullmatch(client_id):
            raise AuditConfigError(f"clients[{index}].id is invalid")
        if client_id in seen:
            raise AuditConfigError(f"duplicate client id: {client_id}")
        seen.add(client_id)

        safe_probe = SAFE_CLIENT_PROBES.get(client_id)
        if safe_probe is None:
            raise AuditConfigError(
                f"{client_id}: client has no reviewed probe allowlist"
            )

        alignment_scope = raw_client.get("alignment_scope")
        if alignment_scope not in VALID_SCOPES:
            raise AuditConfigError(f"{client_id}: invalid alignment_scope")
        if raw_client.get("require_version_parity") is not (
            alignment_scope == "pro-m5"
        ):
            raise AuditConfigError(
                f"{client_id}: require_version_parity must match alignment_scope"
            )
        if raw_client.get("rollout") not in VALID_ROLLOUTS:
            raise AuditConfigError(f"{client_id}: invalid rollout")
        if raw_client.get("rollout") == "canary_required":
            rollout_metadata = raw_client.get("rollout_metadata")
            if (
                not isinstance(rollout_metadata, dict)
                or not rollout_metadata.get("current_pin")
                or rollout_metadata.get("candidate") != raw_client.get("target_version")
                or not rollout_metadata.get("blocked_by")
                or not isinstance(
                    rollout_metadata.get("maintenance_window_required"), bool
                )
            ):
                raise AuditConfigError(
                    f"{client_id}: canary_required needs explicit rollout_metadata"
                )
        installer = raw_client.get("installer")
        if (
            not isinstance(installer, dict)
            or not installer.get("kind")
            or not installer.get("identity")
        ):
            raise AuditConfigError(
                f"{client_id}: installer kind and identity are required"
            )
        binaries = raw_client.get("binaries")
        if binaries != [safe_probe["binary"]]:
            raise AuditConfigError(
                f"{client_id}: binaries do not match the reviewed probe"
            )
        version_args = raw_client.get("version_args")
        if version_args != list(safe_probe["version"]):
            raise AuditConfigError(
                f"{client_id}: version_args do not match the reviewed probe"
            )
        allowed_candidates = {
            f"~/.local/bin/{safe_probe['binary']}",
            f"/opt/homebrew/bin/{safe_probe['binary']}",
            f"/usr/local/bin/{safe_probe['binary']}",
            *safe_probe.get("extra_paths", ()),
        }
        candidate_paths = raw_client.get("candidate_paths")
        if (
            not isinstance(candidate_paths, list)
            or not all(isinstance(path, str) for path in candidate_paths)
            or len(candidate_paths) != len(set(candidate_paths))
            or any(path not in allowed_candidates for path in candidate_paths)
        ):
            raise AuditConfigError(
                f"{client_id}: candidate_paths are outside the reviewed allowlist"
            )
        target_version = str(raw_client.get("target_version", ""))
        minimum_version = str(raw_client.get("minimum_version", ""))
        if parse_version(target_version) != target_version:
            raise AuditConfigError(f"{client_id}: target_version is invalid")
        if parse_version(minimum_version) != minimum_version:
            raise AuditConfigError(f"{client_id}: minimum_version is invalid")
        host_policy = raw_client.get("host_policy")
        if not isinstance(host_policy, dict) or set(host_policy) != VALID_HOST_ROLES:
            raise AuditConfigError(
                f"{client_id}: host_policy must explicitly cover "
                f"{','.join(sorted(VALID_HOST_ROLES))}"
            )
        if any(value not in VALID_PRESENCE for value in host_policy.values()):
            raise AuditConfigError(f"{client_id}: invalid host presence policy")
        auth_probe = raw_client.get("auth_probe")
        expected_auth = safe_probe.get("auth")
        expected_auth_probe = ["{binary}", *expected_auth] if expected_auth else None
        if auth_probe != expected_auth_probe:
            raise AuditConfigError(
                f"{client_id}: auth_probe does not match the reviewed probe"
            )


def validate_nodes(nodes: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return a minimal, validated roster safe for SSH argv construction."""

    raw_nodes = nodes.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise AuditConfigError("nodes.json must contain a non-empty nodes list")
    validated: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_nodes):
        if not isinstance(item, dict):
            raise AuditConfigError(f"nodes[{index}] must be an object")
        name = str(item.get("name", "")).lower()
        hostname = str(item.get("hostname", "")).lower()
        ssh_alias = str(item.get("ssh_alias", ""))
        if name not in VALID_HOST_ROLES or name in seen:
            raise AuditConfigError(f"nodes[{index}].name is invalid or duplicated")
        if not hostname or not SAFE_SSH_ALIAS_RE.fullmatch(ssh_alias):
            raise AuditConfigError(
                f"nodes[{index}] has an unsafe hostname or ssh_alias"
            )
        seen.add(name)
        validated.append({"name": name, "hostname": hostname, "ssh_alias": ssh_alias})
    return validated


def normalize_hostname(value: str) -> str:
    """Normalize macOS hostnames without conflating machine roles."""

    return value.strip().lower().split(".", maxsplit=1)[0]


def detect_host_role(nodes: Sequence[Mapping[str, str]], hostname: str) -> str | None:
    """Resolve a hostname to the checked-in fleet role."""

    normalized = normalize_hostname(hostname)
    for node in nodes:
        if normalize_hostname(node["hostname"]) == normalized:
            return node["name"]
    return None


def parse_version(text: str) -> str | None:
    """Extract a version only; raw command output is never retained."""

    match = VERSION_RE.search(text)
    return match.group(1) if match else None


def _version_parts(version: str) -> tuple[tuple[int, ...], str | None]:
    if parse_version(version) != version:
        raise AuditConfigError(f"invalid canonical version: {version!r}")
    core_and_pre = version.split("+", maxsplit=1)[0]
    core, separator, prerelease = core_and_pre.partition("-")
    return tuple(
        int(part) for part in core.split(".")
    ), prerelease if separator else None


def compare_versions(left: str, right: str) -> int:
    """Compare numeric releases and simple prerelease suffixes."""

    left_numbers, left_pre = _version_parts(left)
    right_numbers, right_pre = _version_parts(right)
    width = max(len(left_numbers), len(right_numbers))
    left_numbers += (0,) * (width - len(left_numbers))
    right_numbers += (0,) * (width - len(right_numbers))
    if left_numbers != right_numbers:
        return -1 if left_numbers < right_numbers else 1
    if left_pre == right_pre:
        return 0
    if left_pre is None:
        return 1
    if right_pre is None:
        return -1

    def token_key(value: str) -> tuple[tuple[int, int | str], ...]:
        tokens: list[tuple[int, int | str]] = []
        for token in re.split(r"[.-]", value):
            tokens.append((0, int(token)) if token.isdigit() else (1, token.lower()))
        return tuple(tokens)

    left_key = token_key(left_pre)
    right_key = token_key(right_pre)
    return -1 if left_key < right_key else 1


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _expand_path(path: Path, home: Path) -> Path:
    value = str(path)
    if value == "~" or value.startswith("~/"):
        value = value.replace("~", str(home), 1)
    return Path(value).absolute()


def _reviewed_launch_path(client: Mapping[str, Any], path: Path, home: Path) -> bool:
    safe_probe = SAFE_CLIENT_PROBES[client["id"]]
    binary = safe_probe["binary"]
    exact_paths = {
        home / ".local" / "bin" / binary,
        Path("/opt/homebrew/bin") / binary,
        Path("/usr/local/bin") / binary,
        home / ".local" / "share" / "mise" / "shims" / binary,
        *(Path(value) for value in safe_probe.get("extra_paths", ())),
    }
    expanded = _expand_path(path, home)
    if expanded in {_expand_path(item, home) for item in exact_paths}:
        return True
    mise_root = home / ".local" / "share" / "mise" / "installs" / "node"
    try:
        relative = expanded.relative_to(_expand_path(mise_root, home))
    except ValueError:
        return False
    return len(relative.parts) == 3 and relative.parts[1:] == ("bin", binary)


def _matches_path_pattern(path: Path, pattern: str, home: Path) -> bool:
    expanded_pattern = str(_expand_path(Path(pattern), home))
    expression = re.escape(expanded_pattern).replace(r"\*", r"[^/]+")
    return re.fullmatch(expression, str(_expand_path(path, home))) is not None


def _reviewed_realpath(
    client: Mapping[str, Any], path: Path, realpath: Path, home: Path
) -> bool:
    """Allow only exact per-client symlink targets, never a broad prefix."""

    expanded_path = _expand_path(path, home)
    expanded_realpath = _expand_path(realpath, home)
    if expanded_path == expanded_realpath:
        return True
    patterns = list(SAFE_CLIENT_PROBES[client["id"]].get("symlink_targets", ()))
    if "/mise/shims/" in str(expanded_path):
        patterns.extend(MISE_SYMLINK_TARGETS)
    return any(
        _matches_path_pattern(expanded_realpath, pattern, home) for pattern in patterns
    )


def _is_mise_shim(path: Path, realpath: Path, reviewed: bool) -> bool:
    return reviewed and (Path(realpath).name == "mise" or "/mise/shims/" in str(path))


def resolve_binaries(
    client: Mapping[str, Any],
    *,
    path_value: str,
    home: Path,
) -> list[dict[str, Any]]:
    """Resolve every PATH and candidate executable in deterministic order."""

    matches: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    safe_probe = SAFE_CLIENT_PROBES[client["id"]]

    def add(path: Path, source: str) -> None:
        expanded = _expand_path(path, home)
        absolute = str(expanded)
        if absolute in seen_paths or not _is_executable(expanded):
            return
        lexically_reviewed = _reviewed_launch_path(client, expanded, home)
        if source == "candidate" and not lexically_reviewed:
            raise AuditConfigError(
                f"{client['id']}: candidate path escaped the reviewed allowlist"
            )
        seen_paths.add(absolute)
        resolved = expanded.resolve()
        realpath = str(resolved)
        reviewed = lexically_reviewed and _reviewed_realpath(
            client, expanded, resolved, home
        )
        is_mise_shim = _is_mise_shim(expanded, resolved, reviewed)
        match = {
            "path": absolute,
            "realpath": realpath,
            "source": "mise-shim" if is_mise_shim else source,
            "shim_kind": "mise" if is_mise_shim else None,
            "reviewed": reviewed,
        }
        if not reviewed:
            match.update(version="not-probed", version_returncode=None)
        elif safe_probe.get("allow_equivalent_install_paths"):
            match["reviewed_equivalent_path"] = True
        matches.append(match)

    for binary in client["binaries"]:
        for directory in path_value.split(os.pathsep):
            add(Path(directory or os.curdir) / binary, "PATH")
    for candidate in client.get("candidate_paths", []):
        add(Path(str(candidate)), "candidate")
    return matches


def _observe_versions(
    paths: list[dict[str, Any]],
    version_args: Sequence[str],
    *,
    runner: CommandRunner,
    timeout: float,
) -> None:
    """Attach sanitized versions to paths, invoking each real binary once."""

    observed: dict[str, tuple[str | None, int]] = {}
    for match in paths:
        if match.get("reviewed") is not True:
            continue
        realpath = match["realpath"]
        if realpath not in observed:
            result = runner([match["path"], *version_args], timeout)
            observed[realpath] = (
                parse_version(f"{result.stdout}\n{result.stderr}"),
                result.returncode,
            )
        version, returncode = observed[realpath]
        match["version"] = version if version is not None else "unknown"
        match["version_returncode"] = returncode


def _auth_boolean(
    client: Mapping[str, Any],
    selected_path: str,
    *,
    runner: CommandRunner,
    timeout: float,
) -> bool | None:
    """Return only an exit-code-derived boolean; discard all account output."""

    probe = client.get("auth_probe")
    if not isinstance(probe, list):
        return None
    argv = [selected_path if item == "{binary}" else item for item in probe]
    return runner(argv, timeout).returncode == 0


def _evaluate_client(
    client: Mapping[str, Any],
    role: str,
    paths: list[dict[str, Any]],
    *,
    check_auth: bool,
    runner: CommandRunner,
    timeout: float,
) -> dict[str, Any]:
    presence = str(client["host_policy"][role])
    reviewed_paths = [item for item in paths if item.get("reviewed") is True]
    unreviewed_paths = [item for item in paths if item.get("reviewed") is not True]
    executable_present = bool(paths)
    installed = bool(reviewed_paths)
    realpaths = {item["realpath"] for item in reviewed_paths}
    concrete_realpaths = {
        item["realpath"] for item in reviewed_paths if item.get("shim_kind") is None
    }
    collision_realpaths = concrete_realpaths or realpaths
    distinct_install_paths = len(collision_realpaths) > 1
    allow_equivalent_paths = bool(
        SAFE_CLIENT_PROBES[client["id"]].get("allow_equivalent_install_paths")
    )
    concrete_observations = [
        item for item in reviewed_paths if item["realpath"] in collision_realpaths
    ]
    equivalent_install_paths = (
        distinct_install_paths
        and allow_equivalent_paths
        and all(
            item.get("version_returncode") == 0
            and item.get("version") not in {None, "unknown"}
            and item.get("reviewed_equivalent_path") is True
            for item in concrete_observations
        )
        and len({item["version"] for item in concrete_observations}) == 1
    )
    binary_collision = distinct_install_paths and not equivalent_install_paths
    selected = reviewed_paths[0] if reviewed_paths else None
    version = selected.get("version") if selected else None
    version_returncode = selected.get("version_returncode") if selected else None
    path_probe_divergence = bool(reviewed_paths) and any(
        item.get("version_returncode") != version_returncode
        or item.get("version") != selected.get("version")
        for item in reviewed_paths
    )
    if version == "unknown":
        version = None

    result: dict[str, Any] = {
        "id": client["id"],
        "display_name": client["display_name"],
        "runtime_class": client["runtime_class"],
        "alignment_scope": client["alignment_scope"],
        "presence": presence,
        "rollout": client["rollout"],
        "rollout_metadata": client.get("rollout_metadata"),
        "target_version": client["target_version"],
        "minimum_version": client["minimum_version"],
        "installed": installed,
        "selected_version": version,
        "version_returncode": version_returncode,
        "selected_path": selected["path"] if selected else None,
        "path_shadowing": len(paths) > 1,
        "binary_collision": binary_collision,
        "equivalent_install_paths": equivalent_install_paths,
        "path_probe_divergence": path_probe_divergence,
        "unreviewed_path_shadow": bool(unreviewed_paths),
        "paths": paths,
        "authenticated": None,
        "compliant": False,
    }

    if presence == "forbidden":
        if executable_present:
            result["status"] = "FORBIDDEN_PRESENT"
        else:
            result.update(status="FORBIDDEN_ABSENT", compliant=True)
        return result
    if unreviewed_paths:
        result["status"] = "UNREVIEWED_PATH_SHADOW"
        return result
    if not installed:
        if presence == "required":
            result["status"] = "REQUIRED_MISSING"
        else:
            result.update(status="ALLOWED_ABSENT", compliant=True)
        return result
    if binary_collision:
        result["status"] = "BINARY_COLLISION"
        return result
    if path_probe_divergence:
        result["status"] = "PATH_PROBE_DIVERGENCE"
        return result
    if version_returncode != 0:
        result["status"] = "VERSION_COMMAND_FAILED"
        return result
    if version is None:
        result["status"] = "VERSION_UNPARSEABLE"
        return result

    minimum = str(client["minimum_version"])
    target = str(client["target_version"])
    if compare_versions(version, minimum) < 0:
        result["status"] = "BELOW_MINIMUM"
        return result
    if client["rollout"] == "canary_required":
        result["status"] = (
            "CANARY_REQUIRED"
            if compare_versions(version, target) != 0
            else "CANARY_EVIDENCE_REQUIRED"
        )
        return result
    comparison = compare_versions(version, target)
    if comparison < 0:
        result["status"] = "BEHIND_TARGET"
        return result
    if comparison > 0:
        result["status"] = "UNVERIFIED_AHEAD_OF_LOCK"
        return result

    if check_auth and selected is not None:
        result["authenticated"] = _auth_boolean(
            client,
            selected["path"],
            runner=runner,
            timeout=timeout,
        )
    if check_auth and result["authenticated"] is False:
        result["status"] = "AUTH_REQUIRED"
        return result
    result.update(status="ALIGNED", compliant=True)
    return result


def audit_host(
    manifest: Mapping[str, Any],
    role: str,
    *,
    hostname: str | None = None,
    path_value: str | None = None,
    home: Path | None = None,
    check_auth: bool = False,
    runner: CommandRunner = subprocess_runner,
    timeout: float = DEFAULT_COMMAND_TIMEOUT,
) -> dict[str, Any]:
    """Audit one host against its role-specific policy."""

    validate_manifest(manifest)
    if role not in VALID_HOST_ROLES:
        raise AuditConfigError(f"unsafe host role: {role!r}")
    effective_home = home or Path.home()
    effective_path = (
        path_value if path_value is not None else os.environ.get("PATH", "")
    )
    resolved_clients: list[tuple[Mapping[str, Any], list[dict[str, Any]]]] = []
    for raw_client in manifest["clients"]:
        paths = resolve_binaries(
            raw_client, path_value=effective_path, home=effective_home
        )
        resolved_clients.append((raw_client, paths))

    worker_count = min(MAX_PROBE_WORKERS, len(resolved_clients))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        observations = [
            executor.submit(
                _observe_versions,
                paths,
                raw_client["version_args"],
                runner=runner,
                timeout=timeout,
            )
            for raw_client, paths in resolved_clients
        ]
        for observation in observations:
            observation.result()

        evaluations = [
            executor.submit(
                _evaluate_client,
                raw_client,
                role,
                paths,
                check_auth=check_auth,
                runner=runner,
                timeout=timeout,
            )
            for raw_client, paths in resolved_clients
        ]
        clients = [evaluation.result() for evaluation in evaluations]
    failures = [item["id"] for item in clients if not item["compliant"]]
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": {
            "role": role,
            "hostname": normalize_hostname(hostname or socket.gethostname()),
            "home": str(_expand_path(effective_home, effective_home)),
        },
        "manifest": {
            "schema_version": manifest["schema_version"],
            "version_policy": manifest["version_policy"]["mode"],
            "lock_refreshed_at": manifest["version_policy"]["lock_refreshed_at"],
        },
        "check_auth": check_auth,
        "clients": clients,
        "summary": {
            "client_count": len(clients),
            "non_compliant": failures,
            "compliant": not failures,
        },
    }


def _manifest_payload(manifest: Mapping[str, Any]) -> str:
    encoded = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii")


def _manifest_from_payload(payload: str) -> dict[str, Any]:
    try:
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        manifest = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditConfigError("invalid internal probe payload") from exc
    if not isinstance(manifest, dict):
        raise AuditConfigError("internal probe payload is not an object")
    validate_manifest(manifest)
    return manifest


def _probe_remote(
    node: Mapping[str, str],
    manifest: Mapping[str, Any],
    *,
    script_source: str,
    check_auth: bool,
    command_timeout: float,
    ssh_timeout: float,
    runner: RemoteRunner,
) -> dict[str, Any]:
    def failed(status: str) -> dict[str, Any]:
        return {
            "host": {"role": node["name"], "hostname": node["hostname"]},
            "probe_status": status,
            "summary": {"compliant": False, "non_compliant": ["peer-probe"]},
            "clients": [],
        }

    argv = [
        "/usr/bin/ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={max(1, int(ssh_timeout))}",
        node["ssh_alias"],
        "/usr/bin/python3",
        "-",
        "--probe-payload",
        _manifest_payload(manifest),
        "--host-role",
        node["name"],
        "--json",
        "--timeout",
        str(command_timeout),
    ]
    if check_auth:
        argv.append("--check-auth")
    result = runner(argv, script_source, ssh_timeout)
    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError:
        return failed("UNREACHABLE_OR_INVALID_REPLY")
    required_client_keys = {
        "id",
        "alignment_scope",
        "presence",
        "rollout",
        "target_version",
        "minimum_version",
        "status",
        "installed",
        "selected_version",
        "version_returncode",
        "selected_path",
        "path_shadowing",
        "binary_collision",
        "equivalent_install_paths",
        "path_probe_divergence",
        "unreviewed_path_shadow",
        "paths",
        "authenticated",
        "compliant",
    }

    def valid_path_observation(path: Any) -> bool:
        if (
            not isinstance(path, dict)
            or not isinstance(path.get("path"), str)
            or not isinstance(path.get("realpath"), str)
            or path.get("source") not in {"PATH", "candidate", "mise-shim"}
            or path.get("shim_kind") not in {None, "mise"}
            or not isinstance(path.get("reviewed"), bool)
        ):
            return False
        if path["reviewed"]:
            version = path.get("version")
            return (
                isinstance(version, str)
                and (version == "unknown" or parse_version(version) == version)
                and isinstance(path.get("version_returncode"), int)
            )
        return (
            path.get("source") in {"PATH", "candidate"}
            and path.get("shim_kind") is None
            and path.get("version") == "not-probed"
            and path.get("version_returncode") is None
        )

    clients = decoded.get("clients") if isinstance(decoded, dict) else None
    reply_clients_valid = isinstance(clients, list) and all(
        isinstance(client, dict)
        and required_client_keys.issubset(client)
        and isinstance(client.get("compliant"), bool)
        and isinstance(client.get("installed"), bool)
        and isinstance(client.get("paths"), list)
        and all(valid_path_observation(path) for path in client["paths"])
        for client in clients
    )
    if not isinstance(decoded, dict) or not reply_clients_valid:
        return failed("INVALID_REPLY_SCHEMA")
    host = decoded.get("host")
    summary = decoded.get("summary")
    expected_ids = [client["id"] for client in manifest["clients"]]
    actual_ids = [client["id"] for client in clients]
    expected_manifest = {
        "schema_version": manifest["schema_version"],
        "version_policy": manifest["version_policy"]["mode"],
        "lock_refreshed_at": manifest["version_policy"]["lock_refreshed_at"],
    }

    def no_runner(argv: Sequence[str], timeout: float) -> CommandResult:
        raise AssertionError("remote reply validation must not execute commands")

    reported_home_value = host.get("home") if isinstance(host, dict) else None
    reported_home = (
        Path(reported_home_value)
        if isinstance(reported_home_value, str)
        and SAFE_HOME_RE.fullmatch(reported_home_value)
        else None
    )

    def path_semantics_match(
        raw_client: Mapping[str, Any], path: Mapping[str, Any]
    ) -> bool:
        if reported_home is None:
            return False
        launch_path = Path(str(path["path"]))
        realpath = Path(str(path["realpath"]))
        if not launch_path.is_absolute() or not realpath.is_absolute():
            return False
        lexically_reviewed = _reviewed_launch_path(
            raw_client, launch_path, reported_home
        )
        expected_reviewed = lexically_reviewed and _reviewed_realpath(
            raw_client, launch_path, realpath, reported_home
        )
        expected_shim = _is_mise_shim(launch_path, realpath, expected_reviewed)
        expected_equivalence = bool(
            expected_reviewed
            and SAFE_CLIENT_PROBES[raw_client["id"]].get(
                "allow_equivalent_install_paths"
            )
        )
        if path.get("source") == "candidate" and not lexically_reviewed:
            return False
        return (
            path.get("reviewed") is expected_reviewed
            and path.get("shim_kind") == ("mise" if expected_shim else None)
            and (path.get("source") == "mise-shim") is expected_shim
            and bool(path.get("reviewed_equivalent_path", False))
            is expected_equivalence
        )

    reply_matches_manifest = actual_ids == expected_ids and reported_home is not None
    for raw_client, reported in zip(manifest["clients"], clients):
        if not reply_matches_manifest:
            break
        if not all(
            path_semantics_match(raw_client, path) for path in reported["paths"]
        ):
            reply_matches_manifest = False
            break
        expected = _evaluate_client(
            raw_client,
            node["name"],
            reported["paths"],
            check_auth=False,
            runner=no_runner,
            timeout=command_timeout,
        )
        reported_auth = reported.get("authenticated")
        should_report_auth = (
            check_auth
            and raw_client.get("auth_probe")
            and expected["status"] == "ALIGNED"
        )
        if should_report_auth:
            if not isinstance(reported_auth, bool):
                reply_matches_manifest = False
                break
            expected["authenticated"] = reported_auth
            if expected["status"] == "ALIGNED" and reported_auth is False:
                expected.update(status="AUTH_REQUIRED", compliant=False)
        elif reported_auth is not None:
            reply_matches_manifest = False
            break
        comparison_keys = {
            "id",
            "display_name",
            "runtime_class",
            "alignment_scope",
            "presence",
            "rollout",
            "rollout_metadata",
            "target_version",
            "minimum_version",
            "installed",
            "selected_version",
            "version_returncode",
            "selected_path",
            "path_shadowing",
            "binary_collision",
            "equivalent_install_paths",
            "path_probe_divergence",
            "unreviewed_path_shadow",
            "authenticated",
            "status",
            "compliant",
        }
        if any(reported.get(key) != expected.get(key) for key in comparison_keys):
            reply_matches_manifest = False
            break

    recomputed_failures = [
        client["id"] for client in clients if not client["compliant"]
    ]
    recomputed_compliant = not recomputed_failures
    if (
        decoded.get("schema_version") != AUDIT_SCHEMA_VERSION
        or decoded.get("manifest") != expected_manifest
        or decoded.get("check_auth") is not check_auth
        or not isinstance(host, dict)
        or host.get("role") != node["name"]
        or normalize_hostname(str(host.get("hostname", "")))
        != normalize_hostname(node["hostname"])
        or actual_ids != expected_ids
        or not reply_matches_manifest
        or not isinstance(summary, dict)
        or summary.get("client_count") != len(clients)
        or summary.get("non_compliant") != recomputed_failures
        or summary.get("compliant") is not recomputed_compliant
    ):
        return failed("INVALID_REPLY_SCHEMA")
    expected_returncode = 0 if recomputed_compliant else 1
    if result.returncode != expected_returncode:
        return failed("EXIT_VERDICT_MISMATCH")
    decoded["probe_status"] = "ANSWERED"
    return decoded


def compare_pro_m5(
    manifest: Mapping[str, Any], audits: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Compare only declared light-client parity; never heavy runtimes."""

    by_role = {
        str(audit.get("host", {}).get("role")): audit
        for audit in audits
        if isinstance(audit.get("host"), dict)
    }
    comparisons: list[dict[str, Any]] = []
    if "pro" not in by_role or "m5" not in by_role:
        return comparisons
    pro_clients = {item["id"]: item for item in by_role["pro"].get("clients", [])}
    m5_clients = {item["id"]: item for item in by_role["m5"].get("clients", [])}
    for client in manifest["clients"]:
        if client.get("alignment_scope") != "pro-m5" or not client.get(
            "require_version_parity"
        ):
            continue
        pro = pro_clients.get(client["id"])
        m5 = m5_clients.get(client["id"])
        pro_required = bool(pro and pro.get("presence") == "required")
        m5_required = bool(m5 and m5.get("presence") == "required")
        both_installed = bool(
            pro and m5 and pro.get("installed") and m5.get("installed")
        )
        if not ((pro_required and m5_required) or both_installed):
            # Optional tools may intentionally exist on only one host. Their
            # exact target is still enforced wherever installed, but absence
            # on the other node is not cross-host drift.
            continue
        pro_version = pro.get("selected_version") if pro else None
        m5_version = m5.get("selected_version") if m5 else None
        same = bool(pro_version and m5_version and pro_version == m5_version)
        comparisons.append(
            {
                "client": client["id"],
                "scope": "pro-m5",
                "pro_version": pro_version,
                "m5_version": m5_version,
                "status": "PARITY" if same else "VERSION_DRIFT",
                "compliant": same,
            }
        )
    return comparisons


def audit_fleet(
    manifest: Mapping[str, Any],
    nodes: Sequence[Mapping[str, str]],
    roles: Sequence[str],
    *,
    local_role: str | None,
    script_source: str,
    check_auth: bool = False,
    command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
    ssh_timeout: float = DEFAULT_SSH_TIMEOUT,
    local_runner: CommandRunner = subprocess_runner,
    remote_runner: RemoteRunner = subprocess_remote_runner,
) -> dict[str, Any]:
    """Audit selected roster roles, using SSH only for peers."""

    requested = set(roles)
    known = {node["name"] for node in nodes}
    unknown = sorted(requested - known)
    if unknown:
        raise AuditConfigError(f"unknown fleet roles: {', '.join(unknown)}")
    audits: list[dict[str, Any]] = []
    for node in nodes:
        if node["name"] not in requested:
            continue
        if node["name"] == local_role:
            audit = audit_host(
                manifest,
                node["name"],
                hostname=socket.gethostname(),
                check_auth=check_auth,
                runner=local_runner,
                timeout=command_timeout,
            )
            audit["probe_status"] = "LOCAL"
        else:
            audit = _probe_remote(
                node,
                manifest,
                script_source=script_source,
                check_auth=check_auth,
                command_timeout=command_timeout,
                ssh_timeout=ssh_timeout,
                runner=remote_runner,
            )
        audits.append(audit)
    comparisons = compare_pro_m5(manifest, audits)
    node_failures = [
        str(audit.get("host", {}).get("role", "unknown"))
        for audit in audits
        if not audit.get("summary", {}).get("compliant", False)
    ]
    parity_failures = [item["client"] for item in comparisons if not item["compliant"]]
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "fleet",
        "roles": list(roles),
        "nodes": audits,
        "comparisons": comparisons,
        "summary": {
            "non_compliant_nodes": node_failures,
            "parity_drift": parity_failures,
            "compliant": not node_failures and not parity_failures,
        },
    }


def render_table(report: Mapping[str, Any]) -> str:
    """Render a compact operator table without raw command/auth output."""

    audits = report.get("nodes") if report.get("mode") == "fleet" else [report]
    lines = [
        "ROLE  CLIENT      SCOPE          POLICY     VERSION       TARGET        STATUS",
        "----  ----------  -------------  ---------  ------------  ------------  --------------------------",
    ]
    for audit in audits:
        role = str(audit.get("host", {}).get("role", "?"))
        if not audit.get("clients"):
            lines.append(
                f"{role:<4}  {'-':<10}  {'-':<13}  {'-':<9}  {'-':<12}  {'-':<12}  "
                f"{audit.get('probe_status', 'NO_REPLY')}"
            )
            continue
        for client in audit["clients"]:
            version = client.get("selected_version") or "-"
            status = str(client["status"])
            if client.get("authenticated") is False and status != "AUTH_REQUIRED":
                status += "+AUTH_REQUIRED"
            lines.append(
                f"{role:<4}  {client['id']:<10}  {client['alignment_scope']:<13}  "
                f"{client['presence']:<9}  {version:<12}  {client['target_version']:<12}  "
                f"{status}"
            )
    if report.get("mode") == "fleet":
        for comparison in report.get("comparisons", []):
            if not comparison["compliant"]:
                lines.append(
                    f"DRIFT pro/m5 {comparison['client']}: "
                    f"{comparison['pro_version'] or '-'} != {comparison['m5_version'] or '-'}"
                )
    summary = report.get("summary", {})
    lines.append(f"VERDICT: {'ALIGNED' if summary.get('compliant') else 'DRIFT'}")
    return "\n".join(lines)


def _parse_roles(value: str) -> list[str]:
    roles = [item.strip().lower() for item in value.split(",") if item.strip()]
    if not roles or any(not SAFE_ROLE_RE.fullmatch(role) for role in roles):
        raise argparse.ArgumentTypeError(
            "roles must be a comma-separated safe role list"
        )
    return roles


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--fleet", action="store_true", help="audit selected SSH peers")
    parser.add_argument(
        "--roles",
        type=_parse_roles,
        default=["pro", "m5"],
        help="comma-separated fleet roles (default: pro,m5)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="run declared read-only auth probes; outputs are suppressed and only booleans remain",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_COMMAND_TIMEOUT,
        help="per-command timeout",
    )
    parser.add_argument("--ssh-timeout", type=float, default=DEFAULT_SSH_TIMEOUT)
    parser.add_argument("--host-role", help=argparse.SUPPRESS)
    parser.add_argument("--probe-payload", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = (
            _manifest_from_payload(args.probe_payload)
            if args.probe_payload
            else load_json(args.manifest)
        )
        validate_manifest(manifest)
        nodes_data = load_json(args.nodes) if not args.probe_payload else {"nodes": []}
        nodes = validate_nodes(nodes_data) if not args.probe_payload else []
        if args.probe_payload:
            if args.host_role not in VALID_HOST_ROLES:
                raise AuditConfigError(
                    "an internal peer probe requires a valid --host-role"
                )
            role = args.host_role
        else:
            if args.host_role is not None:
                raise AuditConfigError(
                    "--host-role is reserved for internal peer probes"
                )
            role = detect_host_role(nodes, socket.gethostname())
        if role is None:
            raise AuditConfigError("current hostname is not in nodes.json")
        if args.timeout <= 0 or args.ssh_timeout <= 0:
            raise AuditConfigError("timeouts must be positive")

        if args.fleet:
            if args.probe_payload:
                raise AuditConfigError(
                    "an internal peer probe cannot recursively run --fleet"
                )
            report = audit_fleet(
                manifest,
                nodes,
                args.roles,
                local_role=role,
                script_source=Path(__file__).read_text(encoding="utf-8"),
                check_auth=args.check_auth,
                command_timeout=args.timeout,
                ssh_timeout=args.ssh_timeout,
            )
        else:
            report = audit_host(
                manifest,
                role,
                check_auth=args.check_auth,
                timeout=args.timeout,
            )
    except AuditConfigError as exc:
        sys.stderr.write(f"llm-fleet-audit: {exc}\n")
        return 2

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_table(report) + "\n")
    return 0 if report.get("summary", {}).get("compliant", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
