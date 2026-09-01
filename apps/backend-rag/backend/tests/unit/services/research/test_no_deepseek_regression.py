"""Regression lint: no live DeepSeek routing left in ConsiglioV1.

ConsiglioV1's fourth member (`consiglio_orchestrator.py::ConsiglioV1`) used
to shell out to a local `deepseek-ask` binary — the direct-API path, retired
2026-07-19 (Zero: pre-authorization revoked, key balance dead — HTTP-402).
Replaced by ``kimi -p ... -m kimi-code/k3`` (CLAUDE.md §5: "replacement
refuter seat is Kimi K3"), same shape as the council/oracle voice system's
swap in `test_no_deepseek_regression.py` under
`backend/tests/services/council/`.

Same AST-based approach as that sibling guard, deliberately not a bare
substring match (cicatrix family #3 "guard-over-match", scar W121): a
docstring correctly recording *why* the retirement happened must not trip
this guard, only a live class/function name, import, or non-docstring
string literal referencing the retired binary/URL/env var.

Scope: this one file, not a directory scan — ConsiglioV1 has exactly one
production file and one test file, both listed explicitly below (unlike the
council/cognitive guard, there is no risk of a sibling module in this
directory silently escaping coverage because there are no sibling modules).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_RESEARCH_DIR = Path(__file__).resolve().parents[4] / "services" / "research"

_GUARDED_FILES = [
    _RESEARCH_DIR / "consiglio_orchestrator.py",
]

_FORBIDDEN_BINARY = "deepseek-ask"
_FORBIDDEN_URL = "api.deepseek.com"
_FORBIDDEN_ENV = "DEEPSEEK_API_KEY"
_FORBIDDEN_TOKENS = (_FORBIDDEN_BINARY, _FORBIDDEN_URL, _FORBIDDEN_ENV)

_DocstringHolder = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """id() of every string-constant AST node in docstring position — the
    same convention ``ast.get_docstring`` uses. Excluded from the scan."""
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
        elif isinstance(node, ast.ImportFrom):
            if node.module and "deepseek" in node.module.lower():
                violations.append(
                    f"{label}: import from module {node.module!r} "
                    f"(line {getattr(node, 'lineno', '?')}) reintroduces a "
                    "DeepSeek code path"
                )
            for alias in node.names:
                if "deepseek" in alias.name.lower():
                    violations.append(
                        f"{label}: imports {alias.name!r} "
                        f"(line {getattr(node, 'lineno', '?')})"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "deepseek" in alias.name.lower():
                    violations.append(
                        f"{label}: imports module {alias.name!r} "
                        f"(line {getattr(node, 'lineno', '?')})"
                    )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_ids:
                continue  # explanatory prose — allowed
            for token in _FORBIDDEN_TOKENS:
                if token in node.value:
                    violations.append(
                        f"{label}: live string literal contains {token!r} "
                        f"(line {getattr(node, 'lineno', '?')})"
                    )

    return violations


# ── Guilt: real reintroduction must be caught ──────────────────────────


@pytest.mark.parametrize("path", _GUARDED_FILES, ids=lambda p: p.name)
def test_no_live_deepseek_token_in_guarded_files(path: Path) -> None:
    assert path.exists(), f"guarded file moved/renamed: {path}"
    source = path.read_text(encoding="utf-8")
    violations = _scan_source(source, str(path))
    assert violations == [], "\n".join(violations)


def test_positive_control_binary_literal_is_caught() -> None:
    """A live command-list literal invoking the retired `deepseek-ask`
    binary must be flagged, not silently pass."""
    source = f'CMD = ["{_FORBIDDEN_BINARY}", prompt]\n'
    violations = _scan_source(source, "synthetic_cmd.py")
    assert any(_FORBIDDEN_BINARY in v for v in violations)


def test_positive_control_url_literal_is_caught() -> None:
    source = f'API_URL = "https://{_FORBIDDEN_URL}/v1/chat/completions"\n'
    violations = _scan_source(source, "synthetic_url.py")
    assert any(_FORBIDDEN_URL in v for v in violations)


def test_positive_control_env_var_literal_is_caught() -> None:
    source = 'import os\nkey = os.environ.get("DEEPSEEK_API_KEY")\n'
    violations = _scan_source(source, "synthetic_env.py")
    assert any(_FORBIDDEN_ENV in v for v in violations)


# ── Innocence: correct historical prose must NOT be caught ─────────────


def test_module_docstring_mentioning_deepseek_is_allowed() -> None:
    """A module docstring recording the retirement (exactly what this
    repo's real file does) must not trip the guard."""
    source = (
        '"""DeepSeek V4 Pro was RETIRED 2026-07-19. The deepseek-ask '
        'binary and api.deepseek.com / DEEPSEEK_API_KEY are the old dead '
        'path — replaced by Kimi K3."""\n'
        "\n"
        "def do_nothing() -> None:\n"
        "    pass\n"
    )
    violations = _scan_source(source, "synthetic_docstring.py")
    assert violations == []


def test_comment_mentioning_deepseek_is_allowed() -> None:
    """`ast` never sees ``#`` comments at all, so they can never trip this
    guard — asserted here so the invariant is explicit, not incidental."""
    source = (
        "# deepseek-ask used to live here (api.deepseek.com, "
        "DEEPSEEK_API_KEY) — retired 2026-07-19, replaced by Kimi K3.\n"
        "def do_nothing() -> None:\n"
        "    pass\n"
    )
    violations = _scan_source(source, "synthetic_comment.py")
    assert violations == []
