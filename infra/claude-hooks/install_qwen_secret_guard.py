#!/usr/bin/env python3
"""install_qwen_secret_guard.py — idempotent per-machine installer that wires
`secret_expansion_guard.py` into the Qwen harness.

WHY THIS EXISTS. PR #6787 registered the guard in `.claude/settings.json`, which
is git-TRACKED, so its registration and the guard file travel together: a checkout
that has one has the other. The Qwen harness cannot be wired that way — `~/.qwen/`
is gitignored — and the first attempt at wiring it by hand pointed the hook at
`/Users/<user>/nuzantara/infra/claude-hooks/secret_expansion_guard.py` while the
shared main checkout was **2 commits behind `origin/main`**, so the file did not
exist there yet.

That is not a harmless failure. `python3 <missing file>` exits **2**, and 2 is
exactly DENY in the hook contract — so every Bash and every Read of every Qwen
session on the machine would have been blocked. It was caught only because the
innocence case was tested as well: `${VAR:+SET}` returned rc=2 **with no shape id
in stderr**, which is the signature of Python failing to open a file, not of the
guard judging anything. A guard that denies everything looks like it works if you
only ever test guilt.

So this installer does two things the hand-edit could not:

  1. It installs the guard into `$HOME` (`~/.claude/hooks/`, mode 0700, the same
     location as the other 190 declared pairs) by COPYING FROM THE REPO, so
     `scripts/lint_home_fork.py --check` — which compares sha256(live) against
     sha256(repo twin) — stays green instead of reporting drift it cannot fix.
     A `$HOME` copy is what makes the hook path independent of whether any shared
     checkout happens to be current.
  2. It REFUSES to leave the wiring in place unless the installed guard actually
     denies a guilty payload AND allows an innocent one. Both halves, every run.
     Wiring is rolled back on failure.

This is the preventive complement to `redact_secrets.py` (which scrubs credential
shapes on the way to a log, born of superscar #4): that one cleans up after a
value reaches disk, this one stops the tool call that would put it in the
transcript at all.

Usage:
    python3 infra/claude-hooks/install_qwen_secret_guard.py [--dry-run]
    python3 infra/claude-hooks/install_qwen_secret_guard.py \
        --settings PATH --hooks-dir DIR --repo-hooks-dir DIR     # testing

Exit 0 = installed (or already installed) and verified. Non-zero = not wired,
and the reason is on stderr. Never prints a credential value.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

GUARD_NAME = "secret_expansion_guard.py"
REGISTRY_NAME = "secret-expansion-registry.json"

# The Qwen harness passes the CANONICAL tool name and evaluates `matcher` against
# that tool's alias set — NOT against Claude's tool names. Measured two ways on
# Air-M5 2026-09-19:
#
#   (a) empirically. A recorder hook (always exit 0, logs only names) registered
#       under three matchers, then a fresh `qwen -p` session ran a read_file:
#           "Bash|Monitor|Read"          -> 0 events   (never fires)
#           "run_shell_command|read_file"-> tool_name=read_file
#           ""                           -> tool_name=read_file, tool_search
#       So `Bash` and `Read` are NOT Qwen tool names; the payload carries
#       `tool_name` in canonical snake_case, with keys
#       cwd/hook_event_name/permission_mode/session_id/timestamp/tool_call_id/
#       tool_input/tool_name.
#   (b) in the 0.24.0 bundle: `TOOL_ALIAS_MAP` is built as canonical +
#       `ToolDisplayNames[key]` + `${displayName}Tool` (+ legacy migrations), and
#       `ToolDisplayNames` gives SHELL->"Shell", READ_FILE->"ReadFile",
#       MONITOR->"Monitor". `SHELL_TOOL_NAMES = ["run_shell_command","ShellTool"]`.
#
# The first attempt shipped `MATCHER = "Bash|Monitor|Read"` — Claude's names — so
# the hook was registered and completely INERT on exactly the two tools that
# leaked (`run_shell_command`, `read_file`). That is superscar #2 in pure form: a
# check that exists, carries the right name, and enforces nothing. Claude-style
# `Bash`/`Read` are kept only as harmless portability extras; an alternative that
# never matches costs nothing.
MATCHER = (
    "run_shell_command|Shell|ShellTool|Bash"
    "|read_file|ReadFile|ReadFileTool|Read"
    "|monitor|Monitor|MonitorTool"
)
# The canonical names Qwen actually emits. A matcher missing any of these is inert
# for that tool, and nothing else in the install path can detect it — which is why
# it is pinned by a test rather than left to review.
REQUIRED_CANONICAL_TOOLS = ("run_shell_command", "read_file", "monitor")
# Guilt and innocence are BOTH mandatory. See the module docstring: the guilt
# half alone cannot tell a working guard from one that denies everything.
#
# tool_name uses the CANONICAL names the Qwen harness actually emits
# (`run_shell_command`, `read_file`), not Claude's — verifying through a name the
# harness never sends would prove nothing about the wiring.
GUILT_PAYLOAD = {
    "tool_name": "run_shell_command",
    "tool_input": {"command": "printenv BAILIAN_TOKEN_PLAN_API_KEY"},
    "cwd": "/tmp",
}
GUILT_READ_PAYLOAD = {
    "tool_name": "read_file",
    "tool_input": {"file_path": "~/.nuzantara-secrets.env"},
    "cwd": "/tmp",
}
INNOCENCE_PAYLOAD = {
    "tool_name": "run_shell_command",
    "tool_input": {"command": 'echo "${BAILIAN_TOKEN_PLAN_API_KEY:+SET}"'},
    "cwd": "/tmp",
}


def _say(msg: str) -> None:
    print(msg)


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _copy_from_repo(repo_hooks: Path, hooks_dir: Path, dry: bool) -> list[Path]:
    """Install guard + registry from the repo so sha256 matches the tracked twin."""
    installed: list[Path] = []
    for name in (GUARD_NAME, REGISTRY_NAME):
        src = repo_hooks / name
        dst = hooks_dir / name
        if not src.is_file():
            raise FileNotFoundError(f"repo source missing: {src}")
        if dry:
            _say(f"  [dry-run] copy {src} -> {dst}")
            installed.append(dst)
            continue
        hooks_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o700 if name.endswith(".py") else 0o600)
        installed.append(dst)
    return installed


def _probe(guard: Path, payload: dict, env: dict | None = None) -> tuple[int, str]:
    """Invoke the installed guard exactly as the harness would: JSON on stdin."""
    e = dict(os.environ)
    if env:
        e.update(env)
    e.pop("NUZ_SECRET_EXPANSION_GUARD_OFF", None)  # never verify through a kill switch
    p = subprocess.run(
        [sys.executable, str(guard)],
        input=json.dumps(payload), capture_output=True, text=True, env=e, timeout=30,
    )
    return p.returncode, (p.stderr or "").strip()


def _verify(guard: Path) -> tuple[bool, str]:
    """Guilt must DENY (rc 2) with a shape id; innocence must ALLOW (rc 0).

    What this proves and what it does NOT: it proves the installed file runs and
    judges the canonical Qwen tool names correctly. It does NOT prove the harness
    will call it — that depends on `MATCHER`, which no payload can exercise from
    here. The matcher is pinned by test instead; see REQUIRED_CANONICAL_TOOLS.
    """
    if not guard.is_file():
        return False, f"installed guard is not a file: {guard}"
    shapes = []
    for label, payload in (("shell guilt", GUILT_PAYLOAD),
                           ("read guilt", GUILT_READ_PAYLOAD)):
        rc, err = _probe(guard, payload)
        if rc != 2:
            return False, f"{label} payload returned rc={rc}, expected 2 (guard is not denying)"
        if not err.startswith("[secret-expansion-guard] DENY"):
            return False, f"{label} payload denied without a contract-conform reason: {err[:120]!r}"
        m = re.search(r"\bX\d\b", err)
        shapes.append(m.group(0) if m else "X?")
    rc2, err2 = _probe(guard, INNOCENCE_PAYLOAD)
    if rc2 != 0:
        # The exact failure this installer exists to prevent: a missing/unreadable
        # guard makes python3 exit 2, which reads as DENY and would brick Bash.
        hint = " (rc=2 with no DENY reason = the interpreter could not run the file)" \
            if rc2 == 2 and not err2.startswith("[secret-expansion-guard]") else ""
        return False, f"innocence payload returned rc={rc2}, expected 0{hint}: {err2[:120]!r}"
    return True, "guilt DENY (%s shell, %s read) + innocence ALLOW" % (shapes[0], shapes[1])


def _add_hook(settings: dict, command: str) -> tuple[bool, str]:
    """Register the PreToolUse entry, REPLACING a stale one. Returns (changed, note).

    Matching on the guard's filename alone is not enough: the first version of this
    installer registered `matcher: "Bash|Monitor|Read"`, which never fires on Qwen
    (see MATCHER). A filename-only check would have found that inert entry on M5 and
    reported "already registered", leaving the machine silently unprotected — the
    failure made permanent by its own idempotency check. So an entry is current only
    if BOTH its command and its matcher match; otherwise it is replaced in place.
    """
    hooks = settings.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    for i, entry in enumerate(pre):
        if not isinstance(entry, dict):
            continue
        inner = entry.get("hooks") or []
        if not any(isinstance(h, dict) and GUARD_NAME in str(h.get("command", ""))
                   for h in inner):
            continue
        if entry.get("matcher") == MATCHER and any(
            isinstance(h, dict) and h.get("command") == command for h in inner
        ):
            return False, "already registered"
        stale_matcher = entry.get("matcher")
        pre[i] = {"matcher": MATCHER, "hooks": [{"type": "command", "command": command}]}
        return True, f"replaced stale registration (matcher was {stale_matcher!r})"
    pre.append({"matcher": MATCHER,
                "hooks": [{"type": "command", "command": command}]})
    return True, "registered"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--settings", default=None,
                    help="target settings.json (default ~/.qwen/settings.json)")
    ap.add_argument("--hooks-dir", default=None,
                    help="install dir (default ~/.claude/hooks)")
    ap.add_argument("--repo-hooks-dir", default=None,
                    help="repo source dir (default <this file's dir>)")
    args = ap.parse_args(argv)

    home = Path(os.path.expanduser("~"))
    settings_path = Path(args.settings) if args.settings else home / ".qwen" / "settings.json"
    hooks_dir = Path(args.hooks_dir) if args.hooks_dir else home / ".claude" / "hooks"
    repo_hooks = (Path(args.repo_hooks_dir) if args.repo_hooks_dir
                  else Path(__file__).resolve().parent)
    installed_guard = hooks_dir / GUARD_NAME

    _say(f"install_qwen_secret_guard: settings={settings_path}")
    _say(f"                         hooks_dir={hooks_dir}")
    _say(f"                         repo source={repo_hooks}")

    try:
        _copy_from_repo(repo_hooks, hooks_dir, args.dry_run)
    except Exception as exc:
        _err(f"REFUSED: cannot install the guard files: {type(exc).__name__}: {exc}")
        return 3

    if args.dry_run:
        _say("  [dry-run] would verify the installed guard and register the hook")
        return 0

    ok, detail = _verify(installed_guard)
    if not ok:
        _err(f"REFUSED: the installed guard did not verify — {detail}")
        _err("         settings.json was NOT modified; no hook was registered.")
        return 4
    _say(f"  verified: {detail}")

    if not settings_path.is_file():
        _err(f"REFUSED: {settings_path} does not exist — will not create a settings file")
        return 5
    try:
        settings = json.loads(settings_path.read_text())
    except Exception as exc:
        _err(f"REFUSED: {settings_path} is not valid JSON ({type(exc).__name__}); "
             f"will not overwrite it")
        return 5
    if not isinstance(settings, dict):
        _err(f"REFUSED: {settings_path} is not a JSON object")
        return 5

    command = f"python3 {installed_guard}"
    changed, note = _add_hook(settings, command)
    if not changed:
        _say(f"  hook {note}; settings.json untouched")
        return 0

    backup = settings_path.with_name(
        f"{settings_path.name}.bak-qwenguard-{time.strftime('%Y%m%dT%H%M%S')}"
    )
    shutil.copy2(settings_path, backup)
    try:
        os.chmod(backup, 0o600)
    except OSError:
        pass
    before_keys = sorted(settings.keys())
    try:
        settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        os.chmod(settings_path, 0o600)
    except Exception as exc:
        _err(f"FAILED to write {settings_path}: {type(exc).__name__}: {exc}")
        _err(f"         backup kept at {backup}")
        return 6

    # Re-read and re-verify: a settings file the harness will not parse is worse
    # than no wiring at all, and the qwen CLI rewrites this file on every flush.
    try:
        reread = json.loads(settings_path.read_text())
    except Exception as exc:
        _err(f"ROLLBACK: {settings_path} does not re-parse after write ({exc}); "
             f"restoring {backup}")
        shutil.copy2(backup, settings_path)
        return 7
    if sorted(reread.keys()) != before_keys and "hooks" not in before_keys:
        _err(f"ROLLBACK: top-level keys changed unexpectedly ({before_keys} -> "
             f"{sorted(reread.keys())}); restoring {backup}")
        shutil.copy2(backup, settings_path)
        return 7

    _say(f"  hook {note} on matcher {MATCHER}")
    _say(f"  backup: {backup}")
    _say(f"  mode: {oct(os.stat(settings_path).st_mode & 0o777)}")
    _say("  NOTE: a running Qwen session loaded its hooks at startup, so this takes")
    _say("        effect for NEW sessions. It also rewrites settings.json to 0644 on")
    _say("        flush; that is harmless now that the file holds no credential.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        _err(f"install_qwen_secret_guard: unexpected {type(exc).__name__}: {exc}")
        sys.exit(1)
