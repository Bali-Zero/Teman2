#!/usr/bin/env python3
"""data_plane_guard — PreToolUse hook 🔴 (data-plane protection, registry-based).

Blocks INTERACTIVE hand-edits of curated datasets that must only be written by
their program's sanctioned COMPILER scripts (e.g. GARUDA-FILIERA's
`scripts/kbli_filiera/*.py` writing `data/kbli-filiera/**`). This generalizes
to every program in the org via `infra/claude-hooks/data-plane-registry.json`
— a new program registers its data plane by adding one entry there; this file
never needs to change.

CONTRACT (identical stdin/exit-code shape to host_boundary.py /
worktree_isolation.py in this same dir): JSON payload on stdin with
`tool_name` (or `name`), `tool_input`, `cwd`. Exit 2 + stderr = BLOCK.
Exit 0 (no stderr, or a WARN line) = ALLOW.

SURFACES COVERED:
  - Edit / Write / NotebookEdit: `tool_input.file_path` (or `notebook_path`).
  - Bash AND Monitor (both execute arbitrary shell commands via
    `tool_input.command` — Monitor is not a lesser surface, it is the SAME
    shell channel with different scheduling): direct shell-level writes —
    redirects, `tee`, `cp`/`install`/`rsync` destination, `mv` source AND
    destination, `sed -i`/`truncate` (ALL non-flag files, not just the
    last), `dd of=`, `touch`, `perl -i`, `rm`.

MATCHING (case-folded — APFS/macOS is case-insensitive, a lowercase edit of
the same real file must still block; W96-adjacent lesson) is worktree-aware:
walks UP from the resolved absolute path to the nearest `.git` entry and
relativizes against THAT root — but only if that root ALSO carries our own
`infra/claude-hooks/data-plane-registry.json` (a foreign git repo that merely
happens to be an ancestor directory, e.g. `/tmp/other/.git`, is never treated
as a Nuzantara checkout/worktree — it falls through to the safe absolute-path
comparison, which cannot match a repo-relative glob).

BASH/MONITOR COMMAND PARSING (superscar #3 studied first: W83/W84/W91/W92/W94
— over-match on substrings, cross-line quote fusion, whole-command
exemptions):
  - The command is noise-stripped (heredoc bodies dropped; quoted strings
    either unwrapped to their bare content — if that content itself looks
    like a plain path, so `> "protected/file"` isn't invisible — or blanked
    otherwise; then unquoted `#`-comments stripped) BEFORE anything else.
  - It is split into SEGMENTS on `&& || ; & | <newline>` (arg separators
    within a segment are `[ \t]` only, never `\s` — an arg-loop must not
    cross a newline and swallow the NEXT, unrelated command).
  - Within each segment, write-verbs are matched ONLY at command position
    (segment start, or right after `$(`/backtick) — `grep rm <file>` or
    `brew install jq` are never mistaken for the verb `rm`/`install` just
    because the word appears; a verb is a command, not a substring.
  - A segment whose command position is `ssh`/`scp` is skipped ENTIRELY for
    THAT segment only (W94: never a whole-command exemption) — the write
    happens on the far end, not here.
  - A pure `cd <path>` segment updates a running list of candidate base
    dirs; every later target is tried against the session cwd AND every
    accumulated cd-dir.
  - A candidate containing glob metacharacters (`*?[`) is expanded against
    the real filesystem (`glob.glob`, capped) so `rm protected/*.jsonl`
    cannot hide behind "no literal path token".
  - Only REDIRECT-sourced targets go through the bare-word plausibility
    filter (needs a separator/extension/dotfile/glob-char to look path-like,
    filtering shell-residue like `2>&1`'s stray `2`); VERB-sourced args
    (cp/mv/rm/tee/etc.) skip that filter — the command-position anchor
    already proves they are real arguments, so a bare `rm manifest` inside
    a protected cwd is not silently exempted just for lacking a slash.

Registry robustness (a malformed registry must degrade to a WARN + pass-
through, NEVER crash the hook and NEVER accidentally protect/block
everything): non-object top-level JSON, a non-list `entries`, a non-object
entry, or a `protected` field that isn't a list of strings (a bare STRING
iterates as characters — `"*"` alone would then match every file) are all
rejected per-item with a WARN, never trusted. The whole dispatch body is
wrapped so ANY unexpected exception degrades to WARN + ALLOW — `sys.exit(2)`
(a real block) is the one thing that still propagates through that wrapper.

Kill switch: DATA_PLANE_GUARD_OFF=1 → always exit 0.

Reference: cicatrix-superscar.md #3 (guard-over-match) + #9 (state-schema
drift) · registry: infra/claude-hooks/data-plane-registry.json · conformance:
infra/guard-conformance/registry.json · wave-2 adversarial review (Codex
gpt-5.6-sol xhigh, 2026-07-16): 2 CRITICAL + 10 MAJOR + 3 MINOR, all fixed
here.
"""
from __future__ import annotations

