#!/usr/bin/env python3
"""agy_code_dispatch.py — drive the Antigravity CLI (`agy`) as a coding agent on a worktree.

Distinct from agy_swarm_commander.py (which is a *reviewer*: no file writes, Gemini-only).
This dispatcher runs `agy` in autonomous coding mode INSIDE a dedicated git worktree so it
can edit files + run tests, then returns a structured result for INDEPENDENT verification by
Claude Code. It is the automated form of steps 2-3 of the Antigravity workflow
(see CLAUDE.md §5 / memory decision_how_we_use_antigravity_ide_2026_06_23).

Design rules (enforced here, not just documented):
- HARD: refuses to run on the main checkout — only `.worktrees/<lane>-<task-id>/`
  (sibling-race superscar #5). The agent NEVER touches main.
- HARD: refuses worktrees whose path resolves outside the repo's `.worktrees/`.
- Prompt is governed + safety-filtered (reuses agy_swarm_commander guardrails).
- Output is redacted for credential shapes and audited to JSONL (no raw prompt).
- Model is explicit (Claude Sonnet/Opus 4.6 on AI Ultra quota, or Gemini) — NOT MAX quota.
- This script does NOT commit/push/PR. Promotion stays with Claude Code (verify) + Zero (merge).

Usage:
  python scripts/agy_code_dispatch.py \
      --worktree .worktrees/ops-portal-bug-d \
      --model "Claude Opus 4.6 (Thinking)" \
      --prompt-file /tmp/bug-d-prompt.txt \
      --timeout 600
  # or --prompt "inline task ..."
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Reuse the governance primitives already battle-tested in the swarm commander.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from agy_swarm_commander import (  # type: ignore
        prompt_hash,
        redact_sensitive,
        validate_prompt,  # internally applies BLOCKED_PROMPT_PATTERNS
    )
except ImportError as exc:  # pragma: no cover - defensive
    print(f"FATAL: cannot import agy_swarm_commander guardrails: {exc}", file=sys.stderr)
    sys.exit(2)


def _main_checkout_root() -> Path:
    """Resolve the MAIN repo checkout root, correct even when this script runs from
    inside a worktree. `git rev-parse --git-common-dir` points at the main repo's
    .git, whose parent is the main checkout (worktrees share it)."""
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(Path(__file__).resolve().parent),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return Path(common).resolve().parent
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: assume scripts/ sits at repo root (only valid in main checkout).
        return Path(__file__).resolve().parent.parent


REPO_ROOT = _main_checkout_root()
WORKTREES_DIR = REPO_ROOT / ".worktrees"
AUDIT_FILENAME = "agy-code-audit.jsonl"

# Allowlisted models (must match `agy models` exactly — verified 2026-06-23 v1.0.10).
ALLOWED_MODELS = {
    "Gemini 3.5 Flash (Medium)",
    "Gemini 3.5 Flash (High)",
    "Gemini 3.1 Pro (High)",
    "Claude Sonnet 4.6 (Thinking)",
    "Claude Opus 4.6 (Thinking)",
}


def resolve_worktree(raw: str) -> Path:
    """Resolve + HARD-validate the target worktree. Refuses main checkout / out-of-tree."""
    path = Path(raw).expanduser()
    # Relative paths resolve against the caller's CWD (not REPO_ROOT), so `--worktree .`
    # from inside a worktree means THAT worktree.
    path = path.resolve()

    if path == REPO_ROOT:
        raise ValueError(
            "REFUSED: target is the main checkout. agy must run in a dedicated worktree "
            "(.worktrees/<lane>-<task-id>) — sibling-race superscar #5."
        )
    try:
        path.relative_to(WORKTREES_DIR)
    except ValueError:
        raise ValueError(
            f"REFUSED: {path} is not under {WORKTREES_DIR}. "
            "Create one via: python scripts/agent_start.py --lane ops --task-id <X> --base-branch origin/main"
        ) from None
    if not (path / ".git").exists():
        raise ValueError(f"REFUSED: {path} is not a git worktree (no .git).")
    return path


def resolve_model(model: str) -> str:
    if model in ALLOWED_MODELS:
        return model
    allowed = "\n  - ".join(sorted(ALLOWED_MODELS))
    raise ValueError(f"Unsupported model '{model}'. Allowed:\n  - {allowed}")


def build_prompt(user_prompt: str) -> str:
    """Governed coding prompt. Validates + frames the autonomous task."""
    validate_prompt(user_prompt)
    return f"""You are an autonomous coding agent working INSIDE a dedicated git worktree.

