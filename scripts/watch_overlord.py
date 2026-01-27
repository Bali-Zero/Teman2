#!/usr/bin/env python3
import time
import subprocess
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).parent.parent
OVERLORD_SCRIPT = PROJECT_ROOT / "scripts" / "overlord.py"
CHECK_INTERVAL = 2  # Check files every 2 seconds
FLY_CHECK_INTERVAL = 300  # Check Fly.io every 5 minutes (300s)


def get_mtime_sum():
    """Get sum of modification times of all python files (rough hash)."""
    total = 0
    try:
        # Fast way to get all py files modification times
        # Using git ls-files to only check tracked files is cleaner usually,
        # but pure glob is fine for watch mode.
        for p in PROJECT_ROOT.glob("**/*.py"):
            if ".venv" in str(p):
                continue
            try:
                total += p.stat().st_mtime
            except OSError:
                pass
    except Exception:
        pass
    return total


def clear_screen():
    print("\033[H\033[J", end="")


def main():
    print("👁️  OVERLORD WATCHDOG ACTIVE")
    print(f"   > Watching: {PROJECT_ROOT}")
    print(f"   > Fly.io Check: Every {FLY_CHECK_INTERVAL}s")
    print("   (Press Ctrl+C to stop)")

    last_mtime = get_mtime_sum()
    last_fly_check = 0

    try:
        while True:
            current_time = time.time()

            # 1. Check for File Changes (Instant Reaction)
            current_mtime = get_mtime_sum()
            if current_mtime != last_mtime:
                print("\n⚡ Change detected! Triggering Overlord...")
                subprocess.run([str(OVERLORD_SCRIPT)])
                last_mtime = current_mtime
                print("👁️  Resuming watch...")

            # 2. Check Production (Periodic)
            if current_time - last_fly_check > FLY_CHECK_INTERVAL:
                # We run overlord but maybe we can just run the health check part?
                # For now, running full script is fine, it includes health check.
                print("\n☁️  Scheduled Production Check...")
                subprocess.run([str(OVERLORD_SCRIPT)])
                last_fly_check = current_time
                print("👁️  Resuming watch...")

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑 Overlord Watchdog stopped.")


if __name__ == "__main__":
    # Ensure executable
    os.chmod(OVERLORD_SCRIPT, 0o755)
    main()
