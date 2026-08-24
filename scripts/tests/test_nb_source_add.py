"""Guilt + innocence tests for scripts/nb_source_add.py.

The CLI boundary is fully stubbed: every test injects a fake ``run_nlm``
callable so no live ``nlm`` subprocess is invoked. OCR subprocesses are
monkey-patched at the function boundary.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import nb_source_add  # noqa: E402


class FakeNlm:
    """Stub nlm CLI that returns queued responses and records every call."""

    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if not self.responses:
            raise RuntimeError(f"unexpected nlm call: {args}")
        resp = self.responses.pop(0)
        return subprocess.CompletedProcess(
            args=args,
            returncode=resp.get("returncode", 0),
            stdout=resp.get("stdout", ""),
            stderr=resp.get("stderr", ""),
        )


def _add_response(source_id: str = "s1") -> dict:
    return {"stdout": f'{{"source_id": "{source_id}", "source_type": "text", "title": "t"}}'}


import json as _json


def _content_json(
    source_type: str = "text",
    char_count: int = 1000,
    content: str = "The quick brown fox",
) -> dict:
    return {
        "stdout": _json.dumps(
            {
                "source_type": source_type,
                "char_count": char_count,
                "content": content,
                "title": "t",
                "url": None,
            }
        )
    }


def _delete_response() -> dict:
    return {"stdout": '{"status": "success", "deleted_source_ids": ["s1"], "deleted_count": 1}'}


# ------------------------------------------------------------------- EMPTINESS


def test_healthy_text_source_passes_both_gates():
    fake = FakeNlm(
        [
            _add_response("s1"),
            _content_json(char_count=1000, content="Keputusan Menteri tentang Visa"),
        ]
    )
    rc = nb_source_add.run_add_verify(
        "nb1",
        text="x",
        title="Keputusan Menteri",
        required_phrases=["Keputusan Menteri", "tentang Visa"],
        run_nlm=fake,
    )
    assert rc == nb_source_add.EXIT_OK
    assert len(fake.calls) == 2
    assert fake.calls[0][1] == "add"
    assert fake.calls[1][1] == "content"


def test_shell_source_fails_emptiness_gate_and_is_deleted():
    fake = FakeNlm(
        [
            _add_response("s1"),
            _content_json(char_count=10, content="Keputusan Menteri"),
            _delete_response(),
        ]
    )
    rc = nb_source_add.run_add_verify(
        "nb1",
        text="x",
        title="Keputusan Menteri",
        required_phrases=["Keputusan Menteri"],
        run_nlm=fake,
    )
    assert rc == nb_source_add.EXIT_EMPTINESS
    assert len(fake.calls) == 3
    assert fake.calls[2][1] == "delete"


# ------------------------------------------------------------------- IDENTITY


def test_wrong_document_fails_identity_gate_and_is_deleted():
    fake = FakeNlm(
        [
            _add_response("s1"),
            _content_json(char_count=5000, content="This is a Sumenep regional by-law"),
            _delete_response(),
        ]
    )
    rc = nb_source_add.run_add_verify(
        "nb1",
        url="https://example.com/UU_6_2011_Keimigrasian.pdf",
        title="UU 6/2011 Keimigrasian",
        required_phrases=["UU 6/2011", "Keimigrasian"],
        run_nlm=fake,
    )
    assert rc == nb_source_add.EXIT_IDENTITY
    assert len(fake.calls) == 3
    assert fake.calls[2][1] == "delete"


def test_identity_gate_is_case_and_whitespace_tolerant():
    fake = FakeNlm(
        [
            _add_response("s1"),
            _content_json(char_count=2000, content="KEPMEN M.IP-19.GR.01.01/2025\nSistem\tKerja"),
        ]
    )
    rc = nb_source_add.run_add_verify(
        "nb1",
        text="x",
        title="Kepmen",
        required_phrases=["kepmen m.ip-19.gr.01.01/2025", "sistem kerja"],
        run_nlm=fake,
    )
    assert rc == nb_source_add.EXIT_OK


# ------------------------------------------------------------------- PHANTOM


def test_phantom_source_is_cleaned_up(monkeypatch):
    monkeypatch.setattr(nb_source_add.time, "sleep", lambda _s: None)
    fake = FakeNlm(
        [
            _add_response("s1"),
            {
                "returncode": 1,
                "stderr": "Source s1 NOT_FOUND",
            },
            _delete_response(),
        ]
    )
    rc = nb_source_add.run_add_verify(
        "nb1",
        url="https://example.com/bad",
        title="bad",
        required_phrases=["x"],
        poll_timeout=0.0,
        run_nlm=fake,
    )
    assert rc == nb_source_add.EXIT_PHANTOM
    assert len(fake.calls) == 3
    assert fake.calls[2][1] == "delete"


# ----------------------------------------------------------------- OCR FALLBACK


def test_pdf_shell_triggers_ocr_fallback_and_keeps_both_sources(monkeypatch):
    monkeypatch.setattr(nb_source_add, "pdf_page_count", lambda _path: 3)
    monkeypatch.setattr(
        nb_source_add,
        "ocr_pdf_to_text",
        lambda _path, lang="eng": "MEMUTUSKAN\nMenimbang\nMengingat\nOperative provisions here",
    )

    fake = FakeNlm(
        [
            _add_response("pdf-s1"),
            _content_json(source_type="pdf", char_count=721, content="https://lh3.googleusercontent.com/notebooklm/x"),
            _add_response("ocr-s2"),
            _content_json(source_type="text", char_count=5000, content="MEMUTUSKAN Menimbang Mengingat"),
        ]
    )
    rc = nb_source_add.run_add_verify(
        "nb1",
        file_path=Path("/tmp/Kepmen_MIP_19_2025.pdf"),
        title="Kepmen M.IP-19.GR.01.01/2025",
        required_phrases=["MEMUTUSKAN", "Mengingat"],
        ocr_fallback=True,
        run_nlm=fake,
    )
    assert rc == nb_source_add.EXIT_OK
    # No delete should have been issued; we have add, content, add, content.
    assert len(fake.calls) == 4
    assert fake.calls[0][1] == "add"
    assert fake.calls[2][1] == "add"


def test_ocr_fallback_identity_failure_deletes_both_sources(monkeypatch):
    monkeypatch.setattr(nb_source_add, "pdf_page_count", lambda _path: 3)
    monkeypatch.setattr(
        nb_source_add,
        "ocr_pdf_to_text",
        lambda _path, lang="eng": "Some unrelated text without the required phrase",
    )

    fake = FakeNlm(
        [
            _add_response("pdf-s1"),
            _content_json(source_type="pdf", char_count=721, content="img-url"),
            _add_response("ocr-s2"),
            _content_json(source_type="text", char_count=2000, content="Some unrelated text"),
            {"stdout": '{"status": "success", "deleted_source_ids": ["pdf-s1", "ocr-s2"], "deleted_count": 2}'},
        ]
    )
    rc = nb_source_add.run_add_verify(
        "nb1",
        file_path=Path("/tmp/doc.pdf"),
        title="doc",
        required_phrases=["MEMUTUSKAN"],
        ocr_fallback=True,
        run_nlm=fake,
    )
    assert rc == nb_source_add.EXIT_IDENTITY
    assert len(fake.calls) == 5
    assert fake.calls[4][1] == "delete"


def test_ocr_runtime_error_deletes_original_pdf(monkeypatch):
    monkeypatch.setattr(nb_source_add, "pdf_page_count", lambda _path: 3)
    monkeypatch.setattr(
        nb_source_add,
        "ocr_pdf_to_text",
        lambda _path, lang="eng": (_ for _ in ()).throw(RuntimeError("tesseract missing")),
    )

    fake = FakeNlm(
        [
            _add_response("pdf-s1"),
            _content_json(source_type="pdf", char_count=721, content="img-url"),
            _delete_response(),
        ]
    )
    rc = nb_source_add.run_add_verify(
        "nb1",
        file_path=Path("/tmp/doc.pdf"),
        title="doc",
        required_phrases=["x"],
        ocr_fallback=True,
        run_nlm=fake,
    )
    assert rc == nb_source_add.EXIT_NLM_ERROR
    assert len(fake.calls) == 3
    assert fake.calls[2][1] == "delete"
