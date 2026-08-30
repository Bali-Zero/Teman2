"""Regression lint: no live DeepSeek routing left in devils_advocate_runner.

`devils_advocate_runner.py` used to shell out directly to the DeepSeek
chat-completions API (`api.deepseek.com`, `DEEPSEEK_API_KEY`) — the direct
door, retired 2026-07-19 (Zero: pre-authorization revoked, key balance dead
— HTTP-402). Replaced by ``kimi -p ... -m kimi-code/k3`` (CLAUDE.md §5:
"replacement refuter seat is Kimi K3"), same swap shape as the council/
oracle voice system (`backend/tests/services/council/test_no_deepseek_regression.py`)
and ConsiglioV1 (`backend/tests/unit/services/research/test_no_deepseek_regression.py`).

Same AST-based approach as both sibling guards, deliberately not a bare
substring match (cicatrix family #3 "guard-over-match", scar W121): a
docstring or comment correctly recording *why* the retirement happened must
not trip this guard — only a live class/function name, import, or
non-docstring string literal referencing the retired binary/URL/env var.

Scope: this one file — `devils_advocate_runner.py` is the only production
file in `infra/eventbus/` that ever called DeepSeek directly (the shared
`scripts/deepseek_client.py` cost-breaker module it used to import is a
separate, still-legitimate multi-caller module and is out of scope here —
it is not itself a DeepSeek routing target, and other callers of it are
untouched by this fix).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_EVENTBUS_DIR = Path(__file__).resolve().parent

_GUARDED_FILES = [
    _EVENTBUS_DIR / "devils_advocate_runner.py",
]

_FORBIDDEN_URL = "api.deepseek.com"
_FORBIDDEN_ENV = "DEEPSEEK_API_KEY"
_FORBIDDEN_MODEL = "deepseek-v4-pro"
_FORBIDDEN_TOKENS = (_FORBIDDEN_URL, _FORBIDDEN_ENV, _FORBIDDEN_MODEL)

_DocstringHolder = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)

_LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}


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


def _explanatory_call_ids(tree: ast.AST) -> set[int]:
    """id() of string constants inside logger.<level>(...) calls or inside
    the exception constructor of raise SomeError(...) — explanatory prose
    naming the retirement, not a live routing token."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            is_log_call = (
                isinstance(func, ast.Attribute)
                and func.attr in _LOG_METHODS
                and isinstance(func.value, ast.Name)
                and func.value.id in ("log", "logger", "logging")
            )
            if is_log_call:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        ids.add(id(arg))
        elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            for arg in node.exc.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    ids.add(id(arg))
    return ids


def _scan_source(source: str, label: str) -> list[str]:
    """Return a list of human-readable violation strings (empty = clean)."""
    tree = ast.parse(source, filename=label)
    exempt_ids = _docstring_node_ids(tree) | _explanatory_call_ids(tree)
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
            if id(node) in exempt_ids:
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


def test_positive_control_url_literal_is_caught() -> None:
    source = f'API_URL = "https://{_FORBIDDEN_URL}/v1/chat/completions"\n'
    violations = _scan_source(source, "synthetic_url.py")
    assert any(_FORBIDDEN_URL in v for v in violations)


def test_positive_control_env_var_literal_is_caught() -> None:
    source = 'import os\nkey = os.environ.get("DEEPSEEK_API_KEY")\n'
    violations = _scan_source(source, "synthetic_env.py")
    assert any(_FORBIDDEN_ENV in v for v in violations)


def test_positive_control_model_literal_is_caught() -> None:
    source = 'MODEL = "deepseek-v4-pro"\n'
    violations = _scan_source(source, "synthetic_model.py")
    assert any(_FORBIDDEN_MODEL in v for v in violations)


def test_positive_control_function_name_is_caught() -> None:
    source = "def call_deepseek():\n    pass\n"
    violations = _scan_source(source, "synthetic_func.py")
    assert any("call_deepseek" in v for v in violations)


# ── Innocence: correct historical prose must NOT be caught ─────────────


def test_module_docstring_mentioning_deepseek_is_allowed() -> None:
    """A module docstring recording the retirement (exactly what this
    repo's real file does) must not trip the guard."""
    source = (
        '"""DeepSeek V4 Pro was RETIRED 2026-07-19. The api.deepseek.com '
        'endpoint and DEEPSEEK_API_KEY are the old dead path — replaced by '
        'Kimi K3."""\n'
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
        "# api.deepseek.com / DEEPSEEK_API_KEY used to live here — "
        "retired 2026-07-19, replaced by Kimi K3.\n"
        "def do_nothing() -> None:\n"
        "    pass\n"
    )
    violations = _scan_source(source, "synthetic_comment.py")
    assert violations == []


def test_logger_call_explaining_the_retirement_is_allowed() -> None:
    source = (
        "import logging\n"
        "log = logging.getLogger(__name__)\n"
        "def f():\n"
        '    log.warning("legacy DEEPSEEK_API_KEY path removed, see api.deepseek.com history")\n'
    )
    violations = _scan_source(source, "synthetic_log.py")
    assert violations == []


def test_raise_explaining_the_retirement_is_allowed() -> None:
    source = (
        "def f():\n"
        '    raise RuntimeError("api.deepseek.com door retired 2026-07-19; DEEPSEEK_API_KEY gone")\n'
    )
    violations = _scan_source(source, "synthetic_raise.py")
    assert violations == []
