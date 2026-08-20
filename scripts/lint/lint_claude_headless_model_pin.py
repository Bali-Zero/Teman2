#!/usr/bin/env python3
"""lint_claude_headless_model_pin.py — bare `claude -p`/`--print` calls must
pin an explicit --model.

Root cause (2026-08-20 investigation, mata-garuda bare-claude-model-pins
mandate): on Pro the interactive Claude Code profile default is
`opus[1m]`. Any `claude --print`/`-p` subprocess spawned WITHOUT an explicit
`--model` silently inherits whatever that ambient CLI default happens to be
at invocation time — for a cron-spawned, unattended, budget-sensitive call
that is a cost/behavior surprise, not a choice. The fix at each call site is
to pin the minimum-sufficient model explicitly (env-overridable, defaulting
per CLAUDE.md root Sec.5 routing: grunt/bounded-extraction = Haiku,
implementer/synthesis = Sonnet 5).

DETECTION ENGINE: reused, not duplicated. lint_claude_headless_limits.py
(SPEC-abcd.md Unita A) already solved the hard anchor-detection and
window/statement-reconstruction problem for exactly this invocation shape —
heredoc stripping, backslash-continuation, quote-balance carry-over,
bracket-extension for long Python argv lists, next-anchor capping so two
adjacent invocations never bleed into one another (family #3/W92, hardened
over several rounds). Duplicating that ~300 lines of scarred logic here would
create a second copy that silently drifts out of sync with the first. This
module imports it via the SAME importlib.util.spec_from_file_location pattern
its own test file already uses, and re-runs the anchor/window pipeline with a
DIFFERENT rule: lint_claude_headless_limits checks that a BYPASS-PERMISSIONS
armed print invocation carries --max-budget-usd; this module checks that
EVERY print-mode invocation (bypass or not — the missing-model risk applies
regardless of tool permissions) carries --model.

GRANDFATHER LIST (mirrors lint_tg_direct_senders.py): the repo already has
pre-existing bare invocations outside the scope of the PR that introduces
this lint. This lint freezes the offending FILES (not individual findings —
same file-level granularity as lint_tg_direct_senders.py, so an unrelated
edit shifting a line number inside an already-grandfathered file is never
mistaken for a new violation) at introduction time. It fails CI only when a
file OUTSIDE that frozen set gains a bare invocation, or when the frozen list
GROWS versus origin/main (anti-bypass: a PR cannot add a new offender and
grandfather it away in the same diff). Existing debt stays visible in
infra/claude-headless-model-pin/grandfathered.json — remediate a file, then
remove it from the list (or re-run --freeze after fixing all listed files).

Exit codes: 0 clean, 1 guilt (new bare invocation outside the grandfather set
/ grown grandfather list), 2 blind-scan guard (0 files scanned — a lint that
scanned nothing must not report "clean", cicatrix W84).
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_ENGINE_PATH = Path(__file__).resolve().parent / "lint_claude_headless_limits.py"


def _load_engine():
    """Import lint_claude_headless_limits.py as a library (not a package-
    relative import: scripts/lint/ is invoked standalone in CI, mirroring how
    its own test file loads it)."""
    spec = importlib.util.spec_from_file_location(
        "lint_claude_headless_limits", _ENGINE_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_engine = _load_engine()

# Standalone `--model` token (excludes anything that merely contains the
# substring — same anchoring discipline as the engine's own FLAG_PRINT_RE).
MODEL_FLAG_RE = re.compile(r"(?<![\w-])--model(?![\w-])")

_STRING_PREFIX_RE = re.compile(r"^[A-Za-z]*")


def _strip_python_triple_quoted_strings(raw_lines: list) -> list:
    """Blank the CONTENT of every Python triple-quoted string literal
    (module/function/class docstrings, and any other `\"\"\"`/`'''`
    literal) before anchor scanning — using Python's own `tokenize` module
    to find the real spans, NOT a hand-rolled quote scanner.

    Discovered false-positive (2026-08-20, follow-up to the model-pin PR):
    prose like `\"\"\"Claude via Max plan OAuth (subprocess to ``claude
    -p``).\"\"\"` trips ANCHOR_BARE_CLAUDE_RE + FLAG_PRINT_RE exactly like a
    real invocation would — the docstring is narrating the module's own
    behavior in English, not spawning anything.

    GOTCHA that killed the first (regex) version of this function, same
    session: `scripts/generate_automations_excel.py:271` has
    `stripped.startswith('\"\"\"')` — a SINGLE-quoted 3-character string
    literal whose CONTENT happens to be `\"\"\"`. A raw substring scan for
    the token `\"\"\"` cannot tell that apart from a real triple-quote
    opener; it read this as an unterminated docstring start and blanked
    every line onward up to the next accidental `\"\"\"` occurrence — which
    silently deleted the anchor for a genuinely real, unpinned invocation
    (`[\"claude\", \"--print\", prompt]`) almost 30 lines later, at line 299.
    `tokenize` already solves exactly this (it is a real Python lexer, not
    a substring search): a STRING token's `.string` is the token's own raw
    source text, so `'\"\"\"'` tokenizes as ONE single-quoted STRING token
    whose text starts with `'`, never mistaken for a triple-quote opener.

    Every real subprocess argv anchor in this repo is a short
    single/double-quoted token inside an argv list (`[\"claude\",
    \"--print\", ...]`) or a `claude_bin`-style variable, never a
    triple-quoted literal — so this function ONLY blanks tokens whose raw
    text (after any string-prefix letters: f/r/b/u and combinations) starts
    with `\"\"\"` or `'''`; ordinary single/double-quoted tokens (including
    the real argv-token anchors) are left completely untouched.

    On a file that does not tokenize cleanly (should not happen for a
    tracked, syntactically valid `.py` file, but the rest of this module
    already tolerates unreadable input) this returns `raw_lines` unchanged
    — declared blind spot, same fail-open policy as `_strip_heredoc_bodies`
    for an unterminated marker."""
    out = list(raw_lines)
    source = "\n".join(out) + "\n"
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return out

    for tok in tokens:
        if tok.type != tokenize.STRING:
            continue
        body = _STRING_PREFIX_RE.sub("", tok.string, count=1)
        if not (body.startswith('"""') or body.startswith("'''")):
            continue  # a real single/double-quoted token — leave it alone
        (sr, sc), (er, ec) = tok.start, tok.end
        sr -= 1  # tokenize rows are 1-based; raw_lines/out are 0-based
        er -= 1
        if sr == er:
            line = out[sr]
            out[sr] = line[:sc] + " " * (ec - sc) + line[ec:]
        else:
            first = out[sr]
            out[sr] = first[:sc] + " " * (len(first) - sc)
            for j in range(sr + 1, er):
                out[j] = ""
            last = out[er]
            out[er] = " " * ec + last[ec:]
    return out


