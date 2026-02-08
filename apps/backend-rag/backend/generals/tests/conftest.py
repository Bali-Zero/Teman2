"""
Conftest for The Generals test suite.

Ensures PYTHONPATH includes apps/backend-rag so that
`from backend.generals.*` imports resolve correctly.
"""

import sys
from pathlib import Path

# Add apps/backend-rag to sys.path so `backend.*` imports work
_backend_root = Path(__file__).resolve().parents[3]  # apps/backend-rag/
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))
