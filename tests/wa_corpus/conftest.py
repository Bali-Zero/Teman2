"""Ensure the repo root is importable so `from scripts.wa_corpus...` resolves
regardless of pytest's invocation directory or import mode."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # .../<worktree-root>
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
