#!/usr/bin/env python3
"""output_hygiene_guard.py — PreToolUse(Bash/Read/Skill) hook, v2.

Re-implementation against docs/specs/2026-09-18-output-hygiene-guard-shapes-spec.md
after the v1 guard (PR #6724) was SUSPENDED at three on-disk gate rounds, each
finding a NEW over-match on an everyday command (cicatrix superscar #3). This
file is graded against that spec's case corpus (its §6, C01-C82), not against
its own improvisation — where this file and v1 differ, the spec wins.

DECISION, not detection (spec §1): DENY (exit 2 + one-line stderr reason,
never rewrites, never runs the command) or ALLOW (exit 0). Fails OPEN on any
exception, malformed/non-dict stdin, an unrelated tool, or malformed tool
input. No subprocess calls anywhere (filesystem APIs only). Kill
switch: NUZ_OUTPUT_HYGIENE_OFF=1. Latency budget: <50ms/call on M5.

Segmentation (spec §2): quoted strings ('...', "...", $'...') and heredoc
bodies (<<TAG/<<'TAG'/<<-TAG) are blanked length-preserving BEFORE anything
else; command substitutions ($(...) and `...`) are NOT blanked — instead
their inner text is judged as its own independent segment (recursion, capped
depth). The command is split into top-level STATEMENTS on `&&`, `||`, `;`,
a lone `&` (background), and newlines; each statement is further split into
pipe-connected STAGES on `|`. Each stage has leading `VAR=`, `env`, `time`,
`timeout [-k …] <dur>`, `nice`, `sudo`, `command`, `exec` peeled repeatedly
(the peeled `timeout` is remembered ONLY to exempt shape S8). `git` global
options (`-C`, `-c`, `--no-pager`, `--git-dir=`, `--work-tree=`, `-p`) are
peeled before the subcommand. A statement whose first stage's head (after
peeling) is `ssh`/`scp`/`rsync` runs off-box and is ALLOWED whole.

Shapes S1-S8 (spec §3) and downstream bounds (spec §4, checked against LATER
stages in the SAME pipe-chain, plus the flood stage's own stdout redirect,
plus running the whole statement in the background) are implemented per the
table verbatim; nothing outside that table is a guilt shape. Visible-entry
counting for S1 (spec §5) counts dotfiles only with -a/-A/--all/--almost-all,
threshold 150, the max across every listed target, message names the count.

S9 applies the same 24 KiB ceiling to the line slice requested through the
Read tool, exempting image/PDF/notebook suffixes. S10 denies only the explicit
skill-name set. Together the three matchers implement ten shapes.

S5 literal -name/-iname/-path bound per spec §3, C61.
"""
from __future__ import annotations

import json
import os
import re
import sys

THRESHOLD_ENTRIES = 150
MAX_FILE_BYTES = 24 * 1024
READ_DEFAULT_LIMIT = 2000
_READ_CHUNK = MAX_FILE_BYTES + 1
READ_EXEMPT_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tif",
    ".tiff", ".heic", ".svg", ".pdf", ".ipynb",
}
DENIED_SKILLS = {
    "claude-api": (
        "84 KiB manual for the paid per-token Anthropic endpoint the Builder "
        "Contract §3 bans"
    ),
}

RUNNER_NAMES = {"pytest", "vitest", "jest", "mocha", "ava", "tap", "jasmine", "karma"}

STDOUT_REDIR_RE = re.compile(r"(?<!\d)(?:&>>|&>|>>|>)(?!&)")
REDIR_TOKEN_RE = re.compile(r"^\d*(?:>>|<<<|<<-?|&>>|&>|>&\d*|<|>)")
HEREDOC_START_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
TOP_SPLIT_RE = re.compile(r"&&|\|\||;|&|\n")

MAX_SUB_DEPTH = 3


# ---------------------------------------------------------------------------
# Noise stripping (heredocs, quotes) and command-substitution extraction
# ---------------------------------------------------------------------------

