"""Enumerate this repo's pytest config roots — the directories pytest treats as
``rootdir``, and therefore the only directories where a ``conftest.py`` is
guaranteed to load for every run under them.

Why this is derived rather than listed: a hardcoded list stays green on the day
someone adds root 16, which is the failure mode the wiring check exists to
prevent (superscar #2 — cured one wrapper out of five, W107).

Two rules this module exists to encode, both measured on 2026-08-29:

* **Dedupe by DIRECTORY, not by file.** ``apps/backend-rag`` carries BOTH a
  ``pytest.ini`` and a ``[tool.pytest.ini_options]`` block in ``pyproject.toml``
  — sixteen config files across fifteen directories. pytest reads the
  ``pytest.ini`` and ignores the pyproject block entirely, so counting files
  would demand conftest wiring for a config that never participates.
* **Let pytest decide, not the glob.** Candidate directories come from a file
  scan, but which file wins is answered by ``_pytest.config.findpaths``, the
  same code path pytest itself runs. Asking the mechanism beats reading a
  description of the mechanism.
"""

from __future__ import annotations

import configparser
from pathlib import Path

from _pytest.config.findpaths import locate_config

#: Filenames that can carry a pytest configuration section.
_CANDIDATE_FILENAMES = ("pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml")

#: Directories excluded from the scan entirely (never a pytest root we own).
_SKIP_DIRS = {".git", ".worktrees", "node_modules", ".venv", "venv", "__pycache__"}


def _declares_pytest_section(path: Path) -> bool:
    """Whether this config file actually carries a pytest section."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if path.name == "pyproject.toml":
        return "[tool.pytest.ini_options]" in text
    if path.name == "pytest.ini":
        return "[pytest]" in text
    # tox.ini uses [pytest]; setup.cfg uses [tool:pytest].
    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
    except configparser.Error:
        return False
    return parser.has_section("pytest") or parser.has_section("tool:pytest")


def candidate_dirs(repo_root: Path) -> list[Path]:
    """Directories holding at least one file that declares a pytest section."""
    found: set[Path] = set()
    for filename in _CANDIDATE_FILENAMES:
        for path in repo_root.rglob(filename):
            if any(part in _SKIP_DIRS for part in path.relative_to(repo_root).parts):
                continue
            if _declares_pytest_section(path):
                found.add(path.parent)
    return sorted(found)


def pytest_config_roots(repo_root: Path) -> list[Path]:
    """The distinct directories pytest would resolve as ``rootdir``.

    Deduped by directory: a directory carrying two config files appears once,
    named by whichever file ``locate_config`` says wins.
    """
    roots: set[Path] = set()
    for directory in candidate_dirs(repo_root):
        _rootdir, inipath, _inicfg, _args = locate_config(directory, [directory])
        if inipath is None:
            continue
        roots.add(Path(inipath).parent)
    return sorted(roots)


def winning_config(directory: Path) -> Path | None:
    """The config file pytest would actually read for a run in ``directory``."""
    _rootdir, inipath, _inicfg, _args = locate_config(directory, [directory])
    return Path(inipath) if inipath is not None else None


def unwired_roots(
    repo_root: Path, reference: bytes, exempt: frozenset[str]
) -> list[str]:
    """Roots that are missing the guard wiring, or carry a diverged copy.

    Returns repo-relative paths so a failure message names the root rather than
    a count. ``exempt`` is passed in by the caller so every exemption is
    written down where a reader can see it, rather than living here.
    """
    missing: list[str] = []
    for root in pytest_config_roots(repo_root):
        rel = root.relative_to(repo_root).as_posix()
        if rel in exempt:
            continue
        conftest = root / "conftest.py"
        if not conftest.is_file() or conftest.read_bytes() != reference:
            missing.append(rel)
    return missing
