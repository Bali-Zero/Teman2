#!/usr/bin/env python3
"""lint_claude_headless_limits.py — antidote for the runaway-headless-loop gap.

Spec: SPEC-abcd.md Unita A (2026-07-16). Every unattended `claude` invocation
that runs with tool permissions bypassed (`--permission-mode bypassPermissions`
or `--dangerously-skip-permissions`) in `-p`/`--print` mode is protected ONLY
by a wall-clock timeout: a runaway agentic loop can burn quota for hours inside
that timeout before anything notices. `--max-budget-usd` truncates it early.

``--max-turns`` does NOT exist as a CLI flag (verified empirically on claude
2.1.211, ``claude --help | grep -i turn`` -> nothing) — this lint never asks
for it and would itself be wrong to suggest it.

RULE: a command/argv that invokes `claude` in `-p`/`--print` mode AND carries
a bypass-permissions marker MUST also carry `--max-budget-usd` in the same
command/argv. Text-only invocations (no bypass marker) are single-shot and
out of scope — see cicatrix family #3/W92 (an over-match cap that fires on
every mention of "claude" would itself be a scar).

ANCHORING (anti over-match, family #3/W92 `429`-in-KBLI precedent): a bare
substring search for "claude" across a whole file would flag path mentions
like `~/.claude/hooks/foo.py` or doc prose. This lint anchors on invocation
shapes only:
  (a) a quoted Python argv element: `"claude"` / `'claude'`
  (b) a shell variable that resolves to the claude binary: `$CLAUDE_BIN`,
      `${CLAUDE_BIN}`, `${<PREFIX>_CLAUDE_BIN}` (the `scripts/organ_birth.py`
      per-organ naming convention)
  (c) the bare command word `claude`, excluding any occurrence immediately
      followed by `/` (a path segment like `.claude/hooks`, NOT the binary)
      or by a word char/hyphen (a model name like `claude-sonnet-5`, or a
      filename like `claude-cascade.sh`, or an identifier like
      `claude_agent_sdk`) and excluding any occurrence immediately preceded
      by a word char or dot (an identifier or a hidden-dir dot, e.g.
      `.claude/`).

Once an anchor is found, the surrounding WINDOW (a bounded number of physical
lines forward, capped at the next anchor so two adjacent invocations never
bleed into each other) is searched for the `-p`/`--print` token and the
bypass-permissions marker — real call sites split flags across several
backslash-continued or quote-continued physical lines, so a single-line match
would miss real violations.

For anchor (a) specifically, in `.py` files, an EXTRA gate applies: the
argv list must actually be handed to a process-spawning call
(`subprocess.run(`/`Popen(`/`check_output(`/`create_subprocess_exec(`/
`create_subprocess_shell(`/`os.exec*`) nearby, else it is skipped as a
documented non-executing builder (e.g. a preview/dry-run argv construction
that is never passed to a process — the spawn is a separate, not-yet-built
step). This is not needed for anchors (b)/(c): a `.sh` file's non-comment
line is executed unconditionally by definition, and an embedded shell
template inside a Python string (`scripts/organ_birth.py`'s wrapper
generator) uses the `$CLAUDE_BIN` shape, not a Python argv literal.

SCOPE: `scripts/`, `infra/`, `apps/`, `agent-library/`, `skills/` — `.sh` and
`.py` files only (the executable-script kinds this repo's cron/launchd/agent
tooling actually uses; `skills/` added because `skills/bali-zero-brand/
_manual_inject_runner.py` spawns a real headless invocation — cicatrix
family #2, "exists but is not armed"). Excluded, anywhere in the relative
path: `docs/`, `research/`, `vendor/`, `tests/`, and (deliberately, beyond
the letter of the spec, to avoid the lint being self-referential — its own
guilt/innocence fixtures embed literal sample text that would otherwise trip
its own anchors) `scripts/lint/` and any `test_*.py`/`*.md` file. Comments
are stripped per-line via the same `line.split("#", 1)[0]` strategy as
`scripts/lint/wr3_lint_cli_only.py` (documented limitation: does not
understand `#` inside a string literal — matches existing repo precedent).

DECLARED SCAN-RADIUS LIMITS (family #3/W92 — an over-match cap can hide a
real violation just as easily as a substring trap can invent one; every
bound below is deliberate, not accidental):

- `WINDOW_FORWARD` (10 lines) is the FLOOR search radius for a python
  anchor before any statement-aware extension runs, and the fallback bound
  when extension is not feasible (see below).
- `LOOKBACK` (8 lines) bounds the backward search for a nearby
  `subprocess.run(`/`Popen(`/etc. call for a `quoted` python anchor
  (unchanged from the original design) — a real spawn call more than 8
  lines BEFORE the argv literal is a declared blind spot.
- Shell (`.sh`) files: instead of the fixed `WINDOW_FORWARD` cap, the scan
  reconstructs the actual shell STATEMENT starting at the anchor — joining
  backslash-line-continuations and lines whose running count of un-escaped
  `"` characters leaves an open quote carried into the next physical line
  (see `_shell_statement_end` — this is what real multi-line wrapper
  invocations look like, e.g. `infra/healer/healer-run.sh`). This kills two
  bugs of the SAME root cause: (a) a `--max-budget-usd` mention in an
  unrelated line inside the old fixed window (a log/echo statement AFTER
  the invocation) used to satisfy the check for a genuinely-unarmed naked
  command — the reconstructed statement never includes that unrelated
  line; (b) a real multi-line invocation whose flags spanned more than 10
  lines used to be silently missed — the reconstruction has no such cap
  (only the declared `SHELL_CMD_SCAN_LIMIT` backstop below, plus the
  existing next-anchor cap so two adjacent invocations never bleed into
  one another).
- `SHELL_CMD_SCAN_LIMIT` (200 lines) is an absolute backstop for the shell
  statement reconstruction — guards against a pathological/malformed quote
  balance (e.g. a genuinely unterminated string) turning the scan into an
  unbounded walk of the rest of the file. Real invocations never approach
  this; it is a safety valve, not a routine limit.
- Python (`.py`) files: the fixed `WINDOW_FORWARD`/next-anchor window is
  extended forward — bounded by `PY_BRACKET_SCAN_LIMIT` (120 lines) and by
  the next anchor — whenever it ends mid an unclosed `[...]` list literal
  (net count of `[` minus `]` inside the window is positive), so a `claude`/
  `$CLAUDE_BIN` argv list that runs longer than `WINDOW_FORWARD` still finds
  its own flags (this is what actually catches
  `skills/bali-zero-brand/_manual_inject_runner.py`'s `cmd = [...]` list).
  DECLARED BLIND SPOT: this only recognizes an unclosed list if the OPENING
  `[` itself falls within the anchor's own forward-looking window — a
  `quoted` `"claude"` anchor whose enclosing list opens on an earlier line
  beyond that window is not detected by bracket-extension and falls back to
  the plain `WINDOW_FORWARD`/`LOOKBACK` bound (same declared-limit class as
  the constants themselves, not silently assumed away).
- Heredoc bodies (`<<'TAG' ... TAG` / `<<TAG ... TAG`) are stripped from the
  scan BEFORE anchors are even located, UNLESS the heredoc's own open line
  names a recognized shell-exec verb (`bash`/`sh`/`zsh`/`dash`/`ksh`/
  `python`/`python3`/`eval`/`ssh`) — i.e. the heredoc is actually being fed
  to an interpreter rather than written out as documentation/example text
  (`cat <<'EOF' > README.md`, or building a prompt string). This is a
  line-based scanner by construction (find the open marker, walk forward
  line-by-line for the literal terminator line) — it never regexes across a
  newline boundary with a negated character class, precisely to avoid the
  W84 bug class (a `[^X]*` spanning `\n` merges unrelated statements).
  DECLARED BLIND SPOT: the exec-verb recognition is a prefix heuristic, not
  a shell parser — a heredoc executed through an unrecognized interpreter
  shape is not detected and stays stripped (documented here, not silently
  assumed innocent).

Exit 0 = clean. Exit 1 = at least one violation. Every count printed is the
true total, never a `[:N]`-truncated slice (cicatrix W97).
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCAN_ROOTS = ("scripts", "infra", "apps", "agent-library", "skills")
INCLUDE_EXTENSIONS = {".sh", ".py"}
EXCLUDE_DIR_NAMES = {
    "docs", "research", "vendor", "tests", "lint",
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "dist", "build", ".worktrees",
}

WINDOW_FORWARD = 10          # physical lines searched forward from an anchor
                              # BEFORE any statement-aware extension (below)
                              # runs; also the python fallback bound.
LOOKBACK = 8                  # physical lines searched backward for
                              # subprocess-context (python `quoted` anchors).
SHELL_CMD_SCAN_LIMIT = 200    # absolute backstop (lines) for the shell
                              # logical-statement reconstruction — a declared
                              # bound against pathological quote-imbalance,
                              # not a routine limit.
PY_BRACKET_SCAN_LIMIT = 120   # ditto, forward bound for the python
                              # bracket-balance window extension.

# ---- anchor patterns --------------------------------------------------------

ANCHOR_QUOTED_CLAUDE_RE = re.compile(r'''(["'])claude\1''')
# `$CLAUDE_BIN` bare, or per-organ-prefixed `${<PREFIX>_CLAUDE_BIN}` (the
# `scripts/organ_birth.py` naming convention) — the prefix group is OPTIONAL,
# a mandatory `[A-Z][A-Z0-9_]*` here would (and did) fail to match the bare form.
ANCHOR_CLAUDE_BIN_VAR_RE = re.compile(r'\$\{?(?:[A-Z][A-Z0-9_]*_)?CLAUDE_BIN\}?')
# bare command word `claude`: not preceded by a word-char/dot (excludes
# identifiers and hidden-dir mentions like `.claude/`), not followed by a
# word-char/dot/slash/hyphen (excludes `.claude/hooks`, `claude-sonnet-5`,
# `claude_agent_sdk`, `claude-cascade.sh`).
ANCHOR_BARE_CLAUDE_RE = re.compile(r'(?<![\w.])claude(?![\w./-])')

# ---- marker patterns ---------------------------------------------------------

# standalone `-p` or `--print` token (excludes `--permission-mode`,
# `--print-timeout`, and any other flag that merely contains the substring).
FLAG_PRINT_RE = re.compile(r'(?<![\w-])(-p|--print)(?![\w-])')
BYPASS_RE = re.compile(r'--dangerously-skip-permissions|bypassPermissions')
BUDGET_RE = re.compile(r'--max-budget-usd')
SUBPROCESS_EXEC_RE = re.compile(
    r'subprocess\.(run|Popen|check_output|check_call)\('
    r'|create_subprocess_(exec|shell)\('
    r'|os\.exec\w*\('
)

# ---- heredoc handling (family #3/W92 P2-7) -----------------------------------

HEREDOC_OPEN_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
HEREDOC_EXEC_VERB_RE = re.compile(r"\b(?:bash|sh|zsh|dash|ksh|python3?|eval|ssh)\b")


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    message: str

    def fmt(self) -> str:
        return f"{self.file}:{self.line}: {self.message}"


def _strip_comment(line: str) -> str:
    """Per-line `#`-comment strip — mirrors wr3_lint_cli_only.py's strategy.
    Does not understand `#` inside a string literal (documented limitation,
    matches existing repo precedent)."""
    return line.split("#", 1)[0]


def _strip_heredoc_bodies(raw_lines: list[str]) -> list[str]:
    """Blank out the BODY of non-executed heredocs (`cat <<'EOF' ...` used to
    print/write documentation or example text) so a documented example of an
    armed invocation inside one is never mistaken for a real call site
    (family #3/W92 P2-7).

    A heredoc whose OPEN line names a recognized shell-exec verb (bash/sh/
    zsh/dash/ksh/python/python3/eval/ssh) is treated as EXECUTED and left
    untouched — its body is real, live shell content and must stay in scope
    for the anchor scan.

    This is a line-based scanner by construction: it finds the open marker,
    then walks forward line-by-line for the literal terminator line. It
    never regexes across a newline boundary with a negated character class
    — the exact shape of the W84 bug (a `[^X]*` that matches `\\n` merges
    unrelated statements across lines). An unterminated heredoc (no matching
    tag before EOF) is a declared blind spot: left untouched rather than
    guessed at."""
    out = list(raw_lines)
    n = len(out)
    idx = 0
    while idx < n:
        m = HEREDOC_OPEN_RE.search(out[idx])
        if not m:
            idx += 1
            continue
        tag = m.group(2)
        prefix = out[idx].split("<<", 1)[0]
        executed = bool(HEREDOC_EXEC_VERB_RE.search(prefix))

        close_idx = None
        for j in range(idx + 1, n):
            if out[j].strip() == tag:
                close_idx = j
                break

        if close_idx is None:
            # unterminated within this file — declared blind spot, move on
            # one line at a time rather than guessing at a fake terminator.
            idx += 1
            continue

        if not executed:
            for j in range(idx + 1, close_idx):
                out[j] = ""
        idx = close_idx + 1
    return out


def _count_unescaped(line: str, ch: str) -> int:
    """Count occurrences of `ch` in `line` not immediately preceded by a
    backslash escape. Naive line-local escape handling — the same class of
    documented heuristic as the rest of this module (it does not understand
    `$()`/nested-quote shell semantics, only raw character parity)."""
    count = 0
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c == ch:
            count += 1
        i += 1
    return count


def _iter_scan_files(repo_root: Path) -> list[Path]:
    out: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in INCLUDE_EXTENSIONS:
                continue
            rel_parts = path.relative_to(repo_root).parts
            if any(part in EXCLUDE_DIR_NAMES for part in rel_parts):
                continue
            if path.name.startswith("test_"):
                continue
            out.append(path)
    return sorted(out)


def _find_anchors(stripped_lines: list[str]) -> list[tuple[int, str]]:
    """Return [(line_idx, anchor_kind)] for every anchor match, in file order.
    anchor_kind in {"quoted", "claude_bin_var", "bare"}."""
    anchors: list[tuple[int, str]] = []
    for idx, line in enumerate(stripped_lines):
        if ANCHOR_QUOTED_CLAUDE_RE.search(line):
            anchors.append((idx, "quoted"))
        elif ANCHOR_CLAUDE_BIN_VAR_RE.search(line):
            anchors.append((idx, "claude_bin_var"))
        elif ANCHOR_BARE_CLAUDE_RE.search(line):
            anchors.append((idx, "bare"))
    return anchors


def _window_end(anchors: list[tuple[int, str]], anchor_pos: int, n_lines: int) -> int:
    """Forward window end index (exclusive): capped by WINDOW_FORWARD lines
    and by the next anchor (so two adjacent invocations never bleed)."""
    anchor_line = anchors[anchor_pos][0]
    cap = min(anchor_line + 1 + WINDOW_FORWARD, n_lines)
    if anchor_pos + 1 < len(anchors):
        next_anchor_line = anchors[anchor_pos + 1][0]
        if anchor_line < next_anchor_line < cap:
            cap = next_anchor_line
    return cap


def _next_anchor_cap(anchors: list[tuple[int, str]], anchor_pos: int,
                      anchor_line: int, hard_cap: int) -> int:
    """Shrink hard_cap to the next anchor's line if that anchor falls inside
    the current bound (anti-bleed: two adjacent invocations are always
    judged independently)."""
    if anchor_pos + 1 < len(anchors):
        next_anchor_line = anchors[anchor_pos + 1][0]
        if anchor_line < next_anchor_line < hard_cap:
            return next_anchor_line
    return hard_cap


def _shell_statement_end(stripped_lines: list[str], anchor_line: int,
                          anchors: list[tuple[int, str]], anchor_pos: int,
                          n_lines: int) -> int:
    """Reconstruct the shell logical-statement end (exclusive) starting at
    anchor_line: keeps consuming physical lines while either (a) the line
    ends with a trailing `\\` continuation, or (b) a running (per-line,
    escape-aware) count of un-escaped `"` characters is odd — an open
    quoted string carrying the statement into the next physical line even
    with NO trailing backslash (mirrors the real pro-healer.sh/
    healer-run.sh shape: `"$CLAUDE_BIN" -p "$(cat "$MANDATE")` left open
    across a blank line, closed several lines later by `... ${REASONS}" \\`).

    Replaces the fixed WINDOW_FORWARD cap for shell files: real invocations
    routinely exceed 10 lines once every flag lives on its own
    backslash-continued line (family #3/W92 P2-5/P2-6). Bounded by
    SHELL_CMD_SCAN_LIMIT and by the next anchor (so two adjacent invocations
    never bleed into one another) — a declared backstop, not a routine
    limit."""
    hard_cap = min(n_lines, anchor_line + 1 + SHELL_CMD_SCAN_LIMIT)
    hard_cap = _next_anchor_cap(anchors, anchor_pos, anchor_line, hard_cap)

    dq_open = False
    idx = anchor_line
    while idx < hard_cap:
        line = stripped_lines[idx]
        if _count_unescaped(line, '"') % 2 == 1:
            dq_open = not dq_open
        ends_with_backslash = line.rstrip().endswith("\\")
        idx += 1
        if dq_open or ends_with_backslash:
            continue
        return idx
    return hard_cap


def _python_window_end(stripped_lines: list[str], anchors: list[tuple[int, str]],
                        anchor_pos: int, n_lines: int) -> int:
    """Python anchor window: starts as the fixed WINDOW_FORWARD/next-anchor
    cap (`_window_end` — the declared fallback bound, see module docstring),
    then extends forward — bounded by PY_BRACKET_SCAN_LIMIT and by the next
    anchor — while the window ends mid an unclosed `[...]` list literal
    (net count of `[` minus `]` inside the window is positive). This is what
    lets a `claude`/`$CLAUDE_BIN` anchor followed by a long argv list (more
    lines than WINDOW_FORWARD) still find its own -p/bypass/budget tokens
    (family #3/W92 P2-6 python branch) without a full Python parser.

    Declared blind spot: only recognizes an unclosed list if the opening
    `[` itself falls within the anchor's own forward-looking window — see
    module docstring."""
    anchor_line = anchors[anchor_pos][0]
    base_end = _window_end(anchors, anchor_pos, n_lines)

    hard_cap = min(n_lines, anchor_line + 1 + PY_BRACKET_SCAN_LIMIT)
    hard_cap = _next_anchor_cap(anchors, anchor_pos, anchor_line, hard_cap)

    net = sum(
        line.count("[") - line.count("]")
        for line in stripped_lines[anchor_line:base_end]
    )
    idx = base_end
    while net > 0 and idx < hard_cap:
        net += stripped_lines[idx].count("[") - stripped_lines[idx].count("]")
        idx += 1
    return idx


def check_file(path: Path, repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return findings

    raw_lines = _strip_heredoc_bodies(raw_lines)
    stripped_lines = [_strip_comment(line) for line in raw_lines]
    anchors = _find_anchors(stripped_lines)
    if not anchors:
        return findings

    rel = str(path.relative_to(repo_root))
    is_python = path.suffix == ".py"

    for pos, (anchor_line, anchor_kind) in enumerate(anchors):
        if is_python:
            window_end = _python_window_end(stripped_lines, anchors, pos, len(stripped_lines))
        else:
            window_end = _shell_statement_end(stripped_lines, anchor_line, anchors, pos, len(stripped_lines))
        window_text = "\n".join(stripped_lines[anchor_line:window_end])

        if not (FLAG_PRINT_RE.search(window_text) and BYPASS_RE.search(window_text)):
            continue  # not a tool-armed print invocation — out of scope

        if is_python and anchor_kind == "quoted":
            lookback_start = max(0, anchor_line - LOOKBACK)
            context_text = "\n".join(stripped_lines[lookback_start:window_end])
            if not SUBPROCESS_EXEC_RE.search(context_text):
                # documented non-executing argv builder — never spawned
                continue

        if BUDGET_RE.search(window_text):
            continue  # already conformant

        findings.append(Finding(
            file=rel,
            line=anchor_line + 1,
            message=(
                "tool-armed headless `claude` invocation (-p/--print + "
                "bypass-permissions) missing --max-budget-usd in the same "
                "command/argv"
            ),
        ))

    return findings


def check(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _iter_scan_files(repo_root):
        findings.extend(check_file(path, repo_root))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    scanned = _iter_scan_files(repo_root)
    findings = check(repo_root)

    print(f"[claude-headless-limits-lint] repo_root = {repo_root}")
    print(f"[claude-headless-limits-lint] scanned {len(scanned)} of {len(scanned)} files")
    print(f"[findings] {len(findings)} of {len(findings)}")
    for f in findings:
        print(f"  - {f.fmt()}")
    if not findings:
        print("  clean — every tool-armed headless `claude -p`/`--print` "
              "invocation carries --max-budget-usd")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
