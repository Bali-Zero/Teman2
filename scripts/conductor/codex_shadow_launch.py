"""Version-pinned synthetic shadow launcher, with an isolated native home.

Only the selected ChatGPT OAuth access credential is copied to a private temporary
runtime directory. The source account, global config and service credentials are
never modified. This is credential minimization, not a separate-UID boundary.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import AsyncIterator, Callable

from scripts.conductor.app_server_rpc import AppServerRPC

# Qualification is specific to these observed native binaries and this profile.
# Pro/Mini evidence covers strict config and catalog, not served Astra or effects.
QUALIFIED_BINARY_SHA256 = {
    "codex-cli 0.147.0": "19c4f144c5226a9f17c58e6f0fa854843b0f77a6eb420f40e2745a12f10f5d37",
    "codex-cli 0.148.0": "b0308517b20543012fa2171aa3d46ce455a7456c4eb2a552ab9468ba4eeb1e50",
    "codex-cli 0.149.0": "f4a74117b8142cda581c95ff753abf4508b5636d89682c1ed77e4a9249af8963",
}
DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "code_mode",
    "code_mode_host",
    "code_mode_only",
    "code_mode_buffered_exec",
    "computer_use",
    "goals",
    "hooks",
    "image_generation",
    "in_app_browser",
    "memories",
    "multi_agent",
    "multi_agent_v2",
    "plugins",
    "remote_plugin",
    "shell_snapshot",
    "shell_tool",
    "skill_mcp_dependency_install",
    "skill_search",
    "unified_exec",
    "view_image",
    "workspace_dependencies",
    "tool_call_mcp_elicitation",
    "tool_suggest",
    "auth_elicitation",
    "default_mode_request_user_input",
    "request_permissions_tool",
    "network_proxy",
)
PROFILE = """model_provider = "openai"
approval_policy = "never"
sandbox_mode = "read-only"
web_search = "disabled"
check_for_update_on_startup = false
allow_login_shell = false
cli_auth_credentials_store = "file"
[mcp_servers]
[shell_environment_policy]
inherit = "none"
set = {}
ignore_default_excludes = false
[features]
""" + "".join(f"{name} = false\n" for name in DISABLED_FEATURES)


def native_binary() -> Path:
    """Resolve observed native installs without executing a Node wrapper."""
    import platform

    arch = {"arm64": "aarch64", "x86_64": "x86_64"}.get(platform.machine())
    if platform.system() != "Darwin" or arch is None:
        raise RuntimeError("native_host_unqualified")
    package_arch = "arm64" if arch == "aarch64" else "x64"
    prefix = Path("/opt/homebrew" if arch == "aarch64" else "/usr/local")
    binary = (
        prefix
        / "lib/node_modules/@openai/codex/node_modules"
        / f"@openai/codex-darwin-{package_arch}/vendor/{arch}-apple-darwin/bin/codex"
    )
    # Mini's observed 0.148.0 install is a native Homebrew Cask, not npm.
    cask = prefix / "Caskroom/codex/0.148.0/bin/codex"
    for candidate in (binary, cask):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise RuntimeError("native_binary_unavailable")


def validate_runtime_binding(version: str, binary_hash: str) -> None:
    """A familiar version string cannot admit different executable bytes."""
    if version not in QUALIFIED_BINARY_SHA256:
        raise PermissionError("native_version_unqualified")
    if QUALIFIED_BINARY_SHA256[version] != binary_hash:
        raise PermissionError("native_binary_unqualified")


def prepare_auth(source: Path, destination: Path) -> None:
    """Copy only a known subscription credential; never render any credential."""
    raw = source.read_bytes()
    if len(raw) > 65536:
        raise PermissionError("auth_file_unbounded")
    account = json.loads(raw)
    if account.get("auth_mode") != "chatgpt" or account.get("OPENAI_API_KEY"):
        raise PermissionError("subscription_auth_required")
    tokens = account.get("tokens")
    if not isinstance(tokens, dict) or not tokens.get("access_token"):
        raise PermissionError("subscription_auth_missing")
    # Do not duplicate refresh authority or rotate the operator's OAuth session.
    # Preserve real refresh metadata; expired access fails closed and requires a
    # fresh native login outside this qualification consumer.
    selected = {
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": {
            k: tokens[k]
            for k in ("id_token", "access_token", "account_id")
            if k in tokens
        },
    }
    if not account.get("last_refresh"):
        raise PermissionError("subscription_refresh_metadata_missing")
    selected["last_refresh"] = account["last_refresh"]
    selected["tokens"]["refresh_token"] = ""
    with open(
        destination, "x", opener=lambda path, flags: os.open(path, flags, 0o600)
    ) as handle:
        json.dump(selected, handle)


@asynccontextmanager
async def launch_shadow(
    auth_home: Path,
) -> AsyncIterator[tuple[AppServerRPC, Path, dict[str, str], Callable[[], str]]]:
    import asyncio

    binary = native_binary()
    binary_hash = sha256(binary.read_bytes()).hexdigest()
    # Refuse unknown code before executing even --version or copying auth state.
    if binary_hash not in QUALIFIED_BINARY_SHA256.values():
        raise PermissionError("native_binary_unqualified")
    # These files are runtime state, not evidence or shared memory. No global
    # HOME, env.set, MCP, hook, shell startup file or inherited env enters them.
    with tempfile.TemporaryDirectory(prefix="dual-consul-shadow-") as directory:
        root = Path(directory)
        home, codex_home, work = root / "home", root / "codex", root / "work"
        for path in (home, codex_home, work):
            path.mkdir(mode=0o700)
        (codex_home / "config.toml").write_text(PROFILE)
        prepare_auth(auth_home / "auth.json", codex_home / "auth.json")
        env = {
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "PATH": "/usr/bin:/bin",
            "TMPDIR": str(root),
            "LANG": "en_US.UTF-8",
        }
        process = await asyncio.create_subprocess_exec(
            str(binary),
            "--version",
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 5)
        except BaseException:
            process.kill()
            await process.wait()
            raise
        version = output.decode().strip()
        if process.returncode:
            raise PermissionError("native_version_unqualified")
        validate_runtime_binding(version, binary_hash)
        metadata = {
            "runtime_version": version,
            "binary_hash": binary_hash,
            "profile_hash": sha256(PROFILE.encode()).hexdigest(),
        }
        async with AppServerRPC(
            [str(binary), "app-server", "--stdio", "--strict-config"],
            work,
            env,
            experimental_api=True,
            reject_tool_activity=True,
        ) as rpc:
            yield (
                rpc,
                work,
                metadata,
                lambda: sha256((codex_home / "auth.json").read_bytes()).hexdigest(),
            )