def _strip_heredoc_bodies(cmd: str) -> str:
    out = list(cmd)
    for m in HEREDOC_START_RE.finditer(cmd):
        delim = m.group(2)
        nl = cmd.find("\n", m.end())
        if nl == -1:
            continue
        body_start = nl + 1
        end_m = re.compile(r"^[ \t]*" + re.escape(delim) + r"[ \t]*$", re.MULTILINE).search(
            cmd, body_start
        )
        body_end = end_m.start() if end_m else len(cmd)
        for i in range(body_start, body_end):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def _strip_quotes(text: str) -> str:
    result = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "$" and i + 1 < n and text[i + 1] == "'":
            j = i + 2
            while j < n and text[j] != "'":
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                j += 1
            end = min(j + 1, n)
            for k in range(i, end):
                if result[k] != "\n":
                    result[k] = " "
            i = end
            continue
        if c in ("'", '"'):
            j = i + 1
            while j < n and text[j] != c:
                if c == '"' and text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                j += 1
            end = min(j + 1, n)
            for k in range(i, end):
                if result[k] != "\n":
                    result[k] = " "
            i = end
            continue
        i += 1
    return "".join(result)


def _strip_noise(cmd: str) -> str:
    return _strip_quotes(_strip_heredoc_bodies(cmd))


def _mask_substitutions(text: str) -> tuple[str, list[str]]:
    """Blank $(...) and `...` spans (for SPLITTING only) and collect their
    inner text (for independent recursive evaluation)."""
    chars = list(text)
    subs: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == "$" and i + 1 < n and text[i + 1] == "(":
            depth = 1
            j = i + 2
            while j < n and depth > 0:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                j += 1
            inner_end = j - 1 if depth == 0 else j
            subs.append(text[i + 2:inner_end])
            for k in range(i, j):
                if chars[k] != "\n":
                    chars[k] = " "
            i = j
            continue
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j == -1:
                i += 1
                continue
            subs.append(text[i + 1:j])
            for k in range(i, j + 1):
                if chars[k] != "\n":
                    chars[k] = " "
            i = j + 1
            continue
        i += 1
    return "".join(chars), subs


# ---------------------------------------------------------------------------
# Segmentation: statements (&& || ; & newline) -> stages (|)
# ---------------------------------------------------------------------------

def _split_statements(split_view: str) -> list[tuple[int, int, str | None]]:
    spans = []
    last = 0
    for m in TOP_SPLIT_RE.finditer(split_view):
        spans.append((last, m.start(), m.group()))
        last = m.end()
    spans.append((last, len(split_view), None))
    return spans


def _split_pipe(split_view: str, start: int, end: int) -> list[tuple[int, int]]:
    spans = []
    last = start
    for i in range(start, end):
        if split_view[i] == "|":
            spans.append((last, i))
            last = i + 1
    spans.append((last, end))
    return spans


# ---------------------------------------------------------------------------
# Prefix / global-option peeling
# ---------------------------------------------------------------------------

_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _peel_prefixes(toks: list[str]) -> tuple[list[str], bool]:
    i, n = 0, len(toks)
    timeout_seen = False
    changed = True
    while changed and i < n:
        changed = False
        while i < n and _ASSIGN_RE.match(toks[i]):
            i += 1
            changed = True
        if i < n and toks[i] == "env":
            i += 1
            while i < n and _ASSIGN_RE.match(toks[i]):
                i += 1
            changed = True
        if i < n and toks[i] == "time":
            i += 1
            changed = True
        if i < n and toks[i] == "timeout":
            i += 1
            timeout_seen = True
            while i < n and toks[i].startswith("-"):
                i += 1
            if i < n:
                i += 1  # the duration value
            changed = True
        if i < n and toks[i] == "nice":
            i += 1
            while i < n and toks[i].startswith("-"):
                i += 1
            changed = True
        if i < n and toks[i] == "sudo":
            i += 1
            changed = True
        if i < n and toks[i] == "command":
            i += 1
            changed = True
        if i < n and toks[i] == "exec":
            i += 1
            changed = True
    return toks[i:], timeout_seen


