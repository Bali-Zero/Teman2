"""
NB Mitochondrial Value Monitor.

Daily cron that measures which NotebookLM notebooks produce value consumed
downstream by Nuzantara. Five metric collectors → tier classifier → SQLite
snapshot → optional Telegram alert + weekly markdown report.

Spec: docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md
Plan: docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md
"""
from __future__ import annotations

import os
from pathlib import Path

__version__ = "0.1.0"

DATA_DIR = Path(
    os.environ.get("NB_MONITOR_DATA_DIR", str(Path.home() / ".agent" / "nb-mitochondrial"))
)
REGISTRY_DIR = Path(
    os.environ.get("NB_MONITOR_REGISTRY_DIR", str(Path.home() / ".agent" / "nb-monitor"))
)
BOOTSTRAP_FILE = REGISTRY_DIR / "active_notebooks_bootstrap_2026-05-07.json"
METRICS_DB = DATA_DIR / "metrics.db"
LOG_FILE = DATA_DIR / "logs" / "nb-monitor.log"
