#!/usr/bin/env python3
"""host_boundary — PreToolUse hook 🔴 (phase-aware-guardrails BLOCK #1 / §9-A).

Blocks MUTATING WRITES to host-sensitive paths OUTSIDE the project worktrees —
in particular the agent's own control plane (`~/.claude/`), credentials
(`~/.ssh`, `~/.aws`, secret dotfiles), and the decision/state dir
(`~/.agent/decisions/`). Reads of secret files emit a non-blocking WARN.

WHY THIS EXISTS (load-bearing): the phase-aware switch introduces
`~/.claude/hooks/_phase.py`. plan-mode is NOT a physical sandbox (panel §9 Q3 —
it is user-in-the-loop; a distracted "Yes" can still write). Without this gate,
an agent could rewrite `_phase.py` / `settings.json` and DISARM the phase switch
itself (auto-bypass). So the guardian of the switch must exist and be hard
BEFORE the switch does. This gate stays 🔴 in EVERY phase (never relaxed in plan).

It does NOT protect the project repo (that's worktree_isolation.py + W79 +
worktree_file_write_check.py). It is the orthogonal "outside the repo" boundary.

Covered surfaces:
  - Bash: `>`/`>>`/`tee`/`sed -i`/`dd of=`/`cp`/`mv`/`install` whose resolved
    destination lands under a protected dir → exit 2 (BLOCK).
  - Edit/Write/MultiEdit: `tool_input.file_path` under a protected dir → exit 2.
  - Read-of-secret (cat/less/head/tail/Read on a secret dotfile) → stderr WARN,
    exit 0 (non-blocking — visibility, not prevention).

Reuses the W79 Bash-write-target extraction (verbatim) from
worktree_isolation.py, so the heredoc/quoting/`lsof`-class false-positive
killers come for free. Conservative by design: a target we cannot resolve is
ALLOWED (we only block HIGH-CONFIDENCE writes into a protected dir).

Kill switch: HOST_BOUNDARY_OFF=1 → always exit 0 (behaviour = before this hook).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from gate_coverage import record as _gc_record
except Exception:
    def _gc_record(hook_name, decision, payload=None):
        pass

# --- Protected destinations (writes here are blocked, anywhere on the host) ----
# Resolved against $HOME. Directory prefixes (a write to any descendant blocks)
# and exact secret files.
_HOME = pathlib.Path(os.path.expanduser("~")).resolve()

PROTECTED_DIRS = [
    _HOME / ".claude",          # hooks, settings.json, _phase.py — the control plane
    _HOME / ".ssh",
    _HOME / ".aws",
    _HOME / ".agent" / "decisions",
]
PROTECTED_FILES = [
    _HOME / ".nuzantara-secrets.env",
    _HOME / ".zshenv",
    _HOME / ".zshrc",
]

# --- CARVE-OUT (2026-06-16): liberati dentro ~/.claude perché NON sono control-plane né credenziali.
# scripts/ = strumenti dell'agente · projects/.../memory/ = la sua memoria. Scriverci non disarma
# guardrail (hooks/settings restano blindati) né tocca secret. Risolve l'over-block "tutto ~/.claude e' sacro".
UNPROTECTED_SUBPATHS = [
    _HOME / ".claude" / "scripts",
    _HOME / ".claude" / "projects",      # la memoria (MEMORY.md + i .md) vive qui
    _HOME / ".claude" / "venvs",
    # CARVE-OUT (2026-06-23): output di apprendimento agent WR2 (proposte amendment, lessons
    # Reflexion, observations). NON control-plane — sono i RISULTATI che gli agent DEVONO scrivere.
    # L'over-block faceva girare ig-metrics-analyst/reflexion senza persistere l'output.
    _HOME / ".claude" / "skills" / "bali-zero-brand" / "_proposed-amendments",
    _HOME / ".claude" / "skills" / "bali-zero-brand" / "_lessons",
    _HOME / ".claude" / "skills" / "bali-zero-brand" / "_observations",
]
# Secret-ISH read targets → WARN only (visibility, not block).
SECRET_READ_HINTS = (
    ".env", "secrets", "id_rsa", "id_ed25519", "credentials",
    ".nuzantara-secrets", "token",
)

# --- W79 write-target extraction (shared with worktree_isolation.py) ----------
# This block is a COPY, and "verbatim" is a promise prose cannot keep: the
# 2026-08-18 W119 cure fixed CPMV_RE in worktree_isolation.py and never reached
# this file, which went on asserting it was verbatim for 13 days — which is
# exactly why nobody looked. The five names below are now pinned identical by
# `test_w119b_write_regex_newline_bleed.py::test_w119b_shared_regexes_are_identical_in_both_hooks`,
# so a one-sided edit goes RED instead of going unnoticed. Change one, change both.
# Quick gate: does the command contain anything that could write a file?
WRITE_HINT_RE = re.compile(r"(>>?|\btee\b|\bsed\b[^|\n]*-i|\bdd\b[^|\n]*\bof=|\b(?:cp|mv|install)\b)")
REDIR_RE = re.compile(r"(?<![0-9>&])>>?\s*([^\s|;&)]+)")
TEE_RE = re.compile(r"\btee[ \t]+(?:-a[ \t]+)?([^\s|;&)]+)")
SEDI_RE = re.compile(r"\bsed\b[^|;&\n]*?-i\S*[ \t]+(?:-e[ \t]+\S+[ \t]+|'[^']*'[ \t]+|\"[^\"]*\"[ \t]+|\S+[ \t]+)([^\s|;&)]+)")
DDOF_RE = re.compile(r"\bdd\b[^|;&\n]*?\bof=([^\s|;&)]+)")
CPMV_RE = re.compile(r"\b(?:cp|mv|install)\b((?:[ \t]+(?:-\S+|[^\s|;&)]+))+)")
# Read commands whose FIRST file arg, if a secret, triggers a WARN.
READ_CMD_RE = re.compile(r"\b(cat|less|more|head|tail|bat)\b\s+((?:-\S+\s+)*)([^\s|;&)]+)")


def _strip_noise(cmd: str) -> str:
    """Neutralize heredoc bodies + quoted strings before scanning for write
    targets (W79 false-positive killer — verbatim)."""
    def _drop_heredocs(s: str) -> str:
        lines = s.split("\n")
        out: list[str] = []
        i = 0
        hd_re = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
        while i < len(lines):
            line = lines[i]
            m = hd_re.search(line)
            out.append(line)
            if m:
                word = m.group(2)
                i += 1
                while i < len(lines) and lines[i].strip() != word:
                    i += 1
                i += 1
                continue
            i += 1
        return "\n".join(out)

    s = _drop_heredocs(cmd)
    s = re.sub(r"'[^']*'", "''", s)
    s = re.sub(r'"[^"]*"', '""', s)
    return s


def _extract_write_targets(cmd: str) -> list[str]:
    """Best-effort write-destination paths (W79 logic — verbatim). Conservative:
    unresolvable target → not returned → ALLOWED."""
    cmd = _strip_noise(cmd)
    targets: list[str] = []
    for m in REDIR_RE.finditer(cmd):
        targets.append(m.group(1))
    for m in TEE_RE.finditer(cmd):
        targets.append(m.group(1))
    for m in SEDI_RE.finditer(cmd):
        targets.append(m.group(1))
    for m in DDOF_RE.finditer(cmd):
        targets.append(m.group(1))
    for m in CPMV_RE.finditer(cmd):
        toks = [t for t in m.group(1).split() if not t.startswith("-")]
        if toks:
            targets.append(toks[-1])
    cleaned = []
    for t in targets:
        t = t.strip().strip("'\"")
        if not t or t.startswith("/dev/") or t in {"&1", "&2"} or t.startswith("$("):
            continue
        cleaned.append(t)
    return cleaned


def _resolve_target(path_str: str, cwd: str) -> pathlib.Path | None:
    """Resolve a possibly-relative target against cwd (W79 — verbatim)."""
    try:
        p = pathlib.Path(os.path.expanduser(path_str))
        if not p.is_absolute() and cwd:
            p = pathlib.Path(cwd) / p
        return p.resolve()
    except Exception:
        return None


def _is_protected(resolved: pathlib.Path) -> bool:
    """True if a resolved path is a protected file or under a protected dir."""
    # carve-out: scripts/memory/venvs sotto ~/.claude sono mani+quaderno, non cervello+chiavi
    for u in UNPROTECTED_SUBPATHS:
        try:
            if resolved == u or resolved.is_relative_to(u):
                return False
        except AttributeError:
            try:
                resolved.relative_to(u); return False
            except ValueError:
                pass
    if resolved in PROTECTED_FILES:
        return True
    for d in PROTECTED_DIRS:
        try:
            if resolved == d or resolved.is_relative_to(d):
                return True
        except AttributeError:  # py<3.9
            try:
                resolved.relative_to(d)
                return True
            except ValueError:
                pass
    return False


def _write_hits_sensitive(cmd: str, cwd: str) -> pathlib.Path | None:
    """Offending path if a Bash write lands in a protected dir/file. Else None."""
    if not WRITE_HINT_RE.search(cmd):
        return None
    for raw in _extract_write_targets(cmd):
        resolved = _resolve_target(raw, cwd)
        if resolved is None:
            continue  # unclassifiable → conservative allow
        if _is_protected(resolved):
            return resolved
    return None


def _read_hits_secret(cmd: str, cwd: str) -> pathlib.Path | None:
    """Offending path if a Bash read targets a secret-ish file (WARN only)."""
    m = READ_CMD_RE.search(_strip_noise(cmd))
    if not m:
        return None
    target = m.group(3)
    low = target.lower()
    if not any(h in low for h in SECRET_READ_HINTS):
        return None
    resolved = _resolve_target(target, cwd)
    if resolved is None:
        return None
    # WARN only for secrets that are protected OR look secret by name
    return resolved


def _block(offending: pathlib.Path, surface: str, payload: dict | None = None) -> None:
    _gc_record("host_boundary", "deny", payload)
    sys.stderr.write(
        "HOST BOUNDARY VIOLATION (write to host-sensitive path)\n"
        f"  surface: {surface}\n"
        f"  target : {offending}\n"
        "  This path is the agent control plane / credentials — writing it can\n"
        "  disarm guardrails or leak/alter secrets. Blocked in EVERY phase\n"
        "  (host_boundary 🔴, phase-aware §9-A). If this is intentional operator\n"
        "  work, run it yourself outside the agent, or set HOST_BOUNDARY_OFF=1.\n"
    )
    sys.exit(2)


def main() -> int:
    if os.environ.get("HOST_BOUNDARY_OFF") == "1":
        _gc_record("host_boundary", "exempt", None)
        return 0
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            # Bug fixed 2026-08-27: valid JSON that isn't a dict (`null`,
            # `42`, `[]`, a bare string) used to crash the next line's
            # `.get()` — genuine unhandled AttributeError, before any
            # try/except here (model_routing_gate.py hit the identical class
            # 2026-08-22 and already carries this guard).
            _gc_record("host_boundary", "exempt", None)
            return 0
    except Exception:
        _gc_record("host_boundary", "exempt", None)
        return 0  # unparseable → never block on our own parse failure

    tool = payload.get("tool_name") or payload.get("name") or ""

    # --- Edit/Write/MultiEdit: direct file_path ---
    if tool in ("Edit", "Write", "MultiEdit"):
        fp = (payload.get("tool_input") or {}).get("file_path", "")
        if fp:
            resolved = _resolve_target(fp, payload.get("cwd", ""))
            if resolved is not None and _is_protected(resolved):
                _block(resolved, f"{tool} file_path", payload)  # exits, does not return
        _gc_record("host_boundary", "allow", payload)
        return 0

    # --- Bash: shell writes + secret reads ---
    if tool == "Bash":
        cmd = (payload.get("tool_input") or {}).get("command", "")
        cwd = payload.get("cwd", "")
        offending = _write_hits_sensitive(cmd, cwd)
        if offending is not None:
            _block(offending, "Bash write", payload)  # exits, does not return
        secret = _read_hits_secret(cmd, cwd)
        if secret is not None:
            sys.stderr.write(
                f"HOST BOUNDARY WARN (read of secret-ish file): {secret}\n"
                "  Allowed, but flagged — avoid printing secrets into transcripts "
                "(cicatrix 2026-06-03 P0). Prefer reading config via code.\n"
            )
        _gc_record("host_boundary", "allow", payload)
        return 0

    _gc_record("host_boundary", "exempt", payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