def _peel_git_globals(toks: list[str]) -> list[str]:
    i, n = 1, len(toks)
    while i < n:
        t = toks[i]
        if t == "-C" and i + 1 < n:
            i += 2
            continue
        if t == "-c" and i + 1 < n:
            i += 2
            continue
        if t.startswith("-c") and "=" in t:
            i += 1
            continue
        if t == "--no-pager":
            i += 1
            continue
        if t.startswith("--git-dir=") or t.startswith("--work-tree="):
            i += 1
            continue
        if t in ("-p", "--paginate"):
            i += 1
            continue
        break
    return toks[i:]


def _strip_redirects(toks: list[str]) -> list[str]:
    out = []
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        m = REDIR_TOKEN_RE.match(t)
        if m:
            if m.end() == len(t):
                i += 2 if i + 1 < n else 1
            else:
                i += 1
            continue
        out.append(t)
        i += 1
    return out


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_path(path_arg: str | None, cwd: str) -> str | None:
    if path_arg is None:
        return cwd
    p = path_arg
    if p == "$HOME" or p.startswith("$HOME/"):
        p = os.path.expanduser("~") + p[len("$HOME"):]
    if "$" in p:
        return None
    try:
        p = os.path.expanduser(p)
        if not os.path.isabs(p):
            p = os.path.join(cwd, p)
        return os.path.realpath(p)
    except Exception:
        return None


def _short(s: str, n: int = 80) -> str:
    return s if len(s) <= n else s[: n - 1] + "\N{HORIZONTAL ELLIPSIS}"


def _resolve_dir(path_arg: str, cwd: str) -> str:
    r = _resolve_path(path_arg, cwd)
    return r if r else cwd


# ---------------------------------------------------------------------------
# Shape checkers — each returns (shape_id, message) or None
# ---------------------------------------------------------------------------

def _check_s1(head: str, args: list[str], cwd: str) -> tuple[str, str] | None:
    args = _strip_redirects(args)
    recursive = head == "tree"
    show_all = False
    dir_flag = False
    targets: list[str] = []
    for t in args:
        if t.startswith("--"):
            if t in ("--recursive", "--tree"):
                recursive = True
            elif t in ("--all", "--almost-all"):
                show_all = True
            elif t == "--directory":
                dir_flag = True
        elif t.startswith("-") and len(t) > 1:
            cluster = t[1:]
            if "R" in cluster:
                recursive = True
            if head == "eza" and "T" in cluster:
                recursive = True
            if "a" in cluster or "A" in cluster:
                show_all = True
            if "d" in cluster:
                dir_flag = True
        else:
            targets.append(t)
    if dir_flag:
        return None
    if recursive:
        shown = _short(targets[0] if targets else ".")
        return ("S1", f"recursive `{head}` ({shown})")
    check_targets = targets or [None]
    max_count, max_shown = -1, "."
    for t in check_targets:
        resolved = _resolve_path(t, cwd)
        count = 0
        if resolved and os.path.isdir(resolved):
            try:
                entries = os.listdir(resolved)
            except Exception:
                entries = []
            count = len(entries) if show_all else sum(1 for e in entries if not e.startswith("."))
        if count > max_count:
            max_count = count
            max_shown = t if t else "."
    if max_count > THRESHOLD_ENTRIES:
        return ("S1", f"`{head}` on a {max_count}-visible-entry directory ({_short(max_shown)})")
    return None


def _check_s2(args: list[str], cwd: str) -> tuple[str, str] | None:
    args = _strip_redirects(args)
    targets = [t for t in args if not t.startswith("-")]
    if not targets:
        return None
    max_size, shown = -1, None
    for t in targets:
        resolved = _resolve_path(t, cwd)
        if not resolved:
            continue
        try:
            if not os.path.isfile(resolved):
                continue
            size = os.path.getsize(resolved)
        except Exception:
            continue
        if size > max_size:
            max_size, shown = size, t
    if max_size > MAX_FILE_BYTES:
        return ("S2", f"`cat`/`bat` of a {max_size // 1024}KB file ({_short(shown or '')})")
    return None


