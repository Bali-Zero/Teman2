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

QUALIFIED_VERSION = "codex-cli 0.147.0"
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
    """Resolve the installed npm native binary without the node wrapper's PATH."""
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
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError("native_binary_unavailable")
    return binary.resolve()


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
        if process.returncode or version != QUALIFIED_VERSION:
            raise PermissionError("native_version_unqualified")
        metadata = {
            "runtime_version": version,
            "binary_hash": sha256(binary.read_bytes()).hexdigest(),
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
