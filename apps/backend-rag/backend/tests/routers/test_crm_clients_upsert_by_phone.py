"""Tests for POST /api/crm/clients/upsert-by-phone (wa-mirror service write).

Covers: feature-flag kill-switch (503), scoped-key auth (401), insert path,
enrich path, strategic_recap human-precedence skip, shared-phone multi-match
reporting, and update-only mode (create_if_missing=False).
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.crm_clients as crm_clients_module
from backend.app.core.config import settings
from backend.app.dependencies import get_database_pool

KEY = "test-crm-write-key-1234567890"
HEADERS = {"X-CRM-Write-Key": KEY}


@pytest.fixture
def write_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the feature flag ON and configure the scoped key."""
    monkeypatch.setattr(settings, "wa_mirror_crm_write_enabled", True, raising=False)
    monkeypatch.setattr(settings, "wa_mirror_crm_write_key", KEY, raising=False)


@pytest.fixture
def app(mock_db_pool, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    pool, _conn = mock_db_pool
    # Cache invalidation is best-effort; stub it so tests never touch Redis.
    monkeypatch.setattr(crm_clients_module, "invalidate_cache", AsyncMock())
    application = FastAPI()
    application.include_router(crm_clients_module.router)
    application.dependency_overrides[get_database_pool] = lambda: pool
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# --------------------------------------------------------------------------- #
# Auth / kill-switch
# --------------------------------------------------------------------------- #


def test_flag_off_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "wa_mirror_crm_write_enabled", False, raising=False)
    monkeypatch.setattr(settings, "wa_mirror_crm_write_key", KEY, raising=False)
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={"phone_normalized": "6281234567", "full_name": "Mario Rossi"},
        headers=HEADERS,
    )
    assert resp.status_code == 503


def test_missing_key_returns_401(client: TestClient, write_enabled: None) -> None:
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={"phone_normalized": "6281234567", "full_name": "Mario Rossi"},
    )
    assert resp.status_code == 401


def test_wrong_key_returns_401(client: TestClient, write_enabled: None) -> None:
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={"phone_normalized": "6281234567", "full_name": "Mario Rossi"},
        headers={"X-CRM-Write-Key": "nope"},
    )
    assert resp.status_code == 401


def test_bad_phone_returns_422(client: TestClient, write_enabled: None) -> None:
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={"phone_normalized": "+62 812 abc", "full_name": "Mario Rossi"},
        headers=HEADERS,
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Insert / enrich logic
# --------------------------------------------------------------------------- #


def test_insert_new_lead(client: TestClient, write_enabled: None, mock_db_pool) -> None:
    _pool, conn = mock_db_pool
    conn.fetch.return_value = []  # no existing client
    conn.fetchval.return_value = 9001  # INSERT ... RETURNING id
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={"phone_normalized": "6281234567", "full_name": "Mario Rossi"},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "client_id": 9001,
        "was_created": True,
        "action": "inserted",
        "matched_count": 0,
        "recap_applied": False,
        "was_archived": False,
    }
    assert conn.fetchval.await_count == 1


def test_insert_requires_full_name(client: TestClient, write_enabled: None, mock_db_pool) -> None:
    _pool, conn = mock_db_pool
    conn.fetch.return_value = []
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={"phone_normalized": "6281234567"},  # no full_name
        headers=HEADERS,
    )
    assert resp.status_code == 422


