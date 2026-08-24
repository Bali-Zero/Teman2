"""Guilt + innocence tests for scripts/nb_source_audit.py.

Every test injects a fake ``run_nlm`` callable; no live NotebookLM API call is
made.
"""
from __future__ import annotations

import json as _json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import nb_source_audit  # noqa: E402


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


def _list_response(sources: list[dict]) -> dict:
    return {"stdout": _json.dumps(sources)}


def _content_response(
    source_type: str = "generated_text",
    char_count: int = 1000,
    content: str = "body",
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


def _not_found_response() -> dict:
    return {"returncode": 1, "stderr": "Source s2 NOT_FOUND"}


# ----------------------------------------------------------------- GUILT (unit)


def test_pdf_shell_below_per_page_floor_is_flagged():
    # 3-page scanned PDF with image URLs but only 721 characters total.
    fake = FakeNlm(
        [
            _list_response(
                [
                    {
                        "id": "pdf-s1",
                        "title": "Kepmen M.IP-19.GR.01.01/2025",
                        "type": "pdf",
                    }
                ]
            ),
            _content_response(
                source_type="pdf",
                char_count=721,
                content="https://lh3.googleusercontent.com/notebooklm/1\n"
                "uuid-1\n"
                "https://lh3.googleusercontent.com/notebooklm/2\n"
                "uuid-2\n"
                "https://lh3.googleusercontent.com/notebooklm/3",
            ),
        ]
    )
    report = nb_source_audit.audit_notebook(
        "nb1", pdf_floor_per_page=500, other_floor=50, sleep_seconds=0, run_nlm=fake
    )
    assert report["shell_count"] == 1
    shell = report["shells"][0]
    assert shell["char_count"] == 721
    assert shell["floor"] == 1500
    assert shell["page_count"] == 3


def test_unreadable_source_is_flagged_but_not_counted_as_shell():
    fake = FakeNlm(
        [
            _list_response(
                [
                    {"id": "s1", "title": "Good", "type": "generated_text"},
                    {"id": "s2", "title": "Phantom", "type": "generated_text"},
                ]
            ),
            _content_response(char_count=1000, content="body"),
            _not_found_response(),
        ]
    )
    report = nb_source_audit.audit_notebook(
        "nb1", pdf_floor_per_page=500, other_floor=50, sleep_seconds=0, run_nlm=fake
    )
    assert report["shell_count"] == 0
    assert report["unreadable_count"] == 1
    assert report["unreadable"][0]["id"] == "s2"


def test_duplicate_titles_are_reported():
    fake = FakeNlm(
        [
            _list_response(
                [
                    {"id": "s1", "title": "Same Title", "type": "generated_text"},
                    {"id": "s2", "title": "Same Title", "type": "generated_text"},
                    {"id": "s3", "title": "Different", "type": "generated_text"},
                ]
            ),
            _content_response(char_count=1000),
            _content_response(char_count=1000),
            _content_response(char_count=1000),
        ]
    )
    report = nb_source_audit.audit_notebook(
        "nb1", pdf_floor_per_page=500, other_floor=50, sleep_seconds=0, run_nlm=fake
    )
    assert report["duplicate_group_count"] == 1
    assert report["duplicates"][0]["count"] == 2
    assert set(report["duplicates"][0]["ids"]) == {"s1", "s2"}


# --------------------------------------------------------------- INNOCENCE (unit)


def test_healthy_sources_produce_clean_report():
    fake = FakeNlm(
        [
            _list_response(
                [
                    {"id": "s1", "title": "A", "type": "generated_text"},
                    {"id": "s2", "title": "B", "type": "url"},
                ]
            ),
            _content_response(char_count=500, content="body one"),
            _content_response(char_count=200, content="body two"),
        ]
    )
    report = nb_source_audit.audit_notebook(
        "nb1", pdf_floor_per_page=500, other_floor=50, sleep_seconds=0, run_nlm=fake
    )
    assert report["source_count"] == 2
    assert report["shell_count"] == 0
    assert report["unreadable_count"] == 0
    assert report["duplicate_group_count"] == 0
    assert report["healthy_count"] == 2


def test_non_pdf_floor_is_absolute_and_respected():
    # A URL source with 30 characters is below the default 50-char floor.
    fake = FakeNlm(
        [
            _list_response([{"id": "s1", "title": "Short", "type": "url"}]),
            _content_response(source_type="url", char_count=30, content="short"),
        ]
    )
    report = nb_source_audit.audit_notebook(
        "nb1", pdf_floor_per_page=500, other_floor=50, sleep_seconds=0, run_nlm=fake
    )
    assert report["shell_count"] == 1
    assert report["shells"][0]["floor"] == 50


# ----------------------------------------------------------------- CLI SURFACE


def test_main_exits_nonzero_when_shells_found(capsys, monkeypatch):
    fake = FakeNlm(
        [
            _list_response([{"id": "s1", "title": "Short", "type": "url"}]),
            _content_response(source_type="url", char_count=30, content="short"),
        ]
    )
    monkeypatch.setattr(nb_source_audit, "default_run_nlm", fake)
    rc = nb_source_audit.main(["--notebook", "nb1", "--sleep", "0"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "shells=1" in captured.out or "SHELL" in captured.out


def test_main_exits_zero_when_only_duplicates_found(capsys, monkeypatch):
    fake = FakeNlm(
        [
            _list_response(
                [
                    {"id": "s1", "title": "Same", "type": "generated_text"},
                    {"id": "s2", "title": "Same", "type": "generated_text"},
                ]
            ),
            _content_response(char_count=1000),
            _content_response(char_count=1000),
        ]
    )
    monkeypatch.setattr(nb_source_audit, "default_run_nlm", fake)
    rc = nb_source_audit.main(["--notebook", "nb1", "--sleep", "0"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "DUPLICATE" in captured.out
