"""Bootstrap the OS environment for LaunchAgent-invoked mata_garuda crons.

Why this exists (cicatrix #1 HOME-fork + W84 TCC, resolved 2026-07-01):
--------------------------------------------------------------------------
The mata_garuda crons used to run through a shell wrapper
(``~/scripts/matagaruda-cron-tcc-safe.sh``) whose only jobs were to
``source ~/.nuzantara-secrets.env`` and ``export GARUDA_REDIS_HOST`` before
exec-ing the venv python. That wrapper had to live OUTSIDE the repo
(``~/scripts``) because a ``.sh`` under ``~/Desktop`` cannot be OPENED by
launchd's ``/bin/zsh`` under macOS TCC (exit 127, W84). Living outside the
repo made it a HOME-fork (cicatrix #1): the repo fix never reached it, and
it silently hardcoded the wrong Redis host in the 2026-06-30 split-brain.

The canonical fix removes the wrapper entirely. launchd calls the venv
python DIRECTLY (``<repo>/.venv/bin/python -u <entry>``) — an adhoc-signed
binary bypasses TCC even under ``~/Desktop``, and living in the repo means
``git pull`` keeps it correct. The only thing the wrapper did that the
plist can't cleanly do is inject secrets WITHOUT writing the Redis password
in cleartext into a world-readable ``.plist`` (cicatrix #4). So that one
responsibility moves here: this module, imported once at package import,
loads ``~/.nuzantara-secrets.env`` into ``os.environ`` (never overwriting a
value the plist already set) and defaults ``GARUDA_REDIS_HOST`` to the
Pro-canonical ``127.0.0.1`` (Stage-1 single-writer, Zero 2026-06-30).

Idempotent + side-effect-safe: it only fills MISSING keys, so importing it
from tests or an interactive shell never clobbers a deliberately-set env.
It reads a 0600 file and never logs any value (cicatrix #4).
"""
from __future__ import annotations

import os
from pathlib import Path

# Guard: run the fill exactly once per process, even across re-imports.
_DONE_FLAG = "_MATA_GARUDA_ENV_BOOTSTRAPPED"

# Canonical Redis = Pro 127.0.0.1 (was Mini 100.93.236.6 → 2026-06-30
# split-brain: crons read Mini while monitor/archiver read Pro, 982 alerts
# sat unsent). Only applied if nothing upstream already set the host.
_DEFAULTS = {
    "GARUDA_REDIS_HOST": "127.0.0.1",
}

# Keys we are willing to import from the secrets file. Explicit allow-list so
# an unrelated secret in that shared file never leaks into a cron's env.
_ALLOWED_SECRET_KEYS = frozenset({
    "GARUDA_REDIS_PASSWORD",
    "GARUDA_REDIS_HOST",
    "GARUDA_REDIS_PORT",
    "GARUDA_CANONICAL_REDIS_HOST",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_CHAT_ID",
    "TELEGRAM_APPROVAL_CHAT_ID",
    "TELEGRAM_PUBLIC_CHANNEL_ID",
})


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a ``KEY=value`` dotenv file. Tolerant of comments/blank lines
    and surrounding quotes. Never raises on a malformed line — skips it."""
    out: dict[str, str] = {}
    try:
        raw = path.read_text()
    except OSError:
        return out
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def bootstrap_env(secrets_path: Path | None = None) -> None:
    """Fill MISSING env keys from the secrets file + apply canonical defaults.

    Never overwrites a key already present in ``os.environ`` (the plist's
    ``EnvironmentVariables`` win). Idempotent per process.
    """
    if os.environ.get(_DONE_FLAG):
        return

    path = secrets_path or Path.home() / ".nuzantara-secrets.env"
    file_env = _parse_env_file(path)
    for key, val in file_env.items():
        if key in _ALLOWED_SECRET_KEYS and key not in os.environ and val:
            os.environ[key] = val

    for key, val in _DEFAULTS.items():
        os.environ.setdefault(key, val)

    os.environ[_DONE_FLAG] = "1"


# Run on import — this module is imported once by the package root.
bootstrap_env()