import fnmatch
import glob as glob_mod
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent  # infra/claude-hooks

# --------------------------------------------------------------------------
# Shared path-plausibility constants (used by both the quote-unwrap step in
# _strip_noise and the redirect-target filter in _is_plausible_path).
# --------------------------------------------------------------------------
_PATH_LIKE_RE = re.compile(r"^[~$]?[\w./@+-]+$")
_FILE_EXT_RE = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,7}$")
_GLOB_CHARS_RE = re.compile(r"[*?\[]")
_GLOB_MATCH_CAP = 2000


def _is_plausible_path(t: str) -> bool:
    """Real write targets have a directory separator, a file extension, a
    dotfile prefix, or glob metacharacters. Rejects operator/shell residue
    that survived noise-stripping (`2`, `''`, `=0.9`). Applied ONLY to
    redirect-sourced targets (C8) — verb-sourced args are already proven
    real by the command-position anchor."""
    if not t or len(t) > 256:
        return False
    if not _PATH_LIKE_RE.match(t):
        return bool(_GLOB_CHARS_RE.search(t))  # glob chars aren't in the path charset
    if "=" in t:
        return False
    has_sep = "/" in t
    has_ext = bool(_FILE_EXT_RE.search(t))
    is_dotfile = t.startswith(".") and len(t) > 1
    return has_sep or has_ext or is_dotfile


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
    """Validated registry entries, or None (+ WARN) on any load failure —
    never block on our own infra breaking, and never trust a malformed
    entry (B1: a bare-string `protected` iterates as characters; `"*"`
    alone would then match every file — that entry is skipped, not the
    whole registry)."""
    path = _registry_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        sys.stderr.write(
            f"data_plane_guard WARN: registry unreadable ({path}): {exc} "
            "— pass-through\n"
        )
        return None
    if not isinstance(data, dict):
        sys.stderr.write(
            f"data_plane_guard WARN: registry malformed (top-level JSON is "
            f"not an object at {path}) — pass-through\n"
        )
        return None
    entries = data.get("entries")
    if not isinstance(entries, list):
        sys.stderr.write(
            f"data_plane_guard WARN: registry malformed (no 'entries' list "
            f"at {path}) — pass-through\n"
        )
        return None
    valid: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            sys.stderr.write(
                f"data_plane_guard WARN: registry entry is not an object, "
                f"skipped: {entry!r}\n"
            )
            continue
        protected = entry.get("protected")
        if not isinstance(protected, list) or not all(isinstance(p, str) for p in protected):
            sys.stderr.write(
                f"data_plane_guard WARN: entry `{entry.get('id', '?')}` has "
                "a malformed 'protected' field (must be a list of strings), "
                "skipped\n"
            )
            continue
        valid.append(entry)
    return valid