Guardrails (hard):
- Work ONLY inside this worktree. Do NOT cd elsewhere, do NOT touch the main checkout,
  do NOT push, commit, open PRs, or deploy — promotion is handled by the operator.
- Do NOT process real client PII (KTP, passport, NPWP, akta, real WhatsApp dumps);
  this is dev work on code, not on production client data.
- Do NOT request credentials, logins, or bypasses.
- Write tests for your change and RUN them. Report real pass/fail counts, not claims.
- If you cannot run a test (missing env/db), say so explicitly — do NOT pretend it passed.

Task:
{user_prompt}

When done, summarize: files changed, the fix, and exactly how you verified (with real
command output / test counts).
"""


def write_audit(record: dict, worktree: Path) -> Path:
    audit_dir = worktree / ".agy-dispatch"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / AUDIT_FILENAME
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return audit_path


def run(
    *,
    worktree: Path,
    model: str,
    prompt: str,
    timeout_s: int,
    agy_bin: str,
    skip_permissions: bool,
    dry_run: bool,
) -> int:
    governed = build_prompt(prompt)
    cmd = [
        agy_bin,
        "--model",
        model,
        "--add-dir",
        str(worktree),
    ]
    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    cmd += ["-p", "--print-timeout", f"{timeout_s}s"]

    # agy must NEVER see the paid Anthropic key — Claude is consumed via AI Ultra OAuth.
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)

    start = time.monotonic()
    if dry_run:
        print(f"DRY_RUN cmd: {' '.join(cmd)}")
        print(f"DRY_RUN cwd: {worktree}")
        print("DRY_RUN prompt (governed, first 400 chars):")
        print(governed[:400])
        return 0

    try:
        completed = subprocess.run(
            cmd,
            input=governed,
            capture_output=True,
            text=True,
            timeout=timeout_s + 10,
            cwd=str(worktree),
            env=env,
        )
        output = completed.stdout or ""
        exit_code = completed.returncode
        if completed.stderr:
            output += f"\n[stderr]\n{completed.stderr}"
    except subprocess.TimeoutExpired:
        output = f"TIMEOUT: agy did not complete within {timeout_s}s."
        exit_code = 124
    except FileNotFoundError:
        print(f"FATAL: agy binary not found: {agy_bin}", file=sys.stderr)
        return 2

    duration = round(time.monotonic() - start, 1)
    safe_output = redact_sensitive(output)

    write_audit(
        {
            "model": model,
            "worktree": str(worktree),
            "prompt_sha256": prompt_hash(prompt),
            "duration_s": duration,
            "exit_code": exit_code,
            "skip_permissions": skip_permissions,
        },
        worktree,
    )

    print(safe_output)
    print(f"\n[agy_code_dispatch] model={model} exit={exit_code} duration={duration}s", file=sys.stderr)
    print("[agy_code_dispatch] NEXT: Claude Code must independently verify (re-read diff, re-run tests).", file=sys.stderr)
    return exit_code


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--worktree", required=True, help="Path to dedicated worktree (.worktrees/<lane>-<id>)")
    p.add_argument("--model", required=True, help='Exact model from `agy models`, e.g. "Claude Opus 4.6 (Thinking)"')
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--prompt", help="Inline task prompt")
    grp.add_argument("--prompt-file", help="Path to a file containing the task prompt")
    p.add_argument("--timeout", type=int, default=600, help="Hard timeout in seconds (default 600)")
    p.add_argument("--agy-bin", default=os.path.expanduser("~/.local/bin/agy"), help="agy executable")
    p.add_argument("--no-skip-permissions", action="store_true", help="Require permission prompts (default: auto-approve)")
    p.add_argument("--dry-run", action="store_true", help="Validate + print the command without running agy")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        worktree = resolve_worktree(args.worktree)
        model = resolve_model(args.model)
        prompt = (
            Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
            if args.prompt_file
            else args.prompt
        )
        validate_prompt(prompt)
    except (ValueError, OSError) as exc:
        msg = str(exc)
        if not msg.startswith("REFUSED:"):
            msg = f"REFUSED: {msg}"
        print(msg, file=sys.stderr)
        return 1

    return run(
        worktree=worktree,
        model=model,
        prompt=prompt,
        timeout_s=args.timeout,
        agy_bin=args.agy_bin,
        skip_permissions=not args.no_skip_permissions,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
