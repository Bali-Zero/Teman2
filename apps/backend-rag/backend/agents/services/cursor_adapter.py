"""
🎯 Cursor Adapter - IDE Integration

Cursor è un IDE AI-powered che può essere integrato nel sistema.
Supporta:
- .cursorrules file per comportamento AI
- CLI per operazioni base
- Context-aware editing
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class CursorAdapter:
    """
    Adapter for Cursor IDE integration.

    Cursor è principalmente IDE-based, ma può essere usato via:
    - CLI per aprire file/folder
    - .cursorrules per configurare comportamento AI
    - Cursor API (se disponibile in futuro)
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self.cursor_cmd = "cursor"
        self.project_root = project_root or Path.cwd()
        self.cursor_rules_file = self.project_root / ".cursorrules"

    def open_file(self, file_path: str) -> bool:
        """Open file in Cursor IDE"""
        try:
            result = subprocess.run(
                [self.cursor_cmd, file_path],
                capture_output=True,
                timeout=10.0,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.warning(f"⚠️ Could not open file in Cursor: {e}")
            return False

    def open_folder(self, folder_path: str) -> bool:
        """Open folder in Cursor IDE"""
        try:
            result = subprocess.run(
                [self.cursor_cmd, folder_path],
                capture_output=True,
                timeout=10.0,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.warning(f"⚠️ Could not open folder in Cursor: {e}")
            return False

    def diff_files(self, file1: str, file2: str) -> str | None:
        """Compare two files using Cursor"""
        try:
            result = subprocess.run(
                [self.cursor_cmd, "--diff", file1, file2],
                capture_output=True,
                text=True,
                timeout=30.0,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.warning(f"⚠️ Cursor diff failed: {e}")
            return None

    def update_cursor_rules(self, rules: str) -> bool:
        """Update .cursorrules file for Cursor IDE"""
        try:
            with open(self.cursor_rules_file, "w") as f:
                f.write(rules)
            logger.info(f"✅ Updated .cursorrules at {self.cursor_rules_file}")
            return True
        except OSError as e:
            logger.error(f"❌ Failed to update .cursorrules: {e}")
            return False

    def read_cursor_rules(self) -> str | None:
        """Read current .cursorrules"""
        try:
            if self.cursor_rules_file.exists():
                with open(self.cursor_rules_file) as f:
                    return f.read()
            return None
        except OSError as e:
            logger.warning(f"⚠️ Could not read .cursorrules: {e}")
            return None

    def is_available(self) -> bool:
        """Check if Cursor CLI is available"""
        try:
            result = subprocess.run(
                [self.cursor_cmd, "--version"],
                capture_output=True,
                timeout=5.0,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            return False


# Singleton instance
_cursor_adapter: CursorAdapter | None = None


def get_cursor_adapter(project_root: Path | None = None) -> CursorAdapter:
    """Get singleton Cursor adapter instance"""
    global _cursor_adapter
    if _cursor_adapter is None:
        _cursor_adapter = CursorAdapter(project_root)
    return _cursor_adapter
