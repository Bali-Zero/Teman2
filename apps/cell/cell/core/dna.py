# cell/core/dna.py
"""DNA loader — thin bridge to cell-core.

Re-exports DNALoader and DNAIntegrityError from cell_core.safety,
preserving CELL-specific behavior: default path from settings, load() returns dict.
"""
import json
from pathlib import Path
from typing import Any

from cell_core.safety import DNAIntegrityError, DNALoader as _CoreLoader

from cell.core.config import settings


class DNALoader(_CoreLoader):
    """CELL-compatible DNALoader with default path and dict-returning load()."""

    def __init__(self, path: Path | None = None) -> None:
        resolved = str(path or settings.dna_path)
        super().__init__(path=resolved)

    def load(self) -> dict[str, Any]:
        """Load and parse DNA JSON as a raw dict (CELL-specific)."""
        return json.loads(self.raw_bytes())


__all__ = ["DNALoader", "DNAIntegrityError"]
