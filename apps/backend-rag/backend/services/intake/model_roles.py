"""Local model-role resolver for the document-intake pipeline."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("zantara.intake.model_roles")

_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[5]
_TOPOLOGY_FILE = "MODEL_TOPOLOGY.json"


def _topology_path() -> Path:
    repo_root = Path(os.getenv("INTAKE_REPO_ROOT", str(_DEFAULT_REPO_ROOT)))
    return repo_root / _TOPOLOGY_FILE


@lru_cache(maxsize=1)
def _load_roles(path: str) -> dict[str, str]:
    data: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    roles = data.get("roles")
    if not isinstance(roles, dict):
        raise ValueError("MODEL_TOPOLOGY.json has no object-valued 'roles' map")
    return {str(key): str(value) for key, value in roles.items()}


def clear_model_role_cache() -> None:
    """Clear cached topology data after env/path changes in tests."""
    _load_roles.cache_clear()


def resolve_model_role(role: str, default: str) -> str:
    """Return a model role from MODEL_TOPOLOGY.json, falling back safely."""
    path = _topology_path()
    try:
        return _load_roles(str(path)).get(role, default)
    except Exception as exc:
        logger.warning(
            "intake model role %s unavailable from %s; using default %s",
            role,
            path,
            default,
            exc_info=exc,
        )
        return default
