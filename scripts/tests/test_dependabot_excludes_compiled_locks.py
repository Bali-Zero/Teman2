"""Dependabot must never edit a uv-compiled lock file.

For the pip ecosystem Dependabot "supports updates to any .txt file" — there is
no heuristic that tells a hand-written manifest from `uv pip compile` output, so
requirements.lock.txt and requirements-prod.lock.txt were picked up as manifests
purely because they end in .txt. Editing one == pin inside a compiled lock
without re-running the compile yields an internally unsatisfiable pin set: the
PR is born dead at install and its ~9 reds are ONE failure fanning out
(measured 2026-09-01 across PRs #5452, #5453, #5454, #5530 — four distinct
conflicts, one mechanism).

The cure is `exclude-paths` on the pip block. This test is what keeps the cure
CLASS-LEVEL. The npm block of the same config records why that matters:
"scoping the fix to one dependency instead of the class is exactly why the
disease came back through four other packages". A third compiled lock added
later must be excluded by existing, not by someone remembering.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "dependabot.yml"

# Compiled-output suffix used by this repo's `uv pip compile` targets. A file
# matching it is OUTPUT and must never be a Dependabot manifest.
COMPILED_LOCK_GLOB = "*.lock.txt"


def _pip_updates(config: dict) -> list[dict]:
    return [
        u
        for u in config.get("updates", [])
        if u.get("package-ecosystem") == "pip"
    ]


def _uncovered_locks(update: dict, root: Path) -> list[str]:
    """Compiled locks in this block's directory that exclude-paths misses.

    Patterns are relative to the block's own `directory`, per Dependabot's
    documented relativity rule, so both sides are compared as bare names
    relative to that directory.
    """
    directory = update.get("directory", "/").lstrip("/")
    scanned = root / directory
    if not scanned.is_dir():
        return []

    patterns = update.get("exclude-paths", []) or []
    uncovered = []
    for lock in sorted(scanned.glob(COMPILED_LOCK_GLOB)):
        name = lock.name
        if not any(fnmatch.fnmatch(name, p) for p in patterns):
            uncovered.append(f"{directory}/{name}")
    return uncovered


def _overbroad_matches(update: dict, root: Path) -> list[str]:
    """PENDING-ARMS L1856: `_uncovered_locks` only ever proves a pattern set
    is not too NARROW — `exclude-paths: ["*"]` satisfies it trivially while
    silently disarming Dependabot for every OTHER file in the directory too,
    not just the compiled locks. This is the under-tested opposite
    direction: any exclude-paths pattern that also matches a non-lock file
    in the block's own directory is over-broad and must be flagged.
    """
    directory = update.get("directory", "/").lstrip("/")
    scanned = root / directory
    if not scanned.is_dir():
        return []
    patterns = update.get("exclude-paths", []) or []
    offenders = []
    for entry in sorted(scanned.iterdir()):
        if not entry.is_file():
            continue
        name = entry.name
        if fnmatch.fnmatch(name, COMPILED_LOCK_GLOB):
            continue  # a compiled lock IS meant to be excluded
        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                offenders.append(f"{directory}/{name} matched by over-broad pattern {pattern!r}")
    return offenders


def _load(text: str) -> dict:
    return yaml.safe_load(text)


# --- innocence: the real config, as shipped -------------------------------


def test_real_config_excludes_every_compiled_lock_it_would_scan():
    config = _load(CONFIG.read_text(encoding="utf-8"))
    updates = _pip_updates(config)
    assert updates, "no pip block found — this guard would be watching nothing"

    offenders = []
    for update in updates:
        offenders.extend(_uncovered_locks(update, ROOT))

    assert not offenders, (
        "Dependabot would treat these uv-compiled locks as editable manifests:\n  "
        + "\n  ".join(offenders)
        + "\n\nAdd them to `exclude-paths` on their pip block. Do NOT instead add "
        "a per-package `ignore` — that is the whack-a-mole this guard exists to "
        "stop (see the module docstring)."
    )


def test_real_config_exclude_paths_are_not_overbroad():
    """The mirror-image of test_real_config_excludes_every_compiled_lock_it_
    would_scan: proves the shipped exclude-paths cover the locks WITHOUT
    also disarming every other file in the same directory."""
    config = _load(CONFIG.read_text(encoding="utf-8"))
    offenders = []
    for update in _pip_updates(config):
        offenders.extend(_overbroad_matches(update, ROOT))
    assert not offenders, (
        "Dependabot's exclude-paths also match non-lock files, silently "
        "disarming updates for them:\n  " + "\n  ".join(offenders)
    )


def test_the_locks_this_guard_protects_actually_exist():
    """A guard whose subject vanished is a guard that passes for free."""
    backend = ROOT / "apps" / "backend-rag"
    locks = sorted(p.name for p in backend.glob(COMPILED_LOCK_GLOB))
    assert locks == ["requirements-prod.lock.txt", "requirements.lock.txt"], (
        f"the compiled-lock set changed: {locks}. Re-read the pip block's "
        "exclude-paths before assuming this guard still covers it."
    )


# --- guilt: the checker must actually fire --------------------------------


def test_guilt_missing_exclude_paths_is_flagged():
    config = _load(
        """
