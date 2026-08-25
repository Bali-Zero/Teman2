"""Dark-flag helpers for the team-bot app.

``is_team_bot_enabled`` mirrors the exact pattern of
``backend/services/rag/agentic/team_crm_tools.py::is_team_crm_tools_enabled()``
(same repo, same shape, default OFF, single env read).

``is_team_bot_multistep_reads_enabled`` / ``max_read_steps`` implement owner
directive #1 §2's amendment to F4/F5: "reads and searches may chain freely,
multi-step ... alza MAX_STEPS a un valore sensato, es. 8". Registered in
the F11/B7 kill-switch registry as ``TEAM_BOT_MULTISTEP_READS_ENABLED``
(``apps/backend-rag/backend/services/client_bot/kill_switches.py`` +
``docs/plans/2026-08-25-due-bot-live/ops/KILL-SWITCHES.md``) — reused,
never re-invented, per the same "one kill switch nobody can find at 3am is
not a kill switch" discipline every other flag in this repo follows.

Everything born OFF: with the dark flag unset (or false),
``max_read_steps()`` returns 1 — TODAY'S EXACT BEHAVIOR — REGARDLESS of
what ``TEAM_BOT_MAX_READ_STEPS`` is set to, so a stray/leftover env var
value can never silently widen the read chain while the feature is meant
to be off. ``max_read_steps()`` is the SINGLE place that decides the
budget, deriving it from the same flag check ``is_team_bot_multistep_
reads_enabled()`` exposes — never two independently-maintained copies of
"is this on" (the exact drift class B6c's F1 finding already found once in
``loop/claim_gate.py``, at a different layer).

Nothing in ``team_bot.registry`` or ``team_bot.loop`` reads these flags
today — they are pure data/functions with no I/O (``turn_plan.py``'s
``try_append_read_step`` takes ``max_steps`` as an explicit parameter for
exactly this reason) and nothing wires them into a live path yet. These
functions exist for the FIRST unit that does — the not-yet-built webhook/
loop runtime.
"""

from __future__ import annotations

import os

__all__ = [
    "ABSOLUTE_MAX_READ_STEPS_ENV_CEILING",
    "DEFAULT_MAX_READ_STEPS",
    "SINGLE_STEP",
    "is_team_bot_brain_tp1_enabled",
    "is_team_bot_enabled",
    "is_team_bot_memory_enabled",
    "is_team_bot_multistep_reads_enabled",
    "is_team_bot_read_tools_enabled",
    "max_read_steps",
]

# Directive #1 §2's own worked example ("es. 8").
DEFAULT_MAX_READ_STEPS = 8

# Exactly today's behavior: one read step per turn, same as a bare
# ToolDecision always was before this amendment.
SINGLE_STEP = 1

# A caller-facing clamp on TEAM_BOT_MAX_READ_STEPS, independent of
# turn_plan.py's own ABSOLUTE_MAX_READ_STEPS (20) — kept equal to it today,
# named separately because the two live in different modules for different
# reasons (this one bounds an operator-editable env var against typos/
# misconfiguration; that one is a pydantic Field's structural ceiling) and
# must not silently drift out of sync (a test asserts they match).
ABSOLUTE_MAX_READ_STEPS_ENV_CEILING = 20


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def is_team_bot_enabled() -> bool:
    """True only when ``TEAM_BOT_ENABLED`` is truthy. Default OFF."""
    return _truthy(os.getenv("TEAM_BOT_ENABLED", "false"))


def is_team_bot_multistep_reads_enabled() -> bool:
    """True only when ``TEAM_BOT_MULTISTEP_READS_ENABLED`` is truthy.
    Default OFF — reads/searches stay single-step (today's exact
    behavior) until this is explicitly flipped."""
    return _truthy(os.getenv("TEAM_BOT_MULTISTEP_READS_ENABLED", "false"))


def max_read_steps() -> int:
    """The read/search chain's step budget for THIS turn.

    Returns ``SINGLE_STEP`` (1) whenever
    ``is_team_bot_multistep_reads_enabled()`` is false — REGARDLESS of
    ``TEAM_BOT_MAX_READ_STEPS``'s value, so the multi-step relaxation
    cannot be reached by setting only the numeric var. When the dark flag
    is on, reads ``TEAM_BOT_MAX_READ_STEPS`` (default
    ``DEFAULT_MAX_READ_STEPS``, i.e. 8), clamped to
    ``[SINGLE_STEP, ABSOLUTE_MAX_READ_STEPS_ENV_CEILING]``; a
    non-integer value falls back to the default rather than raising —
    this is a runtime budget knob, not a contract boundary, and a typo'd
    env var should degrade to the safe default, not crash the loop.
    """
    if not is_team_bot_multistep_reads_enabled():
        return SINGLE_STEP

    raw = os.getenv("TEAM_BOT_MAX_READ_STEPS", str(DEFAULT_MAX_READ_STEPS))
    try:
        configured = int(raw)
    except ValueError:
        configured = DEFAULT_MAX_READ_STEPS
    return max(SINGLE_STEP, min(configured, ABSOLUTE_MAX_READ_STEPS_ENV_CEILING))


