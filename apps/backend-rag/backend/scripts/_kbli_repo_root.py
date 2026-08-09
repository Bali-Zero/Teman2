"""Robust repo-root resolver for the KBLI Qdrant indexers.

Both indexers (index_kbli_gold_content.py, reindex_kbli_2025_final.py) need
to locate data files that live at fixed paths relative to the repository
root.  In the dev checkout ``parents[4]`` happens to reach the root, but in
the Fly container the directory tree is shallower — ``parents[4]`` raises
``IndexError``.  This module replaces the frozen ``parents[N]`` measurement
(a bare ``parents[N]`` is a frozen measurement of one layout — the container
just proved it) with a resolver that:

1. Honours ``KBLI_REPO_ROOT`` (env override — useful for tests and CI).
2. Walks UP from the caller's ``__file__`` looking for the first directory
   that contains *all* the given marker files (relative paths).
3. Prints a clear error to stderr naming every path probed and exits 1 —
   never an ``IndexError``.
"""

import os
import sys
from pathlib import Path

__all__ = ["resolve_repo_root"]


def _fail(message: str) -> None:
    """Write *message* to stderr and exit 1."""
    sys.stderr.write(message + "\n")
    sys.exit(1)


def resolve_repo_root(
    markers: list[str],
    script_file: str,
    *,
    env_var: str = "KBLI_REPO_ROOT",
) -> Path:
    """Return the repository root directory.

    *markers* are paths relative to the root that must **all** exist for a
    candidate directory to be accepted (e.g.
    ``["apps/kbli-navigator/lib/kbli-gold-content.ts"]``).

    *script_file* is the ``__file__`` of the calling script — the walk
    starts from its resolved parent directory.
    """
    # 1. Explicit env override.
    env_root = os.environ.get(env_var)
    if env_root:
        root = Path(env_root).resolve()
        if not root.is_dir():
            _fail(
                f"{env_var}={env_root!r} is not a directory. "
                f"Cannot resolve KBLI repository root.",
            )
        _verify_markers(root, markers, source=env_var)
        return root

    # 2. Walk up from the script's location.
    start = Path(script_file).resolve().parent
    for candidate in [start, *start.parents]:
        if all((candidate / m).exists() for m in markers):
            return candidate

    # 3. Exhausted — exit with a clear error naming the paths probed.
    probed = "\n  ".join(str(p) for p in [start, *start.parents])
    _fail(
        f"Could not resolve KBLI repository root.\n"
        f"  Searched from {start} upward for a directory containing ALL of:\n"
        f"    {', '.join(markers)}\n"
        f"  Directories probed:\n  {probed}\n"
        f"  Set {env_var}=<repo-root> to override.",
    )
    raise RuntimeError("unreachable")  # pragma: no cover — _fail exits


def _verify_markers(root: Path, markers: list[str], *, source: str) -> None:
    """Ensure all marker files exist under *root* when set via *source*."""
    missing = [m for m in markers if not (root / m).exists()]
    if missing:
        _fail(
            f"{source}={root} is missing required marker file(s):\n"
            f"    {', '.join(missing)}\n"
            f"  Check that the path points at the repository root.",
        )