def _s3_bounded(args: list[str]) -> bool:
    for i, t in enumerate(args):
        if t.startswith("-"):
            if re.match(r"^-\d+$", t):
                return True
            if t == "-n" and i + 1 < len(args):
                return True
            if t.startswith("--max-count"):
                return True
            if t.startswith(("--since", "--until", "--after", "--before")):
                return True
            if t == "-L":
                return True
        else:
            if ".." in t:
                return True
    if "--" in args:
        idx = args.index("--")
        if len(args[idx + 1:]) == 1:
            return True
    return False


_S4_FLAGS = {
    "--stat", "--shortstat", "--numstat", "--name-only", "--name-status",
    "--dirstat", "--summary", "-s", "--no-patch", "--quiet", "--exit-code",
    "--check", "--compact-summary",
}


def _s4_bounded(args: list[str]) -> bool:
    for t in args:
        if t in _S4_FLAGS:
            return True
        if t.startswith("--dirstat") or t.startswith("--stat="):
            return True
    return False


_S5_NAME_FLAG_RE = re.compile(
    r"(-name|-iname|-path)\s+(\"[^\"]*\"|'[^']*'|\$'[^']*'|\S+)"
)
_S5_GLOB_CHARS = ("*", "?", "[")


def _s5_unquote(val: str) -> str:
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    if val.startswith("$'") and val.endswith("'") and len(val) >= 3:
        return val[2:-1]
    return val


def _s5_has_literal_name_bound(orig_stage: str) -> bool:
    """§3's S5 row: `-name`/`-iname`/`-path` with a LITERAL (no glob char)
    pattern is an own-bound; a glob pattern (quoted or not) is not. Reads the
    ORIGINAL (pre-quote-blanking) stage text at this call's offsets, because
    `_strip_quotes` blanks a quoted pattern's content length-preserving for
    split-boundary purposes elsewhere — the pattern itself would otherwise be
    invisible (or worse, fragmented by `.split()`) by the time it reaches
    here as a token."""
    for m in _S5_NAME_FLAG_RE.finditer(orig_stage):
        val = _s5_unquote(m.group(2))
        if not any(ch in val for ch in _S5_GLOB_CHARS):
            return True
    return False


_S4_WORD_RE = re.compile(r"\"[^\"]*\"|'[^']*'|\$'[^']*'|\S+")


def _s4_words(orig_text: str) -> list[str]:
    """Quote-aware word split of ORIGINAL (pre-quote-blanking) text, each word
    unquoted — mirrors `_s5_has_literal_name_bound`'s reasoning for §4's
    `sed -n <range>` and `awk <NR-expr>` bounds, which can be quoted just like
    a `find -name` pattern and are otherwise invisible (or fragmented by
    `.split()`) once `_strip_quotes` has blanked them for split-boundary
    purposes elsewhere."""
    return [_s5_unquote(w) for w in _S4_WORD_RE.findall(orig_text)]


def _check_s5(head: str, args: list[str], _cwd: str, orig_stage: str = "") -> tuple[str, str] | None:
    args = _strip_redirects(args)
    if head in ("fd", "fdfind"):
        non_flags = [t for t in args if not t.startswith("-")]
        if non_flags:
            return None
    for i, t in enumerate(args):
        if t in ("-maxdepth", "--max-depth") and i + 1 < len(args):
            return None
        if t.startswith("--max-depth="):
            return None
        if head in ("fd", "fdfind") and t == "-d" and i + 1 < len(args):
            return None
    if head == "find":
        for i, t in enumerate(args):
            if t.startswith("-newer") and i + 1 < len(args):
                return None
            if t in ("-mmin", "-mtime") and i + 1 < len(args):
                return None
        if _s5_has_literal_name_bound(orig_stage):
            return None
        if "-delete" in args and not any(
            p in args
            for p in ("-print", "-print0", "-ls", "-printf", "-fprint", "-fprint0", "-fprintf")
        ):
            return None
    return ("S5", f"`{head}` without -maxdepth/literal -name/-delete")


def _has_recursive_flag(args: list[str]) -> bool:
    for t in args:
        if t in ("-r", "-R", "--recursive"):
            return True
        if t.startswith("-") and not t.startswith("--") and len(t) > 1:
            if "r" in t[1:] or "R" in t[1:]:
                return True
    return False