_SHELL_PRINT_VERB_RE = re.compile(r"^\s*(?:echo|printf|log)\b")


def _shell_bare_anchor_is_print_string(line: str, anchor_start: int) -> bool:
    """True when a "bare" anchor on a shell line sits inside a quoted
    string argument to a known print-verb (echo/printf/log) — e.g.
    `echo "[DRY RUN] Would run claude -p ..."` or `log "DRY RUN: claude
    -p (...)"`. These are diagnostic/log STRINGS narrating the real
    invocation in prose, not the invocation itself, and trip
    ANCHOR_BARE_CLAUDE_RE + FLAG_PRINT_RE purely because the message
    happens to name the command.

    Deliberately narrow (family #3 discipline — an exclusion is a guard
    with the sign flipped, and needs its own guilt+innocence pair): only
    lines that START with a print verb qualify, and only when the anchor
    sits inside an ODD count of unescaped double-quotes on that line — a
    real invocation chained/piped AFTER an echo on the SAME line (e.g.
    `echo "..." ; claude -p "$x" --model foo`) has an EVEN quote count in
    front of the `claude` token (outside the echoed string) and is never
    excluded by this check."""
    if not _SHELL_PRINT_VERB_RE.match(line):
        return False
    prefix = line[:anchor_start]
    return _engine._count_unescaped(prefix, '"') % 2 == 1


