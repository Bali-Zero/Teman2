"""Blackout flag manager — human maintenance window.

Allows operator to pause organism for up to 2h (hardcoded ceiling).
After expiration, flag auto-deletes and organism resumes.
Called by: control_panel HTTP endpoints, Supervisor decision loop
(W1.A reads is_paused() to skip dispatch).
"""
import time
from pathlib import Path
from dataclasses import dataclass


MAX_MINUTES = 120  # 2h hardcoded — no --forever allowed


@dataclass
class BlackoutManager:
    flag_path: Path

    def pause(self, *, minutes: int) -> None:
        """Start blackout for N minutes (1..120). Writes expiry timestamp to flag."""
        if not 1 <= minutes <= MAX_MINUTES:
            raise ValueError(f"minutes must be 1..{MAX_MINUTES}")
        expiry = time.time() + minutes * 60
        self.flag_path.parent.mkdir(parents=True, exist_ok=True)
        self.flag_path.write_text(str(expiry))

    def resume(self) -> None:
        """Clear blackout (removes flag file)."""
        self.flag_path.unlink(missing_ok=True)

    def is_paused(self) -> bool:
        """Check if blackout is currently active. Auto-deletes expired flags."""
        if not self.flag_path.exists():
            return False
        try:
            expiry = float(self.flag_path.read_text().strip())
        except (ValueError, OSError):
            return False
        if time.time() > expiry:
            self.flag_path.unlink(missing_ok=True)
            return False
        return True
