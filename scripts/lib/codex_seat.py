"""Python door onto ``scripts/lib/codex_seat.sh`` — which ChatGPT Pro seat runs.

Deliberately NOT a second implementation. It shells out to the ``.sh`` so the
seat list and the rotation counter keep exactly one home; a Python copy of the
list would be this very defect reproduced — two callers, two lists, and one
machine's second subscription invisible to one of them.

Why any of this exists (measured on all three machines 2026-08-12, by the reply
and not by the exit code): every wrapper and script in the fleet invoked
``codex`` with no ``CODEX_HOME``, i.e. always ``~/.codex``. On Pro — the machine
that runs the crons — ``~/.codex`` answers ``401 Unauthorized`` while a paid,
logged-in seat sits one environment variable away.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_LIB = Path(__file__).resolve().with_suffix(".sh")

# Resolving a seat is a `test -f` per candidate. It cannot hang on the network,
# so the only thing this bounds is a pathological shell.
_TIMEOUT_S = 15


def _call(function: str) -> str:
    """Run one function from the shell lib and return its stdout, or ""."""
    if not _LIB.is_file():
        return ""
    sh = shutil.which("sh") or "/bin/sh"
    try:
        proc = subprocess.run(
            [sh, "-c", f'. "{_LIB}"\n{function}'],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout or ""


def codex_seat_dirs() -> list[str]:
    """Every logged-in seat, absolute paths, in preference order. Possibly
    empty — an empty list means "no seat", never "use the default"."""
    return [line for line in _call("codex_seat_dirs").splitlines() if line.strip()]


def codex_seat_pick() -> str | None:
    """An absolute ``CODEX_HOME`` for a seat that is logged in, or ``None``.

    ``None`` means "no seat found" and callers must leave ``CODEX_HOME`` unset —
    an EMPTY ``CODEX_HOME`` reads to codex as "use the default", which is the
    opposite instruction.

    Never raises: a missing lib, a missing shell or a shell that misbehaves all
    degrade to ``None``, i.e. codex's own default seat — exactly the behaviour
    every caller had before this file existed.
    """
    return _call("codex_seat_pick").strip() or None


def codex_seat_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """``env`` (default: a copy of ``os.environ``) with ``CODEX_HOME`` set to a
    live seat. When no seat resolves the key is left exactly as it was, never
    added empty."""
    out = dict(os.environ if env is None else env)
    seat = codex_seat_pick()
    if seat:
        out["CODEX_HOME"] = seat
    return out
