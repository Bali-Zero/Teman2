"""Compatibility shim: ``TEAM_MEMBERS`` now comes from the one roster loader.

The roster is supplied outside git (see ``backend.core.team_roster``); this module
no longer carries data.
"""

import logging

from backend.core.team_roster import TeamRosterError, load_team_roster

logger = logging.getLogger(__name__)

try:
    TEAM_MEMBERS: list[dict] = load_team_roster()
except TeamRosterError as _exc:
    logger.warning("Team roster unavailable, using empty list: %s", _exc)
    TEAM_MEMBERS = []
