"""
Mata Garuda — Bridge Cursor.

Atomic file-based cursor per il polling Pull (Fly→Pro). Salva l'ultimo id
processato dalla outbox del backend in ~/.agent/decisions/bridge_cursor.json.

Atomic write: tmp file + rename per evitare cursor corrotti su crash.
Corrupt file → torna 0 (safe degradation, ricomincia dall'inizio).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("mata_garuda.bridge.cursor")


class BridgeCursor:
    """File-based cursor per la outbox del backend."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def read(self) -> int:
        """Return last_id consumed, or 0 if missing/corrupt."""
        if not self.path.exists():
            return 0
        try:
            data = json.loads(self.path.read_text())
            return int(data.get("last_id", 0))
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("Corrupt cursor at %s: %s — returning 0", self.path, e)
            return 0

    def write(self, last_id: int) -> None:
        """Atomically write last_id to disk (tmp + rename)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps({"last_id": int(last_id)}))
        os.replace(tmp_path, self.path)