def check_file(path: Path, repo_root: Path) -> list:
    """Same anchor→window pipeline as lint_claude_headless_limits.check_file,
    with the bypass-permissions gate removed and --max-budget-usd swapped for
    --model."""
    findings = []
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return findings

    raw_lines = _engine._strip_heredoc_bodies(raw_lines)
    is_python = path.suffix == ".py"
    if is_python:
        raw_lines = _strip_python_triple_quoted_strings(raw_lines)
    stripped_lines = [_engine._strip_comment(line) for line in raw_lines]
    anchors = _engine._find_anchors(stripped_lines)

    if is_python:
        # "bare" kind is a SHELL concept (an unquoted command word) with no
        # valid Python equivalent: subprocess.run() takes either an argv
        # LIST of quoted string tokens (-> "quoted" kind) or a single quoted
        # command string (still inside quotes) — there is no Python syntax
        # where an executed `claude` token is neither. Empirically, every
        # "bare" Python finding measured live (2026-08-20 follow-up) was a
        # logger/raise/print/f-string message or a regex/argparse-help
        # string narrating the invocation in prose — never the invocation
        # itself. Declared blind spot (not hidden): a Python string holding
        # LITERAL SHELL SCRIPT TEXT with an unpinned `claude -p` (e.g. a
        # wrapper-generator writing a .sh template) would also be dropped
        # here — none exist in this repo today (verified by grep before
        # writing this exclusion), and such a file's OWN `.sh` output, once
        # written to disk, is still scanned directly by the shell path.
        anchors = [(ln, kind) for ln, kind in anchors if kind != "bare"]
    else:
        kept = []
        for ln, kind in anchors:
            if kind == "bare":
                am = _engine.ANCHOR_BARE_CLAUDE_RE.search(stripped_lines[ln])
                if am and _shell_bare_anchor_is_print_string(
                    stripped_lines[ln], am.start()
                ):
                    continue  # echo/log/printf narration, not a real call
            kept.append((ln, kind))
        anchors = kept

    if not anchors:
        return findings

    rel = str(path.relative_to(repo_root))

    for pos, (anchor_line, anchor_kind) in enumerate(anchors):
        if is_python:
            window_end = _engine._python_window_end(
                stripped_lines, anchors, pos, len(stripped_lines)
            )
        else:
            window_end = _engine._shell_statement_end(
                stripped_lines, anchor_line, anchors, pos, len(stripped_lines)
            )
        window_text = "\n".join(stripped_lines[anchor_line:window_end])

        if not _engine.FLAG_PRINT_RE.search(window_text):
            continue  # not a -p/--print invocation at all — out of scope

        if is_python and anchor_kind == "quoted":
            lookback_start = max(0, anchor_line - _engine.LOOKBACK)
            context_text = "\n".join(stripped_lines[lookback_start:window_end])
            if not _engine.SUBPROCESS_EXEC_RE.search(context_text):
                # documented non-executing argv builder — never spawned
                continue

        if MODEL_FLAG_RE.search(window_text):
            continue  # already pinned

        findings.append(
            _engine.Finding(
                file=rel,
                line=anchor_line + 1,
                message=(
                    "headless `claude` -p/--print invocation missing --model "
                    "(silently inherits the CLI profile's ambient default)"
                ),
            )
        )

    return findings


def check(repo_root: Path) -> list:
    findings = []
    for path in _engine._iter_scan_files(repo_root):
        findings.extend(check_file(path, repo_root))
    return findings


def _grandfather_path(root: Path) -> Path:
    return root / "infra" / "claude-headless-model-pin" / "grandfathered.json"


def load_grandfathered(root: Path) -> set:
    try:
        data = json.loads(_grandfather_path(root).read_text())
        return set(data.get("files", []))
    except (OSError, ValueError):
        return set()


def freeze(root: Path) -> int:
    scanned = _engine._iter_scan_files(root)
    if not scanned:
        print(
            "lint_claude_headless_model_pin: BLIND SCAN — zero files scanned, "
            "refusing to freeze",
            file=sys.stderr,
        )
        return 2
    findings = check(root)
    offending_files = sorted({f.file for f in findings})
    payload = {
        "_doc": (
            "Bare `claude -p`/`--print` invocations (missing --model) "
            "grandfathered at lint birth (2026-08-20). This list only "
            "SHRINKS: pin --model at a call site, then remove its file here "
            "(or re-run --freeze once every listed file is fixed). A NEW "
            "file introducing a bare invocation fails CI — see "
            "scripts/lint/lint_claude_headless_model_pin.py."
        ),
        "frozen_at": "2026-08-20",
        "files": offending_files,
    }
    gp = _grandfather_path(root)
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"lint_claude_headless_model_pin: froze {len(offending_files)} "
        f"grandfathered file(s)"
    )
    return 0