# --------------------------------------------------------------------------
# Path resolution — worktree-aware, foreign-repo-aware, case-folded matching
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


def _is_nuzantara_checkout(root: pathlib.Path) -> bool:
    """A5/foreign-repo guard: a `.git` ancestor is only trusted as OUR repo
    root if it also carries our own registry file — any other git
    repository (e.g. `/tmp/other/.git`) is foreign, not a Nuzantara
    checkout/worktree, no matter how it happens to nest."""
    return (root / "infra" / "claude-hooks" / "data-plane-registry.json").exists()


def _repo_relative(resolved: pathlib.Path) -> str:
    """`resolved` relative to its own (trusted) git root; falls back to
    `_repo_root()` only when NO git root was found at all, else to the
    absolute path — which then simply cannot match a repo-relative glob
    (safe under-block, never a false block)."""
    git_root = _git_root_for(resolved)
    if git_root is not None:
        if _is_nuzantara_checkout(git_root):
            try:
                return resolved.relative_to(git_root).as_posix()
            except ValueError:
                pass
        else:
            # Foreign repository — do not fall through to _repo_root() at
            # all; relativizing a foreign path against OUR root could never
            # legitimately match, so go straight to the safe absolute form.
            return resolved.as_posix()
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


def _matched_entry(rel: str, entries: list[dict]) -> tuple[dict, str] | None:
    """First (entry, matched_glob) whose `protected` list matches `rel`,
    case-folded (C1: APFS/macOS is case-insensitive by default — a
    lowercase edit of the SAME real file must still be caught)."""
    rel_l = rel.lower()
    for entry in entries:
        for pattern in entry.get("protected", []):
            if fnmatch.fnmatchcase(rel_l, pattern.lower()):
                return entry, pattern
    return None


# --------------------------------------------------------------------------
# Bash/Monitor channel — direct shell-level writes only
# --------------------------------------------------------------------------

WRITE_HINT_RE = re.compile(
    r"(>>?|\btee\b|\bsed\b[^\n]*-i|\btruncate\b|\brm\b|\btouch\b|\bdd\b|\bperl\b|"
    r"\b(?:cp|mv|install|rsync)\b)"
)

# Command-position anchor: a write-verb only counts as a COMMAND if it sits
# at the start of a segment, or right after a nested command-substitution
# opener. Segments are already split on `&& || ; & | <newline>` (see
# SEGMENT_SPLIT_RE) so those separators never need to appear in this anchor.
_CMD_ANCHOR = r"(?:^|\$\(|`)[ \t]*"
_TOKEN = r"[^\s|;&)]+"  # a single non-flag token (never crosses whitespace)

REDIR_RE = re.compile(r"(?:[0-9]?>|&>)>?[ \t]*(" + _TOKEN + r")")
VERB_RE = re.compile(
    _CMD_ANCHOR + r"(cp|mv|install|rsync|truncate|rm|tee|touch)\b"
    r"((?:[ \t]+(?:-\S+|" + _TOKEN + r"))*)"
)
SED_INVOCATION_RE = re.compile(
    _CMD_ANCHOR + r"sed\b((?:[ \t]+(?:-\S+|" + _TOKEN + r"))*)"
)
DD_RE = re.compile(_CMD_ANCHOR + r"dd\b.*?\bof=(" + _TOKEN + r")")
PERL_INVOCATION_RE = re.compile(
    _CMD_ANCHOR + r"perl\b((?:[ \t]+(?:-\S+|" + _TOKEN + r"))*)"
)

SEGMENT_SPLIT_RE = re.compile(r"&&|\|\||;|&|\||\n")
_SEGMENT_REMOTE_RE = re.compile(r"^[ \t]*(?:ssh|scp)\b")
_CD_SEGMENT_RE = re.compile(r"^[ \t]*cd\b[ \t]+(" + _TOKEN + r")[ \t]*$")

