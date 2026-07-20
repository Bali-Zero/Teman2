"""Tests for scripts/lint/lint_claude_headless_limits.py (SPEC-abcd.md Unita A).

Every GUILT-class detector gets an INNOCENCE case for the adjacent legitimate
state (same discipline lint_home_fork.py / lint_plist_keepalive.py apply to
superscar #1/#7) — a guard mergiato without both a guilt and an innocence test
is exactly the family #3/W92 trap this repo's cicatrix documents.

All fixtures run against a synthetic repo tree in tmp_path — no live-repo
dependence, so a passing suite proves the DETECTION LOGIC, independent of
whatever the real repo currently contains.
"""
from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent / "lint_claude_headless_limits.py"
_spec = importlib.util.spec_from_file_location("lint_claude_headless_limits", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
lchl = importlib.util.module_from_spec(_spec)
# Register in sys.modules BEFORE exec: the module defines a @dataclass, and
# dataclasses resolves annotations via sys.modules[cls.__module__] — without
# this the module is invisible to itself mid-exec and dataclass() crashes.
sys.modules[_spec.name] = lchl
_spec.loader.exec_module(lchl)


# ---------------------------------------------------------------- helpers


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for d in ("scripts", "infra/launchagents/wrappers", "apps/backend-rag/scripts",
              "agent-library/scar_replay", "docs", "research", "vendor",
              "scripts/tests", "scripts/lint"):
        (repo / d).mkdir(parents=True, exist_ok=True)
    return repo


def write(repo: Path, rel: str, content: str) -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content))
    return p


# ---------------------------------------------------------------- GUILT


def test_guilt_single_line_armed_command_missing_budget(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "infra/launchagents/wrappers/foo.sh", '''\
        #!/bin/bash
        output=$(timeout 300 claude -p --model haiku --permission-mode bypassPermissions "$prompt" 2>&1)
        echo "$output"
        ''')
    findings = lchl.check(repo)
    assert len(findings) == 1
    assert findings[0].file == "infra/launchagents/wrappers/foo.sh"
    assert findings[0].line == 2


def test_guilt_multiline_backslash_continuation_missing_budget(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "infra/launchagents/wrappers/bar.sh", '''\
        #!/bin/bash
        "$CLAUDE_BIN" -p "$PROMPT" \\
            --model "$MODEL" --dangerously-skip-permissions \\
            --strict-mcp-config --mcp-config '{"mcpServers":{}}' \\
            </dev/null > "$LOG" 2>&1 &
        ''')
    findings = lchl.check(repo)
    assert len(findings) == 1
    assert findings[0].file == "infra/launchagents/wrappers/bar.sh"


def test_guilt_python_argv_inside_subprocess_run_missing_budget(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "apps/backend-rag/scripts/gen.py", '''\
        import subprocess

        def call():
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=prompt, capture_output=True, text=True, timeout=60,
            )
            return result
        ''')
    findings = lchl.check(repo)
    assert len(findings) == 1
    assert findings[0].file == "apps/backend-rag/scripts/gen.py"


def test_guilt_unterminated_quote_spanning_lines(tmp_path: Path) -> None:
    """Mirrors the real pro-healer.sh/healer-run.sh shape: the invocation line
    has no trailing backslash (a double-quoted string left open carries the
    statement across a blank physical line), so a naive backslash-joiner
    would miss it — the window must still find the flags several lines down."""
    repo = make_repo(tmp_path)
    write(repo, "infra/launchagents/wrappers/healer.sh", '''\
        #!/bin/bash
        "$CLAUDE_BIN" -p "$(cat "$MANDATE")

        CONTESTO: ${REASONS}" \\
            --model "$MODEL" --dangerously-skip-permissions \\
            --strict-mcp-config --mcp-config '{"mcpServers":{}}' \\
            </dev/null > "$SESSION_LOG" 2>&1 &
        ''')
    findings = lchl.check(repo)
    assert len(findings) == 1


# ---------------------------------------------------------------- INNOCENCE


def test_innocence_text_only_no_budget_required(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "scripts/textonly.sh", '''\
        #!/bin/bash
        claude -p --model haiku "$prompt" > "$LOG" 2>&1
        ''')
    findings = lchl.check(repo)
    assert findings == []


