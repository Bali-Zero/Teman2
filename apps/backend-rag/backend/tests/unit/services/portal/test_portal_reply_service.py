"""Execute the shared SQL against a synthetic SQLite relational fixture.

The query uses SQL common to SQLite and Postgres; migration rollout is verified separately.
"""

import sqlite3

import pytest

from backend.services.portal.portal_reply_service import pending_reply_query


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE clients(id INTEGER PRIMARY KEY, full_name TEXT, assigned_to TEXT, deleted_at TEXT);
        CREATE TABLE portal_messages(id INTEGER PRIMARY KEY, client_id INTEGER, direction TEXT, read_at TEXT, created_at TEXT, is_system_generated BOOLEAN DEFAULT FALSE, sent_by TEXT);
        INSERT INTO clients VALUES(1, 'Synthetic A', 'owner@example.test', NULL);
        INSERT INTO clients VALUES(2, 'Synthetic B', 'other@example.test', NULL);
        INSERT INTO portal_messages (id,client_id,direction,read_at,created_at,is_system_generated) VALUES(1, 1, 'client_to_team', '2026-09-25T10:01', '2026-09-25T10:00', FALSE);
        INSERT INTO portal_messages (id,client_id,direction,read_at,created_at,is_system_generated) VALUES(2, 2, 'client_to_team', NULL, '2026-09-25T10:00', FALSE);
    """)
    yield conn
    conn.close()


def pending(db, owner="owner@example.test"):
    query, params = pending_reply_query(owner)
    return [dict(row) for row in db.execute(query, {"1": params[0]} if params else {})]


def test_read_message_remains_pending_and_assignment_scopes_total(db):
    assert pending(db) == [
        {"client_id": 1, "client_name": "Synthetic A", "pending_count": 1, "total_pending": 1}
    ]
    assert pending(db, None)[0]["total_pending"] == 2
    db.execute("UPDATE clients SET deleted_at = '2026-09-25' WHERE id = 1")
    assert pending(db) == []


def test_automatic_notice_does_not_reply_but_manual_reply_does(db):
    db.execute(
        "INSERT INTO portal_messages (id,client_id,direction,read_at,created_at,is_system_generated) VALUES(3, 1, 'team_to_client', NULL, '2026-09-25T10:02', TRUE)"
    )
    assert len(pending(db)) == 1
    db.execute(
        "INSERT INTO portal_messages (id,client_id,direction,read_at,created_at,is_system_generated) VALUES(4, 1, 'team_to_client', NULL, '2026-09-25T10:03', FALSE)"
    )
    assert pending(db) == []
    db.execute(
        "INSERT INTO portal_messages (id,client_id,direction,read_at,created_at,is_system_generated) VALUES(5, 1, 'client_to_team', NULL, '2026-09-25T10:03', FALSE)"
    )
    assert pending(db)[0]["pending_count"] == 1


def test_limit_does_not_reduce_total(db):
    for number in range(3, 15):
        db.execute(
            "INSERT INTO clients VALUES(?, 'Synthetic', 'owner@example.test', NULL)", (number,)
        )
        db.execute(
            "INSERT INTO portal_messages (id,client_id,direction,read_at,created_at,is_system_generated) VALUES(?, ?, 'client_to_team', NULL, '2026-09-25T10:00', FALSE)",
            (number, number),
        )
    rows = pending(db)
    assert len(rows) == 10
    assert rows[0]["total_pending"] == 13
