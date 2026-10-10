"""Single loader for the staff roster (one SSOT, supplied outside git).

Source precedence, first one that EXISTS wins:

1. env ``TEAM_MEMBERS_JSON``  - the JSON document itself (a Fly secret in prod)
2. env ``TEAM_MEMBERS_FILE``  - path to a JSON file
3. ``DEFAULT_ROSTER_PATH``    - ``data/team_members.json`` next to the package

No caching here: callers cache where they need to. Errors name the SOURCE and
never echo the content (the roster is staff personal data).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ENV_JSON = "TEAM_MEMBERS_JSON"
ENV_FILE = "TEAM_MEMBERS_FILE"
DEFAULT_ROSTER_PATH = Path(__file__).resolve().parent.parent / "data" / "team_members.json"


class TeamRosterError(ValueError):
    """The roster source exists but is malformed. Message names the source only."""


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return value


def _resolve() -> tuple[str, Path | None] | None:
    """Return (description, path-or-None-for-inline-env) of the winning source."""
    if _env(ENV_JSON) is not None:
        return f"env:{ENV_JSON}", None
    file_env = _env(ENV_FILE)
    if file_env is not None:
        path = Path(file_env.strip())
        if path.exists():
            return f"file:{path}", path
    if DEFAULT_ROSTER_PATH.exists():
        return f"file:{DEFAULT_ROSTER_PATH}", DEFAULT_ROSTER_PATH
    return None


def team_roster_source() -> str | None:
    """Description of the source ``load_team_roster`` would use, for logs."""
    resolved = _resolve()
    return resolved[0] if resolved else None


def _validate(data: Any, source: str) -> list[dict]:
    if not isinstance(data, list):
        raise TeamRosterError(f"Team roster from {source} is not a JSON list")
    for index, element in enumerate(data):
        if not isinstance(element, dict):
            raise TeamRosterError(f"Team roster from {source}: element {index} is not an object")
    return data


def load_team_roster() -> list[dict]:
    """Load the roster from the first existing source; ``[]`` when none exists."""
    resolved = _resolve()
    if resolved is None:
        return []
    source, path = resolved
    try:
        text = os.environ[ENV_JSON] if path is None else path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TeamRosterError(
            f"Team roster from {source} is unreadable ({type(exc).__name__})"
        ) from None
    try:
        data = json.loads(text)
    except ValueError:
        raise TeamRosterError(f"Team roster from {source} is not valid JSON") from None
    return _validate(data, source)
