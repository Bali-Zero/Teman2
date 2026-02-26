#!/usr/bin/env python3
"""
Enhanced Scribe Runner with additional features
- Performance metrics
- Change detection
- Git integration (optional)
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run_scribe():
    """Run Scribe and capture output"""
    script_dir = Path(__file__).parent.parent
    scribe_path = script_dir / "apps" / "core" / "scribe.py"

    start_time = datetime.now()

    try:
        result = subprocess.run(
            [sys.executable, str(scribe_path)],
            cwd=str(script_dir),
            capture_output=True,
            text=True,
            check=True,
        )

        duration = (datetime.now() - start_time).total_seconds()

        print(f"✅ Scribe completed in {duration:.2f}s")
        print(f"📄 Output: {len(result.stdout)} characters")

        return True, result.stdout

    except subprocess.CalledProcessError as e:
        print(f"❌ Scribe failed: {e}")
        print(f"Error output: {e.stderr}")
        return False, None


def check_changes():
    """Check if documentation files changed"""
    script_dir = Path(__file__).parent.parent
    docs_dir = script_dir / "docs"

    files_to_check = [
        "LIVING_ARCHITECTURE.md",
        "SYSTEM_OVERVIEW.md",
        "SYSTEM_MAP_4D.md",
    ]

    changed_files = []
    for filename in files_to_check:
        file_path = docs_dir / filename
        if file_path.exists():
            # Simple check: file modified in last minute
            mtime = file_path.stat().st_mtime
            if (datetime.now().timestamp() - mtime) < 60:
                changed_files.append(filename)

    return changed_files


if __name__ == "__main__":
    success, output = run_scribe()

    if success:
        changed = check_changes()
        if changed:
            print(f"📝 Updated files: {', '.join(changed)}")
        else:
            print("ℹ️  No changes detected")

    sys.exit(0 if success else 1)