def check_monotone(root: Path) -> tuple:
    """Anti-bypass (mirrors lint_tg_direct_senders.py): a PR cannot add a new
    bare invocation AND grandfather it away in the same diff. Returns
    (ok, illegally_added). Skips gracefully when origin/main has no list yet
    or git is unavailable (selftest: CLAUDE_MODEL_PIN_BASE_JSON)."""
    base_override = os.environ.get("CLAUDE_MODEL_PIN_BASE_JSON", "")
    try:
        if base_override:
            old_raw = Path(base_override).read_text()
        else:
            rel = _grandfather_path(root).relative_to(root)
            old_raw = subprocess.run(
                ["git", "-C", str(root), "show", f"origin/main:{rel}"],
                capture_output=True, text=True, check=True,
            ).stdout
        old = set(json.loads(old_raw).get("files", []))
    except Exception:
        print(
            "lint_claude_headless_model_pin: monotone check skipped (no "
            "grandfathered.json on origin/main yet)"
        )
        return True, set()

    added = load_grandfathered(root) - old
    return (not added), added


def lint(root: Path) -> int:
    scanned = _engine._iter_scan_files(root)
    if not scanned:
        print(
            "lint_claude_headless_model_pin: BLIND SCAN — zero files "
            "scanned; not clean, BROKEN",
            file=sys.stderr,
        )
        return 2

    findings = check(root)
    finding_files = {f.file for f in findings}
    grandfathered = load_grandfathered(root)
    offenders = finding_files - grandfathered

    if offenders:
        print(
            f"lint_claude_headless_model_pin: FAIL — {len(offenders)} file(s) "
            f"with a NEW bare `claude -p`/`--print` invocation missing "
            f"--model:",
            file=sys.stderr,
        )
        for f in sorted(offenders):
            for finding in findings:
                if finding.file == f:
                    print(f"  - {finding.fmt()}", file=sys.stderr)
        return 1

    mono_ok, added = check_monotone(root)
    if not mono_ok:
        print(
            f"lint_claude_headless_model_pin: FAIL — grandfathered.json GREW "
            f"by {len(added)} file(s) vs origin/main (the list only "
            f"shrinks; pin --model instead):",
            file=sys.stderr,
        )
        for f in sorted(added):
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(
        f"lint_claude_headless_model_pin: clean ({len(scanned)} files "
        f"scanned, {len(grandfathered)} grandfathered, 0 new)"
    )
    return 0


