#!/usr/bin/env python3
"""Deterministic STRATO-0 guardrail core — importable, bias-immune, ~0 cost.

This module is the **importable, CI-testable** heart of the static guardrails
fallback that lives at ``~/.claude/hooks/guardrails-static.py`` (a PreToolUse
hook registered in ``~/.claude/settings.json`` and invoked through
``~/.claude/hooks/guardrails-client.sh``).

Why this file exists (P1 STRATO-0 / verify-the-verifiers):
    The hook's matching logic was previously a top-level ``main()`` that read
    stdin and printed ``ALLOW`` / ``BLOCK`` — correct at runtime but **not
    importable**, so it could not be unit-tested and could silently rot. The
    P1 spec lists ``guardrails-static.py (PreToolUse block)`` as STRATO-0 of
    the funnel: "deterministico esistente, immune al bias, costo ~0". A
    deterministic gate that nothing tests is a paper door.

    This module extracts the matching logic byte-identically into a pure
    function ``is_dangerous(payload) -> (bool, reason)`` so a repo test
    (``scripts/test_guardrails_static.py``) can gate it in CI, and the
    ``~/.claude`` hook imports it (with a vendored fallback so it still works
    standalone if the repo is not on the box).

Contract (do NOT change without re-running scripts/test_guardrails_static.py):
    Patterns MUST stay byte-identical to the live daemon's BLOCK_PATTERNS /
    MCP / PROTECTED_PATH / SQL_DESTRUCTIVE_IN_CONTENT sets so the static
    fallback and the daemon never disagree. Duplication-by-design.

References:
    research/operations/specs/P1-verify-the-verifiers.md (STRATO-0)
    research/operations/specs/T1.2-guardrails-hook.md (Iteration 5)
    research/operations/2026-05-29-guardrails-realpath-bypass-patch7.md
"""

from __future__ import annotations

import re
from typing import Any

DESTRUCTIVE_SQL_VERBS = r"DROP|UPDATE|DELETE|INSERT|TRUNCATE"
SQL_ANCHORED = (
    r"^\s*(psql|sqlite3)\b"
    r"(?:\s+[^-][^\s]*|\s+--[^\s]+)*"
    r"\s+-c\s+['\"]"
    rf"(?:{DESTRUCTIVE_SQL_VERBS})\b"
)

ROLLBACK_TAG_ALLOWLIST = re.compile(
    r"^\s*git\s+reset\s+--hard\s+pre-orchestration-fix-\d{8}-\d{6}\s*$",
    re.IGNORECASE,
)