updates:
  - package-ecosystem: "pip"
    directory: "/apps/backend-rag"
"""
    )
    uncovered = _uncovered_locks(_pip_updates(config)[0], ROOT)
    assert sorted(uncovered) == [
        "apps/backend-rag/requirements-prod.lock.txt",
        "apps/backend-rag/requirements.lock.txt",
    ]


def test_guilt_exclude_paths_that_misses_a_lock_is_flagged():
    """Covering ONE lock by name is the per-instance scar, and must fail."""
    config = _load(
        """
updates:
  - package-ecosystem: "pip"
    directory: "/apps/backend-rag"
    exclude-paths:
      - "requirements.lock.txt"
"""
    )
    uncovered = _uncovered_locks(_pip_updates(config)[0], ROOT)
    assert uncovered == ["apps/backend-rag/requirements-prod.lock.txt"]


def test_guilt_a_pattern_matching_only_source_manifests_is_flagged():
    config = _load(
        """
updates:
  - package-ecosystem: "pip"
    directory: "/apps/backend-rag"
    exclude-paths:
      - "requirements-test.txt"
"""
    )
    assert len(_uncovered_locks(_pip_updates(config)[0], ROOT)) == 2


def test_guilt_star_glob_disarms_every_file_not_only_locks():
    """`exclude-paths: ["*"]` would pass the under-coverage check for free —
    the sanity assertion below proves that blindness, then proves the
    over-broad check closes it. Mutates the REAL config's pip block in
    place (same mutation shape as test_guilt_missing_exclude_paths_is_
    flagged above) so the guard is proven against the actual scanned
    directory, not a synthetic fixture."""
    config = _load(CONFIG.read_text(encoding="utf-8"))
    update = _pip_updates(config)[0]
    update["exclude-paths"] = ["*"]
    assert _uncovered_locks(update, ROOT) == [], (
        "sanity: the under-coverage check alone must NOT catch this — that "
        "blindness is exactly what this row exists to close"
    )
    assert _overbroad_matches(update, ROOT), (
        "exclude-paths: ['*'] must be flagged as over-broad: it matches "
        "every file in the directory, not just the compiled locks"
    )


def test_guilt_doublestar_glob_disarms_every_file_not_only_locks():
    config = _load(CONFIG.read_text(encoding="utf-8"))
    update = _pip_updates(config)[0]
    update["exclude-paths"] = ["**"]
    assert _overbroad_matches(update, ROOT)


# --- innocence: the checker must not fire on correct configs --------------


def test_innocence_shipped_glob_is_not_overbroad():
    config = _load(
        """
updates:
  - package-ecosystem: "pip"
    directory: "/apps/backend-rag"
    exclude-paths:
      - "*.lock.txt"
"""
    )
    assert _overbroad_matches(_pip_updates(config)[0], ROOT) == []





def test_innocence_the_shipped_glob_covers_both_locks():
    config = _load(
        """
updates:
  - package-ecosystem: "pip"
    directory: "/apps/backend-rag"
    exclude-paths:
      - "*.lock.txt"
"""
    )
    assert _uncovered_locks(_pip_updates(config)[0], ROOT) == []


def test_innocence_naming_both_locks_explicitly_also_passes():
    """The glob is preferred, but an explicit pair is not a defect."""
    config = _load(
        """
updates:
  - package-ecosystem: "pip"
    directory: "/apps/backend-rag"
    exclude-paths:
      - "requirements.lock.txt"
      - "requirements-prod.lock.txt"
"""
    )
    assert _uncovered_locks(_pip_updates(config)[0], ROOT) == []


def test_innocence_a_directory_with_no_compiled_lock_is_not_flagged():
    config = _load(
        """
updates:
  - package-ecosystem: "pip"
    directory: "/"
"""
    )
    assert _uncovered_locks(_pip_updates(config)[0], ROOT) == []


def test_innocence_non_pip_ecosystems_are_out_of_scope():
    config = _load(
        """
updates:
  - package-ecosystem: "npm"
    directory: "/"
  - package-ecosystem: "github-actions"
    directory: "/"
"""
    )
    assert _pip_updates(config) == []


@pytest.mark.parametrize(
    "name, matched",
    [
        ("requirements.lock.txt", True),
        ("requirements-prod.lock.txt", True),
        ("requirements.txt", False),
        ("requirements-prod.txt", False),
        ("requirements-test.txt", False),
        ("requirements-ci-tools.txt", False),
        ("requirements-livekit-worker.txt", False),
        ("requirements-local-audio.txt", False),
    ],
)
def test_glob_separates_compiled_output_from_hand_written_sources(name, matched):
    """The glob must catch every lock and no source manifest."""
    assert fnmatch.fnmatch(name, COMPILED_LOCK_GLOB) is matched
