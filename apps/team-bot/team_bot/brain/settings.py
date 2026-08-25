"""TP1 credential loading — mirrors (does not import; `apps/team-bot` does
not depend on repo-root `scripts/`) `scripts/arsenal_probe.py::load_tp1_settings_key()`.
Same file, same field, same 0600-expected path, same "diagnostics name the
missing field or file but never include settings content or a value"
contract — team-lead brief: "Read secret NAMES, never values."

Author: Claude (lane B4-tp1 — team-bot TP1 brain adapter).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["TP1_BASE_URL", "TP1CredentialError", "load_tp1_api_key"]

TP1_BASE_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"


class TP1CredentialError(RuntimeError):
    """Raised by `load_tp1_api_key()` when the key cannot be loaded. The
    message names the missing FILE or FIELD, never a value."""


def load_tp1_api_key(path: str = "~/.qwen/settings.json") -> str:
    """Load `env.BAILIAN_TOKEN_PLAN_API_KEY` from Qwen's local settings.

    Raises `TP1CredentialError` (never returns an empty/placeholder string)
    when the file is missing, unreadable, not JSON, or lacks the field —
    every one of those is a caller-visible configuration problem, not a
    silent "try anyway with an empty key" (which would surface as a
    confusing 401 far from its actual cause).
    """
    p = Path(os.path.expanduser(path))
    if not p.exists():
        raise TP1CredentialError(f"{p} not found")
    try:
        parsed = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # ValueError covers json.JSONDecodeError AND a stray non-UTF-8 byte
        # (UnicodeDecodeError raised by read_text itself) — same widened
        # catch as arsenal_probe.py's load_tp1_settings_key, same reason:
        # a corrupt settings file must degrade to a named config error,
        # never propagate as a raw, uncaught exception type.
        raise TP1CredentialError(f"{p} unreadable: {type(e).__name__}") from e
    if not isinstance(parsed, dict):
        raise TP1CredentialError(f"env.BAILIAN_TOKEN_PLAN_API_KEY not set in {p}")
    env = parsed.get("env")
    if not isinstance(env, dict):
        raise TP1CredentialError(f"env.BAILIAN_TOKEN_PLAN_API_KEY not set in {p}")
    value = env.get("BAILIAN_TOKEN_PLAN_API_KEY")
    if not isinstance(value, str) or not value.strip():
        raise TP1CredentialError(f"env.BAILIAN_TOKEN_PLAN_API_KEY not set in {p}")
    return value.strip()