# (compiled-pattern, human-reason). Order matters only for which reason is
# reported on overlap — every pattern is a hard BLOCK.
BLOCK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # DA Patch 6 (emergency 2026-05-22 03:10) — require recursive flag
    (
        re.compile(
            r"\brm\s+(-[a-zA-Z]{0,8}[rR][a-zA-Z]{0,8}\s+){1,4}(/|/\*|\$HOME|~)(\s|$|/[\w\s.-]*/?)",
            re.IGNORECASE,
        ),
        "rm -rf on root/$HOME/~",
    ),
    # Patch 7 (2026-05-29) — close the `cd <protected> && rm -rf <anything>` bypass.
    # The Patch-6 regex only matches when the rm TARGET is literally /, $HOME, ~.
    # A `cd ~/Projects && rm -rf nuzantara` slipped through (the arg `nuzantara`
    # matches none of the alternatives) — empirically used 3x during the
    # 2026-05-28 cleanup. Block any recursive rm preceded by a `cd` into a
    # protected root in the same command line.
    (
        re.compile(
            r"\bcd\s+(/\s|~\s|~/|\$HOME|\$\{HOME\}|/Users/[\w.-]+/?)\S*\s*(&&|;)\s*.*\brm\s+-[a-zA-Z]{0,8}[rR]",
            re.IGNORECASE,
        ),
        "cd into root/$HOME + rm -rf (relative-path bypass)",
    ),
    # Patch 7 — quoted/braced $HOME and pre-expanded absolute home path.
    # Patch-6 only caught the bare `$HOME` token; these forms slipped through:
    #   rm -rf "$HOME"   rm -rf ${HOME}   rm -rf /Users/<username>
    (
        re.compile(
            r"\brm\s+(-[a-zA-Z]{0,8}[rR][a-zA-Z]{0,8}\s+){1,4}['\"]?(\$\{HOME\}|\$HOME|/Users/[\w.-]+)['\"]?(\s|$|/)",
            re.IGNORECASE,
        ),
        "rm -rf on quoted/absolute $HOME",
    ),
    # DA Patch 5 (emergency 2026-05-22 02:55) — anchor git reset to ^
    (re.compile(r"^\s*git\s+reset\s+--hard\b", re.IGNORECASE), "git reset --hard"),
    # main/master must be the push REFSPEC (whole token), not a substring inside a
    # branch name. `git push --force origin feature/redesign-main-nav` is NOT a
    # force-push to main — the old `.*\bmain\b` blocked it (over-match, superscar #3,
    # vaccine 2026-06-16). Now: the ref token is `main`/`master` exactly, or a
    # colon-refspec ending in `:main` / `HEAD:master`, bounded by whitespace/EOL.
    (
        re.compile(r"^\s*git\s+push\s+(--force|-f)\b.*(?:\s|:)(?:main|master)(?:\s|$)", re.IGNORECASE),
        "git push --force on main/master",
    ),
    (re.compile(SQL_ANCHORED, re.IGNORECASE), "psql/sqlite3 destructive SQL via -c"),
    (
        re.compile(r"\bANTHROPIC_API_KEY\s*=\s*['\"]?sk-", re.IGNORECASE),
        "ANTHROPIC_API_KEY assignment (HARD RULE: OAuth only)",
    ),
    (
        re.compile(r"\bANTHROPIC_API_KEY\s*=\s*['\"]?ant-", re.IGNORECASE),
        "ANTHROPIC_API_KEY assignment (HARD RULE: OAuth only)",
    ),
    (re.compile(r"\baws\s+iam\s+delete-", re.IGNORECASE), "AWS IAM delete"),
    (re.compile(r"\bfly\s+apps?\s+destroy\b", re.IGNORECASE), "fly apps destroy"),
    (
        re.compile(r"\bgcloud\s+projects?\s+delete\b", re.IGNORECASE),
        "gcloud projects delete",
    ),
    (re.compile(r"\bdd\s+.*\bof=/dev/[sh]d[a-z]", re.IGNORECASE), "dd to disk device"),
    (re.compile(r">\s*/dev/[sh]d[a-z]", re.IGNORECASE), "redirect to disk device"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\};\s*:", re.IGNORECASE), "fork bomb"),
    (
        re.compile(r"\bbase64\b.*\|\s*(bash|sh|zsh|python|perl)\b", re.IGNORECASE),
        "base64 decode-and-execute",
    ),
    (
        re.compile(r"\becho\s+[A-Za-z0-9+/=]{20,}\s*\|\s*base64\s+-d", re.IGNORECASE),
        "encoded payload base64 decode",
    ),
    (
        re.compile(
            r"\bpython\d?\s+-c\s+['\"].*\b(os\.system|subprocess|exec|eval|os\.remove|shutil\.rmtree)\b",
            re.IGNORECASE,
        ),
        "Python -c arbitrary exec",
    ),
    (
        re.compile(r"\bperl\s+-e\s+['\"].*\bsystem\(", re.IGNORECASE),
        "Perl -e system() bypass",
    ),
    (
        re.compile(r"\bnode\s+-e\s+['\"].*\b(exec|spawn|unlink)\b", re.IGNORECASE),
        "Node -e arbitrary exec",
    ),
    (
        re.compile(r"\bcurl\s+.*\|\s*(bash|sh|zsh)\b", re.IGNORECASE),
        "curl pipe to shell",
    ),
    (
        re.compile(r"\bwget\s+.*\|\s*(bash|sh|zsh)\b", re.IGNORECASE),
        "wget pipe to shell",
    ),
]

