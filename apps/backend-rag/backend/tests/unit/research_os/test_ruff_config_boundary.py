"""Guilt-arm for L1301: packages/research-os-core/ had no [tool.ruff] table,
so ruff's config discovery stopped at that package's own pyproject.toml
(only [build-system]/[project]/...) and never walked up to
apps/backend-rag/pyproject.toml's [tool.ruff] (line-length=100) — every file
under the package silently formatted/linted to ruff's bare default
(line-length 88) instead, and `ruff format --check`'s verdict flipped
depending on whether an invocation happened to pass --config explicitly.

Fix: packages/research-os-core/pyproject.toml now carries
`[tool.ruff]\nextend = "../../apps/backend-rag/pyproject.toml"`.

This test does NOT touch the real package (fragile across future edits) —
it reproduces the two-file relationship (parent config + child package
config) in an isolated tmp_path, mirroring the W82 guilt/innocence
discipline used throughout this repo's own lint tests.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")

# One line at exactly this width: `ruff format --check` disagrees between
# line-length 88 (needs reformat) and 100 (already clean) — measured, not
# guessed (scripts/tests/test_lint_home_fork.py-style "reproduced directly").
_BOUNDARY_LINE = (
    "def f():\n"
    "    result = some_function_call(argument_one, argument_two, argument_three, "
    "arg_four_xxxxxx)\n"
    "    return result\n"
)


def _build_fixture(tmp_path: Path, *, child_has_ruff_table: bool) -> Path:
    """Mirror the REAL topology, not a lookalike: `apps/backend-rag/` and
    `packages/research-os-core/` are SIBLING subtrees under a monorepo root
    that itself carries no pyproject.toml — `sibling_a` is never an
    ANCESTOR directory of `sibling_b`. Measured (see module docstring):
    when the fixture's "parent config" was placed as a literal ancestor of
    the child (the first draft of this test), ruff found it via ordinary
    upward walking regardless of the child's own [tool.ruff] table — that
    reproduced a DIFFERENT bug than the real one. The real defect is that
    backend-rag's config is never reachable by ancestor-walking at all;
    only `extend` (an explicit, named relative link) bridges it.
    """
    root = tmp_path / "monorepo"  # deliberately NO pyproject.toml here
    sibling_a = root / "apps" / "backend-rag"
    sibling_b = root / "packages" / "pkg"
    sibling_a.mkdir(parents=True)
    sibling_b.mkdir(parents=True)
    (sibling_a / "pyproject.toml").write_text(
        '[tool.ruff]\nline-length = 100\ntarget-version = "py310"\n'
    )
    child_config = (
        '[build-system]\nrequires = ["setuptools>=68.0"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        '[project]\nname = "pkg"\nversion = "0.0.0"\n'
    )
    if child_has_ruff_table:
        child_config += '\n[tool.ruff]\nextend = "../../apps/backend-rag/pyproject.toml"\n'
    (sibling_b / "pyproject.toml").write_text(child_config)
    (sibling_b / "module.py").write_text(_BOUNDARY_LINE)
    return sibling_b / "module.py"


def _run_ruff_format_check(
    module: Path, *, config: Path | None = None
) -> subprocess.CompletedProcess:
    """`cwd=module's own fixture root` is load-bearing, not cosmetic: ruff's
    discovery falls back to the CURRENT WORKING DIRECTORY's own project
    settings when nothing is found walking up from the target file — left
    at this process's real cwd (inside this very repo's `apps/backend-rag/`,
    which DOES carry `[tool.ruff]`), that fallback silently answers with the
    real repo's config and hides the defect this test exists to reproduce.
    `--no-cache` for the same reason W121 already names elsewhere in this
    repo: a stale resolution cached under a shared `.ruff_cache` must not
    leak between fixture runs.
    """
    args = ["ruff", "format", "--check", "--no-cache"]
    if config is not None:
        args += ["--config", str(config)]
    args.append(str(module))
    return subprocess.run(args, capture_output=True, timeout=15, cwd=str(module.parents[2]))


def test_guilt_no_local_ruff_table_verdict_flips_with_invocation(tmp_path: Path) -> None:
    module = _build_fixture(tmp_path, child_has_ruff_table=False)
    sibling_a_config = module.parents[2] / "apps" / "backend-rag" / "pyproject.toml"
    default_discovery = _run_ruff_format_check(module)
    explicit_sibling_config = _run_ruff_format_check(module, config=sibling_a_config)
    # Same bytes, opposite verdict, purely a function of invocation — the L1301 defect.
    assert default_discovery.returncode == 1
    assert explicit_sibling_config.returncode == 0


def test_innocence_extend_pins_the_verdict_regardless_of_invocation(tmp_path: Path) -> None:
    module = _build_fixture(tmp_path, child_has_ruff_table=True)
    sibling_a_config = module.parents[2] / "apps" / "backend-rag" / "pyproject.toml"
    default_discovery = _run_ruff_format_check(module)
    explicit_sibling_config = _run_ruff_format_check(module, config=sibling_a_config)
    assert default_discovery.returncode == 0
    assert explicit_sibling_config.returncode == 0


def test_research_os_core_pyproject_extends_backend_rag_ruff_config() -> None:
    """The real fix, read back: the actual package config carries the extend."""
    pkg_pyproject = (
        Path(__file__).resolve().parents[6] / "packages" / "research-os-core" / "pyproject.toml"
    )
    text = pkg_pyproject.read_text()
    assert "[tool.ruff]" in text
    assert "apps/backend-rag/pyproject.toml" in text