def test_innocence_armed_command_with_budget_already_present(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "infra/launchagents/wrappers/ok.sh", '''\
        #!/bin/bash
        output=$(timeout 300 claude -p --model haiku --permission-mode bypassPermissions --max-budget-usd "${FOO_MAX_BUDGET_USD:-5}" "$prompt" 2>&1)
        ''')
    findings = lchl.check(repo)
    assert findings == []


def test_innocence_mention_in_comment(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "scripts/commented.sh", '''\
        #!/bin/bash
        # historical note: this used to run `claude -p --dangerously-skip-permissions`
        # without any budget cap; replaced by the cascade wrapper below.
        echo "nothing to see here"
        ''')
    findings = lchl.check(repo)
    assert findings == []


def test_innocence_claude_in_path_not_a_binary_mention(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "scripts/pathmention.py", '''\
        import os
        from pathlib import Path

        def load_skill():
            skill_path = Path.home() / ".claude/hooks/subagent_stop_verify.py"
            return skill_path.read_text()

        # a bare mention with -p and bypassPermissions nearby should still be
        # fine as long as it never anchors on an actual claude invocation:
        # print("-p --dangerously-skip-permissions")  # doc example only
        ''')
    findings = lchl.check(repo)
    assert findings == []


def test_innocence_model_name_is_not_an_anchor(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "scripts/modelname.sh", '''\
        #!/bin/bash
        MODEL="claude-sonnet-5"
        echo "using $MODEL -p --dangerously-skip-permissions but no real invocation"
        ''')
    findings = lchl.check(repo)
    assert findings == []


def test_innocence_python_argv_builder_never_executed(tmp_path: Path) -> None:
    """Mirrors scripts/modus_autoloop.py::_spawn_session — a documented pure
    argv builder with no subprocess/exec call anywhere near it must not be
    flagged: nothing spawns it (yet), so it carries zero runaway risk."""
    repo = make_repo(tmp_path)
    write(repo, "scripts/builder.py", '''\
        def build_argv(job, mandate):
            """Pure builder — never calls subprocess/os.exec."""
            argv = [
                "claude",
                "--model",
                "opus",
                "--print",
                "--dangerously-skip-permissions",
                mandate,
            ]
            return argv
        ''')
    findings = lchl.check(repo)
    assert findings == []


def test_guilt_python_argv_builder_becomes_violation_once_wired(tmp_path: Path) -> None:
    """The mirror of the previous case: once the SAME argv shape is actually
    handed to subprocess.run, the missing-budget rule must re-activate."""
    repo = make_repo(tmp_path)
    write(repo, "scripts/wired.py", '''\
        import subprocess

        def run_it(job, mandate):
            argv = [
                "claude",
                "--model",
                "opus",
                "--print",
                "--dangerously-skip-permissions",
                mandate,
            ]
            return subprocess.run(argv, capture_output=True)
        ''')
    findings = lchl.check(repo)
    assert len(findings) == 1