MCP_DESTRUCTIVE_TOOLS: set[str] = {
    "mcp__github__pr_merge",
    "mcp__github__pr_delete",
    "mcp__github__pr_create",
    "mcp__github__pr_update",
    "mcp__github__issue_delete",
    "mcp__github__issue_create",
    "mcp__github__release_delete",
    "mcp__github__release_create",
    "mcp__github__repo_delete",
    "mcp__claude_ai_Vercel__deploy_to_vercel",
    "mcp__claude_ai_Vercel__change_toolbar_thread_resolve_status",
}
# DA Patch 1 (H5 critical) — narrowed verb set (see daemon comment)
MCP_DESTRUCTIVE_PATTERN = re.compile(
    r"mcp__.*?__.*?(delete|drop|truncate|destroy|remove|wipe|purge)(?=_|$|[A-Z])",
    re.IGNORECASE,
)
PROTECTED_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p)
    for p in (
        r"\.env(\..*)?$",
        r"\.mcp\.json$",
        r"zantara_core\.py$",
        r"fly\.toml$",
        r"alembic/env\.py$",
    )
]
SQL_FILE_PATTERN = re.compile(r"\.sql$")
SQL_DESTRUCTIVE_IN_CONTENT = re.compile(
    r"\b(DROP\s+TABLE|TRUNCATE\s+TABLE|TRUNCATE\s+\w+|DROP\s+DATABASE|"
    r"DELETE\s+FROM\s+\w+|UPDATE\s+\w+\s+SET|INSERT\s+INTO\s+\w+)\b",
    re.IGNORECASE,
)

_EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def _normalize_sql_match(match: str) -> str:
    """Collapse whitespace in a destructive-SQL match so re-arrangements
    (newlines added, tabs->spaces, etc.) don't look like a NEW destructive."""
    return re.sub(r"\s+", " ", match).strip().upper()


def _new_destructive_introduced(new_content: str, old_content: str) -> bool:
    """Return True if ``new_content`` introduces a destructive SQL statement
    that wasn't present in ``old_content``.

    Diff-aware: an edit that wraps a pre-existing UPDATE/DELETE/DROP in an
    ``IF EXISTS`` guard is NOT a new destructive — both new and old contain
    the same ``UPDATE ...`` matches (one inside the guard, one as the old body).

    Used by Edit/Write/MultiEdit handlers on ``.sql`` files. Without this
    diff awareness the original overbroad regex blocks legitimate defensive
    wrappings (scar 2026-05-23 family: H5-MCP-2026-05-22 +
    SQL-bridge-outbox-mig-192).
    """
    new_matches = {
        _normalize_sql_match(m.group(0))
        for m in SQL_DESTRUCTIVE_IN_CONTENT.finditer(new_content or "")
    }
    if not new_matches:
        return False
    old_matches = {
        _normalize_sql_match(m.group(0))
        for m in SQL_DESTRUCTIVE_IN_CONTENT.finditer(old_content or "")
    }
    return bool(new_matches - old_matches)


