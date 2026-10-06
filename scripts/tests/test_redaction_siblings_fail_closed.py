"""Guilt + innocence for two sibling redactors that let raw text out when they
do not match: cost_ledger_export._redact_dsn (a password containing "@" leaked
its tail into the logged DSN) and memory_index_build (titles reached
MEMORY_INDEX.md without passing through redact()). All values are invented.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "memory"))

import cost_ledger_export  # noqa: E402
import memory_index_build  # noqa: E402


@pytest.mark.parametrize("dsn, secret_fragment", [
    ("postgresql://ro_user:" + "p@zz-tail-FAKE@db.invalid:5432/ledger", "zz-tail-FAKE"),
    ("postgresql://ro_user:" + "a@b@zz-tail-FAKE@db.invalid:5432/ledger", "zz-tail-FAKE"),
    ("postgresql://ro_user:" + "pw@q?FAKE#frag@db.invalid:5432/ledger", "FAKE"),
    ("postgresql://ro_user:" + "pw/x/FAKE-slash@db.invalid:5432/ledger", "FAKE-slash"),
])
def test_dsn_password_never_logged(dsn, secret_fragment):
    out = cost_ledger_export._redact_dsn(dsn)
    assert secret_fragment not in out, out


@pytest.mark.parametrize("dsn, expected", [
    ("postgresql://ro_user:" + "FAKEpw@db.invalid:5432/ledger",
     "postgresql://ro_user:***@db.invalid:5432/ledger"),
    ("postgresql://ro_user@db.invalid/ledger", "postgresql://ro_user:***@db.invalid/ledger"),
    ("not a dsn", "<dsn>"),
])
def test_dsn_ordinary_shapes_unchanged(dsn, expected):
    assert cost_ledger_export._redact_dsn(dsn) == expected


def _write(memdir: Path, name: str, body: str) -> None:
    (memdir / name).write_text(body, encoding="utf-8")


def test_memory_index_title_is_redacted(tmp_path):
    memdir = tmp_path / "memdir"
    memdir.mkdir()
    _write(memdir, "discovery_invented_one_2026_09_01.md",
           "---\nname: call-invented.person@example.invalid\ndescription: clean\n"
           "metadata:\n  type: discovery\n---\n\nbody\n")
    _write(memdir, "fact_invented_two_2026_09_02.md",
           "# Called +62 812 0000 1111 about the invented file\n\nbody\n")
    text, meta = memory_index_build.build_index(str(memdir))
    assert "invented.person@example.invalid" not in text, text
    assert "812 0000 1111" not in text, text
    assert meta["pii_offender_count"] == 2, meta


def test_memory_index_type_heading_and_offender_list_are_redacted(tmp_path):
    memdir = tmp_path / "memdir"
    memdir.mkdir()
    _write(memdir, "custom_note.md",
           "---\nname: clean\ndescription: clean\n"
           "metadata:\n  type: invented.person@example.invalid\n---\n\nbody\n")
    _write(memdir, "note_6281200001111_invented.md", "# clean heading\n\nbody\n")
    text, meta = memory_index_build.build_index(str(memdir))
    assert "invented.person@example.invalid" not in text, text
    assert "6281200001111" not in text, text
    assert not any("6281200001111" in f for f in meta["pii_offender_files"]), meta
    assert meta["pii_offender_count"] == 2, meta


def test_redact_secrets_internal_error_never_returns_input(monkeypatch):
    sys.path.insert(0, str(SCRIPTS.parent / "infra" / "claude-hooks"))
    import redact_secrets

    class Boom:
        def search(self, _text):
            raise RuntimeError("invented engine failure")

    monkeypatch.setattr(redact_secrets, "_COMPILED", (Boom(),))
    out = redact_secrets.redact("echo zz-invented-raw-marker-4242")
    assert "zz-invented-raw-marker-4242" not in out, out
    assert out == "<REDACTED>"


def test_memory_index_clean_titles_unchanged(tmp_path):
    memdir = tmp_path / "memdir"
    memdir.mkdir()
    _write(memdir, "discovery_clean_title_2026_09_03.md",
           "---\nname: merge-queue-arming-rule\ndescription: arm with --auto only\n"
           "metadata:\n  type: discovery\n---\n\nbody\n")
    text, meta = memory_index_build.build_index(str(memdir))
    assert "- merge-queue-arming-rule: arm with --auto only (discovery_clean_title_2026_09_03.md)" in text
    assert meta["pii_offender_count"] == 0, meta
