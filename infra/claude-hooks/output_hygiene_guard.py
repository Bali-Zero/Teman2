#!/usr/bin/env python3
"""output_hygiene_guard.py — PreToolUse(Bash) hook.

Cure for context bloat by accident (Zero, 2026-09-18) after two live
over-reads in one session (`ls ~/.nuzantara-mailbox` 700+ entries,
`ls evidence/2026-09` 300+ entries, both read in full, no bound).

DENIES (exit 2, never rewrites) an UNBOUNDED command: ls/eza on a >150-entry
dir or with -R/--recursive; cat/bat of a >24KB file; git log w/o -n/--max-count; git diff/show w/o
--stat-family; find w/o -maxdepth; grep -r/rg w/o -l/-c/-m; a test runner w/o
-q/--tb=short|line; tail -f/-F (never terminates, no exemption). Exempt if
the SAME pipe-chain past the guilty stage carries head/tail(not -f)/cut/wc/
grep -c/sort|uniq -c/awk NR/sed -n <range>/jq/--jq/python3 -c, redirects to a
file, or backgrounds (trailing `&`/`nohup`).

Quoted strings/heredoc bodies are blanked length-preserving before any guilt
regex runs. Segments split on `&&`/`;`/`||`; a `|` stays inside one segment so
a downstream bound is visible. ssh/scp/rsync segments run off-box, skipped
(cf. worktree_isolation.py W83). `-C <path>`/leading `cd X` honoured.

No subprocess calls. Fails OPEN on any exception. Kill switch:
NUZ_OUTPUT_HYGIENE_OFF=1. Exit 2+stderr = block, exit 0 = allow.
"""
from __future__ import annotations

import json
import os
import re
import sys

TOP_SPLIT_RE = re.compile(r"\|\||&&|;")

BOUND_STAGE_RE = re.compile(
    r"\bhead\b"
    r"|\btail\b(?!\s*-[fF]\b)(?!\s*--follow\b)"
    r"|\bcut\b"
    r"|\bwc\b"
    r"|\bgrep\b[^|]*(-c\b|--count\b|-l\b|--files-with-matches\b|-m\s*\d)"
    r"|\bawk\b[^|]*NR\s*(<|==)"
    r"|\bsed\b[^|]*-n\b[^|]*\d+\s*,\s*\d+\s*p"
    r"|\bjq\b"
    r"|--jq\b"
    r"|\bpython3\s+-c\b"
    r"|\btee\s+\S"
)

CD_RE = re.compile(r"^cd\s+(\S+)$")

# (trigger, own-bound exemption, shape label, suggested bounded form)
SIMPLE_SHAPES = [
    (re.compile(r"^git\s+(?:-C\s+\S+\s+)?log\b"),
     re.compile(r"(?:^|\s)(-n\s*\d+|-\d+\b|--max-count(=|\s+)\d+|\S+\.\.\S+)"),
     "`git log` without -n/--max-count/a range", "`git log -10` or `git log --oneline | head -20`"),
    (re.compile(r"^git\s+(?:-C\s+\S+\s+)?(diff|show)\b"),
     re.compile(r"--stat\b|--name-only\b|--name-status\b|--numstat\b|--shortstat\b"),
     "`git diff`/`git show` without --stat", "`git diff --stat` or `git diff ... | head -40`"),
    (re.compile(r"^find\b"), re.compile(r"-maxdepth\b"),
     "`find` without -maxdepth", "`find . -maxdepth 2 -name x` or `find . -name x | head`"),
    (re.compile(r"^(python3?\s+-m\s+pytest|pytest|npm\s+test|pnpm\s+test|vitest|jest)\b"),
     re.compile(r"-q\b|--quiet\b|--tb=short\b|--tb=line\b"),
     "test runner without -q/--tb=short", "`pytest -q` or `pytest ... 2>&1 | tail -20`"),
]


