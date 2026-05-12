"""Subprocess wrapper for scripts/wr2_canva_pdf_render.py.

Writes slides_json to a temp path, invokes the renderer Python script
via subprocess with 120s timeout, returns the output PDF path or raises
PdfRenderError. The renderer itself is a separate process so a hung
ReportLab call doesn't take down the orchestrator.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]  # backend-rag/backend/services/canva_renderer_v2/ → repo root
RENDER_SCRIPT = REPO_ROOT / "scripts" / "wr2_canva_pdf_render.py"

DEFAULT_TIMEOUT_S = 120


class PdfRenderError(RuntimeError):
    """Raised when the renderer subprocess fails."""


def render_pdf(
    slides_json: dict[str, Any],
    *,
    draft_id: str,
    out_path: Path,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> Path:
    """Render slides_json → PDF at out_path. Raise PdfRenderError on failure."""
    slides_tmp = Path(tempfile.mkstemp(prefix=f"slides_{draft_id}_", suffix=".json")[1])
    slides_tmp.write_text(json.dumps(slides_json))

    cmd = [
        sys.executable,
        str(RENDER_SCRIPT),
        "--slides-json", str(slides_tmp),
        "--out", str(out_path),
    ]
    logger.info("Render draft %s → %s", draft_id, out_path)

    try:
        result = subprocess.run(  # noqa: S603 — known python interpreter
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise PdfRenderError(f"timeout {timeout_s}s for draft {draft_id}") from e
    finally:
        slides_tmp.unlink(missing_ok=True)

    if result.returncode != 0:
        raise PdfRenderError(
            f"subprocess exit≠0 for draft {draft_id}: {result.stderr[:500]}"
        )
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise PdfRenderError(
            f"renderer produced zero-size output for draft {draft_id}"
        )
    return out_path
