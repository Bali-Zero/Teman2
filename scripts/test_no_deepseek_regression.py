#!/usr/bin/env python3
"""Regression lint: the retired DeepSeek DIRECT door never comes back in
``scripts/deepseek_client.py``.

DIFFERENT IN KIND from the sibling guards at
``apps/backend-rag/backend/tests/services/council/test_no_deepseek_regression.py``
and ``.../unit/services/research/test_no_deepseek_regression.py``: those two
guard a full RETIREMENT — DeepSeek routing replaced end-to-end by Kimi K3, so
even a class/function *named* "deepseek" is a violation. This module is a
RE-POINT, not a retirement (2026-08-29, same pass as PR #5211/#5212's Kimi
swaps, but this surface keeps calling DeepSeek models — just through the
Alibaba TP1 gateway instead of the retired ``api.deepseek.com`` direct-billing
door). ``class DeepSeekError`` / ``DeepSeekBudgetExceeded`` /
``DeepSeekBalanceDead`` / ``DeepSeekResult``, the ``deepseek-v4-flash-0731``
model literal, and ``from ... import deepseek_client`` in this file's own
consumers are all CORRECT and must never trip this guard — only the two
identifiers that name the retired door specifically are forbidden:

- a live (non-docstring, non-explanatory-call) string literal containing the
  retired base URL (``api.deepseek.com``)
- a live string literal referencing the retired env var name
  (``DEEPSEEK_API_KEY``) — the TP1 credential is ``BAILIAN_TOKEN_PLAN_API_KEY``

Same AST approach as the sibling guards (cicatrix family #3 "guard-over-match",
scar W121): a docstring or a ``logger.*(...)``/``raise SomeError(...)`` string
argument recording *why* the retirement happened is explanatory prose, not a
live call site, and must not trip this guard. Guilt and innocence are
exercised for every rule below, including the file's own legitimate
`DeepSeek*` class names (innocence — the one behavior this guard MUST NOT
share with its two full-retirement siblings).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent

_GUARDED_FILES = [
    _SCRIPTS_DIR / "deepseek_client.py",
]

_FORBIDDEN_URL = "api.deepseek.com"
_FORBIDDEN_ENV = "DEEPSEEK_API_KEY"
_FORBIDDEN_TOKENS = (_FORBIDDEN_URL, _FORBIDDEN_ENV)

_DocstringHolder = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)

_LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """id() of every string-constant AST node in docstring position (first
    statement of a module/class/function body) — the same convention
    ``ast.get_docstring`` uses. Excluded from the live-code-token scan."""
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


def _explanatory_call_ids(tree: ast.AST) -> set[int]:
    """id() of every string-constant AST node inside a ``logger.<level>(...)``
    call's arguments, or inside a ``raise SomeError(...)`` constructor's
    arguments — explanatory prose for a human, not a live routing call."""
    ids: set[int] = set()

    def _collect_string_constants(node: ast.AST) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                ids.add(id(sub))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            is_log_call = isinstance(node.func, ast.Attribute) and node.func.attr in _LOG_METHODS
            if is_log_call:
                for arg in node.args:
                    _collect_string_constants(arg)
                for kw in node.keywords:
                    if kw.value is not None:
                        _collect_string_constants(kw.value)
        elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            for arg in node.exc.args:
                _collect_string_constants(arg)
            for kw in node.exc.keywords:
                if kw.value is not None:
                    _collect_string_constants(kw.value)

    return ids


def _scan_source(source: str, label: str) -> list[str]:
    """Return a list of human-readable violation strings (empty = clean).

    Deliberately does NOT check class/function names or import statements
    for the substring "deepseek" — unlike the two full-retirement sibling
    guards, this file legitimately keeps DeepSeek-named types and a
    DeepSeek-model default. Only the two RETIRED-DOOR-SPECIFIC tokens are
    forbidden, and only as live (non-docstring, non-explanatory-call) string
    literals.
    """
    tree = ast.parse(source, filename=label)
    exempt_ids = _docstring_node_ids(tree) | _explanatory_call_ids(tree)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in exempt_ids:
            continue  # explanatory prose (docstring or logger/raise) — allowed
        for token in _FORBIDDEN_TOKENS:
            if token in node.value:
                violations.append(
                    f"{label}: live string literal contains {token!r} "
                    f"(line {getattr(node, 'lineno', '?')})"
                )

    return violations


# ── Guilt: real reintroduction must be caught ──────────────────────────


@pytest.mark.parametrize("path", _GUARDED_FILES, ids=lambda p: p.name)
def test_no_live_direct_door_token_in_guarded_files(path: Path) -> None:
    assert path.exists(), f"guarded file moved/renamed: {path}"
    source = path.read_text(encoding="utf-8")
    violations = _scan_source(source, str(path))
    assert violations == [], "\n".join(violations)


def test_positive_control_url_literal_is_caught() -> None:
    source = f'API_URL = "https://{_FORBIDDEN_URL}/v1/chat/completions"\n'
    violations = _scan_source(source, "synthetic_url.py")
    assert any(_FORBIDDEN_URL in v for v in violations)


def test_positive_control_env_var_literal_is_caught() -> None:
    source = 'import os\nkey = os.environ.get("DEEPSEEK_API_KEY")\n'
    violations = _scan_source(source, "synthetic_env.py")
    assert any(_FORBIDDEN_ENV in v for v in violations)


# ── Innocence: correct current code must NOT be caught ─────────────────


def test_module_docstring_mentioning_the_retired_door_is_allowed() -> None:
    """A module docstring recording the retirement (exactly what the real
    file does) must not trip the guard."""
    source = (
        '"""Re-pointed 2026-08-29: this used to call api.deepseek.com with '
        'DEEPSEEK_API_KEY directly. That door was retired 2026-07-19."""\n'
        "\n"
        "def do_nothing() -> None:\n"
        "    pass\n"
    )
    violations = _scan_source(source, "synthetic_docstring.py")
    assert violations == []


