"""Regression lint: no live DeepSeek routing left in the council/oracle voice system.

DeepSeek V4 Pro was RETIRED 2026-07-19 (Zero: pre-authorization revoked, key
balance dead — HTTP-402). Its council/oracle voting seat (``DeepSeekHTTPRunner``
in ``cli_runners.py``, wired via ``oracle_cli.py::_build_proponents``) was
replaced by ``KimiCLIRunner`` (CLAUDE.md §5: "replacement refuter seat is
Kimi K3").

This scans the AST of every ``.py`` file directly under
``backend/services/council/`` and ``backend/services/cognitive/`` (a
directory scan, not a hardcoded file list — a new module dropped into either
directory is picked up automatically) and fails if a *live code token*
reintroduces DeepSeek routing:

- a class/function name containing "deepseek"
- an import (``import``/``from ... import``) whose module path or imported
  original name (not local alias — ``from x import DeepSeekHTTPRunner as Y``
  is still caught, because ``Y`` is not what we check) contains "deepseek"
- a non-exempt string literal containing the retired base URL
  (``api.deepseek.com``) or the retired env var name (``DEEPSEEK_API_KEY``)

It deliberately does NOT fail on the word "deepseek" appearing in a comment
or docstring: this file, ``cli_runners.py``, ``oracle.py`` and
``oracle_cli.py`` all correctly *mention* DeepSeek in prose to record why
the retirement happened — a bare substring match would be a guard that trips
on its own history (cicatrix family #3 "guard-over-match", scar W121: a lint
anchored to the wrong token gives a false result in either direction).
Explanatory ``logger.*(...)`` and ``raise SomeError(...)`` string arguments
get the same prose exemption — an error message or log line NAMING the
retired var/URL for a human's benefit is not a live call site (over-match
found 2026-08-29: ``raise ValueError("DEEPSEEK_API_KEY is no longer
supported")`` and an equivalent ``logger.info(...)`` both tripped the guard
before this exemption existed). Guilt and innocence are exercised for every
rule below.

**What this guard does NOT catch** (documented rather than silently claimed
as comprehensive, per cicatrix family #2 "esiste ≠ armato" — a guard
believed comprehensive is worse than a narrow one known to be narrow):
string concatenation or ``.format()``/f-string interpolation that only
assembles the forbidden substring at runtime (``"api." + "deepseek" +
".com"``), a base URL read purely from an env var with no literal fallback
(nothing here to scan), dynamic dict-key registration under a bare
``"deepseek"`` string (not checked — that word alone is far too common in
legitimate prose to treat as a forbidden token; only the two specific
retired identifiers above are), and a lambda/factory that returns a runner
without naming it. Static AST pattern-matching cannot close all of these
without becoming a dataflow analysis (CodeQL's job, not a lightweight
pytest guard) or risking new over-match. Reviewed adversarially 2026-08-29
(PASS-WITH-CONDITIONS on #5203) — this list is the honest residual.

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

_FORBIDDEN_URL = "api.deepseek.com"
_FORBIDDEN_ENV = "DEEPSEEK_API_KEY"

_DocstringHolder = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)

# logger.<one of these>(...) string args are treated as explanatory prose,
# same as a docstring — not a live call site.
_LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}


def _discover_guarded_files(dirs: list[Path]) -> list[Path]:
    """Every ``*.py`` directly under each directory (non-recursive — matches
    the flat layout both real directories currently have). A new module
    dropped in is discovered automatically; nothing needs editing here."""
    files: list[Path] = []
    for d in dirs:
        files.extend(sorted(d.glob("*.py")))
    return files


_GUARDED_FILES = _discover_guarded_files([_COUNCIL_DIR, _COGNITIVE_DIR])


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


def _explanatory_call_ids(tree: ast.AST) -> set[int]:
    """id() of every string-constant AST node that sits inside the argument
    list of a ``logger.<level>(...)`` call, or inside the exception
    constructor of a ``raise ...(...)`` statement. Both are explanatory
    prose aimed at a human reading logs/tracebacks, not a live routing
    call — exempt from the live-code-token scan for the same reason a
    docstring is.
    """
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
                        f"(line {getattr(node, 'lineno', '?')}) — aliasing it "
                        "does not evade this guard"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "deepseek" in alias.name.lower():
                    violations.append(
                        f"{label}: imports module {alias.name!r} "
                        f"(line {getattr(node, 'lineno', '?')}) reintroduces "
                        "a DeepSeek code path"
                    )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in exempt_ids:
                continue  # explanatory prose (docstring or logger/raise) — allowed
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


def test_guarded_files_actually_cover_the_four_known_files() -> None:
    """The directory scan must still find the files this guard exists for —
    proves the scan isn't silently discovering zero files (e.g. wrong path)."""
    names = {p.name for p in _GUARDED_FILES}
    assert {"cli_runners.py", "tone_council.py", "oracle.py", "oracle_cli.py"} <= names