def _check_s6(head: str, args: list[str], cwd: str) -> tuple[str, str] | None:
    args = _strip_redirects(args)
    for i, t in enumerate(args):
        if t in ("--count", "--files-with-matches", "--quiet"):
            return None
        if t.startswith("--max-count"):
            return None
        if t == "-m" and i + 1 < len(args):
            return None
        if t.startswith("-") and not t.startswith("--") and len(t) > 1:
            if any(ch in t[1:] for ch in "lLcq"):
                return None
    non_flags = [t for t in args if not t.startswith("-")]
    candidates = non_flags[1:] if len(non_flags) >= 2 else non_flags
    if candidates:
        all_files = True
        for c in candidates:
            resolved = _resolve_path(c, cwd)
            if not resolved or not os.path.isfile(resolved):
                all_files = False
                break
        if all_files:
            return None
    return ("S6", f"`{head}` without -l/-c/-m and a non-file target")


def _s7_bounded(args: list[str]) -> bool:
    for i, t in enumerate(args):
        if t in ("--quiet", "--silent", "--tb=short", "--tb=line", "--tb=no"):
            return True
        if t.startswith("--reporter="):
            if t.split("=", 1)[1] == "dot":
                return True
        if t == "--reporter" and i + 1 < len(args) and args[i + 1] == "dot":
            return True
        if t.startswith("-") and not t.startswith("--") and len(t) > 1:
            if "q" in t[1:]:
                return True
    return False


def _check_s7(rest_args: list[str]) -> tuple[str, str] | None:
    rest_args = _strip_redirects(rest_args)
    if _s7_bounded(rest_args):
        return None
    return ("S7", "test runner without -q/--tb=short|line")


def _classify(
    toks: list[str], cwd: str, timeout_peeled: bool, orig_stage: str = ""
) -> tuple[str, str] | None:
    if not toks:
        return None
    head = toks[0]
    args = toks[1:]

    if head == "git":
        rest = _peel_git_globals(toks)
        if not rest:
            return None
        sub, sub_rest = rest[0], rest[1:]
        if sub == "stash" and sub_rest[:1] == ["show"]:
            sub, sub_rest = "show", sub_rest[1:]
        if sub in ("log", "reflog", "shortlog"):
            clean = _strip_redirects(sub_rest)
            if _s3_bounded(clean):
                return None
            return ("S3", f"`git {sub}` without -n/--max-count/a range")
        if sub in ("diff", "show"):
            clean = _strip_redirects(sub_rest)
            if sub == "show":
                for t in clean:
                    if not t.startswith("-") and re.match(r"^[^\s:]+:[^\s]+$", t):
                        return None
            if _s4_bounded(clean):
                return None
            return ("S4", f"`git {sub}` without --stat/--name-only/-s/--no-patch")
        return None

    if head in ("ssh", "scp", "rsync"):
        return None

    if head in ("ls", "eza", "exa", "tree"):
        return _check_s1(head, args, cwd)

    if head in ("cat", "bat", "batcat"):
        return _check_s2(args, cwd)

    if head in ("find", "fd", "fdfind"):
        return _check_s5(head, args, cwd, orig_stage)

    if head == "grep":
        if _has_recursive_flag(args):
            return _check_s6("grep", args, cwd)
        return None
    if head in ("rg", "ag", "ack"):
        return _check_s6(head, args, cwd)

    if head == "tail":
        if any(f in args for f in ("-f", "-F", "--follow")):
            return None if timeout_peeled else ("S8", "`tail -f`/`-F` never terminates")
        return None
    if head == "less":
        if "+F" in args:
            return None if timeout_peeled else ("S8", "`less +F` never terminates")
        return None
    if head == "watch":
        return None if timeout_peeled else ("S8", "`watch` never terminates")
    if head == "journalctl":
        if any(f in args for f in ("-f", "--follow")):
            return None if timeout_peeled else ("S8", "`journalctl -f` never terminates")
        return None

    if head in ("python3", "python") and args[:2] == ["-m", "pytest"]:
        return _check_s7(args[2:])
    if head in ("npm", "pnpm", "yarn") and args[:1] == ["test"]:
        return _check_s7(args[1:])
    if head == "go" and args[:1] == ["test"]:
        return _check_s7(args[1:])
    if head == "cargo" and args[:1] == ["test"]:
        return _check_s7(args[1:])
    if head == "pnpm" and len(args) >= 2 and args[0] == "exec" and args[1] in RUNNER_NAMES:
        return _check_s7(args[2:])
    if head in ("npx", "bunx") and args and args[0] in RUNNER_NAMES:
        return _check_s7(args[1:])
    if head in ("pytest", "vitest", "jest", "mocha"):
        return _check_s7(args)

    return None