# rm/tee/mv/truncate/touch: every non-flag arg is a candidate target.
# rm/tee/touch because every arg IS an independent destination. mv/truncate
# are the odd ones out among "SRC... DEST"-shaped verbs: mv DESTROYS its
# source (unlike cp/install/rsync, whose sources are read-only reads); C5
# multi-file truncate/sed -i truncate/overwrite EVERY file argument, not
# just the last one. cp/install/rsync stay LAST-non-flag-token-only.
_ALL_TARGETS_VERBS = {"rm", "tee", "mv", "truncate", "touch"}


def _perl_has_inplace(args: list[str]) -> bool:
    """True if any short-flag cluster in `args` carries `i` (perl combines
    flags like `-pi`, `-i.bak`, `-i`) — perl only writes files with -i."""
    for a in args:
        if a.startswith("--"):
            continue
        if a.startswith("-") and "i" in a[1:]:
            return True
    return False


def _strip_noise(cmd: str) -> str:
    """Neutralize heredoc bodies, quoted strings, and unquoted comments
    before scanning for write targets.

    Order matters: heredocs first (their body text is free-form and must
    never leak into the scan), then quotes, then comments (a `#` that WAS
    inside a quoted string is already resolved by the time comment-
    stripping runs, so it is never mistaken for a comment marker).

    Quoted strings are UNWRAPPED to their bare inner content when that
    content itself looks like a plain path (C3: `echo x > "protected/file"`
    must not become invisible just because the target is quoted — quoting a
    path is normal, not an escape technique); otherwise they are blanked as
    before (a quoted sed script, a commit message, anything with
    whitespace/metacharacters stays `''`/`\"\"`). W84: char classes exclude
    `\\n` so a stray quote on one line can never fuse with a quote several
    lines later and swallow real commands into "quoted text"."""

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

    def _quote_sub(quote_char: str):
        def _sub(m: re.Match) -> str:
            inner = m.group(1)
            if _PATH_LIKE_RE.match(inner):
                return inner
            return quote_char * 2

        return _sub

    s = _drop_heredocs(cmd)
    s = re.sub(r"'([^'\n]*)'", _quote_sub("'"), s)
    s = re.sub(r'"([^"\n]*)"', _quote_sub('"'), s)
    # A2: strip unquoted shell comments (whitespace-or-line-start `#` to
    # EOL) — `true # rm <protected>` must not leak the comment's content
    # into the scan as if it were a real command.
    s = re.sub(r"(?m)(?:^|(?<=\s))#.*$", "", s)
    return s


def _expand_glob_target(raw: str, cwd: str) -> list[pathlib.Path]:
    """C4: a candidate containing glob metacharacters is expanded against
    the REAL filesystem (glob.glob), capped, and each real match is
    returned as its own candidate. A pattern matching nothing (or an
    unresolvable base) yields an empty list — safe under-block."""
    try:
        p = pathlib.Path(os.path.expanduser(os.path.expandvars(raw)))
        if not p.is_absolute() and cwd:
            p = pathlib.Path(cwd) / p
        pattern = str(p)
    except Exception:
        return []
    try:
        matches = glob_mod.glob(pattern, recursive=True)
    except Exception:
        return []
    out: list[pathlib.Path] = []
    for m in matches[:_GLOB_MATCH_CAP]:
        try:
            out.append(pathlib.Path(m).resolve())
        except Exception:
            continue
    return out


def _resolve_candidates(raw: str, base_cwd: str) -> list[pathlib.Path]:
    if _GLOB_CHARS_RE.search(raw):
        return _expand_glob_target(raw, base_cwd)
    resolved = _resolve_target(raw, base_cwd)
    return [resolved] if resolved is not None else []


