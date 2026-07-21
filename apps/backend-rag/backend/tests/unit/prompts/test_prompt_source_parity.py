"""
Parity test: enforce the single "versioned door" for ZANTARA_MASTER_TEMPLATE.

Regression guard for the F1 split-brain documented in
research/operations/2026-07-17-zantara-prompt-v4-design.md §1/§4.3:
`backend/services/rag/agentic/prompt_builder.py` used to import
ZANTARA_MASTER_TEMPLATE directly from backend.prompts.zantara_core (v1),
bypassing backend.llm.prompt_manager (the module that actually reads
ZANTARA_PROMPT_VERSION). Result: the env var had zero effect on the
WhatsApp bot's brain for as long as v2/v3 existed.

The rule this test enforces: no *consumer* outside the backend.prompts
package may import ZANTARA_MASTER_TEMPLATE from anywhere except
backend.llm.prompt_manager (the one legitimate resolver). Internal
re-exports between zantara_core*.py modules inside backend/prompts/ are
not a second instance of the bug and are exempt.

Uses an AST import-scan (not grep) to avoid false positives on comments/
docstrings that merely mention ZANTARA_MASTER_TEMPLATE (e.g.
prompt_builder_simple.py's module docstring).
"""

import ast
from pathlib import Path

# backend/tests/unit/prompts/test_prompt_source_parity.py -> parents[3] == backend/
BACKEND_ROOT = Path(__file__).resolve().parents[3]
assert BACKEND_ROOT.name == "backend", f"Unexpected BACKEND_ROOT: {BACKEND_ROOT}"

PROMPTS_PACKAGE = BACKEND_ROOT / "prompts"
# The one legitimate resolver: reads ZANTARA_PROMPT_VERSION and exposes the
# resolved template. Everyone else must import from here.
ALLOWED_RESOLVER = BACKEND_ROOT / "llm" / "prompt_manager.py"
TESTS_ROOT = BACKEND_ROOT / "tests"


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _imports_raw_template(py_file: Path) -> bool:
    """True if py_file has an ImportFrom of ZANTARA_MASTER_TEMPLATE from a
    zantara_core* module or the backend.prompts package re-export."""
    try:
        source = py_file.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        # Widened matcher (2026-07-17 design doc §8 panel finding #8): also
        # catch `from backend.prompts import ZANTARA_MASTER_TEMPLATE` via the
        # package's __init__.py re-export, not just the zantara_core* submodules
        # directly.
        matches_module = module == "backend.prompts" or module.startswith(
            "backend.prompts.zantara_core",
        )
        if not matches_module:
            continue
        imported_names = {alias.name for alias in node.names}
        if "ZANTARA_MASTER_TEMPLATE" in imported_names:
            return True
    return False


def _find_offending_files() -> list[str]:
    offenders = []
    for py_file in sorted(BACKEND_ROOT.rglob("*.py")):
        if _is_under(py_file, TESTS_ROOT):
            continue
        if py_file.resolve() == ALLOWED_RESOLVER.resolve():
            continue
        if _is_under(py_file, PROMPTS_PACKAGE):
            continue
        if _imports_raw_template(py_file):
            offenders.append(str(py_file.relative_to(BACKEND_ROOT)))
    return offenders


def test_no_consumer_imports_raw_template_outside_prompt_manager():
    """No module outside backend/prompts/ (and outside the resolver itself)
    may import ZANTARA_MASTER_TEMPLATE directly — it must come through
    backend.llm.prompt_manager so ZANTARA_PROMPT_VERSION is respected."""
    offenders = _find_offending_files()
    assert offenders == [], (
        "Found direct ZANTARA_MASTER_TEMPLATE import(s) outside backend/prompts/ "
        "and outside the versioned door (backend/llm/prompt_manager.py) — this "
        "is the F1 split-brain (ZANTARA_PROMPT_VERSION silently ignored). "
        "Import ZANTARA_MASTER_TEMPLATE from backend.llm.prompt_manager instead:\n"
        + "\n".join(offenders)
    )


def test_prompt_builder_uses_the_versioned_door():
    """Sanity anchor: the specific file this PR fixed (F1) must resolve the
    template via prompt_manager, not via a direct zantara_core* import."""
    target = BACKEND_ROOT / "services" / "rag" / "agentic" / "prompt_builder.py"
    assert target.exists(), f"Expected file missing: {target}"
    source = target.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(target))

    resolved_from_manager = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module == "backend.llm.prompt_manager" and any(
            alias.name == "ZANTARA_MASTER_TEMPLATE" for alias in node.names
        ):
            resolved_from_manager = True

    assert resolved_from_manager, (
        "prompt_builder.py must import ZANTARA_MASTER_TEMPLATE from "
        "backend.llm.prompt_manager (the versioned door), not directly from "
        "a zantara_core* module."
    )
    assert not _imports_raw_template(target), (
        "prompt_builder.py still imports ZANTARA_MASTER_TEMPLATE directly "
        "from a zantara_core* module — the F1 split-brain regressed."
    )
