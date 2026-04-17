"""
☁️ Google Cloud Shell Editor Adapter

Google Cloud Shell Editor è un editor cloud-based disponibile via Google Cloud Console.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class GoogleCloudShellAdapter:
    """
    Adapter for Google Cloud Shell Editor.

    Cloud Shell Editor è disponibile via:
    - Google Cloud Console (web-based)
    - gcloud CLI (se installato)
    """

    def __init__(self) -> None:
        self.gcloud_cmd = "gcloud"
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if Google Cloud SDK is installed"""
        try:
            result = subprocess.run(
                [self.gcloud_cmd, "--version"],
                capture_output=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                version = result.stdout.decode().strip().split("\n")[0]
                logger.info(f"✅ Google Cloud SDK trovato: {version}")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug(f"Google Cloud SDK not available: {e}")

        logger.info("ℹ️ Google Cloud Shell Editor è web-based. Accedi via Google Cloud Console.")
        return False

    async def generate(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """
        Generate using Google Cloud Shell Editor.

        Note: Cloud Shell Editor è principalmente web-based.
        """
        if not self.available:
            raise RuntimeError(
                "Google Cloud Shell Editor non disponibile. "
                "Accedi via: https://console.cloud.google.com",
            )

        logger.info("ℹ️ Google Cloud Shell Editor è web-based.")
        return "Google Cloud Shell Editor disponibile via Google Cloud Console."

    def is_available(self) -> bool:
        """Check if Google Cloud Shell Editor is available"""
        return self.available


# Singleton instance
_cloud_shell_adapter: GoogleCloudShellAdapter | None = None


def get_cloud_shell_adapter() -> GoogleCloudShellAdapter:
    """Get singleton Google Cloud Shell Editor adapter instance"""
    global _cloud_shell_adapter
    if _cloud_shell_adapter is None:
        _cloud_shell_adapter = GoogleCloudShellAdapter()
    return _cloud_shell_adapter