def _extract_from_segment(seg: str) -> list[tuple[str, bool]]:
    """Candidate (raw_target, is_redirect) pairs from a SINGLE segment
    (already confirmed local — never remote-dispatched). Verb/sed/dd/perl
    matches are anchored to command position so a verb-shaped WORD that is
    really an argument to a different command (grep's pattern, echo's
    text, brew's subcommand) is never mistaken for a command of its own."""
    out: list[tuple[str, bool]] = []

    for m in REDIR_RE.finditer(seg):
        out.append((m.group(1), True))

    for m in VERB_RE.finditer(seg):
        verb = m.group(1)
        args = [a for a in m.group(2).split() if not a.startswith("-")]
        if not args:
            continue
        picks = args if verb in _ALL_TARGETS_VERBS else [args[-1]]
        out.extend((a, False) for a in picks)

    # sed -i: ALL non-flag tokens (C5) — robust to both GNU (`sed -i
    # 's/a/b/' file`) and BSD (`sed -i '' 's/a/b/' file`) forms, and to
    # multi-file invocations that mutate every file argument, not just the
    # last one.
    for m in SED_INVOCATION_RE.finditer(seg):
        args = m.group(1).split()
        if not any(a == "-i" or a.startswith("-i") for a in args):
            continue  # sed without -i writes to stdout, not a file write
        nonflag = [a for a in args if not a.startswith("-")]
        out.extend((a, False) for a in nonflag)

    for m in DD_RE.finditer(seg):
        out.append((m.group(1), False))

    for m in PERL_INVOCATION_RE.finditer(seg):
        args = m.group(1).split()
        if not _perl_has_inplace(args):
            continue
        nonflag = [a for a in args if not a.startswith("-")]
        out.extend((a, False) for a in nonflag)

    return out


def _extract_bash_write_targets(cmd: str, cwd: str) -> list[pathlib.Path]:
    """Resolved absolute candidate paths for a Bash/Monitor command,
    honoring segment-scoped ssh/scp skip (A3), cd-tracking (C7), and glob
    expansion (C4). C8: only REDIRECT-sourced candidates go through the
    bare-word plausibility filter — verb-sourced args are already proven
    real by the command-position anchor."""
    stripped = _strip_noise(cmd)
    if not WRITE_HINT_RE.search(stripped):
        return []

    segments = SEGMENT_SPLIT_RE.split(stripped)
    cd_bases: list[str] = [cwd]
    raw_candidates: list[tuple[str, bool]] = []

    for seg in segments:
        if _SEGMENT_REMOTE_RE.match(seg):
            continue  # A3: this segment's write happens on another host
        cd_m = _CD_SEGMENT_RE.match(seg)
        if cd_m:
            new_base = _resolve_target(cd_m.group(1), cd_bases[-1])
            if new_base is not None:
                cd_bases.append(str(new_base))
            continue
        raw_candidates.extend(_extract_from_segment(seg))

    resolved: list[pathlib.Path] = []
    for raw, is_redirect in raw_candidates:
        t = raw.strip().strip("'\"")
        if not t or t.startswith("/dev/") or t in {"&1", "&2"} or t.startswith("$("):
            continue
        if is_redirect and not _is_plausible_path(t):
            continue
        for base in cd_bases:
            resolved.extend(_resolve_candidates(t, base))
    return resolved


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


def _dispatch() -> int:
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

    if tool in ("Bash", "Monitor"):
        cmd = tool_input.get("command", "")
        for resolved in _extract_bash_write_targets(cmd, cwd):
            rel = _repo_relative(resolved)
            hit = _matched_entry(rel, entries)
            if hit is not None:
                entry, pattern = hit
                _block(rel, entry, pattern, f"{tool} write")
        return 0

    return 0


def main() -> int:
    if os.environ.get("DATA_PLANE_GUARD_OFF") == "1":
        return 0
    try:
        return _dispatch()
    except SystemExit:
        raise  # a real block must never be swallowed by the safety net below
    except Exception as exc:
        sys.stderr.write(
            f"data_plane_guard WARN: unexpected internal error ({exc!r}) "
            "— pass-through (never crash-block)\n"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
