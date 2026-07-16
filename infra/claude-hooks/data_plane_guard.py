#!/usr/bin/env python3
"""data_plane_guard — PreToolUse hook 🔴 (data-plane protection, registry-based).

Blocks INTERACTIVE hand-edits of curated datasets that must only be written by
their program's sanctioned COMPILER scripts (e.g. GARUDA-FILIERA's
`scripts/kbli_filiera/*.py` writing `data/kbli-filiera/**`). This generalizes
to every program in the org via `infra/claude-hooks/data-plane-registry.json`
— a new program registers its data plane by adding one entry there; this file
never needs to change.

WHY THIS EXISTS: a compiled dataset hand-edited once by a session "just this
once" silently diverges from the pipeline that is supposed to be its single
source of truth — the exact state-schema-mutation-drift disease (superscar
#9) one layer earlier: catching the edit BEFORE it lands, not after a reader
breaks on it.

CONTRACT (identical stdin/exit-code shape to host_boundary.py /
worktree_isolation.py in this same dir): JSON payload on stdin with
`tool_name` (or `name`), `tool_input`, `cwd`. Exit 2 + stderr = BLOCK.
Exit 0 (no stderr, or a WARN line) = ALLOW.

SURFACES COVERED:
  - Edit / Write / NotebookEdit: `tool_input.file_path` (or `notebook_path`
    for NotebookEdit) resolved and matched against every registry glob.
  - Bash: DIRECT shell-level writes only — redirects (`>`/`>>`), `tee`,
    `cp`/`mv`/`install`/`rsync` destination, `sed -i`, `truncate`, `rm`.
    Reads (`cat`, `grep`, `jq`, a compiler invocation like `python3
    scripts/kbli_filiera/build.py`) are NOT a write operator and pass
    trivially — no write-hint keyword, no target extracted.

WORKTREE-AWARE MATCHING (superscar #3, W83/W84/W91/W92/W94 studied first —
guard-over-match on substrings, cross-line quote fusion, relative paths
resolved against the wrong cwd, whole-command exemptions): a protected glob
is repo-RELATIVE (`data/kbli-filiera/**`), but a session usually edits inside
`.worktrees/<lane>-<task-id>/...`, not the main checkout. Resolving the
absolute file path against a hardcoded main-checkout root would silently
under-block every worktree edit — exactly where sessions do their work. So
matching walks UP from the resolved absolute path looking for the nearest
`.git` entry (a worktree carries its OWN `.git` file; the main checkout
carries a `.git` directory) and relativizes against THAT — the file's own
git root, whichever checkout it happens to live in.

Quote/heredoc noise-stripping on the Bash channel reuses the W84-fixed
recipe (character classes exclude `\n` so a stray apostrophe/quote on one
line can never fuse with a quote on a LATER line and swallow real commands
into "quoted text"). Bash target extraction is deliberately simpler than
worktree_isolation.py's segment-scoped remote-dispatch machinery — that
machinery exists to decide "did this git op touch OUR checkout", a question
this guard doesn't ask. Here the write-hint tokens already stop at
`&`/`;`/`|`/whitespace by construction (the same char classes), so a target
can never bleed across a `&&`/`;`/`|` boundary into the wrong segment. Per
the spec: Edit/Write is the primary surface; Bash is deliberately
conservative and prefers UNDER-blocking over a new over-match member of
family #3.

Kill switch: DATA_PLANE_GUARD_OFF=1 → always exit 0 (behaviour = before this
hook). Missing/corrupt registry → PASS-THROUGH with a WARN (an infra-file
problem must never brick unrelated Edit/Write/Bash calls).

Reference: cicatrix-superscar.md #3 (guard-over-match) + #9 (state-schema
drift) · registry: infra/claude-hooks/data-plane-registry.json · conformance:
infra/guard-conformance/registry.json.
"""
from __future__ import annotations

import fnmatch
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent  # infra/claude-hooks


# --------------------------------------------------------------------------
# Repo/registry resolution
# --------------------------------------------------------------------------

