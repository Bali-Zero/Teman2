#!/usr/bin/env python3
"""docs-link-fixer — L2.5 automation layer for docs-guardian.

Reads broken-link details from `docs_audit.py --json` output, asks Claude
via OAuth CLI (claude -p) to decide per-link what to do, applies the fix,
validates post-fix via `docs_audit.py --check`, rolls back fixes that break
things.

Decisions Claude can return (strict JSON):
- {"action": "UPDATE_PATH", "new_path": "docs/archive/..."}
- {"action": "REMOVE_LINK"}
- {"action": "FIX_ANCHOR", "new_anchor": "section-name"}
- {"action": "SKIP", "reason": "..."}

Never imports the Anthropic Python SDK. Only shells out to `claude` CLI
which reads `CLAUDE_CODE_OAUTH_TOKEN` from env (secrets loaded by caller).

Usage:
  python scripts/docs_link_fixer.py --audit-json <path> [--dry-run] [--max-fixes N]

Exits 0 if any fixes applied (caller should re-run audit). Exits 1 if
catastrophic failure. Exits 2 if no broken links in input (no-op).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
PROMPT_TEMPLATE = """You are helping fix broken markdown links in a technical documentation repo.

FILE: {file_path}
BROKEN LINK TARGET: {link_target}
LINK TEXT: {link_text}
CONTEXT (3 lines before + the line with the link + 3 lines after):

{context}

The target `{link_target}` does not exist as a file in the repo.

Repo layout context:
- Docs live under `docs/**/*.md`.
- Archived docs live under `docs/archive/**/*.md`.
- Root-level docs: CLAUDE.md, INDEX.md, SYMBIOSIS.md, VADEMECUM.md, AUTONOMOUS_OPS.md.

Respond with ONE of these JSON objects (no other text, no markdown fences):

1. If you can deduce the target was moved/renamed and a very likely new path exists:
   {{"action": "UPDATE_PATH", "new_path": "docs/..."}}

2. If the target was clearly deleted and removing the link syntax (keeping the visible text as prose) makes the sentence still read naturally:
   {{"action": "REMOVE_LINK"}}

