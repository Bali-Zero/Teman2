"""Hardcoded action allowlist — CELL can ONLY execute these actions.
This file is NOT modifiable by CELL. Any action not on this list is REJECTED."""
from dataclasses import dataclass

class ActionNotAllowed(Exception):
    pass

@dataclass(frozen=True)
class AllowedAction:
    name: str
    description: str
    command_template: str
    cooldown_seconds: int
    max_per_day: int

_ACTIONS: dict[str, AllowedAction] = {
    "check_health": AllowedAction(name="check_health", description="Check backend health endpoint", command_template="GET {url}/health", cooldown_seconds=0, max_per_day=1440),
    "read_logs": AllowedAction(name="read_logs", description="Read recent Fly.io logs", command_template="fly logs -a {app} -n 100", cooldown_seconds=60, max_per_day=100),
    "restart_service": AllowedAction(name="restart_service", description="Restart Fly.io machine", command_template="fly machine restart {machine_id} -a {app}", cooldown_seconds=3600, max_per_day=3),
    "scale_up": AllowedAction(name="scale_up", description="Scale to 2 machines", command_template="fly scale count 2 -a {app}", cooldown_seconds=1800, max_per_day=5),
    "scale_down": AllowedAction(name="scale_down", description="Scale to 1 machine", command_template="fly scale count 1 -a {app}", cooldown_seconds=1800, max_per_day=5),
    "alert_human": AllowedAction(name="alert_human", description="Send Telegram alert to operator", command_template="telegram_send {message}", cooldown_seconds=300, max_per_day=20),
    "alert_silent": AllowedAction(name="alert_silent", description="Write to cell_alerts table", command_template="INSERT INTO cell_alerts ...", cooldown_seconds=0, max_per_day=1000),
}

class ActionRegistry:
    def get(self, name: str) -> AllowedAction:
        if name not in _ACTIONS:
            raise ActionNotAllowed(f"Action '{name}' is not in the allowlist")
        return _ACTIONS[name]

    def all(self) -> dict[str, AllowedAction]:
        return dict(_ACTIONS)
