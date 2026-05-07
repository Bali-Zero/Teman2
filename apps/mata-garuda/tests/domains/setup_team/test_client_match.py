"""Client match tests (T7)."""
from __future__ import annotations

import json
import sqlite3
from datetime import date

import pytest

from mata_garuda.domains.setup_team.client_match import (
    list_active_clients,
    mark_alerted,
    match_obligations_to_clients,
    upsert_client,
)
from mata_garuda.domains.setup_team.obligation_engine import extract_obligations
from mata_garuda.domains.setup_team.types import Regulation


@pytest.fixture
def db(tmp_path):
    return tmp_path / "setup_team.sqlite"


def _seed_obligation(db, kbli=("63122",)):
    """Use the real T5 obligation_engine pipeline to seed an obligation row."""
    canned = json.dumps(
        [
            {
                "text": "Wajib lapor pelanggaran 3x24 jam",
                "obligation_type": "reporting",
                "article_ref": "Pasal 46",
                "deadline_pattern": "3x24 jam",
                "sanction_if_missed": "denda",
                "effective_date": "2024-10-17",
                "kbli_codes_affected": list(kbli),
            }
        ]
    )
    reg = Regulation(
        source_id="pasal-id:test",
        domain="regulation",
        tier=1,
        title="UU 27/2022 PDP",
        url="https://pasal.id/laws/test",
        published_at=date(2022, 9, 27),
        body_excerpt="Pasal 46",
        tags=("layer:pasal-id",),
    )
    persisted = extract_obligations(reg, claude_runner=lambda _: canned, db_path=db)
    assert persisted and persisted[0].id is not None
    return persisted[0]


def test_upsert_client_inserts_then_updates(db):
    cid = upsert_client("PT Test", ("63122",), db_path=db)
    assert cid > 0
    cid2 = upsert_client("PT Test", ("63122", "62019"), db_path=db)
    assert cid == cid2
    clients = list_active_clients(db_path=db)
    assert len(clients) == 1
    assert clients[0].kbli_codes == ("63122", "62019")


def test_match_obligations_to_clients_kbli_overlap(db):
    obl = _seed_obligation(db, kbli=("63122", "79902"))
    upsert_client("PT Match", ("63122",), db_path=db)
    upsert_client("PT NoMatch", ("82990",), db_path=db)
    upsert_client("PT MultiMatch", ("63122", "79902", "62019"), db_path=db)

    matches = match_obligations_to_clients(obl.id, db_path=db)
    by_name = {m.alert_payload["client_name"]: m for m in matches}
    assert "PT Match" in by_name
    assert "PT NoMatch" not in by_name
    assert "PT MultiMatch" in by_name
    assert by_name["PT Match"].matched_kbli == ("63122",)
    assert set(by_name["PT MultiMatch"].matched_kbli) == {"63122", "79902"}


def test_match_obligations_to_clients_payload_shape(db):
    obl = _seed_obligation(db, kbli=("63122",))
    upsert_client("PT One", ("63122",), contact="ops@x.com", db_path=db)

    matches = match_obligations_to_clients(obl.id, db_path=db)
    assert len(matches) == 1
    p = matches[0].alert_payload
    assert p["channel"] == "#setup-team-alerts"
    assert p["client_name"] == "PT One"
    assert p["obligation_id"] == obl.id
    assert p["obligation_type"] == "reporting"
    assert p["article_ref"] == "Pasal 46"
    assert p["matched_kbli"] == ["63122"]
    assert p["regulation_source_id"] == "pasal-id:test"


def test_match_obligations_to_clients_skips_inactive(db):
    obl = _seed_obligation(db, kbli=("63122",))
    upsert_client("PT Inactive", ("63122",), active=False, db_path=db)
    upsert_client("PT Active", ("63122",), active=True, db_path=db)
    matches = match_obligations_to_clients(obl.id, db_path=db)
    names = {m.alert_payload["client_name"] for m in matches}
    assert names == {"PT Active"}


def test_match_obligations_to_clients_returns_empty_when_no_kbli_overlap(db):
    obl = _seed_obligation(db, kbli=("63122",))
    upsert_client("PT NoMatch", ("82990",), db_path=db)
    assert match_obligations_to_clients(obl.id, db_path=db) == []


def test_match_obligations_to_clients_idempotent_match_table(db):
    obl = _seed_obligation(db, kbli=("63122",))
    upsert_client("PT One", ("63122",), db_path=db)
    match_obligations_to_clients(obl.id, db_path=db)
    match_obligations_to_clients(obl.id, db_path=db)

    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT COUNT(*) FROM client_obligation_match").fetchone()
    conn.close()
    assert rows[0] == 1


def test_match_obligations_unknown_id_returns_empty(db):
    upsert_client("PT One", ("63122",), db_path=db)
    assert match_obligations_to_clients(99999, db_path=db) == []


def test_match_obligations_obligation_with_no_kbli_returns_empty(db):
    obl = _seed_obligation(db, kbli=())  # empty
    upsert_client("PT One", ("63122",), db_path=db)
    assert match_obligations_to_clients(obl.id, db_path=db) == []


def test_mark_alerted_stamps_timestamp(db):
    obl = _seed_obligation(db, kbli=("63122",))
    upsert_client("PT One", ("63122",), db_path=db)
    matches = match_obligations_to_clients(obl.id, db_path=db)
    assert matches
    cid = matches[0].client_id
    ok = mark_alerted(obl.id, cid, when="2026-05-08T12:00:00+00:00", db_path=db)
    assert ok is True

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT alerted_at FROM client_obligation_match WHERE obligation_id=?",
        (obl.id,),
    ).fetchone()
    conn.close()
    assert row["alerted_at"] == "2026-05-08T12:00:00+00:00"


def test_mark_alerted_returns_false_when_no_row(db):
    ok = mark_alerted(99999, 99999, db_path=db)
    assert ok is False
