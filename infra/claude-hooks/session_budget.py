#!/usr/bin/env python3
"""session_budget — artifact-on-death handoff (K3) + session visibility (F7).

Registered on THREE hook events — SubagentStop, SessionEnd, PreCompact — one
script, event told apart via payload["hook_event_name"] (mailbox_inject.py in
this same directory is the existing precedent for one script serving several
event registrations in this codebase). Writes
~/.claude/state/handoff/<session_id>.md with: cwd, branch, `git -C <cwd> diff
--stat` and `git -C <cwd> diff` (capped at DIFF_CAP_BYTES, and
SECRET-REDACTED — see redact_secrets()), transcript size in MB, a
best-effort compaction count, and the last 20 tool NAMES only (never tool
INPUT — that can carry message content / file contents / secrets: NO
message content ever lands in this artifact). Prints the handoff path to
stdout.

WHY THIS EXISTS: cicatrix lesson "a subagent's idle is not its report" — a
subagent (or a session) can die — context exhaustion, crash, SIGTERM, a
sibling's worktree reap — without ever emitting a final message that names
what it was doing or how far it got. This hook is the artifact left behind
regardless of HOW the turn ends, so the next reader (human or the next
session) has cwd/branch/diff/last-tool-names on disk without needing the
dead turn's own cooperation.

Deliberately NO real budget enforcement (2026-08-26 retro §3bis, Sol's
refutation of the original F7 proposal: "no blocco dello Stop — nessun
budget reale, n=1") — this is visibility only, never a gate. It never
blocks, never raises past main(), and degrades silently on every failure.

Kill switch: SESSION_BUDGET_OFF=1 → no-op, exits 0 without writing anything.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

STATE_DIR = os.path.expanduser("~/.claude/state/handoff")
# Shares the gate-coverage state ROOT for the self-counted compaction
# counter (own subkey/extension, unrelated to gate decisions themselves) —
# one less directory for the operator to know about.
COUNTER_DIR = os.path.expanduser("~/.claude/state/gate-coverage")
DIFF_CAP_BYTES = 200_000
GIT_TIMEOUT_S = 10
LAST_N_TOOLS = 20
TRANSCRIPT_TAIL_BYTES = 2_000_000

# Best-effort secret redaction for the git-diff text this hook writes into a
# NEW artifact. Not a security boundary (the diff content is already local
# to this machine) — it is the specific guard the mandate asked for: a
# leaked key/token shape must never be transcribed verbatim into the handoff.
# Order does not change the outcome (every pattern redacts to the same
# marker) — kept roughly specific-to-generic for readability only.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{4,}"),                        # OpenAI/Anthropic-shaped key
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),                        # GitHub PAT
    re.compile(r"gh[oprsu]_[A-Za-z0-9]{20,}"),                  # other GitHub token classes
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),                # Slack token
    re.compile(r"AKIA[0-9A-Z]{16}"),                            # AWS access key id
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),                      # Google API key
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT-shaped
    re.compile(
        r"(?i)(api[_-]?key|access[_-]?token|auth[_-]?token|secret|password|passwd)"
        r"[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_\-\./+]{8,}"
    ),  # generic key: value / key=value shape
]


def redact_secrets(text: str) -> str:
    if not text:
        return text
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def _run(cmd: list, cwd: str | None = None, timeout: int = GIT_TIMEOUT_S) -> str:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout or ""
    except Exception:
        return ""


def _git_branch(cwd: str) -> str:
    out = _run(["git", "-C", cwd, "branch", "--show-current"], cwd=cwd)
    return out.strip() or "(detached HEAD or not a git repo)"


def _transcript_size_mb(transcript_path):
    if not transcript_path:
        return None
    try:
        return round(os.path.getsize(transcript_path) / (1024 * 1024), 2)
    except Exception:
        return None


def _last_n_tool_names(transcript_path, n: int = LAST_N_TOOLS, tail_bytes: int = TRANSCRIPT_TAIL_BYTES) -> list:
    """Best-effort last N tool NAMES only — never tool input (see module
    docstring: NO message content). Bounded tail-read."""
    if not transcript_path:
        return []
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            if size > tail_bytes:
                f.seek(size - tail_bytes)
                f.readline()
            text = f.read().decode("utf-8", errors="ignore")
    except Exception:
        return []
    names: list = []
    for line in text.splitlines():
        if '"type":"tool_use"' not in line and '"type": "tool_use"' not in line:
            continue
        try:
            evt = json.loads(line)
        except Exception:
            continue
        if not isinstance(evt, dict):
            continue
        content = (evt.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                name = item.get("name")
                if isinstance(name, str) and name:
                    names.append(name)
    return names[-n:]


def _bump_compaction_counter(session_id: str) -> int:
    """Self-counted, best-effort: incremented every time THIS hook fires for
    a PreCompact event on this session. Deliberately honest about what it
    is: no transcript field is documented/verified in this codebase to carry
    a compaction index, so inventing one would be exactly the
    phantom-citation class the repo's own anti-hallucination discipline
    forbids (cicatrix family #6). Undercounts if this hook was only
    installed mid-session — its own counter starts at 0 from install time,
    not from session start."""
    try:
        os.makedirs(COUNTER_DIR, exist_ok=True)
        path = os.path.join(COUNTER_DIR, f"{session_id}.compactions")
        n = 0
        if os.path.exists(path):
            try:
                with open(path) as f:
                    n = int((f.read() or "0").strip() or "0")
            except Exception:
                n = 0
        n += 1
        with open(path, "w") as f:
            f.write(str(n))
        return n
    except Exception:
        return 0


def _read_compaction_counter(session_id: str) -> int:
    try:
        path = os.path.join(COUNTER_DIR, f"{session_id}.compactions")
        if os.path.exists(path):
            with open(path) as f:
                return int((f.read() or "0").strip() or "0")
    except OSError:
        pass  # fail-open: missing/unreadable counter file — 0 is the honest answer, never crash a hook
    except ValueError:
        pass  # fail-open: counter file holds non-numeric garbage — same honest-zero answer
    return 0


def build_handoff_markdown(payload: dict) -> str:
    session_id = payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown"
    event = payload.get("hook_event_name") or "unknown-event"
    cwd = payload.get("cwd") or os.getcwd()
    transcript_path = payload.get("transcript_path")

    branch = _git_branch(cwd)
    diff_stat = _run(["git", "-C", cwd, "diff", "--stat"], cwd=cwd)
    diff_full = redact_secrets(_run(["git", "-C", cwd, "diff"], cwd=cwd))
    truncated = False
    diff_bytes = diff_full.encode("utf-8", errors="ignore")
    if len(diff_bytes) > DIFF_CAP_BYTES:
        diff_full = diff_bytes[:DIFF_CAP_BYTES].decode("utf-8", errors="ignore")
        truncated = True

    size_mb = _transcript_size_mb(transcript_path)
    last_tools = _last_n_tool_names(transcript_path)

    compactions = _bump_compaction_counter(session_id) if event == "PreCompact" else _read_compaction_counter(session_id)

    transcript_line = transcript_path or "(none in payload)"
    if size_mb is not None:
        transcript_line += f" ({size_mb} MB)"

    lines = [
        f"# Session handoff — {session_id}",
        "",
        f"- event: {event}",
        f"- ts: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        f"- cwd: {cwd}",
        f"- branch: {branch}",
        f"- transcript: {transcript_line}",
        f"- compactions observed by this hook: {compactions} "
        f"(self-counted from install time, not harness-derived — see module docstring)",
        "",
        "## git diff --stat",
        "```",
        diff_stat.strip() or "(clean)",
        "```",
        "",
        f"## git diff (secret-redacted, capped at {DIFF_CAP_BYTES} bytes"
        f"{' — TRUNCATED' if truncated else ''})",
        "```diff",
        diff_full.strip() or "(clean)",
        "```",
        "",
        f"## last {len(last_tools)} tool names (names only — no input/content)",
        "```",
        ", ".join(last_tools) if last_tools else "(none found in transcript tail)",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    if os.environ.get("SESSION_BUDGET_OFF") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    try:
        session_id = payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown"
        safe_id = "".join(c for c in str(session_id) if c.isalnum() or c in "-_") or "unknown"
        md = build_handoff_markdown(payload)
        os.makedirs(STATE_DIR, exist_ok=True)
        out_path = os.path.join(STATE_DIR, f"{safe_id}.md")
        with open(out_path, "w") as f:
            f.write(md)
        print(f"[session_budget] handoff written: {out_path}")
    except Exception as exc:
        sys.stderr.write(f"session_budget: internal error ({exc!r}) — fail-open\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