def is_team_bot_memory_enabled() -> bool:
    """True only when ``TEAM_BOT_MEMORY_ENABLED`` is truthy. Default OFF.

    Lane B8, owner directive #1 §3. Registered in the F11/B7 kill-switch
    registry, plane ``team_replies`` — the memory card only ever feeds reply
    generation and never touches CRM, so it is not ``team_mutations``.
    Nothing in ``team_bot.memory`` reads this flag itself (the store has no
    I/O-gating opinion of its own, same as ``SqlitePendingActionStore``); a
    future loop-wiring caller checks it before ``record_episodic_event`` /
    ``render_member_card``. ``forget_member`` / ``forget_target`` are
    deliberately NOT gated by it anywhere — a member's right to have their
    own data deleted does not depend on whether writes are currently on.

    Uses the shared ``_truthy`` helper rather than re-inlining the accepted
    spellings: B8 wrote the tuple inline because the helper did not exist on
    the base it branched from, and two independently-maintained copies of
    "is this on" is the exact drift class this module already learned about.
    """
    return _truthy(os.getenv("TEAM_BOT_MEMORY_ENABLED", "false"))


def is_team_bot_read_tools_enabled() -> bool:
    """True only when ``TEAM_BOT_READ_TOOLS_ENABLED`` is truthy. Default
    OFF. Registered PLANNED in the F11/B7 kill-switch registry
    (``apps/backend-rag/backend/services/client_bot/kill_switches.py`` +
    ``docs/plans/2026-08-25-due-bot-live/ops/KILL-SWITCHES.md``, plane
    ``team_replies``) before this function existed; lane B9 (the executor
    seam) wires the first real read of it and flips that registry entry's
    ``status`` to WIRED in the same change, per the doc's own rule ("wired
    means a named source file reads this env var TODAY").

    The registry's own ``effect_when_off`` describes a LOOP-layer gate
    ("R0/R1 read tools ... are not exposed to the model") that does not
    exist yet (no live loop/webhook runtime in this app today). Lane B9's
    ``team_bot.executor.tool_executor.ToolExecutor`` checks this flag at a
    LOWER layer — immediately before it would ever dispatch a call —
    as defense-in-depth for exactly the case the loop-layer gate is
    supposed to prevent from ever reaching here, mirroring
    ``services/rag/agentic/team_crm_tools.py``'s own documented pattern:
    "even if a future refactor registers these tools unconditionally,
    execute() still refuses when the flag is off."
    """
    return _truthy(os.getenv("TEAM_BOT_READ_TOOLS_ENABLED", "false"))


def is_team_bot_brain_tp1_enabled() -> bool:
    """True only when ``TEAM_BOT_BRAIN_TP1_ENABLED`` is truthy. Default OFF
    (everything ships dark). While ``False``, ``BrainRouter`` never attempts
    any of the three TP1 cloud tiers and goes straight to the local
    read-only degradation lane — this is the single gesture to pull the
    cloud brain out of rotation without touching ``TEAM_BOT_REPLY_ENABLED``
    (the master "send a reply at all" switch).

    Pre-existing bug fixed in passing (lane B9, discovered while adding
    ``is_team_bot_read_tools_enabled`` above and editing this same file):
    this call site referenced ``_env_truthy``, a name that does not exist
    anywhere in this module — a bare call to this function would have
    raised ``NameError``. Untested by the 381 tests that pass on this
    branch today (nothing calls ``is_team_bot_brain_tp1_enabled`` yet — it
    is, like everything else here, "not wired into a live path yet"), so
    the defect was live but silent. Fixed to use the same shared
    ``_truthy`` helper every other flag in this module already uses —
    exactly the "two independently-maintained copies of 'is this on'"
    drift class this module's own docstring warns about, except this
    instance drifted all the way to a nonexistent name rather than a
    second working copy.
    """
    return _truthy(os.getenv("TEAM_BOT_BRAIN_TP1_ENABLED", "false"))
