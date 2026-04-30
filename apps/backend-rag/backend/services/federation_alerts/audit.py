"""JSONL audit trail for the Federation Alert Dispatcher.

One file per UTC day under ``~/logs/alert-dispatcher/`` (or the path in
``FEDERATION_ALERT_AUDIT_DIR``). Never blocks the daemon's main loop —
write errors degrade silently with a logger warning. The DB is the
authoritative state; this trail is for human post-mortem.

Schema per line (line-delimited JSON):

    {
        "ts": "2026-04-30T05:11:23.456Z",
        "event": "alert.received" | "proposal.advanced" | ...,
        "proposal_id": "uuid-or-null",
        "run_id": "rid-or-null",
        "mode": "observe|dry_deliberate|dry_action|production",
        "data": {... event-specific fields ...},
    }

Sensitive payload fields (full prompts, NPWP, NIB, etc.) are NEVER
logged here — callers pass already-redacted summaries.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class AuditLogger:
    """Append-only JSONL writer for the dispatcher.

    Best-effort: write errors are logged but never raised — losing one
    audit line is preferable to crashing the daemon mid-deliberation.
    """

    def __init__(self, log_dir: str) -> None:
        self._log_dir = Path(log_dir).expanduser()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(
                "audit log dir creation failed: %s (path=%s)",
                exc, self._log_dir,
            )

    def _file_for_today(self) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._log_dir / f"{date}.jsonl"

    def emit(
        self,
        event: str,
        *,
        proposal_id: str | None = None,
        run_id: str | None = None,
        mode: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Write one audit line. Never raises."""
        record = {
            "ts": _utc_now_iso(),
            "event": event,
            "proposal_id": proposal_id,
            "run_id": run_id,
            "mode": mode,
            "data": data or {},
        }
        path = self._file_for_today()
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
                f.write("\n")
        except OSError as exc:
            # Best-effort: try to recover by re-creating the dir, then give up.
            logger.warning("audit write failed: %s; retrying", exc)
            self._ensure_dir()
            try:
                with path.open("a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                    )
                    f.write("\n")
            except OSError as exc2:
                logger.warning(
                    "audit write retry failed: %s (record dropped)", exc2
                )

    def __repr__(self) -> str:
        return f"AuditLogger(log_dir={self._log_dir!s})"


__all__ = ["AuditLogger"]
