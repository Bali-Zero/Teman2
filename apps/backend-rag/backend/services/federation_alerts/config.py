"""Configuration for the Federation Alert Dispatcher daemon.

Reads:
- DATABASE_URL (asyncpg DSN)
- TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID (from ~/.nuzantara-secrets.env)
- FEDERATION_ALERT_MODE (env override; can only DOWNGRADE from DB)
- FEDERATION_ALERT_DAEMON_OWNER (defaults to hostname)
- FEDERATION_ALERT_LEASE_TTL_SEC (default 300)
- FEDERATION_ALERT_DELIBERATION_TIMEOUT_SEC (default 180)

The mode is the SAFER of (DB value, env value). Env can only force a
DOWNGRADE — admin must edit system_settings to upgrade past the env cap.
This pattern (B10) prevents deploys from accidentally promoting
production while a Pro/Air machine has its env stuck on dry_action.
"""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass


def _default_owner() -> str:
    """Identifier for this daemon instance — used in lease_owner."""
    try:
        host = socket.gethostname()
    except OSError:
        host = "unknown"
    return f"fad-daemon@{host}@{os.getpid()}"


@dataclass(frozen=True)
class FADConfig:
    """Runtime configuration for the daemon process."""

    database_url: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    daemon_owner: str
    lease_ttl_sec: int
    deliberation_timeout_sec: int
    env_mode: str | None
    audit_log_dir: str

    @classmethod
    def from_env(cls) -> FADConfig:
        return cls(
            database_url=os.environ.get("DATABASE_URL", ""),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.environ.get("TELEGRAM_OWNER_CHAT_ID") or None,
            daemon_owner=os.environ.get("FEDERATION_ALERT_DAEMON_OWNER")
            or _default_owner(),
            lease_ttl_sec=int(
                os.environ.get("FEDERATION_ALERT_LEASE_TTL_SEC", "300")
            ),
            deliberation_timeout_sec=int(
                os.environ.get(
                    "FEDERATION_ALERT_DELIBERATION_TIMEOUT_SEC", "180"
                )
            ),
            env_mode=os.environ.get("FEDERATION_ALERT_MODE") or None,
            audit_log_dir=os.environ.get(
                "FEDERATION_ALERT_AUDIT_DIR",
                os.path.expanduser("~/logs/alert-dispatcher"),
            ),
        )

    def assert_required(self) -> None:
        """Raise if required values are missing.

        Telegram token is OPTIONAL — daemon falls back to JSONL only when
        it can't reach Telegram. DATABASE_URL is mandatory.
        """
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL not set; daemon cannot LISTEN federation_alert"
            )