def _strip_noise(cmd: str) -> str:
    """Blank quoted-string bodies and heredoc bodies, length-preserving."""
    out = list(cmd)
    for m in re.finditer(r"<<-?\s*(['\"]?)(\w+)\1", cmd):
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
    text = "".join(out)
    result = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ("'", '"'):
            j = i + 1
            while j < n and text[j] != c:
                if c == '"' and text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                j += 1
            for k in range(i, min(j + 1, n)):
                if result[k] != "\n":
                    result[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(result)


def _segments(text: str) -> list[tuple[int, int]]:
    spans, last = [], 0
    for m in TOP_SPLIT_RE.finditer(text):
        spans.append((last, m.start()))
        last = m.end()
    spans.append((last, len(text)))
    return spans


def _stages(text: str, start: int, end: int) -> list[tuple[int, int]]:
    spans, last = [], start
    for i in range(start, end):
        if text[i] == "|":
            spans.append((last, i))
            last = i + 1
    spans.append((last, end))
    return spans


def _grep_trigger(toks: list[str]) -> bool:
    if not toks:
        return False
    if toks[0] == "rg":
        return True
    if toks[0] == "grep":
        for t in toks[1:]:
            if t.startswith("-") and not t.startswith("--") and ("r" in t or "R" in t):
                return True
    return False


def _grep_bound_own(toks: list[str]) -> bool:
    for t in toks[1:]:
        if t in ("--count", "--files-with-matches"):
            return True
        if t.startswith("-") and not t.startswith("--") and any(ch in t for ch in "lcm"):
            return True
    return False


def _grep_targets_are_files(toks: list[str], cwd: str) -> bool:
    """`rg pat file.py` / `grep -rn pat file.py` read one named file each: not a flood."""
    # the pattern is usually quoted and already stripped to blanks, so the file may be the
    # only token left; an unquoted pattern occupies the first slot
    non_flags = [t for t in toks[1:] if not t.startswith("-")]
    candidates = non_flags[1:] if len(non_flags) >= 2 else non_flags
    if not candidates:
        return False
    for p in candidates:
        target = _resolve_path(p, cwd)
        if target is None or not os.path.isfile(target):
            return False
    return True


def _ls_recursive(toks: list[str]) -> bool:
    for t in toks[1:]:
        if t in ("--recursive", "--tree"):
            return True
        if t.startswith("-") and not t.startswith("--") and ("R" in t or (toks[0] == "eza" and "T" in t)):
            return True
    return False


def _resolve_path(path_arg: str | None, cwd: str) -> str | None:
    if not path_arg:
        return cwd
    try:
        p = os.path.expanduser(path_arg)
        if not os.path.isabs(p):
            p = os.path.join(cwd, p)
        return os.path.realpath(p)
    except Exception:
        return None


def _bounded(original: str, seg_start: int, seg_end: int,
             stages: list[tuple[int, int]], idx: int) -> bool:
    st_start, st_end = stages[idx]
    # a STDOUT redirect bounds the stage; `2>/dev/null` and `2>&1` do not
    if re.search(r"(?<!2)>>?\s*(?!&)\S", original[st_start:st_end]):
        return True
    seg_text = original[seg_start:seg_end]
    if re.match(r"^\s*nohup\b", seg_text):
        return True
    r = seg_text.rstrip()
    if r.endswith("&") and not r.endswith("&&"):
        return True
    for j in range(idx + 1, len(stages)):
        s_start, s_end = stages[j]
        stage_orig = original[s_start:s_end]
        if BOUND_STAGE_RE.search(stage_orig):
            return True
        toks = stage_orig.strip().split()
        if toks and toks[0] == "sort" and j + 1 < len(stages):
            nxt = original[stages[j + 1][0]: stages[j + 1][1]].strip().split()
            if nxt and nxt[0] == "uniq" and "-c" in nxt:
                return True
    return False


def _short(s: str, n: int = 80) -> str:
    return s if len(s) <= n else s[: n - 1] + "\N{HORIZONTAL ELLIPSIS}"


def _deny(shape: str, suggestion: str) -> int:
    sys.stderr.write(
        f"BLOCKED (output-hygiene): {shape} — an unbounded call like this can flood the "
        f"session context. Use a bounded form instead, e.g. {suggestion}.\n"
    )
    return 2


def _check_stage(toks: list[str], stage_stripped: str, original: str,
                  seg_start: int, seg_end: int, stages: list[tuple[int, int]],
                  idx: int, cwd: str) -> int | None:
    head = toks[0]
    own = stage_stripped.strip()

    if head in ("ls", "eza"):
        path_arg = next((t for t in toks[1:] if not t.startswith("-")), None)
        if _ls_recursive(toks) and not _bounded(original, seg_start, seg_end, stages, idx):
            shown = _short(path_arg or ".")
            return _deny(
                f"recursive `ls -R`/`eza -T` ({shown})",
                f"`find {shown} -maxdepth 2 | head -40` or `ls -R {shown} | head -60`",
            )
        target = _resolve_path(path_arg, cwd)
        if target is None:
            return None
        try:
            n = len(os.listdir(target))
        except Exception:
            return None
        if n > 150 and not _bounded(original, seg_start, seg_end, stages, idx):
            shown = _short(path_arg or ".")
            return _deny(
                f"`ls`/`eza` on a {n}-entry directory ({shown})",
                f"`ls {shown} | head -40` or `ls -1 {shown} | wc -l`",
            )
        return None

    if head in ("cat", "bat"):
        non_flags = [t for t in toks[1:] if not t.startswith("-")]
        if len(non_flags) != 1:
            return None
        target = _resolve_path(non_flags[0], cwd)
        if target is None:
            return None
        try:
            size = os.stat(target).st_size
            is_file = os.path.isfile(target)
        except Exception:
            return None
        if is_file and size > 24 * 1024 and not _bounded(original, seg_start, seg_end, stages, idx):
            shown = _short(non_flags[0])
            kb = size // 1024
            return _deny(
                f"`cat`/`bat` of a {kb}KB file ({shown})",
                f"`cat {shown} | tail -40` or `sed -n '1,200p' {shown}`",
            )
        return None

    if _grep_trigger(toks):
        if _grep_bound_own(toks) or _grep_targets_are_files(toks, cwd) \
                or _bounded(original, seg_start, seg_end, stages, idx):
            return None
        return _deny("`grep -r`/`rg` without -l/-c/-m", "`grep -rl foo .` or `grep -rn foo . | head`")

    for trigger, bound_own, shape, suggestion in SIMPLE_SHAPES:
        if trigger.match(own):
            if bound_own.search(own) or _bounded(original, seg_start, seg_end, stages, idx):
                return None
            return _deny(shape, suggestion)

    return None


def _join_path(cwd: str, path: str) -> str:
    p = os.path.expanduser(path)
    if os.path.isabs(p):
        return p
    return os.path.normpath(os.path.join(cwd, p))


def _evaluate(stripped: str, original: str, cwd: str) -> int | None:
    segments = _segments(stripped)

    # Shape 8 (tail -f/-F) — never bounded, checked across every stage first.
    for seg_start, seg_end in segments:
        for st_start, st_end in _stages(stripped, seg_start, seg_end):
            toks = stripped[st_start:st_end].strip().split()
            if toks and toks[0] == "tail" and any(t in ("-f", "-F", "--follow") for t in toks[1:]):
                return _deny("`tail -f`/`-F`", "`tail -n 200 <file>` (never `-f` in a tool call)")

    effective_cwd = cwd
    for seg_start, seg_end in segments:
        seg_stripped = stripped[seg_start:seg_end].strip()
        stages = _stages(stripped, seg_start, seg_end)
        first_toks = stripped[stages[0][0]: stages[0][1]].strip().split()
        if first_toks and first_toks[0] in ("ssh", "scp", "rsync"):
            continue  # remote dispatch — runs off-box
        for idx, (st_start, st_end) in enumerate(stages):
            toks = stripped[st_start:st_end].strip().split()
            if not toks:
                continue
            verdict = _check_stage(
                toks, stripped[st_start:st_end], original, seg_start, seg_end,
                stages, idx, effective_cwd,
            )
            if verdict:
                return verdict
        cd_m = CD_RE.match(seg_stripped)
        if cd_m:
            effective_cwd = _join_path(effective_cwd, cd_m.group(1))
    return None


def main() -> int:
    if os.environ.get("NUZ_OUTPUT_HYGIENE_OFF") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict) or data.get("tool_name") != "Bash":
        return 0
    cmd = ((data.get("tool_input") or {}).get("command") or "")
    if not isinstance(cmd, str) or not cmd.strip():
        return 0
    cwd = data.get("cwd") or os.getcwd()
    try:
        stripped = _strip_noise(cmd)
        verdict = _evaluate(stripped, cmd, cwd)
        return verdict if verdict else 0
    except Exception:
        return 0  # fail-open: a guard that can crash a session is worse than a miss


if __name__ == "__main__":
    sys.exit(main())