def _downstream_bound(
    text: str, orig_text: str, stage_spans: list[tuple[int, int]], idx: int
) -> bool:
    for j in range(idx + 1, len(stage_spans)):
        s, e = stage_spans[j]
        seg = text[s:e]
        orig_seg = orig_text[s:e]
        toks = seg.split()
        if not toks:
            continue
        head, rest = toks[0], toks[1:]
        if head in ("head", "wc", "cut", "xargs", "jq", "md5", "md5sum", "shasum", "sha256sum"):
            return True
        if head == "tail":
            return True
        if head == "grep":
            for t in rest:
                if t in ("-c", "--count", "-l", "--files-with-matches"):
                    return True
                if t.startswith("-") and not t.startswith("--") and any(ch in t[1:] for ch in "cl"):
                    return True
                if t == "-m" or t.startswith("--max-count"):
                    return True
        if head == "gh" and "--jq" in rest:
            return True
        if head == "sed" and "-n" in rest:
            # -n's range argument (e.g. "1,40p") is often single- or
            # double-quoted; a quoted range is blanked in `seg`/`rest`, so
            # look it up, quoted or bare, in the ORIGINAL segment text.
            for w in _s4_words(orig_seg):
                if re.match(r"^\d+,\d+p$", w):
                    return True
        if head == "awk" and "NR" in orig_seg:
            # same reasoning: an `awk 'NR<=20'` program is normally quoted,
            # so "NR" itself is blanked out of `seg` by the time it gets
            # here — check the ORIGINAL segment instead.
            return True
        if head == "sort":
            return True
        if head == "uniq" and "-c" in rest:
            return True
        if head in ("python3", "python") and rest[:1] and rest[0] in ("-", "-c"):
            return True
    return False


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _line_bytes(handle) -> int:
    """Length of the next line, newline included, read in chunks of at most
    MAX_FILE_BYTES + 1 so a newline-free multi-MB file never lands in memory
    whole (spalla review of #6747). 0 at EOF."""
    total = 0
    while True:
        chunk = handle.readline(_READ_CHUNK)
        if not chunk:
            return total
        total += len(chunk)
        if chunk.endswith(b"\n"):
            return total


def _check_s9(tool_input: dict, cwd: str) -> tuple[str, str] | None:
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    resolved = os.path.expanduser(file_path)
    if not os.path.isabs(resolved):
        resolved = os.path.abspath(os.path.join(cwd, resolved))
    try:
        if not os.path.isfile(resolved):
            return None
        if os.path.splitext(resolved)[1].lower() in READ_EXEMPT_SUFFIXES:
            return None
    except Exception:
        return None

    offset = tool_input.get("offset", 1)
    limit = tool_input.get("limit", READ_DEFAULT_LIMIT)
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or isinstance(limit, bool)
        or not isinstance(limit, int)
    ):
        return None

    first_line = max(offset, 1)
    skip = first_line - 1
    slice_bytes = 0
    slice_lines = 0
    try:
        with open(resolved, "rb") as handle:
            for _ in range(skip):
                if not _line_bytes(handle):
                    return None
            for _ in range(max(limit, 0)):
                n = _line_bytes(handle)
                if not n:
                    break
                slice_bytes += n
                slice_lines += 1
    except Exception:
        return None

    if slice_bytes <= MAX_FILE_BYTES:
        return None

    total_lines = 0
    capped = False
    try:
        with open(resolved, "rb") as handle:
            while _line_bytes(handle):
                total_lines += 1
                if total_lines >= 100_000:
                    capped = True
                    break
    except Exception:
        return None
    total = f"{total_lines}+" if capped else str(total_lines)
    last_line = first_line + slice_lines - 1
    kib = slice_bytes // 1024
    short = _short(file_path)
    return (
        "S9",
        f"`Read` of {short} would return {kib} KiB "
        f"(lines {first_line}-{last_line} of {total}); pass offset/limit for a "
        "slice <= 24 KiB, or grep -n the heading you need first",
    )


