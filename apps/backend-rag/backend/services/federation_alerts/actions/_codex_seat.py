"""Shared door onto scripts/lib/codex_seat.py for the federation_alerts codex
actions (codex_xhigh_fix, codex_image_gen).

NOT duplicated per-action. Both actions spawn `codex` as a subprocess; a
second copy of this root-finder + importlib glue per action is exactly the
defect scripts/lib/codex_seat.sh's own docstring warns against reproducing
(W106b: "a duplicated list is the very defect codex_seat.sh exists to kill" —
applies equally to the glue that reaches it, not just the seat list itself).

Measured 2026-08-12 on Pro (the machine that runs the federation_alerts
daemon): the default `~/.codex` answers 401 Unauthorized while a paid,
logged-in second seat (`~/.codex-acct2`) sits one environment variable away.
Neither codex_xhigh_fix nor codex_image_gen ever touched CODEX_HOME before
this file existed — every HITL-approved fix/image-gen action was silently
pinned to whichever seat happened to be the CLI's own default.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _repo_root() -> Path:
    """Resolve the repo root in worktrees, CI, and the canonical Pro checkout.

    Independent of codex_xhigh_fix._default_project_root() (used there for
    `cwd`, a different concern) — this one only needs to find
    scripts/lib/codex_seat.py, so it is allowed to answer differently without
    the two ever needing to agree.
    """
    env_root = os.environ.get("NUZANTARA_REPO_ROOT")
    if env_root:
        return Path(env_root).expanduser()

    legacy_root = Path(os.path.expanduser("~/nuzantara"))
    if legacy_root.exists():
        return legacy_root

    for parent in Path(__file__).resolve().parents:
        if (parent / "apps" / "backend-rag").exists():
            return parent

    return legacy_root


def codex_seat_home() -> str | None:
    """A logged-in CODEX_HOME, via scripts/lib/codex_seat.py, or None.

    Loaded by path (this package may run without the repo root on
    sys.path). Never raises: a missing helper, a missing repo root, or a
    shell that misbehaves all degrade to None — callers must leave
    CODEX_HOME unset in that case, which is codex's own default seat, i.e.
    exactly the behaviour every caller had before seat rotation existed.
    """
    helper = _repo_root() / "scripts" / "lib" / "codex_seat.py"
    if not helper.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_codex_seat_lib", helper)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.codex_seat_pick()
    except Exception:  # broad on purpose — a seat hint may never break an action
        return None
