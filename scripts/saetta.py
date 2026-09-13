#!/usr/bin/env python3
"""On-demand SAETTA bootstrap: preflight, resolve a manifest, invoke native Workflow.

Uses only installed subscription CLIs. Preflight proves configuration, not model
availability: a completed native smoke journal is the separate execution receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path


def machine(host: str, home: Path) -> str:
    host = host.lower().split(".")[0]
    if "mini" in host:
        return "Mini"
    if "m5" in host or host == "air-m5":
        return "M5"
    if host == "nuzantara" and home.name == "nuzantara":
        return "Pro"
    return "UNKNOWN"


def command(argv: list[str], *, cwd: Path | None = None, env=None):
    return subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True,
                          stdin=subprocess.DEVNULL, timeout=20, check=False)


def repo_root(path: Path) -> Path:
    result = command(["git", "rev-parse", "--show-toplevel"], cwd=path)
    root = Path(result.stdout.strip()).resolve()
    if result.returncode or not (root / "scripts/agent_start.py").is_file():
        raise ValueError("repo must resolve to a Nuzantara checkout")
    return root


def executable(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for prefix in (Path.home() / ".local/bin", Path.home() / ".local/share/mise/shims",
                   Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
        path = prefix / name
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def version_text(output: str) -> str | None:
    match = re.search(r"(?<![A-Za-z0-9])v?(\d+\.\d+(?:\.\d+)?(?:[a-z0-9.-]*)?)\b", output)
    return match.group(1) if match else None


def context_check(home: Path, repo: Path) -> dict:
    bridge = home / "hooks/nuzantara-context/context_bridge.py"
    result = {"ready": False, "rootCovered": False, "hooksBound": False,
              "thresholds": {}, "bridgeSha256": None}
    try:
        policy = json.loads((home / "nuzantara-context-policy.json").read_text())
        hooks = json.loads((home / "hooks.json").read_text()).get("hooks", {})
        roots = [Path(p).expanduser().resolve() for p in policy.get("roots", [])]
        result["rootCovered"] = any(repo == p or p in repo.parents for p in roots)
        events = ("SessionStart", "PreToolUse", "PostToolUse", "PreCompact", "PostCompact",
                  "Stop", "SubagentStart", "SubagentStop")
        def bound(event):
            for group in hooks.get(event, []):
                for hook in group.get("hooks", []):
                    parts = shlex.split(hook.get("command", ""))
                    if str(bridge) in parts and parts[-1:] == ["hook"]:
                        return True
            return False
        result["hooksBound"] = all(bound(event) for event in events)
        spec = importlib.util.spec_from_file_location("saetta_installed_context", bridge)
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(bridge.parent))
        try:
            spec.loader.exec_module(module)
            result["thresholds"] = {role: module.threshold(policy, role)
                                    for role in ("imperator", "dux", "builder")}
        finally:
            sys.path.pop(0)
        result["bridgeSha256"] = hashlib.sha256(bridge.read_bytes()).hexdigest()
        result["ready"] = bool(policy.get("enabled") and result["rootCovered"]
                               and result["hooksBound"]
                               and all(v == 0.6 for v in result["thresholds"].values()))
    except (OSError, ValueError, AttributeError, ImportError, TypeError, KeyError):
        result["error"] = "context_install_invalid_or_missing"
    return result


def preflight(repo: Path, env=None, claude: Path | None = None, *, require_workflow=True) -> dict:
    env = os.environ if env is None else env
    host = machine(socket.gethostname(), Path.home())
    tools = {}
    for name in ("claude", "codex", "node", "git", "gh"):
        binary = str(claude) if name == "claude" and claude else executable(name)
        info = {"path": binary, "version": None, "ready": False}
        if binary:
            try:
                proc = command([binary, "--version"], cwd=repo, env=env)
                # Version output only; never forward errors or auth payloads.
                version = version_text(proc.stdout)
                info.update(version=version, ready=proc.returncode == 0 and bool(version))
            except (OSError, subprocess.SubprocessError):
                pass
        tools[name] = info
    auth = False
    if tools["claude"]["ready"]:
        try:
            proc = command([tools["claude"]["path"], "auth", "status", "--json"], env=env)
            data = json.loads(proc.stdout)
            auth = proc.returncode == 0 and data.get("loggedIn") is True and data.get("authMethod") in (
                "claude.ai", "oauth_token") and data.get("apiProvider") == "firstParty"
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    context = context_check(Path(env.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve(), repo)
    script = repo / "infra/workflows/saetta.js"
    ready = host != "UNKNOWN" and all(t["ready"] for t in tools.values()) and auth and context["ready"] and (script.is_file() or not require_workflow)
    return {"ready": ready, "host": host, "repo": str(repo), "tools": tools,
            "claudeAuthenticated": auth, "codexContext": context,
            "workflowPresent": script.is_file(), "workflowRequired": require_workflow,
            "heavyExecutionHost": "Pro" if host == "M5" else host,
            "nativeExecutionVerified": False}


def prepare(manifest: dict, base: Path, repo: Path) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    mission = manifest.get("mission", "")
    if not isinstance(mission, str) or not re.fullmatch(r"[A-Za-z0-9-]+", mission):
        raise ValueError("invalid mission identifier")
    if manifest.get("colour", "BLUE") != "BLUE":
        raise ValueError("this native Claude launcher supports BLUE missions")
    cap = manifest.get("maxParallel", 3)
    if type(cap) is not int or not 1 <= cap <= 3:
        raise ValueError("maxParallel must be 1..3")
    rows = manifest.get("tasks")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 12:
        raise ValueError("tasks must contain 1..12 tasks")
    tasks = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid task")
        key = row.get("key", "")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", key):
            raise ValueError("invalid task key")
        brief = row.get("brief")
        if not isinstance(brief, str) or not brief:
            raise ValueError("brief path required")
        brief = (base / Path(brief).expanduser()).resolve()
        if not brief.is_file():
            raise ValueError("brief is missing")
        deps = row.get("dependsOn", [])
        scope = row.get("scope", [])
        if not isinstance(deps, list) or not all(isinstance(x, str) for x in deps):
            raise ValueError("dependency list required")
        if not isinstance(scope, list) or not scope or any(
            not isinstance(x, str) or not x or x.startswith("/")
            or re.search(r"[\x00-\x1f\x7f*?]", x)
            or any(part in ("", ".", "..") for part in x.removesuffix("/").split("/"))
            for x in scope
        ):
            raise ValueError("scope must contain repository-relative paths")
        tasks.append({"key": key, "brief": str(brief), "dependsOn": deps, "scope": scope})
    by_key = {t["key"]: t for t in tasks}
    if len(by_key) != len(tasks):
        raise ValueError("duplicate task key")
    done, visiting = set(), set()
    def visit(key):
        if key not in by_key:
            raise ValueError("unknown dependency")
        if key in visiting:
            raise ValueError("dependency cycle")
        if key in done:
            return
        visiting.add(key)
        for dependency in by_key[key]["dependsOn"]:
            visit(dependency)
        visiting.remove(key)
        done.add(key)
    for key in by_key:
        visit(key)
    output = manifest.get("outputDir", "output/saetta/" + mission)
    if not isinstance(output, str) or not output:
        raise ValueError("outputDir must be a path")
    return {"mission": mission, "colour": "BLUE", "repo": str(repo.resolve()),
            "outputDir": str((repo / Path(output).expanduser()).resolve()),
            "tasks": tasks, "maxParallel": cap}


def workflow_request(script: Path, args: dict, *, smoke=False) -> dict:
    request = {"scriptPath": str(script), "args": args}
    if smoke:
        request = {"script": 'export const meta = {name:"saetta-native-smoke",description:"Read-only native runtime smoke"}; '
                   'const r = await agent("Return the exact marker SAETTA_NATIVE_SMOKE. Do not use tools or change files.",'
                   '{label:"smoke",model:"sonnet",effort:"low",schema:{type:"object",properties:{marker:{type:"string",enum:["SAETTA_NATIVE_SMOKE"]}},required:["marker"]}}); '
                   'if (!r) throw new Error("native child did not return"); return r;'}
    return request


def launch_argv(claude: str, script: Path, args: dict, *, smoke=False, session_id=None) -> list[str]:
    request = workflow_request(script, args, smoke=smoke)
    prompt = ("Zero explicitly authorized this SAETTA workflow invocation. Call the native Workflow tool exactly once with "
              + json.dumps(request) + ". Wait for its completion notification, then read its journal and report the actual "
              "runId, scriptPath, transcriptDir and returned result. Never simulate Workflow in Bash/Node. "
              "A launch acknowledgement is not completion. If the tool is unavailable or denied, report BLOCK. "
              "Do not resume or send messages to any pre-existing session or workflow.")
    argv = [claude, "-p", "--session-id", session_id or str(uuid.uuid4()),
            "--model", "opus", "--effort", "xhigh", "--output-format", "stream-json",
            "--verbose", "--allowedTools", "Workflow,Read,TaskOutput", "--permission-mode", "auto"]
    if smoke:
        argv.extend(["--tools", "Workflow,Read,TaskOutput"])
    return argv + ["--", prompt]


def terminate_group(process: subprocess.Popen, grace: float = 1) -> None:
    """Drain the owned process group even when its leader exits before descendants."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            process.wait()
            return
        time.sleep(min(0.05, max(0, deadline - time.monotonic())))
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_bounded(argv: list[str], *, cwd: Path, env: dict, timeout: float, receipt=None) -> int:
    process = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL)
    try:
        code = process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        code = 124 if isinstance(exc, subprocess.TimeoutExpired) else 130
        terminate_group(process)
        print(json.dumps({"verdict": "BLOCK", "reason": "timeout" if code == 124 else "cancelled"}))
        return code
    result = receipt() if code == 0 and receipt else {
        "verdict": "BLOCK", "reason": "cli_failed" if code else "native_receipt_missing"}
    print(json.dumps(result))
    return 0 if code == 0 and result.get("verdict") == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "prepare", "run", "smoke"))
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--claude-config", type=Path, help="Explicit existing OAuth profile; no account switching")
    parser.add_argument("--claude", type=Path, help="Explicit installed OAuth seat wrapper, e.g. ~/.local/bin/claude-acct3")
    parser.add_argument("--heavy", action="store_true", help="Refuse heavy execution on the M5 thin client")
    parser.add_argument("--timeout", type=int, help="Whole invocation limit in seconds (default: smoke 180, run 3600)")
    options = parser.parse_args()
    try:
        repo = repo_root(options.repo)
        timeout = options.timeout if options.timeout is not None else (180 if options.action == "smoke" else 3600)
        if not 1 <= timeout <= 86400:
            raise ValueError("timeout must be 1..86400 seconds")
        env = dict(os.environ)
        claude = options.claude.expanduser().resolve() if options.claude else None
        if claude and (not claude.is_file() or not os.access(claude, os.X_OK)):
            raise ValueError("Claude executable does not exist or is not executable")
        if options.claude_config:
            profile = options.claude_config.expanduser().resolve()
            if not profile.is_dir():
                raise ValueError("Claude profile directory does not exist")
            env["CLAUDE_CONFIG_DIR"] = str(profile)
        args = {}
        if options.action in ("prepare", "run"):
            if options.manifest is None:
                raise ValueError("manifest required")
            manifest = options.manifest.resolve()
            args = prepare(json.loads(manifest.read_text()), manifest.parent, repo)
        if options.action == "prepare":
            print(json.dumps(args, indent=2))
            return 0
        report = preflight(repo, env, claude, require_workflow=options.action != "smoke")
        if options.action == "preflight" or not report["ready"]:
            print(json.dumps(report, indent=2))
            return 0 if report["ready"] else 1
        if options.heavy and report["host"] == "M5":
            raise ValueError("heavy work must run on Pro via ssh pro")
        common = command(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=repo)
        if options.action == "run" and Path(common.stdout.strip()).parent.resolve() == repo:
            raise ValueError("run requires a dedicated broker worktree")
        from saetta_receipt import sessions, verify
        session_id = str(uuid.uuid4())
        roots = list(Path.home().glob(".claude*"))
        if env.get("CLAUDE_CONFIG_DIR"):
            roots.append(Path(env["CLAUDE_CONFIG_DIR"]).expanduser().resolve())
        if sessions(session_id, roots):
            raise ValueError("session already exists")
        smoke = options.action == "smoke"
        script = repo / "infra/workflows/saetta.js"
        request = workflow_request(script, args, smoke=smoke)
        script_hash = None if smoke else hashlib.sha256(script.read_bytes()).hexdigest()
        argv = launch_argv(report["tools"]["claude"]["path"], script, args,
                           smoke=smoke, session_id=session_id)
        return run_bounded(argv, cwd=repo, env=env, timeout=timeout,
                           receipt=lambda: verify(session_id, roots, request, smoke=smoke,
                                                  script_sha256=script_hash))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Do not forward JSON parsing excerpts, subprocess output, or user-supplied payloads.
        print(json.dumps({"ready": False, "error": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
