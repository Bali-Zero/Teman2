"""Conftest for scripts tests.

Inserts apps/backend-rag root into sys.path so that `from scripts.X import Y`
resolves to the repo's scripts/ dir, not the test's local namespace.
Pytest's auto-rootdir behavior shadows scripts/ when tests live in a folder
named 'scripts/' too — this conftest fixes that.
"""
import sys
from pathlib import Path

# apps/backend-rag/ is parents[3] from this file (conftest.py → scripts → tests → backend → backend-rag)
_BACKEND_RAG_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_RAG_ROOT))
