"""DNA loader with SHA-256 integrity verification.

The DNA is CELL's immutable core — rules that cannot be modified
by CELL itself. Every pulse cycle verifies DNA integrity.
"""
import hashlib
import json
from pathlib import Path
from typing import Any

from cell.core.config import settings


class DNAIntegrityError(Exception):
    """Raised when DNA file has been tampered with."""


class DNALoader:
    """Loads and verifies the immutable DNA file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or settings.dna_path

    def raw_bytes(self) -> bytes:
        """Read DNA file as raw bytes (for hashing)."""
        return self._path.read_bytes()

    def load(self) -> dict[str, Any]:
        """Load and parse DNA JSON."""
        return json.loads(self.raw_bytes())

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of DNA file."""
        return hashlib.sha256(self.raw_bytes()).hexdigest()

    def verify_integrity(self, expected_hash: str) -> bool:
        """Verify DNA file has not been tampered with."""
        return self.compute_hash() == expected_hash

    def verify_or_raise(self, expected_hash: str) -> dict[str, Any]:
        """Load DNA, verify integrity, raise if tampered."""
        if not self.verify_integrity(expected_hash):
            raise DNAIntegrityError(
                f"DNA tampered! Expected {expected_hash[:16]}..., "
                f"got {self.compute_hash()[:16]}..."
            )
        return self.load()
