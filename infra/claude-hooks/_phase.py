#!/usr/bin/env python3
"""_phase — shared phase-detection helper for phase-aware-guardrails (STEP 2).

`is_plan_phase(payload)` is True ONLY when the session is in plan-mode, so the
"green" gates (orchestrate_gate / dispatch_nudge / stadio_zero_nudge /
worktree_isolation scratch-git) can step aside during exploration and stay hard
during implementation — automatically, no manual toggle.

SIGNAL (empirically verified 2026-06-14 via a temporary PreToolUse probe that
captured the real hook stdin): the field is top-level `permission_mode`
(snake_case) with value `"plan"` in plan-mode vs `"bypassPermissions"`/`"default"`
otherwise. The spec originally assumed camelCase `permissionMode` from the
TRANSCRIPT — the transcript uses camelCase but the HOOK STDIN uses snake_case.
We read snake_case PRIMARY + camelCase fallback so a future Claude Code rename
in either direction can't silently disarm us.

FAIL-SAFE: field absent / unparseable → False (guardrail STAYS ON / deny-by-
default). A relaxation only ever happens on a POSITIVE "plan" signal, never on
absence (panel §9 Q2).

KILL SWITCH: NUZ_PHASE_AWARE_OFF=1 → always False (behaviour = before phase-aware;
every green gate behaves exactly as today). This wins over everything.

MANUAL ESCAPE: NUZ_PHASE=plan → True, for plan-phase work outside the plan-mode
UI (e.g. a brainstorm in chat where Shift+Tab wasn't pressed).

This module is itself protected from agent writes by host_boundary 🔴 (it lives
in ~/.claude/hooks/), so it cannot be silently rewritten to auto-bypass.
"""
from __future__ import annotations

import os
from typing import Any


def is_plan_phase(payload: Any) -> bool:
    """True iff the session is in plan-mode. Fail-safe to False on anything else."""
    # Kill switch wins over all (operator full disable).
    if os.environ.get("NUZ_PHASE_AWARE_OFF") == "1":
        return False
    if not isinstance(payload, dict):
        return False
    # snake_case is the proven hook-stdin grafia; camelCase kept as defensive fallback.
    mode = payload.get("permission_mode") or payload.get("permissionMode") or ""
    if mode == "plan":
        return True
    # Manual escape for plan-phase work outside the plan-mode UI.
    if os.environ.get("NUZ_PHASE") == "plan":
        return True
    return False
