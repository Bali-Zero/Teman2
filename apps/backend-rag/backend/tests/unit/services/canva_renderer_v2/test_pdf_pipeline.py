"""PDF pipeline: invoke wr2_canva_pdf_render.py via subprocess, return path or None."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from backend.services.canva_renderer_v2._pdf_pipeline import render_pdf, PdfRenderError


def test_render_pdf_success(tmp_path):
    slides = {"carousel_id": "test", "slide_count": 1, "slides": [
        {"index": 1, "layout_family": "cover-photo", "heading": "x", "body": "y"}
    ]}
    pdf_dest = tmp_path / "wr2_test.pdf"

    def fake_run(args, **kwargs):
        # Write a valid-looking PDF (first 4 bytes %PDF)
        pdf_dest.write_bytes(b"%PDF-1.4\n... fake pdf body\n%%EOF")
        return MagicMock(returncode=0, stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        result = render_pdf(slides, draft_id="test", out_path=pdf_dest)
        assert result == pdf_dest
        assert pdf_dest.exists() and pdf_dest.stat().st_size > 4


def test_render_pdf_subprocess_exit_nonzero(tmp_path):
    slides = {"slides": []}
    pdf_dest = tmp_path / "wr2_test.pdf"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="ReportLab error")
        with pytest.raises(PdfRenderError, match="exit≠0"):
            render_pdf(slides, draft_id="test", out_path=pdf_dest)


def test_render_pdf_zero_size_output(tmp_path):
    slides = {"slides": []}
    pdf_dest = tmp_path / "wr2_test.pdf"
    pdf_dest.write_bytes(b"")  # zero size

    def fake_run(args, **kwargs):
        return MagicMock(returncode=0, stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        with pytest.raises(PdfRenderError, match="zero.size"):
            render_pdf(slides, draft_id="test", out_path=pdf_dest)


def test_render_pdf_timeout(tmp_path):
    slides = {"slides": []}
    pdf_dest = tmp_path / "wr2_test.pdf"
    with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("python", 120)):
        with pytest.raises(PdfRenderError, match="timeout"):
            render_pdf(slides, draft_id="test", out_path=pdf_dest)
