#!/usr/bin/env python3
"""Bounded Antigravity/Gemini runner for Nuzantara Swarm Commander.

The Antigravity CLI is useful as a cloud reviewer, but it must be treated as an
adjunct: bounded by timeout, audited by prompt hash, and prevented from making
state-changing decisions for the knowledge graph.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "ai-dispatch-output"
AUDIT_FILENAME = "agy-swarm-audit.jsonl"
MAX_CONTEXT_CHARS = 40_000

MODEL_ALIASES: dict[str, str] = {
    "flash-high": "Gemini 3.5 Flash (High)",
    "pro-high": "Gemini 3.1 Pro (High)",
}

MODE_POLICIES: dict[str, str] = {
    "fast-review": (
        "Fast reviewer. Identify obvious gaps, source needs, contradictions, "
        "and next actions. Prefer short, actionable output."
    ),
    "deep-review": (
        "Deep reviewer. Map assumptions, alternative explanations, missing "
        "evidence, risks, and high-leverage research branches."
    ),
    "redteam": (
        "Adversarial reviewer. Try to falsify the proposed conclusion. Separate "
        "evidence from inference and flag overclaiming."
    ),
    "source-triage": (
        "Source triage reviewer. Rank official, media, social, archive, and "
        "registry sources by likely yield and reliability."
    ),
    "swarm": (
        "Swarm commander. Decompose the task into specialist lanes, assign the "
        "best model/tool family per lane, define stop conditions, and return a "
        "bounded execution plan."
    ),
}

BLOCKED_PROMPT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brm\s+-rf\b", re.IGNORECASE), "destructive shell command"),
    (re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE), "destructive git command"),
    (re.compile(r"\bgit\s+push\s+--force\b", re.IGNORECASE), "destructive git command"),
    (
        re.compile(r"\b(dangerously|danger-full-access|--yolo|skip-permissions)\b", re.IGNORECASE),
        "permission bypass",
    ),
    (
        re.compile(r"\b(api[_-]?key|token|secret|password)\s*(=|:|is|e'|e)\s*\S+", re.IGNORECASE),
        "secret material",
    ),
)

REDACTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(api[_-]?key|token|secret|password)\s*(=|:|is|e'|e)\s*\S+", re.IGNORECASE),
)


def prompt_hash(prompt: str) -> str:
    """Return a stable SHA-256 digest for audit without storing raw prompts."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def resolve_model(model_key: str) -> str:
    """Resolve an allowlisted model alias or exact allowlisted model label."""
    if model_key in MODEL_ALIASES:
        return MODEL_ALIASES[model_key]
    if model_key in MODEL_ALIASES.values():
        return model_key
    allowed = ", ".join(sorted(MODEL_ALIASES))
    raise ValueError(f"Unsupported agy model '{model_key}'. Allowed aliases: {allowed}")


def validate_mode(mode: str) -> str:
    """Validate a commander mode."""
    if mode not in MODE_POLICIES:
        allowed = ", ".join(sorted(MODE_POLICIES))
        raise ValueError(f"Unsupported mode '{mode}'. Allowed modes: {allowed}")
    return mode


def validate_prompt(prompt: str, *, label: str = "prompt") -> None:
    """Fail closed on destructive instructions or secret material."""
    if not prompt.strip():
        raise ValueError(f"{label} is empty")
    for pattern, reason in BLOCKED_PROMPT_PATTERNS:
        if pattern.search(prompt):
            raise ValueError(f"Blocked {label}: {reason}")


def redact_sensitive(text: str) -> str:
    """Redact obvious credential shapes from model output."""
    redacted = text
    for pattern in REDACTION_PATTERNS:
        redacted = pattern.sub(r"\1=<REDACTED>", redacted)
    return redacted