def test_innocence_excluded_directories_are_never_scanned(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    for rel in (
        "docs/example.sh",
        "research/example.py",
        "vendor/example.sh",
        "scripts/tests/example.py",
        "scripts/lint/example.py",
    ):
        write(repo, rel, '''\
            claude -p --model haiku --dangerously-skip-permissions "$prompt"
            ''')
    findings = lchl.check(repo)
    assert findings == []


def test_innocence_markdown_and_test_files_excluded(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "scripts/README.md", '''\
        claude -p --model haiku --dangerously-skip-permissions "$prompt"
        ''')
    write(repo, "scripts/test_something.py", '''\
        def test_guilt_sample():
            cmd = ["claude", "--print", "--dangerously-skip-permissions"]
            assert cmd
        ''')
    findings = lchl.check(repo)
    assert findings == []


def test_innocence_two_adjacent_invocations_do_not_bleed_windows(tmp_path: Path) -> None:
    """A conformant invocation immediately followed by a non-conformant one
    (or vice versa) must be judged independently — the window must stop at
    the next anchor, never borrow a neighbor's --max-budget-usd."""
    repo = make_repo(tmp_path)
    write(repo, "scripts/two_calls.sh", '''\
        #!/bin/bash
        claude -p --model haiku --dangerously-skip-permissions --max-budget-usd 5 "$prompt1"
        claude -p --model haiku --dangerously-skip-permissions "$prompt2"
        ''')
    findings = lchl.check(repo)
    assert len(findings) == 1
    assert findings[0].file == "scripts/two_calls.sh"
    assert findings[0].line == 3


# -------------------------------------------------------- P2-5/P2-6/P2-7 (guilt)


def test_guilt_budget_flag_mentioned_in_nearby_log_string_still_violates(tmp_path: Path) -> None:
    """P2-5 (W91-twin): a naked command must not be excused by a
    --max-budget-usd MENTION living in an unrelated line inside the old
    fixed forward window (here: a log line AFTER the invocation). The
    reconstructed shell statement for the invocation itself ends at its own
    line (no continuation), so the budget-shaped text on line 3 must never
    satisfy this armed-but-unbudgeted command."""
    repo = make_repo(tmp_path)
    write(repo, "infra/launchagents/wrappers/logmention.sh", '''\
        #!/bin/bash
        claude -p --model haiku --dangerously-skip-permissions "$prompt"
        echo "remember to pass --max-budget-usd next time" >> "$LOG"
        ''')
    findings = lchl.check(repo)
    assert len(findings) == 1
    assert findings[0].line == 2


def test_guilt_multiline_continuation_beyond_window_forward_still_violates(tmp_path: Path) -> None:
    """P2-6 (shell branch): a real invocation whose flags are spread across
    MORE than WINDOW_FORWARD (10) backslash-continued lines must still be
    caught — the shell logical-statement reconstruction has no fixed-window
    cap, only the SHELL_CMD_SCAN_LIMIT backstop."""
    repo = make_repo(tmp_path)
    write(repo, "infra/launchagents/wrappers/longcontinuation.sh", '''\
        #!/bin/bash
        "$CLAUDE_BIN" -p \\
            --model "$MODEL" \\
            --permission-mode bypassPermissions \\
            --strict-mcp-config \\
            --mcp-config '{"mcpServers":{}}' \\
            --output-format stream-json \\
            --include-partial-messages \\
            --verbose \\
            --add-dir "$WORKTREE" \\
            --allowed-tools "Bash,Read,Edit" \\
            --disallowed-tools "WebSearch" \\
            "$PROMPT" \\
            </dev/null > "$LOG" 2>&1 &
        ''')
    findings = lchl.check(repo)
    assert len(findings) == 1
    assert findings[0].file == "infra/launchagents/wrappers/longcontinuation.sh"


def test_innocence_heredoc_prose_with_armed_example_command(tmp_path: Path) -> None:
    """P2-7: a heredoc that just PRINTS/WRITES documentation (no recognized
    exec verb on its open line) must never be scanned — an example command
    embedded in prose is not a real call site."""
    repo = make_repo(tmp_path)
    write(repo, "scripts/doc_writer.sh", '''\
        #!/bin/bash
        cat <<'EOF' > README-example.md
        Example (for documentation only), do NOT copy verbatim:
            claude -p --model haiku --dangerously-skip-permissions "$prompt"
        EOF
        echo "wrote docs"
        ''')
    findings = lchl.check(repo)
    assert findings == []


def test_guilt_heredoc_executed_via_bash_still_violates(tmp_path: Path) -> None:
    """P2-7 twin: a heredoc that IS actually executed (`bash <<'EOF' ... EOF`)
    must stay in scope — stripping only applies to non-executed (pure
    documentation) heredocs."""
    repo = make_repo(tmp_path)
    write(repo, "scripts/executed_heredoc.sh", '''\
        #!/bin/bash
        bash <<'EOF'
        claude -p --model haiku --dangerously-skip-permissions "$prompt"
        EOF
        ''')
    findings = lchl.check(repo)
    assert len(findings) == 1
    assert findings[0].file == "scripts/executed_heredoc.sh"


# ---------------------------------------------------------------- main()/CLI


def test_main_exit_0_on_clean_repo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = make_repo(tmp_path)
    write(repo, "scripts/clean.sh", '''\
        claude -p --model haiku --dangerously-skip-permissions --max-budget-usd 5 "$prompt"
        ''')
    rc = lchl.main(["--repo-root", str(repo)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "clean" in out


def test_main_exit_1_on_violation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = make_repo(tmp_path)
    write(repo, "scripts/dirty.sh", '''\
        claude -p --model haiku --dangerously-skip-permissions "$prompt"
        ''')
    rc = lchl.main(["--repo-root", str(repo)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "scripts/dirty.sh:1" in out
    # never a truncated count (cicatrix W97): "[findings] N of N"
    assert "[findings] 1 of 1" in out
