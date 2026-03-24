"""
🌊 Windsurf Adapter - AI Coding Platform

Windsurf è un "Agentic IDE powered by AI Flow paradigm" installato come app macOS.
CLI disponibile in: /Applications/Windsurf.app/Contents/Resources/app/bin/windsurf
"""
from __future__ import annotations


import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class WindsurfAdapter:
    """
    Adapter for Windsurf AI coding platform.

    Windsurf è un IDE completo con AI integrata.
    CLI disponibile nel bundle dell'app macOS.
    """

    def __init__(self):
        # Paths possibili per Windsurf CLI
        self.windsurf_paths = [
            "/Applications/Windsurf.app/Contents/Resources/app/bin/windsurf",
            "windsurf",  # Se è nel PATH
        ]
        self.windsurf_cmd = self._find_windsurf()
        self.available = self._check_availability()

    def _find_windsurf(self) -> str:
        """Find Windsurf CLI executable"""
        for path in self.windsurf_paths:
            if os.path.exists(path) or path == "windsurf":
                try:
                    result = subprocess.run(
                        [path, "--version"],
                        capture_output=True,
                        timeout=5.0,
                    )
                    if result.returncode == 0:
                        logger.info(f"✅ Windsurf trovato: {path}")
                        return path
                except Exception:
                    continue
        return self.windsurf_paths[0]  # Default al primo path

    def _check_availability(self) -> bool:
        """Check if Windsurf is installed"""
        try:
            result = subprocess.run(
                [self.windsurf_cmd, "--version"],
                capture_output=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                version = result.stdout.decode().strip()
                logger.info(f"✅ Windsurf disponibile: {version}")
                return True
            return False
        except Exception as e:
            logger.debug(f"Windsurf non disponibile: {e}")
            return False

    def open_file(self, file_path: str) -> bool:
        """Open file in Windsurf IDE"""
        try:
            # Windsurf può aprire file via CLI
            result = subprocess.run(
                [self.windsurf_cmd, file_path],
                capture_output=True,
                timeout=10.0,
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"⚠️ Could not open file in Windsurf: {e}")
            return False

    def open_folder(self, folder_path: str) -> bool:
        """Open folder in Windsurf IDE"""
        try:
            result = subprocess.run(
                [self.windsurf_cmd, folder_path],
                capture_output=True,
                timeout=10.0,
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"⚠️ Could not open folder in Windsurf: {e}")
            return False

    async def generate(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """
        Generate code using Windsurf.

        Note: Windsurf è principalmente IDE-based.
        Per uso programmatico, apri file/folder nell'IDE.
        """
        if not self.available:
            raise RuntimeError("Windsurf not available. Install from: https://windsurf.com/editor")

        # Windsurf è principalmente IDE-based
        # Per ora, apri file se fornito nel context
        if context and "file" in context:
            self.open_file(context["file"])
            return "File opened in Windsurf IDE. Use Windsurf IDE for AI-powered editing."

        logger.warning("⚠️ Windsurf è IDE-based. Usa Windsurf IDE direttamente per editing AI.")
        return "Windsurf è disponibile. Usa Windsurf IDE per editing AI-powered."

    def is_available(self) -> bool:
        """Check if Windsurf is available"""
        return self.available


# Singleton instance
_windsurf_adapter: WindsurfAdapter | None = None


def get_windsurf_adapter() -> WindsurfAdapter:
    """Get singleton Windsurf adapter instance"""
    global _windsurf_adapter
    if _windsurf_adapter is None:
        _windsurf_adapter = WindsurfAdapter()
    return _windsurf_adapter