def read_context_file(context_file: str | None, *, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Read optional bounded context for the commander prompt."""
    if not context_file:
        return ""
    path = Path(context_file).expanduser()
    data = path.read_text(encoding="utf-8", errors="replace")
    validate_prompt(data, label=f"context file {path}")
    if len(data) <= max_chars:
        return data
    return f"{data[:max_chars]}\n\n[TRUNCATED: context exceeded {max_chars} characters]"


def build_prompt(mode: str, user_prompt: str, *, context: str = "") -> str:
    """Construct the governed prompt sent to agy."""
    validate_mode(mode)
    validate_prompt(user_prompt)
    context_block = ""
    if context:
        context_block = f"""
Context:
{context}
"""
    return f"""You are an external bounded reviewer inside Nuzantara Swarm Commander.

Global guardrails:
- Work only from public, user-provided, or repository-local sanitized context.
- Do not request credentials, browser logins, private account access, or bypasses.
- Do not scrape private social accounts or propose evading platform controls.
- Do not write files, run tools, mutate databases, or call external APIs.
- Do not promote knowledge-graph nodes, merge identities, or assert allegations as facts.
- Treat person/profile links as candidates until verified by source-backed review.
- Return evidence needs, source targets, confidence, and blocked actions explicitly.

Mode objective:
{MODE_POLICIES[mode]}
{context_block}
User task:
{user_prompt}

Output format:
1. Decision / stance
2. Candidate findings
3. Evidence gaps
4. Source/tool plan
5. Risks and blocked actions
"""


def write_audit(record: dict[str, Any], output_dir: Path) -> Path:
    """Append a minimal audit record without raw prompt text."""
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / AUDIT_FILENAME
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return audit_path


def run_commander(
    *,
    model_key: str,
    mode: str,
    prompt: str,
    timeout_s: int,
    agy_bin: str = "agy",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    dry_run: bool = False,
    context_file: str | None = None,
) -> dict[str, Any]:
    """Run agy in bounded print mode and return structured result metadata."""
    model = resolve_model(model_key)
    mode = validate_mode(mode)
    context = read_context_file(context_file)
    final_prompt = build_prompt(mode, prompt, context=context)
    digest = prompt_hash(final_prompt)
    print_timeout = f"{timeout_s}s"
    command = [
        agy_bin,
        "--model",
        model,
        "--sandbox",
        "--print-timeout",
        print_timeout,
        "--print",
        final_prompt,
    ]
    command_preview = command[:-1] + ["<prompt omitted>"]
    started_at = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()

    if dry_run:
        duration_s = round(time.monotonic() - started_at, 3)
        result_output = "DRY_RUN: agy was not executed."
        exit_code = 0
        timed_out = False
    else:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout_s + 5,
            )
            exit_code = completed.returncode
            timed_out = False
            result_output = redact_sensitive((completed.stdout or "") + (completed.stderr or ""))
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            timed_out = True
            partial_stdout = exc.stdout or ""
            partial_stderr = exc.stderr or ""
            if isinstance(partial_stdout, bytes):
                partial_stdout = partial_stdout.decode("utf-8", errors="replace")
            if isinstance(partial_stderr, bytes):
                partial_stderr = partial_stderr.decode("utf-8", errors="replace")
            result_output = redact_sensitive(
                f"TIMEOUT: agy did not complete within {timeout_s + 5}s.\n"
                f"{partial_stdout}{partial_stderr}"
            )

        duration_s = round(time.monotonic() - started_at, 3)

    audit_record: dict[str, Any] = {
        "ts": now,
        "tool": "agy_swarm_commander",
        "mode": mode,
        "model_key": model_key,
        "model": model,
        "timeout_s": timeout_s,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "ok": exit_code == 0,
        "duration_s": duration_s,
        "prompt_hash": digest,
        "output_chars": len(result_output),
        "dry_run": dry_run,
    }
    audit_path = write_audit(audit_record, output_dir)

    return {
        "ok": exit_code == 0,
        "mode": mode,
        "model_key": model_key,
        "model": model,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "duration_s": duration_s,
        "prompt_hash": digest,
        "command_preview": command_preview,
        "audit_path": str(audit_path),
        "dry_run": dry_run,
        "output": result_output.rstrip(),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Model alias: flash-high or pro-high")
    parser.add_argument("--mode", required=True, help="Mode: fast-review, deep-review, redteam, source-triage, swarm")
    parser.add_argument("--prompt", required=True, help="User task prompt")
    parser.add_argument("--timeout", type=int, default=90, help="Hard timeout in seconds")
    parser.add_argument("--agy-bin", default="agy", help="agy executable path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Audit/output directory")
    parser.add_argument("--context-file", help="Optional bounded context file")
    parser.add_argument("--dry-run", action="store_true", help="Validate and audit without executing agy")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv or sys.argv[1:])
    try:
        result = run_commander(
            model_key=args.model,
            mode=args.mode,
            prompt=args.prompt,
            timeout_s=args.timeout,
            agy_bin=args.agy_bin,
            output_dir=Path(args.output_dir),
            dry_run=args.dry_run,
            context_file=args.context_file,
        )
    except ValueError as exc:
        result = {"ok": False, "exit_code": 2, "error": str(exc)}
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 2

    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
