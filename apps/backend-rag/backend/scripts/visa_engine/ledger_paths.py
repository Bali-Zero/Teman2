"""ledger_paths.py — the ONE way a receipt's saved text is located inside a ledger.

Shared by ``fold_pack_generic`` and ``portal_judge`` so the judge can never read a page
the fold would refuse. A receipt's ``text_file`` is reduced to its basename and looked up
under ``<ledger_dir>/text`` (the receipts of a moved ledger carry the absolute path of a
dead worktree); a receipt that names none falls back to ``text/<8id>.txt`` (old layout).
A name that resolves outside ``text/`` (``..``, a symlink out) is refused.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class LedgerPathError(ValueError):
    """A receipt's text_file would leave the ledger text directory."""


def receipt_text_path(text_dir: Path, receipt: dict[str, Any]) -> Path:
    record = str(receipt.get("source_record_id", ""))[:8]
    named = receipt.get("text_file")
    name = Path(str(named)).name if named else f"{record}.txt"
    if name in {"", ".", ".."}:
        raise LedgerPathError(f"{record}: text_file {named!r} names no file")
    path = text_dir / name
    if path.resolve().parent != text_dir.resolve():
        raise LedgerPathError(
            f"{record}: text_file {named!r} is not inside the ledger text directory"
        )
    return path


def read_receipt_text(text_dir: Path, receipt: dict[str, Any]) -> str | None:
    """The saved text of ONE receipt, None when the file is absent."""
    path = receipt_text_path(text_dir, receipt)
    return path.read_text(encoding="utf-8") if path.is_file() else None