def _read_prior_content(file_path: str) -> str:
    """Best-effort read of the on-disk content a Write would replace.

    A missing/unreadable file means a new file is being created — any
    destructive content IS being introduced, so return empty string.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return ""


# Patterns whose danger lives in shell STRUCTURE (a real pipe-to-interpreter),
# NOT in quoted text. For these we match against the QUOTE-STRIPPED command so a
# dangerous string mentioned inside an echo/grep argument is not a false block.
# Identified by reason-substring (stable across pattern edits). Over-match cancer
# (superscar #3) found 2026-06-16 by the innocence vaccine:
# `echo 'curl x | bash is dangerous'` was BLOCKED because the literal appeared in
# a quoted arg. SQL-via-`-c` / API-key patterns are NOT here — they NEED the
# quoted content, so they keep matching the raw command.
_STRUCTURE_ONLY_REASONS = (
    "curl pipe to shell",
    "wget pipe to shell",
    "base64 decode-and-execute",
)


def _strip_quotes(cmd: str) -> str:
    """Empty the CONTENT of single/double-quoted strings, preserving structure.

    `echo 'curl x | bash'` -> `echo ''`. A `| bash` that survives this is real
    shell structure, not a phrase inside an argument. State-free two-pass is
    sufficient: we only need to blank the content, not parse nesting perfectly.
    Mirrors worktree_isolation._strip_noise (same false-positive killer)."""
    cmd = re.sub(r"'[^']*'", "''", cmd)
    cmd = re.sub(r'"[^"]*"', '""', cmd)
    return cmd


def _eval_bash(tool_input: dict[str, Any]) -> tuple[bool, str | None]:
    command = tool_input.get("command", "") or ""
    if ROLLBACK_TAG_ALLOWLIST.match(command):
        return False, None
    stripped = _strip_quotes(command)
    for pat, reason in BLOCK_PATTERNS:
        # structure-only patterns match the quote-stripped view (no phrase-in-arg
        # false positives); all others match the raw command (need quoted payload).
        target = stripped if reason in _STRUCTURE_ONLY_REASONS else command
        if pat.search(target):
            return True, reason
    return False, None


def _eval_mcp(tool_name: str, tool_input: dict[str, Any]) -> tuple[bool, str | None]:
    if tool_name in MCP_DESTRUCTIVE_TOOLS:
        return True, f"MCP destructive tool: {tool_name}"
    if MCP_DESTRUCTIVE_PATTERN.search(tool_name):
        return True, f"MCP tool with destructive verb in name: {tool_name}"
    if isinstance(tool_input, dict):
        for key, value in tool_input.items():
            if isinstance(value, str) and SQL_DESTRUCTIVE_IN_CONTENT.search(value):
                return True, f"SQL destructive in MCP input field '{key}'"
    return False, None


def _eval_edit(tool_name: str, tool_input: dict[str, Any]) -> tuple[bool, str | None]:
    file_path = tool_input.get("file_path", "") or ""
    for pat in PROTECTED_PATH_PATTERNS:
        if pat.search(file_path):
            return True, f"{tool_name} on protected path: {file_path}"
    if not SQL_FILE_PATTERN.search(file_path):
        return False, None
    # Diff-aware on .sql: block only if the edit INTRODUCES a destructive
    # statement not present before. Lets defensive wrappers through.
    if tool_name == "MultiEdit":
        for edit in tool_input.get("edits", []) or []:
            if isinstance(edit, dict):
                new_s = edit.get("new_string", "") or ""
                old_s = edit.get("old_string", "") or ""
                if _new_destructive_introduced(new_s, old_s):
                    return (
                        True,
                        f"SQL destructive introduced in MultiEdit on {file_path}",
                    )
    elif tool_name == "Edit":
        new_s = tool_input.get("new_string", "") or ""
        old_s = tool_input.get("old_string", "") or ""
        if _new_destructive_introduced(new_s, old_s):
            return True, f"SQL destructive introduced in Edit on {file_path}"
    elif tool_name == "Write":
        content = tool_input.get("content", "") or ""
        prior = _read_prior_content(file_path)
        if _new_destructive_introduced(content, prior):
            return True, f"SQL destructive introduced in Write to {file_path}"
    else:
        # NotebookEdit on .sql — unusual, fall back to legacy strict
        content = (
            tool_input.get("content", "") or tool_input.get("new_string", "") or ""
        )
        if SQL_DESTRUCTIVE_IN_CONTENT.search(content):
            return True, f"SQL destructive in {file_path}"
    return False, None


def is_dangerous(payload: dict[str, Any]) -> tuple[bool, str | None]:
    """Deterministically classify a Claude Code tool_use payload.

    Returns ``(True, reason)`` if the tool_use matches a known-dangerous
    pattern and must be BLOCKED, else ``(False, None)`` to ALLOW.

    ``payload`` is the PreToolUse JSON: ``{"tool_name": str, "tool_input": dict}``.
    This function is pure (no I/O) except for the Write-on-.sql branch, which
    reads the target file from disk to do diff-aware SQL detection.
    """
    if not isinstance(payload, dict):
        # Defensive: caller should pass a dict. A non-dict is malformed —
        # the hook fails-closed on parse errors before reaching here.
        return True, "malformed payload (non-dict)"

    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    if tool_name == "Bash":
        return _eval_bash(tool_input)
    if tool_name.startswith("mcp__"):
        return _eval_mcp(tool_name, tool_input)
    if tool_name in _EDIT_TOOLS:
        return _eval_edit(tool_name, tool_input)
    return False, None


def evaluate(payload: dict[str, Any]) -> str:
    """Render the ``ALLOW`` / ``BLOCK <reason>`` line the client expects.

    ``~/.claude/hooks/guardrails-client.sh`` parses stdout with the cases
    ``ALLOW*`` and ``"BLOCK "*`` — the trailing space after BLOCK is part of
    the contract, so a bare reason MUST be space-prefixed.
    """
    blocked, reason = is_dangerous(payload)
    if blocked:
        return f"BLOCK {reason}"
    return "ALLOW"
