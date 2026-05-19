#!/usr/bin/env python3
"""WR2 Canva PDF orchestrator entrypoint — invoked by launchd plist every 5min.

Thin wrapper around backend.services.canva_renderer_v2.orchestrator.run().
Returns ExitCode integer for launchd SuccessfulExit evaluation.
"""
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

from backend.services.canva_renderer_v2.orchestrator import run  # noqa: E402


if __name__ == "__main__":
    exit_code = asyncio.run(run())
    sys.exit(int(exit_code))
