"""Tests for scripts/lint/lint_claude_headless_context_diet.py.

Every GUILT-class detector gets an INNOCENCE case for the adjacent
legitimate state (same discipline lint_home_fork.py / lint_plist_keepalive.py
apply to superscar #1/#7) — a guard merged without both a guilt and an
innocence test is exactly the family #3/W92 trap this repo's cicatrix
documents.

All fixtures run against a synthetic repo tree in tmp_path — no live-repo
dependence, so a passing suite proves the DETECTION LOGIC, independent of
whatever the real repo currently contains.
"""
from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent / "lint_claude_headless_context_diet.py"
_spec = importlib.util.spec_from_file_location(
    "lint_claude_headless_context_diet", _MODULE_PATH
)
assert _spec is not None and _spec.loader is not None
lcd = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = lcd
_spec.loader.exec_module(lcd)


# ---------------------------------------------------------------- helpers


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for d in ("scripts", "infra/launchagents/wrappers", "apps/backend-rag/scripts"):
        (repo / d).mkdir(parents=True, exist_ok=True)
    return repo


def write(repo: Path, rel: str, content: str) -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content))
    return p


# ---------------------------------------------------------------- GUILT


def test_guilt_bare_python_argv_no_flag(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "apps/backend-rag/scripts/gen.py", '''\
        import subprocess

        def call():
            return subprocess.run(
                ["claude", "--print", "--model", "haiku", prompt],
                timeout=60,
            )
        ''')
    findings = lcd.check(repo)
    assert len(findings) == 1
    assert findings[0].file == "apps/backend-rag/scripts/gen.py"


def test_guilt_bare_shell_invocation_no_flag(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "infra/launchagents/wrappers/foo.sh", '''\
        #!/bin/bash
        output=$(timeout 300 claude -p --model haiku "$prompt" 2>&1)
        echo "$output"
        ''')
    findings = lcd.check(repo)
    assert len(findings) == 1
    assert findings[0].file == "infra/launchagents/wrappers/foo.sh"


def test_guilt_pragma_with_no_reason_still_flagged(tmp_path: Path) -> None:
    """A bare `context-diet: exempt` with nothing after it is debt wearing
    a label, not a recorded decision."""
    repo = make_repo(tmp_path)
    write(repo, "apps/backend-rag/scripts/bare_pragma.py", '''\
        import subprocess

        def call():
            return subprocess.run(
                # context-diet: exempt
                ["claude", "--print", "--model", "haiku", prompt],
            )
        ''')
    findings = lcd.check(repo)
    assert len(findings) == 1


# ------------------------------------------------------------ INNOCENCE


def test_innocence_restricted_flag_python(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "apps/backend-rag/scripts/gen.py", '''\
        import subprocess

        def call():
            return subprocess.run(
                ["claude", "--print", "--model", "haiku",
                 "--restricted", "--strict-mcp-config", prompt],
            )
        ''')
    assert lcd.check(repo) == []


def test_innocence_safe_mode_flag_shell(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "infra/launchagents/wrappers/foo.sh", '''\
        #!/bin/bash
        output=$(timeout 300 claude -p --model haiku --safe-mode "$prompt" 2>&1)
        echo "$output"
        ''')
    assert lcd.check(repo) == []


def test_innocence_setting_sources_flag_python(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "apps/backend-rag/scripts/gen.py", '''\
        import subprocess

        def call():
            return subprocess.run(
                ["claude", "--print", "--model", "haiku",
                 "--setting-sources", "", prompt],
            )
        ''')
    assert lcd.check(repo) == []


def test_innocence_exempt_pragma_python(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "apps/backend-rag/scripts/canva_call.py", '''\
        import subprocess

        def call():
            return subprocess.run(
                # context-diet: exempt — the Canva project MCP must load
                ["claude", "--print", "--model", "haiku", prompt],
            )
        ''')
    assert lcd.check(repo) == []


def test_innocence_exempt_pragma_shell(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write(repo, "infra/launchagents/wrappers/canva.sh", '''\
        #!/bin/bash
        # context-diet: exempt — the Canva project MCP must load
        output=$(timeout 300 claude -p --model haiku "$prompt" 2>&1)
        echo "$output"
        ''')
    assert lcd.check(repo) == []


def test_innocence_restricted_foo_flag_never_matches(tmp_path: Path) -> None:
    """--restricted-foo is not --restricted (same anchoring discipline as
    MODEL_FLAG_RE) — still a finding."""
    repo = make_repo(tmp_path)
    write(repo, "apps/backend-rag/scripts/lookalike.py", '''\
        import subprocess

        def call():
            return subprocess.run(
                ["claude", "--print", "--model", "haiku",
                 "--restricted-foo", prompt],
            )
        ''')
    findings = lcd.check(repo)
    assert len(findings) == 1


def test_innocence_path_mention_never_matches(tmp_path: Path) -> None:
    """A path mention like `~/.claude/hooks/x.py` is never an invocation
    anchor at all — the engine's own bare-anchor exclusion handles this."""
    repo = make_repo(tmp_path)
    write(repo, "scripts/notes.py", '''\
        # see ~/.claude/hooks/x.py for the hook that fires on Stop
        def unrelated():
            return 1
        ''')
    assert lcd.check(repo) == []
