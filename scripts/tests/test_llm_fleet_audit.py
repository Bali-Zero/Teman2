"""Tests for the read-only, fail-visible LLM fleet audit."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SPEC = importlib.util.spec_from_file_location(
    "llm_fleet_audit", REPO / "scripts" / "llm_fleet_audit.py"
)
assert SPEC and SPEC.loader
lfa = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lfa
SPEC.loader.exec_module(lfa)


@pytest.fixture(autouse=True)
def restore_safe_client_probes() -> Any:
    original = copy.deepcopy(lfa.SAFE_CLIENT_PROBES)
    yield
    lfa.SAFE_CLIENT_PROBES.clear()
    lfa.SAFE_CLIENT_PROBES.update(original)


def client(
    client_id: str = "tool",
    *,
    target: str = "1.2.3",
    minimum: str = "1.2.3",
    rollout: str = "tracked",
    scope: str = "pro-m5",
    policies: dict[str, str] | None = None,
    candidates: list[str] | None = None,
    auth: bool = False,
) -> dict[str, Any]:
    safe_probe: dict[str, Any] = {"binary": client_id, "version": ("--version",)}
    if auth:
        safe_probe["auth"] = ("auth", "status")
    lfa.SAFE_CLIENT_PROBES[client_id] = safe_probe
    host_policy = {"pro": "required", "m5": "required", "mini": "allowed"}
    if policies:
        host_policy.update(policies)
    value: dict[str, Any] = {
        "id": client_id,
        "display_name": client_id.title(),
        "runtime_class": "light-cloud-client",
        "alignment_scope": scope,
        "require_version_parity": scope == "pro-m5",
        "installer": {"kind": "fixture", "identity": f"fixture-{client_id}"},
        "binaries": [client_id],
        "candidate_paths": candidates or [],
        "version_args": ["--version"],
        "target_version": target,
        "minimum_version": minimum,
        "rollout": rollout,
        "host_policy": host_policy,
    }
    if auth:
        value["auth_probe"] = ["{binary}", "auth", "status"]
    if rollout == "canary_required":
        value["rollout_metadata"] = {
            "current_pin": minimum,
            "candidate": target,
            "blocked_by": "fixture canary",
            "maintenance_window_required": False,
        }
    return value


def manifest(*clients: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "version_policy": {
            "mode": "latest-stable",
            "lock_refreshed_at": "2026-08-10",
        },
        "clients": list(clients) or [client()],
    }


def executable(path: Path, body: str = "#!/bin/sh\necho 1.2.3\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


class FakeRunner:
    def __init__(self, versions: dict[str, str], auth_rc: int = 0) -> None:
        self.versions = versions
        self.auth_rc = auth_rc
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str], timeout: float) -> Any:
        self.calls.append(list(argv))
        if "auth" in argv:
            # Deliberately sensitive-looking output: the audit must discard it.
            return lfa.CommandResult(
                self.auth_rc,
                stdout="account=user@example.invalid token=do-not-emit",
            )
        return lfa.CommandResult(
            0,
            stdout=self.versions.get(str(Path(argv[0]).resolve()), "tool unknown"),
        )


def audit_one(
    tmp_path: Path,
    raw_client: dict[str, Any],
    *,
    role: str = "pro",
    runner: FakeRunner | None = None,
    check_auth: bool = False,
) -> dict[str, Any]:
    binary = executable(tmp_path / ".local" / "bin" / raw_client["binaries"][0])
    effective_runner = runner or FakeRunner({str(binary.resolve()): "tool 1.2.3"})
    return lfa.audit_host(
        manifest(raw_client),
        role,
        hostname="fixture-host",
        path_value=str(binary.parent),
        home=tmp_path,
        check_auth=check_auth,
        runner=effective_runner,
    )


def peer_client_report(
    raw_client: dict[str, Any],
    *,
    role: str = "m5",
    version: str = "1.2.3",
) -> dict[str, Any]:
    binary = raw_client["binaries"][0]
    path = f"/Users/fixture/.local/bin/{binary}"
    paths = [
        {
            "path": path,
            "realpath": path,
            "source": "PATH",
            "shim_kind": None,
            "reviewed": True,
            "version": version,
            "version_returncode": 0,
        }
    ]

    def no_runner(argv: Sequence[str], timeout: float) -> Any:
        raise AssertionError("peer fixture unexpectedly ran a command")

    return lfa._evaluate_client(
        raw_client,
        role,
        paths,
        check_auth=False,
        runner=no_runner,
        timeout=1,
    )


def peer_host_report(
    checked_manifest: dict[str, Any],
    clients: list[dict[str, Any]],
    *,
    role: str = "m5",
    hostname: str = "air-m5",
    home: str = "/Users/fixture",
    check_auth: bool = False,
) -> dict[str, Any]:
    failures = [item["id"] for item in clients if not item["compliant"]]
    return {
        "schema_version": 1,
        "host": {"role": role, "hostname": hostname, "home": home},
        "manifest": {
            "schema_version": checked_manifest["schema_version"],
            "version_policy": checked_manifest["version_policy"]["mode"],
            "lock_refreshed_at": checked_manifest["version_policy"][
                "lock_refreshed_at"
            ],
        },
        "check_auth": check_auth,
        "clients": clients,
        "summary": {
            "client_count": len(clients),
            "compliant": not failures,
            "non_compliant": failures,
        },
    }


def test_checked_in_manifest_is_valid_and_has_pinned_light_clients() -> None:
    checked = lfa.load_json(REPO / "infra" / "fleet" / "llm-clients.json")
    lfa.validate_manifest(checked)
    by_id = {item["id"]: item for item in checked["clients"]}
    assert checked["version_policy"]["mode"] == "latest-stable"
    assert checked["version_policy"]["lock_refreshed_at"] == "2026-08-11"
    assert "FLEET_TOPOLOGY.json" in checked["_doc"]
    assert by_id["codex"]["target_version"] == "0.147.0"
    assert by_id["claude"]["target_version"] == "2.1.226"
    assert by_id["kimi"]["target_version"] == "0.34.0"
    assert by_id["nlm"]["target_version"] == "0.9.8"
    assert by_id["nlm"]["auth_probe"] == ["{binary}", "login", "--check"]
    assert by_id["grok"]["target_version"] == "1.0.0"
    assert by_id["opencode"]["target_version"] == "1.18.16"
    assert by_id["qwen"]["target_version"] == "0.21.9"
    assert by_id["aider"]["target_version"] == "0.86.2"
    assert by_id["aider"]["rollout_metadata"]["current_pin"] == "0.86.2"
    assert by_id["aider"]["host_policy"]["pro"] == "required"
    assert by_id["aider"]["host_policy"]["m5"] == "required"
    assert by_id["cline"]["rollout_metadata"]["current_pin"] == "2.6.0"
    assert "codesign" in by_id["cline"]["rollout_metadata"]["blocked_by"]
    assert by_id["ollama"]["rollout_metadata"]["maintenance_window_required"] is True
    assert by_id["openclaw"]["rollout_metadata"]["maintenance_window_required"] is True
    assert by_id["ollama"]["host_policy"]["m5"] == "forbidden"
    assert by_id["openclaw"]["host_policy"]["m5"] == "forbidden"
    assert by_id["ollama"]["alignment_scope"] == "host-specific"
    assert by_id["ollama"]["rollout"] == "canary_required"


def test_checked_in_manifest_contains_no_email_address() -> None:
    text = (REPO / "infra" / "fleet" / "llm-clients.json").read_text(encoding="utf-8")
    assert re.search(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", text) is None


def test_ai_dispatch_status_delegates_to_roster_audit_not_stale_peer_logic() -> None:
    text = (REPO / "scripts" / "ai-dispatch.sh").read_text(encoding="utf-8")
    status_block = text.split("    status)", maxsplit=1)[1].split(
        "    help|*)", maxsplit=1
    )[0]
    assert 'llm_fleet_audit.py" --fleet --roles pro,m5' in status_block
    assert "--check-auth" in status_block
    assert "Air decommission" not in status_block
    assert 'exit "$audit_rc"' in status_block
    assert text.count("AIDER_ROUTE_RETIRED") == 2
    assert "openrouter/deepseek/deepseek-chat-v3-0324" not in text
    assert "openrouter/anthropic/claude-sonnet-4" not in text


def test_ai_dispatch_python_bridges_do_not_interpolate_user_input() -> None:
    text = (REPO / "scripts" / "ai-dispatch.sh").read_text(encoding="utf-8")
    assert "ctx = '''$SYSTEM_CTX'''" not in text
    assert "prompt = '''$PROMPT'''" not in text
    assert "query = '''$PROMPT'''" not in text
    assert "count = int('$count')" not in text
    assert 'python3 - "$CONTEXT_FILE" "$PROMPT"' in text
    assert 'python3 - "$PROMPT" "$count"' in text
    python_blocks = re.findall(r"<<'PY'\n(.*?)\nPY\n", text, flags=re.DOTALL)
    assert len(python_blocks) == 3
    for index, source in enumerate(python_blocks):
        compile(source, f"ai-dispatch-heredoc-{index}.py", "exec")


def test_manifest_rejects_command_injection_in_version_args() -> None:
    unsafe = client()
    unsafe["version_args"] = ["--version", "{credential}"]
    with pytest.raises(lfa.AuditConfigError, match="reviewed probe"):
        lfa.validate_manifest(manifest(unsafe))


def test_manifest_rejects_arbitrary_executable_candidate() -> None:
    unsafe = client()
    unsafe["candidate_paths"] = ["/bin/sh"]
    with pytest.raises(lfa.AuditConfigError, match="candidate_paths"):
        lfa.validate_manifest(manifest(unsafe))


def test_manifest_rejects_auth_probe_not_rooted_at_selected_binary() -> None:
    unsafe = client()
    unsafe["auth_probe"] = ["sh", "-c", "anything"]
    with pytest.raises(lfa.AuditConfigError, match="auth_probe"):
        lfa.validate_manifest(manifest(unsafe))


def test_manifest_requires_explicit_policy_for_every_fleet_role() -> None:
    unsafe = client()
    unsafe["host_policy"].pop("mini")
    with pytest.raises(lfa.AuditConfigError, match="explicitly cover"):
        lfa.validate_manifest(manifest(unsafe))


def test_manifest_scope_and_parity_flag_cannot_disagree() -> None:
    unsafe = client()
    unsafe["require_version_parity"] = False
    with pytest.raises(lfa.AuditConfigError, match="must match alignment_scope"):
        lfa.validate_manifest(manifest(unsafe))


@pytest.mark.parametrize("field", ["target_version", "minimum_version"])
def test_manifest_rejects_version_text_with_embedded_release(field: str) -> None:
    unsafe = client()
    unsafe[field] = "release v1.2.3"
    with pytest.raises(lfa.AuditConfigError, match=f"{field} is invalid"):
        lfa.validate_manifest(manifest(unsafe))


def test_detect_host_role_uses_normalized_roster_hostname() -> None:
    nodes = [
        {"name": "m5", "hostname": "air-m5", "ssh_alias": "air"},
        {"name": "pro", "hostname": "nuzantara", "ssh_alias": "pro"},
    ]
    assert lfa.detect_host_role(nodes, "Nuzantara.local") == "pro"
    assert lfa.detect_host_role(nodes, "Air-M5") == "m5"
    assert lfa.detect_host_role(nodes, "unknown") is None


def test_nodes_reject_ssh_alias_that_can_be_parsed_as_an_option() -> None:
    with pytest.raises(lfa.AuditConfigError, match="unsafe hostname or ssh_alias"):
        lfa.validate_nodes(
            {"nodes": [{"name": "m5", "hostname": "air-m5", "ssh_alias": "-Fconfig"}]}
        )


def test_resolve_binaries_preserves_path_order_and_detects_candidates(
    tmp_path: Path,
) -> None:
    first = executable(tmp_path / ".local" / "bin" / "tool")
    second = executable(
        tmp_path
        / ".local"
        / "share"
        / "mise"
        / "installs"
        / "node"
        / "22"
        / "bin"
        / "tool"
    )
    raw_client = client()
    paths = lfa.resolve_binaries(
        raw_client,
        path_value=os.pathsep.join([str(first.parent), str(second.parent)]),
        home=tmp_path,
    )
    assert [item["path"] for item in paths] == [str(first), str(second)]
    assert all(item["source"] == "PATH" for item in paths)


def test_candidate_path_finds_binary_missing_from_path(tmp_path: Path) -> None:
    candidate = executable(tmp_path / ".local" / "bin" / "tool")
    paths = lfa.resolve_binaries(
        client(candidates=[str(candidate)]), path_value="", home=tmp_path
    )
    assert paths == [
        {
            "path": str(candidate),
            "realpath": str(candidate.resolve()),
            "source": "candidate",
            "shim_kind": None,
            "reviewed": True,
        }
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("codex-cli 0.147.0", "0.147.0"),
        ("Claude Code v2.1.226", "2.1.226"),
        ("openclaw 2026.7.1-2", "2026.7.1-2"),
        ("no release here", None),
    ],
)
def test_parse_version(raw: str, expected: str | None) -> None:
    assert lfa.parse_version(raw) == expected


def test_compare_versions_handles_padding_and_prereleases() -> None:
    assert lfa.compare_versions("1.2", "1.2.0") == 0
    assert lfa.compare_versions("1.2.4", "1.2.3") > 0
    assert lfa.compare_versions("1.2.3-rc.1", "1.2.3") < 0
    assert lfa.compare_versions("2026.7.1-2", "2026.6.11") > 0


def test_required_exact_target_is_aligned(tmp_path: Path) -> None:
    report = audit_one(tmp_path, client())
    audited = report["clients"][0]
    assert audited["status"] == "ALIGNED"
    assert audited["compliant"] is True
    assert report["summary"]["compliant"] is True


def test_required_missing_is_not_a_false_green(tmp_path: Path) -> None:
    report = lfa.audit_host(
        manifest(client()),
        "pro",
        path_value="",
        home=tmp_path,
        runner=FakeRunner({}),
    )
    assert report["clients"][0]["status"] == "REQUIRED_MISSING"
    assert report["summary"]["compliant"] is False


def test_allowed_missing_and_forbidden_missing_are_compliant(tmp_path: Path) -> None:
    allowed = client("optional", policies={"pro": "allowed"})
    forbidden = client("heavy", policies={"pro": "forbidden"}, scope="host-specific")
    report = lfa.audit_host(
        manifest(allowed, forbidden),
        "pro",
        path_value="",
        home=tmp_path,
        runner=FakeRunner({}),
    )
    assert [item["status"] for item in report["clients"]] == [
        "ALLOWED_ABSENT",
        "FORBIDDEN_ABSENT",
    ]
    assert report["summary"]["compliant"] is True


def test_forbidden_present_fails_even_at_target_version(tmp_path: Path) -> None:
    report = audit_one(
        tmp_path,
        client(policies={"m5": "forbidden"}, scope="host-specific"),
        role="m5",
    )
    assert report["clients"][0]["status"] == "FORBIDDEN_PRESENT"
    assert report["summary"]["compliant"] is False


def test_two_distinct_real_binaries_are_a_fail_visible_collision(
    tmp_path: Path,
) -> None:
    first = executable(tmp_path / ".local" / "bin" / "tool")
    second = executable(
        tmp_path
        / ".local"
        / "share"
        / "mise"
        / "installs"
        / "node"
        / "22"
        / "bin"
        / "tool"
    )
    runner = FakeRunner(
        {str(first.resolve()): "tool 1.2.3", str(second.resolve()): "tool 1.2.3"}
    )
    report = lfa.audit_host(
        manifest(client()),
        "pro",
        path_value=os.pathsep.join([str(first.parent), str(second.parent)]),
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["path_shadowing"] is True
    assert audited["binary_collision"] is True
    assert audited["status"] == "BINARY_COLLISION"
    assert audited["compliant"] is False


def test_reviewed_dispatcher_and_install_are_equivalent_only_at_same_version(
    tmp_path: Path,
) -> None:
    raw_client = client("dispatcher")
    lfa.SAFE_CLIENT_PROBES["dispatcher"]["allow_equivalent_install_paths"] = True
    wrapper = executable(tmp_path / ".local" / "bin" / "dispatcher")
    install = executable(
        tmp_path
        / ".local"
        / "share"
        / "mise"
        / "installs"
        / "node"
        / "22"
        / "bin"
        / "dispatcher"
    )
    runner = FakeRunner(
        {
            str(wrapper.resolve()): "dispatcher 1.2.3",
            str(install.resolve()): "dispatcher 1.2.3",
        }
    )
    report = lfa.audit_host(
        manifest(raw_client),
        "pro",
        path_value=os.pathsep.join([str(wrapper.parent), str(install.parent)]),
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["path_shadowing"] is True
    assert audited["binary_collision"] is False
    assert audited["equivalent_install_paths"] is True
    assert audited["status"] == "ALIGNED"


def test_reviewed_equivalent_paths_still_fail_on_version_divergence(
    tmp_path: Path,
) -> None:
    raw_client = client("dispatcher_drift")
    lfa.SAFE_CLIENT_PROBES["dispatcher_drift"]["allow_equivalent_install_paths"] = True
    wrapper = executable(tmp_path / ".local" / "bin" / "dispatcher_drift")
    install = executable(
        tmp_path
        / ".local"
        / "share"
        / "mise"
        / "installs"
        / "node"
        / "22"
        / "bin"
        / "dispatcher_drift"
    )
    runner = FakeRunner(
        {
            str(wrapper.resolve()): "dispatcher 1.2.3",
            str(install.resolve()): "dispatcher 1.2.2",
        }
    )
    report = lfa.audit_host(
        manifest(raw_client),
        "pro",
        path_value=os.pathsep.join([str(wrapper.parent), str(install.parent)]),
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["binary_collision"] is True
    assert audited["equivalent_install_paths"] is False
    assert audited["status"] == "BINARY_COLLISION"


def test_unreviewed_shadow_path_is_never_executed(
    tmp_path: Path,
) -> None:
    raw_client = client("dispatcher_shadow")
    lfa.SAFE_CLIENT_PROBES["dispatcher_shadow"]["allow_equivalent_install_paths"] = True
    canonical = executable(tmp_path / ".local" / "bin" / "dispatcher_shadow")
    shadow = executable(tmp_path / "unreviewed" / "dispatcher_shadow")
    runner = FakeRunner(
        {
            str(canonical.resolve()): "dispatcher 1.2.3",
            str(shadow.resolve()): "dispatcher 1.2.3",
        }
    )
    report = lfa.audit_host(
        manifest(raw_client),
        "pro",
        path_value=os.pathsep.join([str(canonical.parent), str(shadow.parent)]),
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["binary_collision"] is False
    assert audited["equivalent_install_paths"] is False
    assert audited["unreviewed_path_shadow"] is True
    assert audited["status"] == "UNREVIEWED_PATH_SHADOW"
    assert audited["compliant"] is False
    assert [item["path"] for item in audited["paths"]] == [
        str(canonical),
        str(shadow),
    ]
    assert audited["paths"][1]["reviewed"] is False
    assert audited["paths"][1]["version"] == "not-probed"
    assert audited["paths"][1]["version_returncode"] is None
    assert len(runner.calls) == 1


def test_unreviewed_precedence_shadow_fails_without_execution(tmp_path: Path) -> None:
    raw_client = client("dispatcher_shadow")
    canonical = executable(tmp_path / ".local" / "bin" / "dispatcher_shadow")
    shadow = executable(tmp_path / "unreviewed" / "dispatcher_shadow")
    runner = FakeRunner(
        {
            str(canonical.resolve()): "dispatcher 1.2.3",
            str(shadow.resolve()): "dispatcher 9.9.9",
        }
    )
    report = lfa.audit_host(
        manifest(raw_client),
        "pro",
        path_value=os.pathsep.join([str(shadow.parent), str(canonical.parent)]),
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["status"] == "UNREVIEWED_PATH_SHADOW"
    assert [item["path"] for item in audited["paths"]] == [
        str(shadow),
        str(canonical),
    ]
    assert audited["selected_path"] == str(canonical)
    assert runner.calls == [[str(canonical), "--version"]]


@pytest.mark.parametrize("position", ["leading", "middle", "trailing"])
def test_empty_path_component_is_current_directory_and_never_ignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    position: str,
) -> None:
    raw_client = client()
    canonical = executable(tmp_path / ".local" / "bin" / "tool")
    shadow = executable(tmp_path / "working" / "tool")
    monkeypatch.chdir(shadow.parent)
    if position == "leading":
        path_value = os.pathsep + str(canonical.parent)
    elif position == "middle":
        path_value = os.pathsep.join(
            [str(canonical.parent), "", str(tmp_path / "missing")]
        )
    else:
        path_value = str(canonical.parent) + os.pathsep
    runner = FakeRunner(
        {
            str(canonical.resolve()): "tool 1.2.3",
            str(shadow.resolve()): "tool 9.9.9",
        }
    )
    report = lfa.audit_host(
        manifest(raw_client),
        "pro",
        path_value=path_value,
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["status"] == "UNREVIEWED_PATH_SHADOW"
    assert any(item["path"] == str(shadow) for item in audited["paths"])
    assert all(call[0] != str(shadow) for call in runner.calls)


def test_allowlisted_symlink_to_untrusted_target_is_not_executed(
    tmp_path: Path,
) -> None:
    target = executable(tmp_path / ".local" / "evil" / "tool")
    canonical = tmp_path / ".local" / "bin" / "tool"
    canonical.parent.mkdir(parents=True)
    canonical.symlink_to(target)
    runner = FakeRunner({str(target.resolve()): "tool 9.9.9"})
    report = lfa.audit_host(
        manifest(client()),
        "pro",
        path_value=str(canonical.parent),
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["status"] == "UNREVIEWED_PATH_SHADOW"
    assert audited["paths"][0]["reviewed"] is False
    assert audited["paths"][0]["realpath"] == str(target.resolve())
    assert runner.calls == []


def test_two_paths_to_same_real_binary_are_aliases_not_collision(
    tmp_path: Path,
) -> None:
    real = executable(tmp_path / ".local" / "bin" / "tool")
    raw_client = client()
    lfa.SAFE_CLIENT_PROBES["tool"] = {
        "binary": "tool",
        "version": ("--version",),
        "symlink_targets": ("~/.local/bin/tool",),
    }
    alias = (
        tmp_path
        / ".local"
        / "share"
        / "mise"
        / "installs"
        / "node"
        / "22"
        / "bin"
        / "tool"
    )
    alias.parent.mkdir(parents=True)
    alias.symlink_to(real)
    runner = FakeRunner({str(real.resolve()): "tool 1.2.3"})
    report = lfa.audit_host(
        manifest(raw_client),
        "pro",
        path_value=os.pathsep.join([str(alias.parent), str(real.parent)]),
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["path_shadowing"] is True
    assert audited["binary_collision"] is False
    assert audited["status"] == "ALIGNED"
    # The canonical executable is observed once, despite two launch paths.
    assert len(runner.calls) == 1


def test_mise_shim_plus_concrete_install_is_not_a_false_collision(
    tmp_path: Path,
) -> None:
    mise = executable(
        tmp_path
        / ".local"
        / "share"
        / "mise"
        / "installs"
        / "mise"
        / "1"
        / "bin"
        / "mise"
    )
    shim = tmp_path / ".local" / "share" / "mise" / "shims" / "tool"
    shim.parent.mkdir(parents=True)
    shim.symlink_to(mise)
    concrete = executable(tmp_path / ".local" / "bin" / "tool")
    runner = FakeRunner(
        {str(mise.resolve()): "tool 1.2.3", str(concrete.resolve()): "tool 1.2.3"}
    )
    report = lfa.audit_host(
        manifest(client()),
        "pro",
        path_value=os.pathsep.join([str(shim.parent), str(concrete.parent)]),
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["paths"][0]["shim_kind"] == "mise"
    assert audited["path_shadowing"] is True
    assert audited["binary_collision"] is False
    assert audited["status"] == "ALIGNED"


def test_mise_shim_version_divergence_is_fail_visible(tmp_path: Path) -> None:
    mise = executable(
        tmp_path
        / ".local"
        / "share"
        / "mise"
        / "installs"
        / "mise"
        / "1"
        / "bin"
        / "mise"
    )
    shim = tmp_path / ".local" / "share" / "mise" / "shims" / "tool"
    shim.parent.mkdir(parents=True)
    shim.symlink_to(mise)
    concrete = executable(tmp_path / ".local" / "bin" / "tool")
    runner = FakeRunner(
        {str(mise.resolve()): "tool 1.2.2", str(concrete.resolve()): "tool 1.2.3"}
    )
    report = lfa.audit_host(
        manifest(client()),
        "pro",
        path_value=os.pathsep.join([str(concrete.parent), str(shim.parent)]),
        home=tmp_path,
        runner=runner,
    )
    audited = report["clients"][0]
    assert audited["binary_collision"] is False
    assert audited["path_probe_divergence"] is True
    assert audited["status"] == "PATH_PROBE_DIVERGENCE"


@pytest.mark.parametrize(
    ("observed", "expected"),
    [
        ("tool 1.2.2", "BELOW_MINIMUM"),
        ("tool 1.2.4", "UNVERIFIED_AHEAD_OF_LOCK"),
        ("tool has no version", "VERSION_UNPARSEABLE"),
    ],
)
def test_version_drift_never_reports_aligned(
    tmp_path: Path, observed: str, expected: str
) -> None:
    binary = executable(tmp_path / ".local" / "bin" / "tool")
    runner = FakeRunner({str(binary.resolve()): observed})
    report = audit_one(tmp_path, client(), runner=runner)
    assert report["clients"][0]["status"] == expected
    assert report["summary"]["compliant"] is False


def test_nonzero_version_command_never_reports_aligned(tmp_path: Path) -> None:
    def failed_version(argv: Sequence[str], timeout: float) -> Any:
        return lfa.CommandResult(137, stdout="tool 1.2.3")

    report = audit_one(tmp_path, client(), runner=failed_version)
    audited = report["clients"][0]
    assert audited["selected_version"] == "1.2.3"
    assert audited["version_returncode"] == 137
    assert audited["status"] == "VERSION_COMMAND_FAILED"
    assert report["summary"]["compliant"] is False


@pytest.mark.parametrize("observed", ["tool 1.2.2", "tool 1.2.3"])
def test_canary_required_is_never_silently_aligned(
    tmp_path: Path, observed: str
) -> None:
    binary = executable(tmp_path / ".local" / "bin" / "tool")
    runner = FakeRunner({str(binary.resolve()): observed})
    report = audit_one(
        tmp_path,
        client(minimum="1.2.0", rollout="canary_required"),
        runner=runner,
    )
    assert report["clients"][0]["status"] in {
        "CANARY_REQUIRED",
        "CANARY_EVIDENCE_REQUIRED",
    }
    assert report["summary"]["compliant"] is False


def test_auth_is_default_off_and_when_enabled_exposes_only_boolean(
    tmp_path: Path,
) -> None:
    binary = executable(tmp_path / ".local" / "bin" / "tool")
    runner = FakeRunner({str(binary.resolve()): "tool 1.2.3"})
    default_report = audit_one(tmp_path, client(auth=True), runner=runner)
    assert default_report["clients"][0]["authenticated"] is None
    assert all("auth" not in call for call in runner.calls)

    checked = audit_one(
        tmp_path,
        client(auth=True),
        runner=runner,
        check_auth=True,
    )
    assert checked["clients"][0]["authenticated"] is True
    serialized = json.dumps(checked)
    assert "user@example.invalid" not in serialized
    assert "do-not-emit" not in serialized


def test_failed_auth_probe_is_fail_visible_when_requested(tmp_path: Path) -> None:
    binary = executable(tmp_path / ".local" / "bin" / "tool")
    runner = FakeRunner({str(binary.resolve()): "tool 1.2.3"}, auth_rc=1)
    checked = audit_one(
        tmp_path,
        client(auth=True),
        runner=runner,
        check_auth=True,
    )
    audited = checked["clients"][0]
    assert audited["authenticated"] is False
    assert audited["status"] == "AUTH_REQUIRED"
    assert checked["summary"]["compliant"] is False


def test_compare_pro_m5_checks_light_parity_but_skips_heavy_runtime() -> None:
    checked_manifest = manifest(
        client("codex"),
        client(
            "ollama",
            scope="host-specific",
            policies={"pro": "required", "m5": "forbidden"},
        ),
    )
    audits = [
        {
            "host": {"role": "pro"},
            "clients": [
                {
                    "id": "codex",
                    "presence": "required",
                    "installed": True,
                    "selected_version": "1.2.3",
                },
                {
                    "id": "ollama",
                    "presence": "required",
                    "installed": True,
                    "selected_version": "1.2.3",
                },
            ],
        },
        {
            "host": {"role": "m5"},
            "clients": [
                {
                    "id": "codex",
                    "presence": "required",
                    "installed": True,
                    "selected_version": "1.2.2",
                },
                {
                    "id": "ollama",
                    "presence": "forbidden",
                    "installed": False,
                    "selected_version": None,
                },
            ],
        },
    ]
    comparisons = lfa.compare_pro_m5(checked_manifest, audits)
    assert comparisons == [
        {
            "client": "codex",
            "scope": "pro-m5",
            "pro_version": "1.2.3",
            "m5_version": "1.2.2",
            "status": "VERSION_DRIFT",
            "compliant": False,
        }
    ]


def test_compare_pro_m5_does_not_require_parity_for_optional_absence() -> None:
    optional = client(
        "jules", policies={"pro": "allowed", "m5": "allowed", "mini": "allowed"}
    )
    audits = [
        {
            "host": {"role": "pro"},
            "clients": [
                {
                    "id": "jules",
                    "presence": "allowed",
                    "installed": True,
                    "selected_version": "1.2.3",
                }
            ],
        },
        {
            "host": {"role": "m5"},
            "clients": [
                {
                    "id": "jules",
                    "presence": "allowed",
                    "installed": False,
                    "selected_version": None,
                }
            ],
        },
    ]
    assert lfa.compare_pro_m5(manifest(optional), audits) == []


def test_remote_invalid_reply_is_not_misreported_as_clean() -> None:
    node = {"name": "m5", "hostname": "air-m5", "ssh_alias": "air"}

    def remote_runner(argv: Sequence[str], script_source: str, timeout: float) -> Any:
        assert argv[0] == "/usr/bin/ssh"
        assert "/usr/bin/python3" in argv
        assert "def audit_host" in script_source
        return lfa.CommandResult(0, stdout="not-json")

    result = lfa._probe_remote(
        node,
        manifest(client()),
        script_source="def audit_host(): pass",
        check_auth=False,
        command_timeout=1,
        ssh_timeout=2,
        runner=remote_runner,
    )
    assert result["probe_status"] == "UNREACHABLE_OR_INVALID_REPLY"
    assert result["summary"]["compliant"] is False


@pytest.mark.parametrize(
    ("reported_role", "returncode", "expected_status"),
    [
        ("pro", 0, "INVALID_REPLY_SCHEMA"),
        ("m5", 1, "EXIT_VERDICT_MISMATCH"),
    ],
)
def test_remote_reply_role_and_exit_must_match_verdict(
    reported_role: str, returncode: int, expected_status: str
) -> None:
    node = {"name": "m5", "hostname": "air-m5", "ssh_alias": "air"}
    raw_client = client()
    checked_manifest = manifest(raw_client)
    peer = peer_host_report(
        checked_manifest,
        [peer_client_report(raw_client)],
        role=reported_role,
    )

    def remote_runner(argv: Sequence[str], script_source: str, timeout: float) -> Any:
        return lfa.CommandResult(returncode, stdout=json.dumps(peer))

    result = lfa._probe_remote(
        node,
        checked_manifest,
        script_source="# probe",
        check_auth=False,
        command_timeout=1,
        ssh_timeout=2,
        runner=remote_runner,
    )
    assert result["probe_status"] == expected_status
    assert result["summary"]["compliant"] is False


def test_remote_reply_must_match_manifest() -> None:
    node = {"name": "m5", "hostname": "air-m5", "ssh_alias": "air"}
    raw_client = client()
    checked_manifest = manifest(raw_client)
    reported = peer_client_report(raw_client)
    reported["target_version"] = "9.9.9"
    peer = peer_host_report(checked_manifest, [reported])

    def remote_runner(argv: Sequence[str], script_source: str, timeout: float) -> Any:
        return lfa.CommandResult(0, stdout=json.dumps(peer))

    result = lfa._probe_remote(
        node,
        checked_manifest,
        script_source="# probe",
        check_auth=False,
        command_timeout=1,
        ssh_timeout=2,
        runner=remote_runner,
    )
    assert result["probe_status"] == "INVALID_REPLY_SCHEMA"
    assert result["summary"]["compliant"] is False


def test_remote_reply_cannot_self_declare_arbitrary_path_as_reviewed() -> None:
    node = {"name": "m5", "hostname": "air-m5", "ssh_alias": "air"}
    raw_client = client()
    checked_manifest = manifest(raw_client)
    reported = peer_client_report(raw_client)
    reported["paths"][0].update(path="/tmp/tool", realpath="/tmp/tool")
    reported["selected_path"] = "/tmp/tool"
    peer = peer_host_report(checked_manifest, [reported])

    def remote_runner(argv: Sequence[str], script_source: str, timeout: float) -> Any:
        return lfa.CommandResult(0, stdout=json.dumps(peer))

    result = lfa._probe_remote(
        node,
        checked_manifest,
        script_source="# probe",
        check_auth=False,
        command_timeout=1,
        ssh_timeout=2,
        runner=remote_runner,
    )
    assert result["probe_status"] == "INVALID_REPLY_SCHEMA"
    assert result["summary"]["compliant"] is False


def test_remote_reply_requires_auth_boolean_when_requested() -> None:
    node = {"name": "m5", "hostname": "air-m5", "ssh_alias": "air"}
    raw_client = client(auth=True)
    checked_manifest = manifest(raw_client)
    peer = peer_host_report(
        checked_manifest,
        [peer_client_report(raw_client)],
        check_auth=True,
    )

    def remote_runner(argv: Sequence[str], script_source: str, timeout: float) -> Any:
        return lfa.CommandResult(0, stdout=json.dumps(peer))

    result = lfa._probe_remote(
        node,
        checked_manifest,
        script_source="# probe",
        check_auth=True,
        command_timeout=1,
        ssh_timeout=2,
        runner=remote_runner,
    )
    assert result["probe_status"] == "INVALID_REPLY_SCHEMA"
    assert result["summary"]["compliant"] is False


@pytest.mark.parametrize(
    ("authenticated", "returncode", "expected_status", "expected_compliant"),
    [
        (True, 0, "ALIGNED", True),
        (False, 1, "AUTH_REQUIRED", False),
    ],
)
def test_remote_reply_accepts_recomputed_auth_verdict(
    authenticated: bool,
    returncode: int,
    expected_status: str,
    expected_compliant: bool,
) -> None:
    node = {"name": "m5", "hostname": "air-m5", "ssh_alias": "air"}
    raw_client = client(auth=True)
    checked_manifest = manifest(raw_client)
    reported = peer_client_report(raw_client)
    reported.update(
        authenticated=authenticated,
        status=expected_status,
        compliant=expected_compliant,
    )
    peer = peer_host_report(checked_manifest, [reported], check_auth=True)

    def remote_runner(argv: Sequence[str], script_source: str, timeout: float) -> Any:
        return lfa.CommandResult(returncode, stdout=json.dumps(peer))

    result = lfa._probe_remote(
        node,
        checked_manifest,
        script_source="# probe",
        check_auth=True,
        command_timeout=1,
        ssh_timeout=2,
        runner=remote_runner,
    )
    assert result["probe_status"] == "ANSWERED"
    assert result["clients"][0]["status"] == expected_status
    assert result["summary"]["compliant"] is expected_compliant


def test_fleet_report_includes_peer_noncompliance_and_parity_drift(
    tmp_path: Path,
) -> None:
    binary = executable(tmp_path / ".local" / "bin" / "tool")
    local_runner = FakeRunner({str(binary.resolve()): "tool 1.2.3"})
    nodes = [
        {"name": "pro", "hostname": "nuzantara", "ssh_alias": "pro"},
        {"name": "m5", "hostname": "air-m5", "ssh_alias": "air"},
    ]
    raw_client = client()
    lfa.SAFE_CLIENT_PROBES["tool"]["extra_paths"] = (str(binary),)
    checked_manifest = manifest(raw_client)
    peer = peer_host_report(
        checked_manifest,
        [peer_client_report(raw_client, version="1.2.2")],
    )

    def remote_runner(argv: Sequence[str], script_source: str, timeout: float) -> Any:
        return lfa.CommandResult(1, stdout=json.dumps(peer))

    old_path = os.environ.get("PATH")
    os.environ["PATH"] = str(binary.parent)
    try:
        report = lfa.audit_fleet(
            checked_manifest,
            nodes,
            ["pro", "m5"],
            local_role="pro",
            script_source="# probe",
            local_runner=local_runner,
            remote_runner=remote_runner,
        )
    finally:
        if old_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = old_path
    assert report["summary"]["non_compliant_nodes"] == ["m5"]
    assert report["summary"]["parity_drift"] == ["tool"]
    assert report["summary"]["compliant"] is False
    assert "VERDICT: DRIFT" in lfa.render_table(report)


def test_main_returns_nonzero_for_required_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "manifest.json"
    nodes_path = tmp_path / "nodes.json"
    manifest_path.write_text(json.dumps(manifest(client())), encoding="utf-8")
    nodes_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "name": "pro",
                        "hostname": "fixture-pro",
                        "ssh_alias": "pro",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(lfa.socket, "gethostname", lambda: "fixture-pro")
    rc = lfa.main(
        [
            "--manifest",
            str(manifest_path),
            "--nodes",
            str(nodes_path),
            "--json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert output["summary"]["compliant"] is False
    assert output["clients"][0]["status"] == "REQUIRED_MISSING"


def test_main_rejects_local_host_role_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "manifest.json"
    nodes_path = tmp_path / "nodes.json"
    manifest_path.write_text(json.dumps(manifest(client())), encoding="utf-8")
    nodes_path.write_text(
        json.dumps(
            {"nodes": [{"name": "pro", "hostname": "fixture-pro", "ssh_alias": "pro"}]}
        ),
        encoding="utf-8",
    )
    rc = lfa.main(
        [
            "--manifest",
            str(manifest_path),
            "--nodes",
            str(nodes_path),
            "--host-role",
            "m5",
            "--json",
        ]
    )
    assert rc == 2
    assert "reserved for internal peer probes" in capsys.readouterr().err


def test_probe_script_streams_over_stdin_without_peer_file_dependency(
    tmp_path: Path,
) -> None:
    optional = client("aider", policies={"m5": "allowed"})
    payload = lfa._manifest_payload(manifest(optional))
    source = (REPO / "scripts" / "llm_fleet_audit.py").read_text(encoding="utf-8")
    result = lfa.subprocess_remote_runner(
        [
            sys.executable,
            "-",
            "--probe-payload",
            payload,
            "--host-role",
            "m5",
            "--timeout",
            "30",
            "--json",
        ],
        source,
        60,
    )
    assert result.returncode in {0, 1}, result.stderr
    decoded = json.loads(result.stdout)
    assert decoded["host"]["role"] == "m5"
    assert decoded["clients"][0]["id"] == "aider"