def _repo_root() -> pathlib.Path:
    """CLAUDE_PROJECT_DIR if set (the harness always points this at the
    active session's project dir — main checkout or worktree), else the
    hook file's own repo root (two parents up from infra/claude-hooks/)."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return pathlib.Path(env)
    return HERE.parent.parent


def _registry_path() -> pathlib.Path:
    return _repo_root() / "infra" / "claude-hooks" / "data-plane-registry.json"


def _load_registry() -> list[dict] | None:
    """Registry entries, or None (+ WARN on stderr) on any load failure —
    never block on our own infra breaking."""
    path = _registry_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        sys.stderr.write(
            f"data_plane_guard WARN: registry unreadable ({path}): {exc} "
            "— pass-through\n"
        )
        return None
    entries = data.get("entries")
    if not isinstance(entries, list):
        sys.stderr.write(
            f"data_plane_guard WARN: registry malformed (no 'entries' list "
            f"at {path}) — pass-through\n"
        )
        return None
    return entries


# --------------------------------------------------------------------------
# Path resolution — worktree-aware repo-relative matching
# --------------------------------------------------------------------------

def _git_root_for(path: pathlib.Path) -> pathlib.Path | None:
    """Nearest ancestor carrying a `.git` entry (file, in a worktree, or
    dir, in the main checkout) — the file's OWN repo root, not a hardcoded
    one. Pure filesystem walk, no subprocess."""
    cur = path if path.is_dir() else path.parent
    for ancestor in (cur, *cur.parents):
        if (ancestor / ".git").exists():
            return ancestor
    return None


def _repo_relative(resolved: pathlib.Path) -> str:
    """`resolved` relative to its own git root (worktree-aware); falls back
    to `_repo_root()`, then to the absolute path (which then simply will
    not match any repo-relative glob — safe under-block, never a false
    block)."""
    git_root = _git_root_for(resolved)
    if git_root is not None:
        try:
            return resolved.relative_to(git_root).as_posix()
        except ValueError:
            pass
    try:
        return resolved.relative_to(_repo_root()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_target(path_str: str, cwd: str) -> pathlib.Path | None:
    """Resolve a possibly-relative path against cwd. None on any failure —
    an unresolvable target is never blocked (conservative)."""
    try:
        p = pathlib.Path(os.path.expanduser(os.path.expandvars(path_str)))
        if not p.is_absolute() and cwd:
            p = pathlib.Path(cwd) / p
        return p.resolve()
    except Exception:
        return None


# Residue filter (adapted from worktree_isolation.py's _is_plausible_path):
# a real write target has a directory separator, a file extension, or is a
# dotfile. Rejects operator/shell residue that survived noise-stripping
# (`2`, `''`, `=0.9`) so it can never be mistaken for a protected path.
_PATH_LIKE_RE = re.compile(r"^[~$]?[\w./@+-]+$")
_FILE_EXT_RE = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,7}$")


def _is_plausible_path(t: str) -> bool:
    if not t or len(t) > 256:
        return False
    if not _PATH_LIKE_RE.match(t):
        return False
    if "=" in t:
        return False
    has_sep = "/" in t
    has_ext = bool(_FILE_EXT_RE.search(t))
    is_dotfile = t.startswith(".") and len(t) > 1
    return has_sep or has_ext or is_dotfile


def _matched_entry(rel: str, entries: list[dict]) -> tuple[dict, str] | None:
    """First (entry, matched_glob) whose `protected` list matches `rel`."""
    for entry in entries:
        for pattern in entry.get("protected", []):
            if fnmatch.fnmatchcase(rel, pattern):
                return entry, pattern
    return None


# --------------------------------------------------------------------------
# Bash channel — direct shell-level writes only
# --------------------------------------------------------------------------

WRITE_HINT_RE = re.compile(
    r"(>>?|\btee\b|\bsed\b[^|;&]*-i|\btruncate\b|\brm\b|\b(?:cp|mv|install|rsync)\b)"
)
REDIR_RE = re.compile(r"(?:[0-9]?>|&>)>?\s*([^\s|;&)]+)")
VERB_RE = re.compile(
    r"\b(cp|mv|install|rsync|truncate|rm|tee)\b((?:\s+(?:-\S+|[^\s|;&)]+))+)"
)
SED_INVOCATION_RE = re.compile(r"\bsed\b((?:\s+(?:-\S+|[^\s|;&)]+))+)")

# rm/tee can write MULTIPLE targets in one invocation (every non-flag arg is
# a destination); cp/mv/install/rsync/truncate take the LAST non-flag token
# (source(s)... DEST).
_ALL_TARGETS_VERBS = {"rm", "tee"}


def _strip_noise(cmd: str) -> str:
    """Neutralize heredoc bodies + quoted strings before scanning for write
    targets (W79/W84 false-positive killer, cloned from worktree_isolation.py
    / host_boundary.py). W84: the quote char-classes MUST exclude `\\n` — a
    class that crosses newlines fuses an apostrophe on one line with a quote
    several lines later, collapsing multiple commands into one mangled
    string and producing a phantom write-target."""
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
    s = re.sub(r"'[^'\n]*'", "''", s)
    s = re.sub(r'"[^"\n]*"', '""', s)
    return s


def _extract_bash_write_targets(cmd: str) -> list[str]:
    """Best-effort candidate write-destination paths. Conservative: a target
    we cannot confidently extract is simply not returned (→ command is
    ALLOWED, per the spec's under-block preference on this channel)."""
    stripped = _strip_noise(cmd)
    if not WRITE_HINT_RE.search(stripped):
        return []

    targets: list[str] = []

    for m in REDIR_RE.finditer(stripped):
        targets.append(m.group(1))

    for m in VERB_RE.finditer(stripped):
        verb = m.group(1)
        args = [a for a in m.group(2).split() if not a.startswith("-")]
        if not args:
            continue
        if verb in _ALL_TARGETS_VERBS:
            targets.extend(args)
        else:
            targets.append(args[-1])

    # sed -i: take the LAST non-flag token of the whole invocation, not a
    # positional "script argument" guess — robust to BOTH GNU
    # (`sed -i 's/a/b/' file`, one quoted-script arg) and BSD/macOS
    # (`sed -i '' 's/a/b/' file`, an EXTRA empty-suffix arg before the
    # script) forms, since after noise-stripping every quoted arg collapses
    # to `''`/`""` and the real file path is always the tail token either way.
    for m in SED_INVOCATION_RE.finditer(stripped):
        args = m.group(1).split()
        if not any(a == "-i" or a.startswith("-i") for a in args):
            continue  # sed without -i writes to stdout, not a file write
        nonflag = [a for a in args if not a.startswith("-")]
        if nonflag:
            targets.append(nonflag[-1])

    cleaned: list[str] = []
    for t in targets:
        t = t.strip().strip("'\"")
        if not t or t.startswith("/dev/") or t in {"&1", "&2"} or t.startswith("$("):
            continue
        if not _is_plausible_path(t):
            continue
        cleaned.append(t)
    return cleaned


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def _block(rel: str, entry: dict, pattern: str, surface: str) -> None:
    sys.stderr.write(
        "DATA-PLANE GUARD VIOLATION (hand-edit of a curated dataset)\n"
        f"  surface : {surface}\n"
        f"  target  : {rel}\n"
        f"  matched : registry entry `{entry.get('id', '?')}` (owner: "
        f"{entry.get('owner', '?')}), glob `{pattern}`\n"
        "  This dataset is compiled, not hand-edited. Route the change\n"
        f"  through the program's compiler scripts ({entry.get('compilers', '?')}),\n"
        "  or open an implementer-lane PR that touches the source-of-truth\n"
        "  inputs instead. Escape hatch (only if this block is itself wrong):\n"
        "  DATA_PLANE_GUARD_OFF=1\n"
    )
    sys.exit(2)


def main() -> int:
    if os.environ.get("DATA_PLANE_GUARD_OFF") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # unparseable → never block on our own parse failure

    entries = _load_registry()
    if entries is None:
        return 0  # pass-through, WARN already emitted by _load_registry

    tool = payload.get("tool_name") or payload.get("name") or ""
    cwd = payload.get("cwd", "")
    tool_input = payload.get("tool_input") or {}

    if tool in ("Edit", "Write", "NotebookEdit"):
        fp = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if fp:
            resolved = _resolve_target(fp, cwd)
            if resolved is not None:
                rel = _repo_relative(resolved)
                hit = _matched_entry(rel, entries)
                if hit is not None:
                    entry, pattern = hit
                    _block(rel, entry, pattern, f"{tool} file_path")
        return 0

    if tool == "Bash":
        cmd = tool_input.get("command", "")
        for raw in _extract_bash_write_targets(cmd):
            resolved = _resolve_target(raw, cwd)
            if resolved is None:
                continue
            rel = _repo_relative(resolved)
            hit = _matched_entry(rel, entries)
            if hit is not None:
                entry, pattern = hit
                _block(rel, entry, pattern, "Bash write")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