def _check_s10(tool_input: dict) -> tuple[str, str] | None:
    skill = tool_input.get("skill")
    if not isinstance(skill, str) or not skill:
        return None
    name = skill.rsplit(":", 1)[-1]
    reason = DENIED_SKILLS.get(name)
    if reason is None:
        return None
    return (
        "S10",
        f"skill `{name}` is denied here: {reason}; use the claude-code-guide "
        "agent or context7 for Claude API docs",
    )


def _evaluate(cmd: str, cwd: str, depth: int = 0) -> tuple[str, str] | None:
    if not cmd or not cmd.strip() or depth > MAX_SUB_DEPTH:
        return None
    noise_stripped = _strip_noise(cmd)
    split_view, subs = _mask_substitutions(noise_stripped)
    statements = _split_statements(split_view)
    effective_cwd = cwd
    for start, end, delim in statements:
        if not split_view[start:end].strip():
            continue
        is_bg = delim == "&"
        stage_spans = _split_pipe(split_view, start, end)
        first_raw = noise_stripped[stage_spans[0][0]:stage_spans[0][1]]
        first_peeled, _ = _peel_prefixes(first_raw.split())
        if first_peeled and first_peeled[0] in ("ssh", "scp", "rsync"):
            continue
        whole_toks = noise_stripped[start:end].strip().split()
        peeled_whole, _ = _peel_prefixes(whole_toks)
        if len(stage_spans) == 1 and len(peeled_whole) == 2 and peeled_whole[0] == "cd":
            effective_cwd = _resolve_dir(peeled_whole[1], effective_cwd)
            continue
        for idx, (s_start, s_end) in enumerate(stage_spans):
            raw_stage = noise_stripped[s_start:s_end]
            # `noise_stripped` and `cmd` are the same length (quote/heredoc
            # blanking is length-preserving), so these offsets are also valid
            # into the ORIGINAL command text — needed by S5 to recover a
            # quoted -name/-iname/-path pattern's real content.
            orig_stage = cmd[s_start:s_end]
            toks = raw_stage.split()
            if not toks:
                continue
            peeled_toks, timeout_peeled = _peel_prefixes(toks)
            if not peeled_toks:
                continue
            verdict = _classify(peeled_toks, effective_cwd, timeout_peeled, orig_stage)
            if verdict is None:
                continue
            if is_bg:
                continue
            if STDOUT_REDIR_RE.search(raw_stage):
                continue
            if _downstream_bound(noise_stripped, cmd, stage_spans, idx):
                continue
            return verdict
    for sub_text in subs:
        r = _evaluate(sub_text, effective_cwd, depth + 1)
        if r:
            return r
    return None


def main() -> int:
    if os.environ.get("NUZ_OUTPUT_HYGIENE_OFF") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    cwd = data.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()
    try:
        tool_name = data.get("tool_name")
        if tool_name == "Bash":
            cmd = tool_input.get("command")
            if not isinstance(cmd, str) or not cmd.strip():
                return 0
            verdict = _evaluate(cmd, cwd)
        elif tool_name == "Read":
            verdict = _check_s9(tool_input, cwd)
        elif tool_name == "Skill":
            verdict = _check_s10(tool_input)
        else:
            return 0
    except Exception:
        return 0
    if not verdict:
        return 0
    shape_id, message = verdict
    if shape_id in ("S9", "S10"):
        sys.stderr.write(f"BLOCKED (output-hygiene) [{shape_id}]: {message}\n")
    else:
        sys.stderr.write(
            f"BLOCKED (output-hygiene) [{shape_id}]: {message} — can flood the session "
            f"context. Bound it: head/tail/wc/grep -c/--stat/-maxdepth/-q, a redirect, "
            f"or run it in the background.\n"
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