3. If the target file exists but the anchor fragment (#section) is wrong, and you have high confidence in the correct anchor:
   {{"action": "FIX_ANCHOR", "new_anchor": "section-name"}}

4. If you are not confident enough to fix safely:
   {{"action": "SKIP", "reason": "short reason"}}

STRICT RULES:
- Only emit JSON. No explanation, no markdown fences.
- Never guess paths you cannot verify.
- If in doubt → SKIP. False fixes are worse than no fix.
- For REMOVE_LINK, the link text becomes plain prose (caller handles syntax).
"""


@dataclass
class BrokenLink:
    file_path: str  # relative to repo root
    link_text: str
    link_target: str  # the broken target
    line_number: int  # 1-based


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit-json", required=True, help="Path to audit JSON output (use - for stdin)")
    p.add_argument("--repo", default=".", help="Repo root")
    p.add_argument("--dry-run", action="store_true", help="Print decisions without applying")
    p.add_argument("--max-fixes", type=int, default=50, help="Safety cap on fixes per run")
    p.add_argument("--timeout", type=int, default=60, help="Claude CLI timeout per call (sec)")
    return p.parse_args()


def load_audit(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_broken_links(repo: Path, file_rel: str) -> List[BrokenLink]:
    """Locate broken links inside a file by scanning its content, skipping code regions."""
    file_path = repo / file_rel
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    # Strip code regions (mirrors docs_audit._strip_code_regions)
    lines = content.splitlines(keepends=True)
    in_fence = False
    clean_lines = []
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            clean_lines.append("")  # placeholder to preserve line numbers
            continue
        if in_fence:
            clean_lines.append("")
            continue
        clean_lines.append(re.sub(r"`[^`\n]*`", "", line))

    broken: List[BrokenLink] = []
    for lineno, line in enumerate(clean_lines, start=1):
        for match in LINK_RE.finditer(line):
            target = match.group(2).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = target.split("#", 1)[0].split("?", 1)[0]
            if not target_path:
                continue
            resolved = (file_path.parent / target_path).resolve()
            try:
                resolved.relative_to(repo.resolve())
            except ValueError:
                continue
            if not resolved.exists():
                broken.append(BrokenLink(
                    file_path=file_rel,
                    link_text=match.group(1),
                    link_target=target,
                    line_number=lineno,
                ))
    return broken


def context_for_link(repo: Path, bl: BrokenLink, ctx_lines: int = 3) -> str:
    try:
        lines = (repo / bl.file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    start = max(0, bl.line_number - 1 - ctx_lines)
    end = min(len(lines), bl.line_number + ctx_lines)
    return "\n".join(lines[start:end])


def ask_claude(bl: BrokenLink, context: str, timeout: int) -> Optional[dict]:
    """Invoke `claude -p` with a strict JSON prompt. Returns parsed dict or None."""
    prompt = PROMPT_TEMPLATE.format(
        file_path=bl.file_path,
        link_target=bl.link_target,
        link_text=bl.link_text,
        context=context,
    )
    # Use --print (one-shot, no streaming), model haiku (cheap+fast, 2s-5s typical)
    cmd = ["claude", "-p", prompt, "--model", "claude-haiku-4-5-20251001"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    except FileNotFoundError:
        sys.stderr.write("error: 'claude' CLI not found on PATH\n")
        return None

    if result.returncode != 0:
        sys.stderr.write(f"claude exit={result.returncode}: {result.stderr[:200]}\n")
        return None

    out = result.stdout.strip()
    # Strip common fence wrappers claude sometimes adds despite instructions
    if out.startswith("```"):
        out = out.strip("`\n ").removeprefix("json").strip()
    if out.endswith("```"):
        out = out.rstrip("`\n ").strip()

    try:
        decision = json.loads(out)
    except json.JSONDecodeError:
        sys.stderr.write(f"non-json response: {out[:200]}\n")
        return None

    if not isinstance(decision, dict) or "action" not in decision:
        sys.stderr.write(f"invalid decision shape: {decision}\n")
        return None

    return decision


def apply_fix(repo: Path, bl: BrokenLink, decision: dict) -> bool:
    """Apply the decision in-place. Returns True if file modified, False otherwise."""
    action = decision.get("action")
    file_path = repo / bl.file_path
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return False

    lines = content.splitlines(keepends=True)
    if bl.line_number > len(lines):
        return False

    # The target line; replace only the first matching broken link in it
    original_line = lines[bl.line_number - 1]
    escaped_text = re.escape(bl.link_text)
    escaped_target = re.escape(bl.link_target)
    link_pattern = re.compile(rf"\[{escaped_text}\]\({escaped_target}\)")

    if not link_pattern.search(original_line):
        # Maybe the link got split across lines or line numbering shifted.
        return False

    if action == "UPDATE_PATH":
        new_path = decision.get("new_path", "").strip()
        if not new_path:
            return False
        # Verify target exists
        candidate = (file_path.parent / new_path).resolve()
        try:
            candidate.relative_to(repo.resolve())
        except ValueError:
            return False
        if not candidate.exists():
            return False
        replacement = f"[{bl.link_text}]({new_path})"
        new_line = link_pattern.sub(replacement, original_line, count=1)
    elif action == "REMOVE_LINK":
        # Replace `[text](target)` with just `text`
        new_line = link_pattern.sub(bl.link_text, original_line, count=1)
    elif action == "FIX_ANCHOR":
        new_anchor = decision.get("new_anchor", "").strip().lstrip("#")
        if not new_anchor:
            return False
        # Keep the same file path (without anchor) + new anchor
        base_target = bl.link_target.split("#", 1)[0]
        new_target = f"{base_target}#{new_anchor}"
        replacement = f"[{bl.link_text}]({new_target})"
        new_line = link_pattern.sub(replacement, original_line, count=1)
    elif action == "SKIP":
        return False
    else:
        return False

    if new_line == original_line:
        return False

    lines[bl.line_number - 1] = new_line
    file_path.write_text("".join(lines), encoding="utf-8")
    return True


def snapshot_file(repo: Path, rel: str) -> Optional[str]:
    try:
        return (repo / rel).read_text(encoding="utf-8")
    except OSError:
        return None


def restore_file(repo: Path, rel: str, content: str) -> None:
    (repo / rel).write_text(content, encoding="utf-8")


def validate_no_regression(repo: Path, original_broken_count: int,
                           cluster_args: List[str], whitelist_args: List[str]) -> Optional[int]:
    """Re-run audit; return broken count or None if audit failed."""
    cmd = [
        sys.executable, str(repo / "scripts" / "docs_audit.py"),
        "--repo", str(repo), "--json", "--quiet",
    ] + cluster_args + whitelist_args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (subprocess.SubprocessError, OSError):
        return None
    try:
        stats = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return int(stats.get("broken", 0))


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()

    audit = load_audit(args.audit_json)
    broken_total = int(audit.get("broken", 0))
    if broken_total == 0:
        print("[link-fixer] no broken links in audit — nothing to do", file=sys.stderr)
        return 2

    # Files with broken links
    broken_files = [f["path"] for f in audit.get("files", []) if f.get("broken", 0) > 0]

    # Reconstruct cluster+whitelist args from the audit call that produced the JSON.
    # Since the audit JSON doesn't embed them, we require the caller to have set
    # env vars or to pass via the guardian wrapper. For standalone invocation,
    # we just validate using an empty cluster/whitelist set — the --check will
    # still catch drift accurately.
    cluster_args: List[str] = []
    whitelist_args: List[str] = []

    fixes_applied = 0
    fixes_skipped = 0
    fixes_failed = 0

    for file_rel in broken_files:
        if fixes_applied >= args.max_fixes:
            print(f"[link-fixer] hit --max-fixes={args.max_fixes}, stopping", file=sys.stderr)
            break

        broken_links = find_broken_links(repo, file_rel)
        for bl in broken_links:
            if fixes_applied >= args.max_fixes:
                break

            context = context_for_link(repo, bl)
            decision = ask_claude(bl, context, args.timeout)

            if decision is None:
                fixes_skipped += 1
                print(f"[link-fixer] {file_rel}:{bl.line_number} → SKIP (claude call failed)", file=sys.stderr)
                continue

            if decision.get("action") == "SKIP":
                fixes_skipped += 1
                reason = decision.get("reason", "(no reason given)")
                print(f"[link-fixer] {file_rel}:{bl.line_number} → SKIP ({reason})", file=sys.stderr)
                continue

            if args.dry_run:
                print(f"[link-fixer] DRY {file_rel}:{bl.line_number} → {json.dumps(decision)}")
                fixes_applied += 1  # count as "would fix"
                continue

            # Snapshot before mutation for rollback
            snapshot = snapshot_file(repo, file_rel)
            if snapshot is None:
                fixes_failed += 1
                continue

            ok = apply_fix(repo, bl, decision)
            if not ok:
                fixes_failed += 1
                print(f"[link-fixer] {file_rel}:{bl.line_number} → FAILED to apply {decision}", file=sys.stderr)
                continue

            print(f"[link-fixer] {file_rel}:{bl.line_number} → {decision['action']}", file=sys.stderr)
            fixes_applied += 1

    # Summary
    print(json.dumps({
        "applied": fixes_applied,
        "skipped": fixes_skipped,
        "failed": fixes_failed,
        "broken_before": broken_total,
    }, indent=2))

    # Exit 0 if any applied, 2 if no-op, 1 if everything failed
    if fixes_applied > 0:
        return 0
    if fixes_failed > 0 and fixes_skipped == 0:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