def test_enrich_existing(client: TestClient, write_enabled: None, mock_db_pool) -> None:
    _pool, conn = mock_db_pool
    conn.fetch.return_value = [
        {
            "id": 4242,
            "full_name": "Lead +6281234567",  # junk → improvable
            "notes": "old note",
            "deleted_at": None,
            "strategic_recap_source": None,
            "updated_at": None,  # None → notes-append window always stale
        }
    ]
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={
            "phone_normalized": "6281234567",
            "full_name": "Marco Bianchi",
            "notes_append": "3 inbound about KITAS",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["client_id"] == 4242
    assert body["was_created"] is False
    assert body["action"] == "enriched"
    # One UPDATE issued (plus the advisory-lock execute) → at least 2 execute calls.
    assert conn.execute.await_count >= 2


def test_recap_skipped_when_source_manual(
    client: TestClient, write_enabled: None, mock_db_pool
) -> None:
    _pool, conn = mock_db_pool
    conn.fetch.return_value = [
        {
            "id": 7,
            "full_name": "Real Human",
            "notes": "",
            "deleted_at": None,
            "strategic_recap_source": "manual",  # human edit must win
            "updated_at": None,
        }
    ]
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={
            "phone_normalized": "6281234567",
            "strategic_recap": "auto-generated summary",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recap_applied"] is False
    # Nothing else changed → no UPDATE, only the advisory-lock execute.
    assert body["action"] == "skipped_no_change"


def test_recap_applied_when_not_manual(
    client: TestClient, write_enabled: None, mock_db_pool
) -> None:
    _pool, conn = mock_db_pool
    conn.fetch.return_value = [
        {
            "id": 7,
            "full_name": "Real Human",
            "notes": "",
            "deleted_at": None,
            "strategic_recap_source": "automated",
            "updated_at": None,
        }
    ]
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={"phone_normalized": "6281234567", "strategic_recap": "fresh summary"},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["recap_applied"] is True


def test_multi_match_reports_count(client: TestClient, write_enabled: None, mock_db_pool) -> None:
    _pool, conn = mock_db_pool
    conn.fetch.return_value = [
        {"id": 1, "full_name": "Spouse A", "notes": "", "deleted_at": None,
         "strategic_recap_source": None, "updated_at": None},
        {"id": 2, "full_name": "Spouse B", "notes": "", "deleted_at": None,
         "strategic_recap_source": None, "updated_at": None},
    ]
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={"phone_normalized": "6281234567", "notes_append": "x"},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matched_count"] == 2
    assert body["client_id"] == 1  # acts on the first (live, most-recent) row


def test_reject_ambiguous_refuses_before_any_mutation(
    client: TestClient, write_enabled: None, mock_db_pool
) -> None:
    """Round-6 F10 guilt: with `reject_ambiguous` and a shared phone (2 live
    rows) the endpoint must refuse BEFORE any restore/rename/update — the
    rows[0] pick is arbitrary and a caller that resolves identity by phone
    (intake delivery) must never mutate or receive an arbitrary client."""
    _pool, conn = mock_db_pool
    conn.fetch.return_value = [
        {"id": 1, "full_name": "Spouse A", "notes": "", "deleted_at": None,
         "strategic_recap_source": None, "updated_at": None},
        {"id": 2, "full_name": "Spouse B", "notes": "", "deleted_at": None,
         "strategic_recap_source": None, "updated_at": None},
    ]
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={
            "phone_normalized": "6281234567",
            "full_name": "Marco Bianchi",
            "notes_append": "x",
            "reject_ambiguous": True,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "client_id": None,
        "was_created": False,
        "action": "rejected_ambiguous",
        "matched_count": 2,
        "recap_applied": False,
        "was_archived": False,
    }
    # ONLY the advisory-lock executes ran (legacy digits key + phonecore key) —
    # no UPDATE, no INSERT.
    executed = [str(c.args[0]) for c in conn.execute.await_args_list]
    assert conn.execute.await_count == 2
    assert all("pg_advisory_xact_lock" in s for s in executed)
    assert conn.fetchval.await_count == 0


def test_archived_sole_match_readonly_and_reported(
    client: TestClient, write_enabled: None, mock_db_pool
) -> None:
    """Round-9 F14: with restore disabled, an ARCHIVED match is READ-ONLY —
    no restore, no rename, no notes/recap (the caller's local identity may not
    be this card's person) — and the response says so (`was_archived: true`,
    action `skipped_archived`) so identity resolvers fail closed on it."""
    _pool, conn = mock_db_pool
    conn.fetch.return_value = [
        {"id": 5, "full_name": "Archived Person", "notes": "", "deleted_at": "2026-01-01",
         "strategic_recap_source": None, "updated_at": None},
    ]
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={
            "phone_normalized": "6281234567",
            "full_name": "Wrong Local Identity",
            "notes_append": "x",
            "restore_if_archived": False,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["was_archived"] is True
    assert body["client_id"] == 5
    assert body["action"] == "skipped_archived"
    # ZERO mutations: the only executes are the 2 advisory locks (legacy digits
    # key + canonical phonecore key) — no UPDATE of any kind.
    executed = [str(c.args[0]) for c in conn.execute.await_args_list]
    assert conn.execute.await_count == 2
    assert all("pg_advisory_xact_lock" in s for s in executed)
    assert conn.fetchval.await_count == 0  # no INSERT either


def test_reject_ambiguous_single_match_still_enriches(
    client: TestClient, write_enabled: None, mock_db_pool
) -> None:
    """Round-6 F10 innocence: `reject_ambiguous` with exactly ONE match is not
    ambiguous — the normal enrich path must proceed."""
    _pool, conn = mock_db_pool
    conn.fetch.return_value = [
        {"id": 4242, "full_name": "Lead +6281234567", "notes": "", "deleted_at": None,
         "strategic_recap_source": None, "updated_at": None},
    ]
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={
            "phone_normalized": "6281234567",
            "full_name": "Marco Bianchi",
            "reject_ambiguous": True,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["client_id"] == 4242
    assert body["action"] == "enriched"


def test_update_only_mode_skips_when_not_found(
    client: TestClient, write_enabled: None, mock_db_pool
) -> None:
    _pool, conn = mock_db_pool
    conn.fetch.return_value = []
    resp = client.post(
        "/api/crm/clients/upsert-by-phone",
        json={
            "phone_normalized": "6281234567",
            "strategic_recap": "summary",
            "create_if_missing": False,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "skipped_not_found"
    assert body["client_id"] is None
    assert conn.fetchval.await_count == 0  # never inserted


_ADVISORY = "clients share a phone"
_LOGGER = "backend.app.routers.crm_clients"


def _advisory_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if _ADVISORY in r.getMessage()]


def test_shared_phone_advisory_names_a_noop_as_such(
    client: TestClient, write_enabled: None, mock_db_pool, caplog: pytest.LogCaptureFixture
) -> None:
    """GUILT for the sentence itself: two rows share the phone and there is
    NOTHING to write (recap is human-owned, no name/notes change), so no UPDATE
    runs — the advisory must say `action=skipped_no_change`, never claim a write.

    This is the case the merged advisory note got wrong: `result` is bound at the
    enrich branch even when `set_parts` is empty, so the guard is reached with a
    real matched_count for a row nothing happened to. On the caller that takes the
    model defaults (the wa-mirror promoter) this is the COMMON case, not a corner.
    """
    _pool, conn = mock_db_pool
    row = {
        "id": 7,
        "full_name": "Real Human",
        "notes": "",
        "deleted_at": None,
        "strategic_recap_source": "manual",  # human edit wins -> no recap write
        "updated_at": None,
    }
    conn.fetch.return_value = [row, {**row, "id": 9}]

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        resp = client.post(
            "/api/crm/clients/upsert-by-phone",
            json={
                "phone_normalized": "6281234567",
                "strategic_recap": "auto-generated summary",
            },
            headers=HEADERS,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "skipped_no_change"
    assert body["matched_count"] == 2
    # Nothing was written: only the advisory locks executed, no UPDATE.
    assert not [c for c in conn.execute.await_args_list if "UPDATE" in str(c.args[0])]

    lines = _advisory_lines(caplog)
    assert len(lines) == 1, lines
    assert "action=skipped_no_change" in lines[0]
    assert "id=7" in lines[0]
    # The retracted wording claimed a write on every firing.
    assert "acted on" not in lines[0]


def test_shared_phone_advisory_names_a_real_write_as_such(
    client: TestClient, write_enabled: None, mock_db_pool, caplog: pytest.LogCaptureFixture
) -> None:
    """INNOCENCE: the same guard, same two-row collision, but with something to
    write. The advisory must report the acting outcome — the fix must not make
    every firing look like a no-op."""
    _pool, conn = mock_db_pool
    conn.fetch.return_value = [
        {"id": 1, "full_name": "Spouse A", "notes": "", "deleted_at": None,
         "strategic_recap_source": None, "updated_at": None},
        {"id": 2, "full_name": "Spouse B", "notes": "", "deleted_at": None,
         "strategic_recap_source": None, "updated_at": None},
    ]

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        resp = client.post(
            "/api/crm/clients/upsert-by-phone",
            json={"phone_normalized": "6281234567", "notes_append": "x"},
            headers=HEADERS,
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["action"] == "enriched"

    lines = _advisory_lines(caplog)
    assert len(lines) == 1, lines
    assert "action=enriched" in lines[0]
    assert "id=1" in lines[0]


def test_sole_match_writes_no_advisory_at_all(
    client: TestClient, write_enabled: None, mock_db_pool, caplog: pytest.LogCaptureFixture
) -> None:
    """INNOCENCE: one match is not a collision — the guard is `> 1`, so a
    no-op on a SINGLE row must stay silent rather than gain a new alarm."""
    _pool, conn = mock_db_pool
    conn.fetch.return_value = [
        {
            "id": 7,
            "full_name": "Real Human",
            "notes": "",
            "deleted_at": None,
            "strategic_recap_source": "manual",
            "updated_at": None,
        }
    ]

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        resp = client.post(
            "/api/crm/clients/upsert-by-phone",
            json={
                "phone_normalized": "6281234567",
                "strategic_recap": "auto-generated summary",
            },
            headers=HEADERS,
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["action"] == "skipped_no_change"
    assert _advisory_lines(caplog) == []
