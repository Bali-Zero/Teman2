"""Obligation engine tests (T5).

claude --print subprocess is replaced with an in-test stub via the
`claude_runner` parameter. SQLite is redirected to tmp_path. NER is
optional and not exercised here (foundation has its own tests).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from mata_garuda.domains.setup_team.obligation_engine import (
    SCHEMA_DDL,
    VALID_OBLIGATION_TYPES,
    _normalise_obligation_type,
    _parse_claude_json,
    _strip_anthropic_env,
    extract_obligations,
)
from mata_garuda.domains.setup_team.types import Regulation


def _make_regulation(**overrides) -> Regulation:
    base = dict(
        source_id="pasal-id:test-1",
        domain="regulation",
        tier=1,
        title="UU 27/2022 PDP",
        url="https://pasal.id/laws/test-1",
        published_at=date(2022, 9, 27),
        body_excerpt=(
            "Pasal 4 ayat (2): Pengendali wajib lapor pelanggaran dalam 3x24 jam. "
            "KBLI 63122 termasuk dalam pengaturan."
        ),
        tags=("layer:pasal-id",),
    )
    base.update(overrides)
    return Regulation(**base)


# ---------------- helpers ---------------- #


def test_strip_anthropic_env_removes_known_keys():
    env = {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "ANTHROPIC_AUTH_TOKEN": "...",
        "PATH": "/usr/bin",
        "OTHER": "keep",
    }
    out = _strip_anthropic_env(env)
    assert "ANTHROPIC_API_KEY" not in out
    assert "ANTHROPIC_AUTH_TOKEN" not in out
    assert out["PATH"] == "/usr/bin"
    assert out["OTHER"] == "keep"


def test_normalise_obligation_type_defaults_unknown_to_reporting():
    assert _normalise_obligation_type("filing") == "filing"
    assert _normalise_obligation_type("REPORTING") == "reporting"
    assert _normalise_obligation_type("misc") == "reporting"
    assert _normalise_obligation_type("") == "reporting"
    assert _normalise_obligation_type(None) == "reporting"  # type: ignore[arg-type]


def test_parse_claude_json_handles_markdown_fences():
    raw = (
        "```json\n"
        '[{"text":"x","obligation_type":"filing","article_ref":"Pasal 1",'
        '"deadline_pattern":"30 hari","sanction_if_missed":"denda",'
        '"effective_date":"2024-01-01","kbli_codes_affected":["63122"]}]\n'
        "```"
    )
    out = _parse_claude_json(raw)
    assert len(out) == 1
    assert out[0]["text"] == "x"


def test_parse_claude_json_handles_prose_prefix():
    raw = (
        "Sure, here is the JSON:\n"
        '[{"text":"y","obligation_type":"reporting","article_ref":"Pasal 2",'
        '"deadline_pattern":"","sanction_if_missed":"","effective_date":"",'
        '"kbli_codes_affected":[]}]'
    )
    out = _parse_claude_json(raw)
    assert len(out) == 1


def test_parse_claude_json_returns_empty_on_garbage():
    assert _parse_claude_json("") == []
    assert _parse_claude_json("not json at all") == []
    assert _parse_claude_json('{"single":"object"}') == []  # not a list


# ---------------- extract_obligations ---------------- #


def test_extract_obligations_with_mock_runner_persists_to_sqlite(tmp_path):
    db = tmp_path / "setup_team.sqlite"
    canned = json.dumps(
        [
            {
                "text": "Pengendali wajib lapor pelanggaran data dalam 3x24 jam",
                "obligation_type": "reporting",
                "article_ref": "Pasal 46",
                "deadline_pattern": "3x24 jam",
                "sanction_if_missed": "denda administratif",
                "effective_date": "2024-10-17",
                "kbli_codes_affected": ["63122"],
            }
        ]
    )

    def fake_runner(prompt: str) -> str:
        # Verify the prompt got the regulation context.
        assert "UU 27/2022 PDP" in prompt
        assert "pasal-id:test-1" in prompt
        return canned

    reg = _make_regulation()
    result = extract_obligations(reg, claude_runner=fake_runner, db_path=db)

    assert len(result) == 1
    obl = result[0]
    assert obl.id is not None
    assert obl.text.startswith("Pengendali wajib lapor")
    assert obl.obligation_type == "reporting"
    assert obl.article_ref == "Pasal 46"
    assert obl.deadline_pattern == "3x24 jam"
    assert obl.sanction_if_missed == "denda administratif"
    assert obl.effective_date == date(2024, 10, 17)
    assert obl.kbli_codes_affected == ("63122",)
    assert obl.human_validated is False

    # Verify persisted row matches.
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM obligations").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["regulation_source_id"] == "pasal-id:test-1"
    assert json.loads(rows[0]["kbli_codes_affected"]) == ["63122"]
    assert rows[0]["human_validated"] == 0


def test_extract_obligations_idempotent_on_rerun(tmp_path):
    db = tmp_path / "setup_team.sqlite"
    canned = json.dumps(
        [
            {
                "text": "Wajib SPT tahunan",
                "obligation_type": "filing",
                "article_ref": "Pasal 4",
                "deadline_pattern": "31 Maret",
                "sanction_if_missed": "denda 100rb",
                "effective_date": "2026-01-01",
                "kbli_codes_affected": ["62019"],
            }
        ]
    )
    reg = _make_regulation()
    extract_obligations(reg, claude_runner=lambda _: canned, db_path=db)
    extract_obligations(reg, claude_runner=lambda _: canned, db_path=db)
    extract_obligations(reg, claude_runner=lambda _: canned, db_path=db)

    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT COUNT(*) AS n FROM obligations").fetchone()
    conn.close()
    assert rows[0] == 1, "UNIQUE constraint should keep rerun idempotent"


def test_extract_obligations_returns_empty_on_empty_runner(tmp_path):
    db = tmp_path / "setup_team.sqlite"
    reg = _make_regulation()
    result = extract_obligations(reg, claude_runner=lambda _: "", db_path=db)
    assert result == []
    # DB schema still created though no row inserted — but only if we opened it.
    # We opened only when items existed, so file may not exist.
    # Either case is fine; test that no row is present if file exists.
    if db.exists():
        conn = sqlite3.connect(str(db))
        try:
            cnt = conn.execute("SELECT COUNT(*) FROM obligations").fetchone()[0]
            assert cnt == 0
        except sqlite3.OperationalError:
            pass  # table not created — also acceptable
        conn.close()


def test_extract_obligations_normalises_unknown_obligation_type(tmp_path):
    db = tmp_path / "setup_team.sqlite"
    canned = json.dumps(
        [
            {
                "text": "Wajib bayar sanksi",
                "obligation_type": "WEIRD_TYPE_NOT_IN_ENUM",
                "article_ref": "Pasal 1",
                "deadline_pattern": "30 hari",
                "sanction_if_missed": "denda",
                "effective_date": "",
                "kbli_codes_affected": [],
            }
        ]
    )
    reg = _make_regulation()
    out = extract_obligations(reg, claude_runner=lambda _: canned, db_path=db)
    assert len(out) == 1
    assert out[0].obligation_type == "reporting"  # fallback


def test_extract_obligations_handles_csv_kbli_string(tmp_path):
    """LLM sometimes returns CSV instead of array — be defensive."""
    db = tmp_path / "setup_team.sqlite"
    canned = json.dumps(
        [
            {
                "text": "x",
                "obligation_type": "filing",
                "article_ref": "Pasal 1",
                "deadline_pattern": "",
                "sanction_if_missed": "",
                "effective_date": "",
                "kbli_codes_affected": "63122, 62019",  # CSV string!
            }
        ]
    )
    reg = _make_regulation()
    out = extract_obligations(reg, claude_runner=lambda _: canned, db_path=db)
    assert out[0].kbli_codes_affected == ("63122", "62019")


def test_extract_obligations_skips_items_with_empty_text(tmp_path):
    db = tmp_path / "setup_team.sqlite"
    canned = json.dumps(
        [
            {"text": "", "obligation_type": "filing", "article_ref": "x"},  # skip
            {
                "text": "real",
                "obligation_type": "filing",
                "article_ref": "Pasal 1",
                "deadline_pattern": "",
                "sanction_if_missed": "",
                "effective_date": "",
                "kbli_codes_affected": [],
            },
        ]
    )
    reg = _make_regulation()
    out = extract_obligations(reg, claude_runner=lambda _: canned, db_path=db)
    assert len(out) == 1
    assert out[0].text == "real"


def test_extract_obligations_runner_signature_is_documented(tmp_path):
    """Contract test: runner is `Callable[[str], str]` — verify by passing a
    runner that records the prompt."""
    db = tmp_path / "setup_team.sqlite"
    captured: list[str] = []

    def runner(p: str) -> str:
        captured.append(p)
        return "[]"

    reg = _make_regulation(body_excerpt="Pasal 4 ayat (1) wajib lapor.")
    extract_obligations(reg, claude_runner=runner, db_path=db)
    assert len(captured) == 1
    assert "Pasal 4 ayat (1)" in captured[0]
    assert "Indonesian regulation" in captured[0]


def test_schema_creates_obligations_table_with_indexes(tmp_path):
    """SCHEMA_DDL contract: 1 table + 3 indexes."""
    db = tmp_path / "x.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(SCHEMA_DDL)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='obligations'"
    ).fetchall()
    conn.close()
    names = {r[0] for r in rows}
    assert "idx_obligations_source" in names
    assert "idx_obligations_type" in names
    assert "idx_obligations_validated" in names


def test_valid_obligation_types_includes_5_canonical():
    assert {
        "filing",
        "reporting",
        "payment",
        "operational",
        "registration",
    } == VALID_OBLIGATION_TYPES
