#!/usr/bin/env python3
"""lint_claude_headless_context_diet.py — every headless `claude -p`/
`--print` invocation must carry a context-diet flag, or an explicit
exemption pragma.

WHY (measured 2026-09-17 on M5 with fleet mail pending at Stop; numbers are
environment-dependent — hooks, pending fleet mail, plugins — re-measure
with `scripts/bench/cc_headless_shape_bench.sh` rather than trusting this
table cold): same PONG prompt, `--model haiku --output-format json
--max-turns 1` on every shape. The DEFAULT shape — no diet flag at all —
cost 36,322 input tokens AND came back with `result: null`
(`terminal_reason: max_turns`), because a HOME `Stop` hook injected fleet
mail as `hookAdditionalContext`, forcing a second turn the budget didn't
allow (a re-measure with no fleet mail pending saw 16,908 tokens and a
normal 1-turn answer instead — the flag choice below is unaffected either
way). `--restricted --strict-mcp-config` cost 15,064 tokens and answered.
`--safe-mode` cost 16,923 tokens and answered (tools and permissions stay
normal; every customization — hooks, plugins, project CLAUDE.md/skills,
project MCP — turns off). `--setting-sources ""` (a genuinely EMPTY value,
not the 2-char string `""` — a bench script that passes the literal
quote-characters gets `Invalid setting source: ""` from the CLI, which is
a bench BUG, not a CLI limitation) cost 26,973 tokens on CLI 2.1.274 and
answered — the most expensive cure of the three, because
CLAUDE.md/skills/plugins/project-MCP still load; it only trims settings
FILES, not the surrounding project context. `--bare` is NOT a usable
substitute: its auth is strictly
`ANTHROPIC_API_KEY` (OAuth is never read), i.e. the banned paid endpoint
(CLAUDE.md root Sec.3) — this lint does not accept it as a cure. Recipe: a
text-only seat wants `--restricted --strict-mcp-config`; a seat that needs
Read/Write/Bash wants `--safe-mode`; a seat that needs a custom `--agent`
or a project MCP (Canva, NotebookLM) records a per-site decision with the
exemption pragma instead. Full measurement table:
`research/agent-craft/cc-meta-loop/BACKLOG.md` section "C4 measured" on
branch `agent/air-m5/infra/cc-meta-loop-v2`.

RULE: an invocation is CURED when its reconstructed window carries at least
one of `--restricted`, `--safe-mode`, `--setting-sources` (anchored so
`--restricted-foo` never matches, same discipline as MODEL_FLAG_RE in
lint_claude_headless_model_pin.py). It is EXEMPT when the same window (or
the physical line immediately above the anchor) carries the pragma
`context-diet: exempt — <reason>` (a `#` comment in both `.py` and `.sh`).
Everything else is a finding.

DETECTION ENGINE: reused, not duplicated — same sibling relationship as
lint_claude_headless_model_pin.py to lint_claude_headless_limits.py. This
module imports the anchor/window engine via the SAME
`importlib.util.spec_from_file_location` pattern, and ALSO imports
lint_claude_headless_model_pin.py itself (never modified) to reuse its two
narration-exclusion helpers (`_strip_python_triple_quoted_strings`,
`_shell_bare_anchor_is_print_string`) — a docstring or an echo/log line
that merely NAMES `--restricted`/`--safe-mode` while narrating a call in
prose is exactly the same false-positive shape that already bit the
model-pin lint on `--model`, and duplicating that fix a second time here
would only create a second copy to drift out of sync.

GRANDFATHER LIST (mirrors lint_claude_headless_model_pin.py): pre-existing
bare invocations outside the scope of the PR that introduces this lint are
frozen at FILE granularity in
infra/claude-headless-context-diet/grandfathered.json. The list only
SHRINKS — a PR cannot add a new offender and grandfather it away in the
same diff (checked against origin/main).

ADVISORY until backlog row C1d lands: this lint is wired into
scripts/quickcheck.sh, a LOCAL pre-push consumer — it reports on every
push from a dev machine, but nothing here fails CI or blocks a merge yet.
Wiring it into a `.github/workflows/` step (the only way to make a new
offender a required red) is a hot-zone-path edit and needs its own Gear-3
PR (C1d) — see the sibling model-pin lint for the CI-wired shape this one
is meant to grow into.

Exit codes: 0 clean, 1 guilt (new offending invocation outside the
grandfather set / grown grandfather list), 2 blind-scan guard (0 files
scanned — cicatrix W84).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_ENGINE_PATH = Path(__file__).resolve().parent / "lint_claude_headless_limits.py"
_MODEL_PIN_PATH = Path(__file__).resolve().parent / "lint_claude_headless_model_pin.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_engine = _load_module(_ENGINE_PATH, "lint_claude_headless_limits")
_model_pin = _load_module(_MODEL_PIN_PATH, "lint_claude_headless_model_pin")

# Standalone context-diet flag (excludes anything that merely contains the
# substring, e.g. `--restricted-network` — same anchoring discipline as
# MODEL_FLAG_RE).
CONTEXT_DIET_FLAG_RE = re.compile(
    r"(?<![\w-])(--restricted|--safe-mode|--setting-sources)(?![\w-])"
)

# `# context-diet: exempt — <reason>` (em-dash or hyphen, reason required —
# a bare `context-diet: exempt` with nothing after it is not a recorded
# decision, it's debt wearing a pragma).
PRAGMA_RE = re.compile(r"context-diet:\s*exempt\s*[—–-]\s*\S")


def check_file(path: Path, repo_root: Path) -> list:
    """Same anchor->window pipeline as lint_claude_headless_model_pin.check_file,
    with --model swapped for the context-diet flag set, plus the pragma
    exemption."""
    findings = []
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return findings

    raw_lines = _engine._strip_heredoc_bodies(raw_lines)
    is_python = path.suffix == ".py"
    if is_python:
        raw_lines = _model_pin._strip_python_triple_quoted_strings(raw_lines)
    stripped_lines = [_engine._strip_comment(line) for line in raw_lines]
    anchors = _engine._find_anchors(stripped_lines)

    if is_python:
        # no "bare" shape in Python argv/command-string invocations — see
        # lint_claude_headless_model_pin.check_file for the full reasoning.
        anchors = [(ln, kind) for ln, kind in anchors if kind != "bare"]
    else:
        kept = []
        for ln, kind in anchors:
            if kind == "bare":
                am = _engine.ANCHOR_BARE_CLAUDE_RE.search(stripped_lines[ln])
                if am and _model_pin._shell_bare_anchor_is_print_string(
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

        if CONTEXT_DIET_FLAG_RE.search(window_text):
            continue  # already cured

        # Pragma check runs against the RAW (comment-bearing) text — the
        # window itself, plus the one physical line immediately above the
        # anchor, both in one slice.
        pragma_start = max(0, anchor_line - 1)
        raw_window = "\n".join(raw_lines[pragma_start:window_end])
        if PRAGMA_RE.search(raw_window):
            continue  # exempt, recorded decision

        findings.append(
            _engine.Finding(
                file=rel,
                line=anchor_line + 1,
                message=(
                    "headless `claude` -p/--print invocation missing a "
                    "context-diet flag (--restricted / --safe-mode / "
                    "--setting-sources) or an exempt pragma "
                    "(`# context-diet: exempt — <reason>`)"
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
    return root / "infra" / "claude-headless-context-diet" / "grandfathered.json"


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
            "lint_claude_headless_context_diet: BLIND SCAN — zero files "
            "scanned, refusing to freeze",
            file=sys.stderr,
        )
        return 2
    findings = check(root)
    offending_files = sorted({f.file for f in findings})
    payload = {
        "_doc": (
            "Headless `claude -p`/`--print` invocations missing a "
            "context-diet flag (--restricted/--safe-mode/--setting-sources) "
            "or an exempt pragma, grandfathered at lint birth (2026-09-17). "
            "This list only SHRINKS: apply the recipe (text-only seat -> "
            "--restricted --strict-mcp-config; Read/Write/Bash seat -> "
            "--safe-mode; custom --agent or project MCP -> record a "
            "`# context-diet: exempt — <reason>` pragma) at a call site, "
            "then remove its file here (or re-run --freeze once every "
            "listed file is fixed). ADVISORY until backlog row C1d lands: "
            "a NEW file introducing a bare invocation is reported by "
            "scripts/quickcheck.sh on every push from a dev machine — it "
            "does not fail CI, because that would require wiring this "
            "lint into a .github/workflows/ step, which is a hot-zone "
            "path and needs its own Gear-3 PR (C1d). See "
            "scripts/lint/lint_claude_headless_context_diet.py."
        ),
        "frozen_at": "2026-09-17",
        "files": offending_files,
    }
    gp = _grandfather_path(root)
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"lint_claude_headless_context_diet: froze {len(offending_files)} "
        f"grandfathered file(s)"
    )
    return 0


def check_monotone(root: Path) -> tuple:
    """Anti-bypass: a PR cannot add a new offending invocation AND
    grandfather it away in the same diff."""
    base_override = os.environ.get("CLAUDE_CONTEXT_DIET_BASE_JSON", "")
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
            "lint_claude_headless_context_diet: monotone check skipped (no "
            "grandfathered.json on origin/main yet)"
        )
        return True, set()

    added = load_grandfathered(root) - old
    return (not added), added


def lint(root: Path) -> int:
    scanned = _engine._iter_scan_files(root)
    if not scanned:
        print(
            "lint_claude_headless_context_diet: BLIND SCAN — zero files "
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
            f"lint_claude_headless_context_diet: FAIL — {len(offenders)} "
            f"file(s) with a NEW headless invocation missing a "
            f"context-diet flag or exempt pragma:",
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
            f"lint_claude_headless_context_diet: FAIL — grandfathered.json "
            f"GREW by {len(added)} file(s) vs origin/main (the list only "
            f"shrinks; cure the call site instead):",
            file=sys.stderr,
        )
        for f in sorted(added):
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(
        f"lint_claude_headless_context_diet: clean ({len(scanned)} files "
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

        # ---- GUILT: python argv missing a diet flag ----
        repo = make_repo(tmp_path / "guilt_py")
        write(repo, "apps/backend-rag/scripts/gen.py", '''\
            import subprocess

            def call():
                result = subprocess.run(
                    ["claude", "--print", "--model", "haiku", prompt],
                    timeout=60,
                )
                return result
            ''')
        findings = check(repo)
        check_ok("python argv missing a diet flag is flagged", len(findings) == 1)

        # ---- GUILT: shell invocation missing a diet flag ----
        repo = make_repo(tmp_path / "guilt_sh")
        write(repo, "infra/launchagents/wrappers/foo.sh", '''\
            #!/bin/bash
            output=$(timeout 300 claude -p --model haiku "$prompt" 2>&1)
            echo "$output"
            ''')
        findings = check(repo)
        check_ok("shell invocation missing a diet flag is flagged", len(findings) == 1)

        # ---- INNOCENCE: --restricted present (python) ----
        repo = make_repo(tmp_path / "innocent_restricted")
        write(repo, "apps/backend-rag/scripts/gen.py", '''\
            import subprocess

            def call():
                result = subprocess.run(
                    ["claude", "--print", "--model", "haiku", "--restricted",
                     "--strict-mcp-config", prompt],
                    timeout=60,
                )
                return result
            ''')
        check_ok("python argv WITH --restricted passes", check(repo) == [])

        # ---- INNOCENCE: --safe-mode present (shell) ----
        repo = make_repo(tmp_path / "innocent_safe_mode")
        write(repo, "infra/launchagents/wrappers/foo.sh", '''\
            #!/bin/bash
            output=$(timeout 300 claude -p --model haiku --safe-mode "$prompt" 2>&1)
            echo "$output"
            ''')
        check_ok("shell invocation WITH --safe-mode passes", check(repo) == [])

        # ---- INNOCENCE: --setting-sources present (python) ----
        repo = make_repo(tmp_path / "innocent_setting_sources")
        write(repo, "apps/backend-rag/scripts/gen.py", '''\
            import subprocess

            def call():
                return subprocess.run(
                    ["claude", "--print", "--model", "haiku",
                     "--setting-sources", "", prompt],
                )
            ''')
        check_ok("python argv WITH --setting-sources passes", check(repo) == [])

        # ---- INNOCENCE: exempt pragma, line above the anchor (python) ----
        repo = make_repo(tmp_path / "innocent_pragma_py")
        write(repo, "apps/backend-rag/scripts/canva_call.py", '''\
            import subprocess

            def call():
                return subprocess.run(
                    # context-diet: exempt — the Canva project MCP must load
                    ["claude", "--print", "--model", "haiku", prompt],
                )
            ''')
        check_ok("python exempt pragma above the anchor passes", check(repo) == [])

        # ---- INNOCENCE: exempt pragma, shell (# in .sh too) ----
        repo = make_repo(tmp_path / "innocent_pragma_sh")
        write(repo, "infra/launchagents/wrappers/canva.sh", '''\
            #!/bin/bash
            # context-diet: exempt — the Canva project MCP must load
            output=$(timeout 300 claude -p --model haiku "$prompt" 2>&1)
            echo "$output"
            ''')
        check_ok("shell exempt pragma above the anchor passes", check(repo) == [])

        # ---- GUILT still stands: pragma with no reason after "exempt" is
        # debt wearing a label, not a recorded decision ----
        repo = make_repo(tmp_path / "guilt_bare_pragma")
        write(repo, "apps/backend-rag/scripts/bare_pragma.py", '''\
            import subprocess

            def call():
                # context-diet: exempt
                return subprocess.run(
                    ["claude", "--print", "--model", "haiku", prompt],
                )
            ''')
        findings = check(repo)
        check_ok(
            "pragma with no reason after 'exempt' still flagged",
            len(findings) == 1,
        )

        # ---- INNOCENCE: prose/comment mention of a diet flag never
        # matches on its own (engine strips comments before scanning the
        # flag; only the pragma check reads raw text) ----
        repo = make_repo(tmp_path / "innocent_comment")
        write(repo, "scripts/notes.py", '''\
            # call claude --print --restricted "hello" to test
            def unrelated():
                return 1
            ''')
        check_ok("comment mention never matches", check(repo) == [])

        # ---- INNOCENCE: module docstring narrating --safe-mode in prose
        # never trips the anchor scan (reused from model_pin) ----
        repo = make_repo(tmp_path / "innocent_docstring")
        write(repo, "scripts/oauth_client.py", '''\
            """Claude via Max plan OAuth (subprocess to ``claude -p
            --safe-mode``).
            """
            import subprocess

            def call():
                return subprocess.run(
                    ["claude", "--print", "-p", prompt, "--restricted"],
                )
            ''')
        check_ok("module docstring never matches", check(repo) == [])

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

        new_offender = write(repo, "scripts/new_offender.py", '''\
            import subprocess

            def call():
                return subprocess.run(["claude", "--print", "-p", prompt])
            ''')
        check_ok("new offender FAILS", lint(repo) == 1)
        new_offender.unlink()

        current = json.loads(_grandfather_path(repo).read_text())
        os.environ["CLAUDE_CONTEXT_DIET_BASE_JSON"] = str(
            _write_base_json(tmp_path, {"files": []})
        )
        check_ok("grandfather growth vs stale (empty) base FAILS", lint(repo) == 1)

        os.environ["CLAUDE_CONTEXT_DIET_BASE_JSON"] = str(
            _write_base_json(tmp_path, current)
        )
        check_ok("grandfather stable vs matching base PASSES", lint(repo) == 0)
        del os.environ["CLAUDE_CONTEXT_DIET_BASE_JSON"]

        empty_repo = tmp_path / "empty"
        empty_repo.mkdir()
        check_ok("blind scan on empty tree -> exit 2", lint(empty_repo) == 2)
        check_ok("blind scan on empty tree freeze -> exit 2", freeze(empty_repo) == 2)

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
