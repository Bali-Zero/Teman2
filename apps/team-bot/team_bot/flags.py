"""Dark-flag helper for the team-bot app.

Mirrors the exact pattern of
``backend/services/rag/agentic/team_crm_tools.py::is_team_crm_tools_enabled()``
(same repo, same shape, default OFF, single env read) so the webhook/loop
units that come after this one have a flag ready rather than each inventing
its own. Nothing in ``team_bot.registry`` or ``team_bot.loop`` reads this
flag today — they are pure data/functions with no I/O and nothing wires them
into a live path yet. This function exists for the FIRST unit that does.
"""

from __future__ import annotations

import os

__all__ = ["is_team_bot_enabled"]


def is_team_bot_enabled() -> bool:
    """True only when ``TEAM_BOT_ENABLED`` is truthy. Default OFF."""
    return os.getenv("TEAM_BOT_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