def test_directory_scan_discovers_a_new_module_without_editing_this_file() -> None:
    """Prove the scan is a real directory glob, not a disguised hardcoded
    list — a brand-new file dropped into a guarded directory must appear
    with zero changes to ``_GUARDED_FILES`` or this test file.

    Uses an isolated tmp directory (not the real council/ tree) so this
    test never mutates the actual source checkout.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / "existing.py").write_text("x = 1\n", encoding="utf-8")
        before = _discover_guarded_files([tmp_dir])
        assert {p.name for p in before} == {"existing.py"}

        (tmp_dir / "brand_new_module.py").write_text("y = 2\n", encoding="utf-8")
        after = _discover_guarded_files([tmp_dir])
        assert {p.name for p in after} == {"existing.py", "brand_new_module.py"}


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
    the class name or URL (e.g. a caller building its own client). Plain
    assignment/call context (not logger/raise) — must NOT be exempted."""
    source = 'import os\nkey = os.environ.get("DEEPSEEK_API_KEY")\n'
    violations = _scan_source(source, "synthetic_env.py")
    assert any("DEEPSEEK_API_KEY" in v for v in violations)


def test_positive_control_aliased_import_is_caught() -> None:
    """`from x import DeepSeekHTTPRunner as ReplacementRunner` must still be
    flagged — aliasing the local name must not evade the guard, since the
    check reads the imported original name, not the alias."""
    source = "from some.new.module import DeepSeekHTTPRunner as ReplacementRunner\n"
    violations = _scan_source(source, "synthetic_aliased_import.py")
    assert any("DeepSeekHTTPRunner" in v for v in violations)


def test_positive_control_module_path_import_is_caught() -> None:
    """`import foo.deepseek_bridge` must be flagged even with no forbidden
    class name or literal anywhere in the importing file."""
    source = "import services.deepseek_bridge\n"
    violations = _scan_source(source, "synthetic_module_import.py")
    assert any("deepseek_bridge" in v for v in violations)


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


def test_logger_call_explaining_the_retirement_is_allowed() -> None:
    """`logger.info("...DEEPSEEK_API_KEY...")` explaining the retirement to
    an operator reading logs must not trip the guard — over-match found
    2026-08-29 during PR #5203 review: this exact shape was previously
    flagged as a live violation."""
    source = (
        "import logging\n"
        'logger = logging.getLogger(__name__)\n'
        "def warn_once() -> None:\n"
        '    logger.info("DEEPSEEK_API_KEY was retired 2026-07-19, see CLAUDE.md")\n'
    )
    violations = _scan_source(source, "synthetic_logger.py")
    assert violations == []


def test_raise_explaining_the_retirement_is_allowed() -> None:
    """`raise ValueError("DEEPSEEK_API_KEY is no longer supported")` must not
    trip the guard — same 2026-08-29 over-match as the logger case above."""
    source = (
        "def reject() -> None:\n"
        '    raise ValueError("DEEPSEEK_API_KEY is no longer supported")\n'
    )
    violations = _scan_source(source, "synthetic_raise.py")
    assert violations == []


def test_raise_with_forbidden_url_reference_is_allowed() -> None:
    """Same exemption for the URL token, not just the env var — a
    ConnectionError message naming the old dead endpoint for a human is
    prose, not a live call site."""
    source = (
        "def reject() -> None:\n"
        '    raise ConnectionError("cannot reach the retired api.deepseek.com endpoint")\n'
    )
    violations = _scan_source(source, "synthetic_raise_url.py")
    assert violations == []
