"""Dark-flag helper for the team-bot app.

Mirrors the exact pattern of
``backend/services/rag/agentic/team_crm_tools.py::is_team_crm_tools_enabled()``
(same repo, same shape, default OFF, single env read) so the webhook/loop
units that come after this one have a flag ready rather than each inventing
its own. Nothing in ``team_bot.registry`` or ``team_bot.loop`` reads this
flag today — they are pure data/functions with no I/O and nothing wires them
into a live path yet. This function exists for the FIRST unit that does.

``is_team_bot_memory_enabled`` (lane B8, owner directive #1 §3) is the
matching gate for ``team_bot.memory`` — registered in
``apps/backend-rag/backend/services/client_bot/kill_switches.py`` as
``TEAM_BOT_MEMORY_ENABLED``, plane ``team_replies`` (the memory card feeds
reply generation; it never touches CRM, so it is not the ``team_mutations``
plane). Same "default OFF, single env read" shape — nothing in
``team_bot.memory`` reads this flag itself (the store has no I/O-gating
opinion of its own, same as ``SqlitePendingActionStore``); a future
loop-wiring caller checks it before calling ``record_episodic_event``/
``render_member_card``. ``forget_member``/``forget_target`` are
deliberately NOT gated by this flag anywhere in this package — a member's
right to have their own data deleted does not depend on whether writes are
currently turned on.
"""

from __future__ import annotations

import os

__all__ = ["is_team_bot_enabled", "is_team_bot_memory_enabled"]


def is_team_bot_enabled() -> bool:
    """True only when ``TEAM_BOT_ENABLED`` is truthy. Default OFF."""
    return os.getenv("TEAM_BOT_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def is_team_bot_memory_enabled() -> bool:
    """True only when ``TEAM_BOT_MEMORY_ENABLED`` is truthy. Default OFF."""
    return os.getenv("TEAM_BOT_MEMORY_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
