#!/usr/bin/env python3
"""Tri-LLM Review Panel for autonomous code review.

Three independent reviewers vote on a PR diff:

1. **Codex** (gpt-5.5 high, OAuth Pro) — agentic coding specialist
2. **Claude Opus 4.7 max effort** (OAuth, free) — deep reasoning
3. **DeepSeek Reasoner v4** (~$0.01/query, allowed by hard rule)

Voting outcome:
- ≥2/3 GREEN + CI green → eligible for auto-merge
- 1/3 GREEN → escalation to user via Telegram (no auto-merge)
- 0/3 GREEN → revert + Linear ticket

Each reviewer returns a structured verdict via JSON:
    {
        "verdict": "green" | "yellow" | "red",
        "p0_issues": [...],
        "p1_issues": [...],
        "summary": "..."
    }

Usage:
    python codex_tri_llm_review.py --pr <number>
    python codex_tri_llm_review.py --diff-file /path/to/diff.patch
    python codex_tri_llm_review.py --branch feature/xyz [--base main]

Output:
    JSON on stdout with full panel decision + per-reviewer verdicts.
    Exit code:
        0 = panel green (≥2/3 verde, eligible auto-merge)
        1 = panel yellow (1/3 verde, escalation)
        2 = panel red (0/3 verde, revert recommended)
        3 = error (panel did not complete)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import shlex
import subprocess
import sys
import textwrap
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Hard rule: NO ANTHROPIC_API_KEY. Defense-in-depth strip.
for forbidden in ("ANTHROPIC_API_KEY", "AWS_BEDROCK_ANTHROPIC_KEY", "VERTEX_AI_ANTHROPIC_KEY"):
    if forbidden in os.environ:
        del os.environ[forbidden]

REPO_ROOT = Path("/Users/nuzantara/Desktop/nuzantara")
LOG_DIR = Path.home() / "logs" / "tri-llm-review"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("tri-llm-review")

# ─────────────────────────────────────────────────────────────────────────────
# Verdict structure
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ReviewVerdict:
    reviewer: str  # "codex" | "claude-opus" | "deepseek"
    verdict: str  # "green" | "yellow" | "red"
    p0_issues: list[str] = field(default_factory=list)
    p1_issues: list[str] = field(default_factory=list)
    summary: str = ""
    duration_s: float = 0.0
    error: str | None = None
    raw_output: str = ""  # truncated to 2000 chars for log


@dataclass
class PanelDecision:
    pr_number: int | None
    branch: str | None
    diff_sha: str  # sha256[:16] of the diff for traceability
    diff_lines: int
    verdicts: list[ReviewVerdict]
    panel_outcome: str  # "green" | "yellow" | "red"
    green_count: int
    auto_merge_eligible: bool
    timestamp: str


# ─────────────────────────────────────────────────────────────────────────────
# Reviewer prompt
# ─────────────────────────────────────────────────────────────────────────────

REVIEW_PROMPT_TEMPLATE = """You are reviewing a code change in the Nuzantara monorepo (production AI/RAG platform for Bali Zero, Indonesia business services).

Read repository AGENTS.md files (root + relevant subdirs) for project-specific rules. The most important rules:
- Hard rule: NO new code path may introduce ANTHROPIC_API_KEY usage. Only `claude_oauth_client.py` is allowed for Anthropic.
- Hard rule: NO new OPENAI_API_KEY usage beyond existing embedding model `text-embedding-3-small`.
- Embedding model is FROZEN — any change = P0 reject.
- `backend/app/dependencies.py` is imported by ALL routers. Changes need full chain test.
- Migrations: unique numbers, `-- === ROLLBACK ===` marker required, Squawk-clean.
- Routers: must be in BOTH `router_manifest.py` AND explicit `include_router()` call in `router_registration.py`.
- Public endpoints: new `/api/*` route must be in `public_endpoints.py` `_INFRA` group if intended public.
- Async HTTP: `httpx.AsyncClient()` in method/loop = P0 reject. Persistent client only.
- No `print()` in business logic. Use `logger`.
- No hardcoded secrets ever.

