"""Regression lint: no live DeepSeek routing left in the council/oracle voice system.

DeepSeek V4 Pro was RETIRED 2026-07-19 (Zero: pre-authorization revoked, key
balance dead — HTTP-402). Its council/oracle voting seat (``DeepSeekHTTPRunner``
in ``cli_runners.py``, wired via ``oracle_cli.py::_build_proponents``) was
replaced by ``KimiCLIRunner`` (CLAUDE.md §5: "replacement refuter seat is
Kimi K3").

This scans the AST of the files that used to wire DeepSeek in and fails if a
*live code token* — a class/function name, or a string literal outside a
docstring — reintroduces it. It deliberately does NOT fail on the word
"deepseek" appearing in a comment or docstring: this file, ``cli_runners.py``,
``oracle.py`` and ``oracle_cli.py`` all correctly *mention* DeepSeek in
prose to record why the retirement happened — a bare substring match would
be a guard that trips on its own history (cicatrix family #3 "guard-over-match",
scar W121: a lint anchored to the wrong token gives a false result in either
direction). Guilt and innocence are both exercised below.

Note: FLEET_TOPOLOGY.json documents a *separate* 2026-08-10 "DeepSeek
re-admission" via the TP1/Alibaba token-plan gateway — a different vendor
relationship from the retired direct ``api.deepseek.com`` +
``DEEPSEEK_API_KEY`` path this test guards. That doctrine question is out of
scope here; if this council/oracle system is ever deliberately re-armed
against TP1, update this test as part of that (documented) decision, not by
accident.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_COUNCIL_DIR = Path(__file__).resolve().parents[3] / "services" / "council"
_COGNITIVE_DIR = Path(__file__).resolve().parents[3] / "services" / "cognitive"

_GUARDED_FILES = [
    _COUNCIL_DIR / "cli_runners.py",
    _COUNCIL_DIR / "__init__.py",
    _COUNCIL_DIR / "tone_council.py",
    _COUNCIL_DIR / "prompts.py",
    _COGNITIVE_DIR / "oracle.py",
    _COGNITIVE_DIR / "oracle_cli.py",
]

_FORBIDDEN_URL = "api.deepseek.com"
_FORBIDDEN_ENV = "DEEPSEEK_API_KEY"

_DocstringHolder = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """id() of every string-constant AST node that sits in docstring position
    (first statement of a module/class/function body) — the same convention
    ``ast.get_docstring`` uses. Excluded from the live-code-token scan.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, _DocstringHolder):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            ids.add(id(first.value))
    return ids


def _scan_source(source: str, label: str) -> list[str]:
    """Return a list of human-readable violation strings (empty = clean)."""
    tree = ast.parse(source, filename=label)
    docstring_ids = _docstring_node_ids(tree)
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if "deepseek" in node.name.lower():
                violations.append(
                    f"{label}: {type(node).__name__} named {node.name!r} "
                    "reintroduces a DeepSeek code path"
                )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_ids:
                continue  # explanatory prose — allowed
            if _FORBIDDEN_URL in node.value:
                violations.append(
                    f"{label}: live string literal contains {_FORBIDDEN_URL!r} "
                    f"(line {getattr(node, 'lineno', '?')})"
                )
            if _FORBIDDEN_ENV in node.value:
                violations.append(
                    f"{label}: live string literal references "
                    f"{_FORBIDDEN_ENV!r} (line {getattr(node, 'lineno', '?')})"
                )

    return violations


# ── Guilt: real reintroduction must be caught ──────────────────────────


@pytest.mark.parametrize("path", _GUARDED_FILES, ids=lambda p: p.name)
def test_no_live_deepseek_token_in_guarded_files(path: Path) -> None:
    assert path.exists(), f"guarded file moved/renamed: {path}"
    source = path.read_text(encoding="utf-8")
    violations = _scan_source(source, str(path))
    assert violations == [], "\n".join(violations)


def test_positive_control_class_name_is_caught() -> None:
    """Prove the scanner actually fires: a reintroduced DeepSeek runner class
    must be flagged, not silently pass."""
    source = (
        "class DeepSeekHTTPRunner:\n"
        "    '''Reintroduced by accident.'''\n"
        "    pass\n"
    )
    violations = _scan_source(source, "synthetic_class.py")
    assert any("DeepSeekHTTPRunner" in v for v in violations)


def test_positive_control_url_literal_is_caught() -> None:
    """A live API_URL constant pointing at the retired endpoint must be
    flagged even with no DeepSeek-named class around it.

    Uses the ``_FORBIDDEN_URL`` module constant rather than a duplicated raw
    literal on both sides of the ``in`` check — the raw-literal form trips
    CodeQL's py/incomplete-url-substring-sanitization heuristic (it pattern
    -matches "domain-literal in string" regardless of context; this is a
    diagnostic-message check, not a URL trust decision, but the query can't
    tell the difference from syntax alone).
    """
    source = f'API_URL = "https://{_FORBIDDEN_URL}/v1/chat/completions"\n'
    violations = _scan_source(source, "synthetic_url.py")
    assert any(_FORBIDDEN_URL in v for v in violations)


def test_positive_control_env_var_literal_is_caught() -> None:
    """Reading the retired env var back in must be flagged too, even without
    the class name or URL (e.g. a caller building its own client)."""
    source = 'import os\nkey = os.environ.get("DEEPSEEK_API_KEY")\n'
    violations = _scan_source(source, "synthetic_env.py")
    assert any("DEEPSEEK_API_KEY" in v for v in violations)


# ── Innocence: correct historical prose must NOT be caught ─────────────


def test_module_docstring_mentioning_deepseek_is_allowed() -> None:
    """A module docstring recording the retirement (exactly what this repo's
    real files do) must not trip the guard — this is the W121-style
    over-match this test is designed to avoid."""
    source = (
        '"""DeepSeek V4 Pro was RETIRED 2026-07-19. See api.deepseek.com and '
        'DEEPSEEK_API_KEY for the old dead path — replaced by Kimi K3."""\n'
        "\n"
        "def do_nothing() -> None:\n"
        "    pass\n"
    )
    violations = _scan_source(source, "synthetic_docstring.py")
    assert violations == []


def test_class_docstring_mentioning_deepseek_is_allowed() -> None:
    """Same, but for a class-level docstring (cli_runners.py's real shape)."""
    source = (
        "class KimiCLIRunner:\n"
        '    """Replaces DeepSeekHTTPRunner, retired 2026-07-19 '
        '(api.deepseek.com, DEEPSEEK_API_KEY)."""\n'
        "    pass\n"
    )
    violations = _scan_source(source, "synthetic_class_docstring.py")
    assert violations == []


def test_comment_mentioning_deepseek_is_allowed() -> None:
    """`ast` never sees ``#`` comments at all, so they can never trip this
    guard — asserted here so the invariant is explicit, not incidental."""
    source = (
        "# DeepSeek used to live here (api.deepseek.com, DEEPSEEK_API_KEY) — "
        "retired 2026-07-19, replaced by Kimi K3.\n"
        "def do_nothing() -> None:\n"
        "    pass\n"
    )
    violations = _scan_source(source, "synthetic_comment.py")
    assert violations == []
