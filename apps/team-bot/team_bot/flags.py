"""Dark-flag helper for the team-bot app.

Mirrors the exact pattern of
``backend/services/rag/agentic/team_crm_tools.py::is_team_crm_tools_enabled()``
(same repo, same shape, default OFF, single env read) so the webhook/loop
units that come after this one have a flag ready rather than each inventing
its own. Nothing in ``team_bot.registry`` or ``team_bot.loop`` reads this
flag today — they are pure data/functions with no I/O and nothing wires them
into a live path yet. This function exists for the FIRST unit that does.

``is_team_bot_brain_tp1_enabled`` is lane B4-tp1's own switch, registered in
``apps/backend-rag/backend/services/client_bot/kill_switches.py`` (plane
``team_replies`` — F11 has no dedicated "brain generation" plane distinct
from replies; this is the narrower gesture that pulls only the CLOUD tiers
out of rotation, leaving ``TEAM_BOT_REPLY_ENABLED`` as the master switch for
whether a reply is sent at all). Read directly by
``team_bot.brain.router.BrainRouter`` — see that module for the resulting
"skip straight to local read-only" behavior when this is ``False``.
"""

from __future__ import annotations

import os

__all__ = ["is_team_bot_brain_tp1_enabled", "is_team_bot_enabled"]


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def is_team_bot_enabled() -> bool:
    """True only when ``TEAM_BOT_ENABLED`` is truthy. Default OFF."""
    return _env_truthy("TEAM_BOT_ENABLED")


def is_team_bot_brain_tp1_enabled() -> bool:
    """True only when ``TEAM_BOT_BRAIN_TP1_ENABLED`` is truthy. Default OFF
    (everything ships dark). While ``False``, ``BrainRouter`` never attempts
    any of the three TP1 cloud tiers and goes straight to the local
    read-only degradation lane — this is the single gesture to pull the
    cloud brain out of rotation without touching ``TEAM_BOT_REPLY_ENABLED``
    (the master "send a reply at all" switch)."""
    return _env_truthy("TEAM_BOT_BRAIN_TP1_ENABLED")