Review priorities:
- P0 = block merge (security, hard-rule violation, prod-breaking, embedding model change, missing rollback marker, etc.)
- P1 = should fix before merge (style/contract drift, missing tests on critical path, public endpoint missing registration)
- P2 = nice-to-have (do not include in your verdict)

Output ONLY this JSON structure (no preamble, no markdown):
{{
    "verdict": "green" | "yellow" | "red",
    "p0_issues": ["specific file:line — issue description", ...],
    "p1_issues": ["specific file:line — issue description", ...],
    "summary": "1-2 sentence overall assessment"
}}

Verdict rules:
- "green" = no P0, ≤2 P1
- "yellow" = no P0, 3-5 P1
- "red" = ANY P0, OR >5 P1

Diff to review:
```diff
{diff}
```

PR context:
- Branch: {branch}
- Base: {base}
- Files changed: {files_count}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def get_diff(args: argparse.Namespace) -> tuple[str, list[str], str | None, str | None]:
    """Return (diff_text, files_changed, branch, base)."""
    if args.diff_file:
        diff_text = Path(args.diff_file).read_text()
        files = [
            line.split(" b/")[1].strip()
            for line in diff_text.splitlines()
            if line.startswith("diff --git ")
        ]
        return diff_text, files, args.branch, args.base
    if args.pr is not None:
        # Use gh to fetch PR diff
        result = subprocess.run(
            ["gh", "pr", "diff", str(args.pr), "--repo", "Balizero1987/Teman2"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gh pr diff failed: {result.stderr}")
        diff_text = result.stdout
        files_result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(args.pr),
                "--repo",
                "Balizero1987/Teman2",
                "--json",
                "files,headRefName,baseRefName",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if files_result.returncode != 0:
            raise RuntimeError(f"gh pr view failed: {files_result.stderr}")
        meta = json.loads(files_result.stdout)
        files = [f["path"] for f in meta.get("files", [])]
        return diff_text, files, meta.get("headRefName"), meta.get("baseRefName")
    if args.branch:
        base = args.base or "main"
        result = subprocess.run(
            ["git", "diff", f"{base}...{args.branch}"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git diff failed: {result.stderr}")
        files_result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...{args.branch}"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        files = [f for f in files_result.stdout.splitlines() if f]
        return result.stdout, files, args.branch, base
    raise ValueError("Specify one of --pr / --diff-file / --branch")


def build_prompt(diff: str, branch: str | None, base: str | None, files: list[str]) -> str:
    return REVIEW_PROMPT_TEMPLATE.format(
        diff=diff[: args_global.max_diff_chars],
        branch=branch or "unknown",
        base=base or "main",
        files_count=len(files),
    )


def parse_verdict(reviewer: str, raw: str, duration_s: float, error: str | None = None) -> ReviewVerdict:
    """Parse reviewer JSON output, fall back to red if unparseable."""
    if error:
        return ReviewVerdict(
            reviewer=reviewer,
            verdict="red",
            summary=f"reviewer failed: {error}",
            duration_s=duration_s,
            error=error,
            raw_output=raw[:2000],
        )
    text = raw.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    if text.startswith("json"):
        text = text[4:].lstrip()
    # Find JSON block
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return ReviewVerdict(
            reviewer=reviewer,
            verdict="red",
            summary="reviewer did not return JSON",
            duration_s=duration_s,
            error="no_json",
            raw_output=raw[:2000],
        )
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        return ReviewVerdict(
            reviewer=reviewer,
            verdict="red",
            summary=f"json decode error: {e}",
            duration_s=duration_s,
            error="json_decode",
            raw_output=raw[:2000],
        )
    verdict = data.get("verdict", "red")
    if verdict not in ("green", "yellow", "red"):
        verdict = "red"
    return ReviewVerdict(
        reviewer=reviewer,
        verdict=verdict,
        p0_issues=data.get("p0_issues", []),
        p1_issues=data.get("p1_issues", []),
        summary=data.get("summary", ""),
        duration_s=duration_s,
        raw_output=raw[:2000],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reviewers
# ─────────────────────────────────────────────────────────────────────────────


async def review_codex(prompt: str) -> ReviewVerdict:
    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            "codex",
            "--profile",
            "review",
            "exec",
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        duration = time.time() - start
        if proc.returncode != 0:
            return parse_verdict(
                "codex", stdout.decode(errors="replace"), duration, error=stderr.decode(errors="replace")[:500]
            )
        return parse_verdict("codex", stdout.decode(errors="replace"), duration)
    except asyncio.TimeoutError:
        return parse_verdict("codex", "", time.time() - start, error="timeout")
    except Exception as e:
        return parse_verdict("codex", "", time.time() - start, error=str(e))


async def review_claude_opus(prompt: str) -> ReviewVerdict:
    """Use Claude OAuth via local `claude` CLI — no API key, free under MAX plan."""
    start = time.time()
    # Strip ANTHROPIC_API_KEY from env passed to subprocess (defense in depth)
    env = os.environ.copy()
    for forbidden in ("ANTHROPIC_API_KEY", "AWS_BEDROCK_ANTHROPIC_KEY", "VERTEX_AI_ANTHROPIC_KEY"):
        env.pop(forbidden, None)
    # Need OAuth token from env, then keychain, then file
    if not env.get("CLAUDE_CODE_OAUTH_TOKEN") and not env.get("CLAUDE_CODE_OAUTH_TOKEN_1"):
        # Try keychain first (canonical location per memory discovery_oauth_token_keychain.md)
        keychain_result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True,
            text=True,
            check=False,
        )
        if keychain_result.returncode == 0 and keychain_result.stdout.strip():
            env["CLAUDE_CODE_OAUTH_TOKEN"] = keychain_result.stdout.strip()
        else:
            token_path = Path.home() / ".claude" / "token"
            if token_path.exists():
                env["CLAUDE_CODE_OAUTH_TOKEN"] = token_path.read_text().strip()
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "--model",
            "claude-opus-4-7",
            "--max-turns",
            "1",
            "--print",
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        duration = time.time() - start
        if proc.returncode != 0:
            return parse_verdict(
                "claude-opus", stdout.decode(errors="replace"), duration, error=stderr.decode(errors="replace")[:500]
            )
        return parse_verdict("claude-opus", stdout.decode(errors="replace"), duration)
    except asyncio.TimeoutError:
        return parse_verdict("claude-opus", "", time.time() - start, error="timeout")
    except Exception as e:
        return parse_verdict("claude-opus", "", time.time() - start, error=str(e))


async def review_deepseek(prompt: str) -> ReviewVerdict:
    """DeepSeek Reasoner v4 via API (~$0.01/query — explicitly allowed)."""
    start = time.time()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        # Try sourcing from .nuzantara-secrets.env
        secrets_path = Path.home() / ".nuzantara-secrets.env"
        if secrets_path.exists():
            for line in secrets_path.read_text().splitlines():
                if line.startswith("DEEPSEEK_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        return parse_verdict("deepseek", "", time.time() - start, error="no_api_key")

    try:
        import httpx  # type: ignore[import-not-found]
    except ImportError:
        return parse_verdict("deepseek", "", time.time() - start, error="httpx_missing")

    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            r = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-reasoner",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a strict code reviewer. Output ONLY the JSON requested, no preamble.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 8192,
                    "temperature": 0,
                },
            )
        duration = time.time() - start
        if r.status_code != 200:
            return parse_verdict(
                "deepseek", r.text[:1000], duration, error=f"http_{r.status_code}"
            )
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return parse_verdict("deepseek", content, duration)
    except Exception as e:
        return parse_verdict("deepseek", "", time.time() - start, error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Main panel
# ─────────────────────────────────────────────────────────────────────────────


async def run_panel(prompt: str) -> list[ReviewVerdict]:
    """Run all 3 reviewers in parallel, return verdicts (one per reviewer)."""
    logger.info("Launching tri-LLM panel (codex + claude-opus + deepseek)")
    results = await asyncio.gather(
        review_codex(prompt),
        review_claude_opus(prompt),
        review_deepseek(prompt),
        return_exceptions=False,
    )
    for r in results:
        logger.info(
            "  %s: %s (%.1fs)%s",
            r.reviewer,
            r.verdict,
            r.duration_s,
            f" — {r.error}" if r.error else "",
        )
    return list(results)


def compute_outcome(verdicts: list[ReviewVerdict]) -> tuple[str, int, bool]:
    """Return (panel_outcome, green_count, auto_merge_eligible)."""
    green_count = sum(1 for v in verdicts if v.verdict == "green")
    if green_count >= 2:
        return "green", green_count, True
    if green_count == 1:
        return "yellow", green_count, False
    return "red", green_count, False


def telegram_notify(decision: PanelDecision) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        secrets_path = Path.home() / ".nuzantara-secrets.env"
        if secrets_path.exists():
            for line in secrets_path.read_text().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        logger.warning("No TELEGRAM_BOT_TOKEN — skipping notify")
        return
    try:
        import httpx  # type: ignore[import-not-found]

        emoji = {"green": "✅", "yellow": "⚠️", "red": "🔴"}.get(decision.panel_outcome, "❓")
        pr_ref = f"PR #{decision.pr_number}" if decision.pr_number else f"branch `{decision.branch}`"
        msg = (
            f"{emoji} Tri-LLM Panel: {decision.panel_outcome.upper()} ({decision.green_count}/3 green)\n"
            f"{pr_ref}\n"
            f"Verdicts: " + " · ".join(f"{v.reviewer}={v.verdict}" for v in decision.verdicts)
        )
        if not decision.auto_merge_eligible and decision.green_count >= 1:
            msg += "\n⏳ Escalation: human review required"
        elif decision.panel_outcome == "red":
            msg += "\n🛑 Revert recommended"
        with httpx.Client(timeout=10.0) as client:
            client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            )
    except Exception as e:
        logger.warning("Telegram notify failed: %s", e)


async def main_async(args: argparse.Namespace) -> int:
    diff_text, files, branch, base = get_diff(args)
    if not diff_text.strip():
        logger.error("Empty diff — aborting")
        return 3
    diff_sha = hashlib.sha256(diff_text.encode()).hexdigest()[:16]
    diff_lines = diff_text.count("\n")
    logger.info("Diff sha=%s lines=%d files=%d branch=%s base=%s", diff_sha, diff_lines, len(files), branch, base)

    prompt = build_prompt(diff_text, branch, base, files)
    verdicts = await run_panel(prompt)
    outcome, green_count, auto_merge_eligible = compute_outcome(verdicts)

    decision = PanelDecision(
        pr_number=args.pr,
        branch=branch,
        diff_sha=diff_sha,
        diff_lines=diff_lines,
        verdicts=verdicts,
        panel_outcome=outcome,
        green_count=green_count,
        auto_merge_eligible=auto_merge_eligible,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )

    # Persist log entry
    log_file = LOG_DIR / f"panel-{time.strftime('%Y%m%d')}.jsonl"
    with log_file.open("a") as f:
        f.write(json.dumps(asdict(decision), default=str) + "\n")

    # Output JSON to stdout
    print(json.dumps(asdict(decision), default=str, indent=2))

    # Telegram notify (if enabled)
    if args.notify:
        telegram_notify(decision)

    return {"green": 0, "yellow": 1, "red": 2}.get(outcome, 3)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pr", type=int, help="GitHub PR number (uses gh CLI)")
    src.add_argument("--diff-file", type=Path, help="Path to a diff/patch file")
    src.add_argument("--branch", help="Local branch name (diffed against --base)")
    ap.add_argument("--base", default="main", help="Base branch for --branch mode (default: main)")
    ap.add_argument("--max-diff-chars", type=int, default=80000, help="Truncate diff at N chars (default: 80k)")
    ap.add_argument("--notify", action="store_true", help="Send Telegram notify on completion")
    return ap.parse_args()


if __name__ == "__main__":
    args_global = parse_args()
    sys.exit(asyncio.run(main_async(args_global)))
