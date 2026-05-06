"""Pytest configuration: ensure repo root is on sys.path so that
``from scripts.pricelist_2026 import schema`` resolves correctly."""
import sys
from pathlib import Path

# Repo root is 3 levels up from this file (tests/ -> pricelist_2026/ -> scripts/ -> repo root)
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