def selftest() -> int:
    import tempfile
    import textwrap

    failures = []

    def check_ok(name, cond):
        print(("  ok  " if cond else "  FAIL") + f" {name}")
        if not cond:
            failures.append(name)

    def write(repo, rel, content):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content))
        return p

    def make_repo(tmp_path):
        repo = tmp_path / "repo"
        for d in ("scripts", "infra/launchagents/wrappers",
                  "apps/backend-rag/scripts", "scripts/tests"):
            (repo / d).mkdir(parents=True, exist_ok=True)
        return repo

    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)

        # ---- GUILT: python argv missing --model ----
        repo = make_repo(tmp_path / "guilt_py")
        write(repo, "apps/backend-rag/scripts/gen.py", '''\
            import subprocess

            def call():
                result = subprocess.run(
                    ["claude", "--print", "-p", prompt],
                    timeout=60,
                )
                return result
            ''')
        findings = check(repo)
        check_ok("python argv missing --model is flagged", len(findings) == 1)
        if findings:
            check_ok(
                "flags the right file",
                findings[0].file == "apps/backend-rag/scripts/gen.py",
            )

        # ---- GUILT: shell invocation missing --model ----
        repo = make_repo(tmp_path / "guilt_sh")
        write(repo, "infra/launchagents/wrappers/foo.sh", '''\
            #!/bin/bash
            output=$(timeout 300 claude -p "$prompt" 2>&1)
            echo "$output"
            ''')
        findings = check(repo)
        check_ok("shell invocation missing --model is flagged", len(findings) == 1)

        # ---- INNOCENCE: --model present (python) ----
        repo = make_repo(tmp_path / "innocent_py")
        write(repo, "apps/backend-rag/scripts/gen.py", '''\
            import subprocess

            def call():
                result = subprocess.run(
                    ["claude", "--print", "-p", prompt, "--model", "haiku"],
                    timeout=60,
                )
                return result
            ''')
        check_ok("python argv WITH --model passes", check(repo) == [])

        # ---- INNOCENCE: --model present (shell) ----
        repo = make_repo(tmp_path / "innocent_sh")
        write(repo, "infra/launchagents/wrappers/foo.sh", '''\
            #!/bin/bash
            output=$(timeout 300 claude -p --model haiku "$prompt" 2>&1)
            echo "$output"
            ''')
        check_ok("shell invocation WITH --model passes", check(repo) == [])

        # ---- INNOCENCE: prose/comment mention never matches (AST/anchor
        # engine only sees quoted-argv or shell-command anchors, never a
        # comment — the engine strips comments before scanning) ----
        repo = make_repo(tmp_path / "innocent_comment")
        write(repo, "scripts/notes.py", '''\
            # call claude --print -p "hello" to test — no --model on purpose
            def unrelated():
                return 1
            ''')
        check_ok("comment mention never matches", check(repo) == [])

        # ---- INNOCENCE: non-executing argv builder (no nearby subprocess
        # call) is out of scope, same as the engine's own budget check ----
        repo = make_repo(tmp_path / "innocent_builder")
        write(repo, "scripts/preview.py", '''\
            def preview_cmd():
                cmd = ["claude", "--print", "-p", "hello"]
                return cmd  # never spawned
            ''')
        check_ok("non-executing argv builder is out of scope", check(repo) == [])

        # ---- INNOCENCE: multi-line module docstring narrating the real
        # invocation in prose (2026-08-20 follow-up — exact shape of
        # apps/backend-rag/backend/llm/claude_oauth_client.py:1) ----
        repo = make_repo(tmp_path / "innocent_module_docstring")
        write(repo, "scripts/oauth_client.py", '''\
            """Claude via Max plan OAuth (subprocess to ``claude -p``).

            Project policy: all Claude integrations must use the Max plan
            OAuth token, never ANTHROPIC_API_KEY.
            """
            import subprocess

            def call():
                return subprocess.run(
                    ["claude", "--print", "-p", prompt, "--model", "haiku"],
                )
            ''')
        check_ok(
            "multi-line module docstring never matches",
            check(repo) == [],
        )

        # ---- INNOCENCE: one-line function docstring, same-line open+close
        # (e.g. `"""Load the agent .md body ..."""` style) ----
        repo = make_repo(tmp_path / "innocent_oneline_docstring")
        write(repo, "scripts/oneline.py", '''\
            def helper():
                """Isolated cwd for `claude --print` subprocess call."""
                return 1
            ''')
        check_ok("one-line docstring never matches", check(repo) == [])

        # ---- GUILT still stands: a REAL bare invocation textually adjacent
        # to (right after) a docstring is still flagged — the stripper only
        # blanks the docstring SPAN, not the code around it ----
        repo = make_repo(tmp_path / "guilt_after_docstring")
        write(repo, "scripts/after_doc.py", '''\
            """Some module doing `claude -p` things, for humans to read."""
            import subprocess

            def call():
                return subprocess.run(["claude", "--print", "-p", prompt])
            ''')
        findings = check(repo)
        check_ok(
            "real invocation after a docstring is still flagged",
            len(findings) == 1,
        )

        # ---- REGRESSION: a single-quoted string whose CONTENT is `"""`
        # must never be misread as a triple-quote opener (2026-08-20 —
        # the exact bug that killed the first regex-based version of the
        # stripper on scripts/generate_automations_excel.py:271, silently
        # blanking a real invocation ~30 lines later) ----
        repo = make_repo(tmp_path / "guilt_quote_lookalike")
        write(repo, "scripts/lookalike.py", '''\
            import subprocess

            def classify(stripped):
                if stripped.startswith('"""'):
                    return "docstring"
                return "other"

            def call(prompt):
                return subprocess.run(["claude", "--print", prompt])
            ''')
        findings = check(repo)
        check_ok(
            "single-quoted 3-double-quote-content string never mistaken "
            "for a triple-quote opener (real invocation past it still "
            "flagged)",
            len(findings) == 1
            and findings[0].file == "scripts/lookalike.py",
        )

        # ---- INNOCENCE: shell echo/log dry-run narration (2026-08-20
        # follow-up — exact shape of
        # infra/launchagents/wrappers/cron-agent.sh:391-392) ----
        repo = make_repo(tmp_path / "innocent_shell_echo")
        write(repo, "infra/launchagents/wrappers/dryrun.sh", '''\
            #!/bin/bash
            claude_bin="${CRON_AGENT_CLAUDE_BIN:-claude}"
            if [ "$dry_run" = "1" ]; then
                echo "[DRY RUN] Would run claude -p with prompt from $f"
                log "DRY RUN: claude -p (${#prompt} chars)"
                return 0
            fi
            "$claude_bin" -p --model "$cron_model" "$prompt"
            ''')
        check_ok(
            "echo/log dry-run narration of claude -p never matches",
            check(repo) == [],
        )

        # ---- GUILT still stands: a REAL invocation chained AFTER an echo
        # on the SAME line is still flagged (proves the quote-parity check
        # doesn't overreach past the echoed string) ----
        repo = make_repo(tmp_path / "guilt_after_echo_same_line")
        write(repo, "infra/launchagents/wrappers/chained.sh", '''\
            #!/bin/bash
            echo "starting" ; claude -p "$prompt"
            ''')
        findings = check(repo)
        check_ok(
            "real invocation chained after echo on the same line is still flagged",
            len(findings) == 1,
        )

        # ---- freeze / lint / monotone roundtrip ----
        repo = make_repo(tmp_path / "roundtrip")
        write(repo, "scripts/old_offender.py", '''\
            import subprocess

            def call():
                return subprocess.run(["claude", "--print", "-p", prompt])
            ''')
        rc = freeze(repo)
        check_ok("freeze exits 0", rc == 0)
        gf = json.loads(_grandfather_path(repo).read_text())["files"]
        check_ok("old offender grandfathered", "scripts/old_offender.py" in gf)
        check_ok("grandfathered tree lints clean", lint(repo) == 0)

        # GUILT: a NEW offender outside the grandfather set fails
        new_offender = write(repo, "scripts/new_offender.py", '''\
            import subprocess

            def call():
                return subprocess.run(["claude", "--print", "-p", prompt])
            ''')
        check_ok("new offender FAILS", lint(repo) == 1)
        new_offender.unlink()  # isolate the monotone checks below

        # monotone: growing the grandfather list vs a stale base fails, even
        # though the live tree itself now has no offender outside the list.
        current = json.loads(_grandfather_path(repo).read_text())
        os.environ["CLAUDE_MODEL_PIN_BASE_JSON"] = str(
            _write_base_json(tmp_path, {"files": []})
        )
        check_ok("grandfather growth vs stale (empty) base FAILS", lint(repo) == 1)

        # innocence: base matching the current (stable) list passes.
        os.environ["CLAUDE_MODEL_PIN_BASE_JSON"] = str(
            _write_base_json(tmp_path, current)
        )
        check_ok("grandfather stable vs matching base PASSES", lint(repo) == 0)
        del os.environ["CLAUDE_MODEL_PIN_BASE_JSON"]

        # blind-scan guard
        empty_repo = tmp_path / "empty"
        empty_repo.mkdir()
        check_ok("blind scan on empty tree → exit 2", lint(empty_repo) == 2)
        check_ok("blind scan on empty tree freeze → exit 2", freeze(empty_repo) == 2)

    print("SELFTEST", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


def _write_base_json(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / f"base_{len(list(tmp_path.glob('base_*.json')))}.json"
    p.write_text(json.dumps(payload))
    return p


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    root = args.repo_root.resolve()
    if args.freeze:
        return freeze(root)
    return lint(root)


if __name__ == "__main__":
    sys.exit(main())