def test_comment_mentioning_the_retired_door_is_allowed() -> None:
    """``ast`` never sees ``#`` comments at all, so they can never trip this
    guard — asserted here so the invariant is explicit, not incidental."""
    source = (
        "# api.deepseek.com + DEEPSEEK_API_KEY — retired 2026-07-19, now TP1.\n"
        "def do_nothing() -> None:\n"
        "    pass\n"
    )
    violations = _scan_source(source, "synthetic_comment.py")
    assert violations == []


def test_logger_call_naming_the_retired_door_is_allowed() -> None:
    source = (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        'logger.warning("DEEPSEEK_API_KEY is retired, use BAILIAN_TOKEN_PLAN_API_KEY")\n'
    )
    violations = _scan_source(source, "synthetic_logger.py")
    assert violations == []


def test_raise_call_naming_the_retired_door_is_allowed() -> None:
    source = (
        "class DeepSeekError(RuntimeError):\n"
        "    pass\n"
        "\n"
        "def f():\n"
        '    raise DeepSeekError("no api.deepseek.com support anymore")\n'
    )
    violations = _scan_source(source, "synthetic_raise.py")
    assert violations == []


def test_deepseek_named_classes_and_model_literal_are_allowed() -> None:
    """The one behavior this guard MUST NOT share with its two
    full-retirement siblings: DeepSeek-named types and the
    deepseek-v4-flash-0731 model literal are correct here, not a
    reintroduction of the retired door."""
    source = (
        "class DeepSeekError(RuntimeError):\n"
        "    pass\n"
        "\n"
        "class DeepSeekBalanceDead(DeepSeekError):\n"
        "    pass\n"
        "\n"
        "DEFAULT_MODEL = 'deepseek-v4-flash-0731'\n"
        "PROVIDER = 'deepseek'\n"
    )
    violations = _scan_source(source, "synthetic_legit_deepseek.py")
    assert violations == []


def test_tp1_credential_env_var_literal_is_allowed() -> None:
    source = 'import os\nkey = os.environ.get("BAILIAN_TOKEN_PLAN_API_KEY")\n'
    violations = _scan_source(source, "synthetic_tp1_env.py")
    assert violations == []
