"""Unit tests for the obligations reviewer API (PR A2).

Follows the intake_review unit-test template (test_crm_enhanced_alerts.py):
a bare FastAPI() app with dependency_overrides for the admin gate and a fake
pool/connection, plus monkeypatched fake repositories so no real Postgres is
needed. The fakes reuse the REAL ``ObligationRow``/``AlertRow`` dataclasses so
the router's response-shaping code (``_to_out``) is exercised unchanged.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers import compliance_obligations
from backend.services.compliance.alert_repository import AlertRow
from backend.services.compliance.obligations_repository import ObligationRow

ADMIN_USER = {"email": "admin@example.com", "role": "admin"}
NON_ADMIN_USER = {"email": "user@example.com", "role": "user"}


# --------------------------------------------------------------------------- #
# In-memory fake DB: shared by direct-SQL calls (client/company lookups in
# /generate, the 404-vs-409 status probe in approve/reject) and by the fake
# repositories below (which the router uses for everything else).
# --------------------------------------------------------------------------- #
class Store:
    def __init__(self) -> None:
        self.clients: dict[int, dict[str, Any]] = {}
        self.companies: dict[int, dict[str, Any]] = {}
        self.obligations: list[dict[str, Any]] = []
        self.alerts: list[dict[str, Any]] = []
        self.op_log: list[tuple[str, Any, bool]] = []
        self.acquire_count = 0
        self._next_id = 1

    def acquire(self) -> _AcquireCtx:
        self.acquire_count += 1
        return _AcquireCtx(self)

    def next_id(self) -> int:
        value = self._next_id
        self._next_id += 1
        return value


class _AcquireCtx:
    def __init__(self, store: Store) -> None:
        self.store = store

    async def __aenter__(self) -> FakeConn:
        return FakeConn(self.store)

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _CountingTxn:
    """Records enter/exit on the owning FakeConn so tests can pin the boundary."""

    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    async def __aenter__(self) -> None:
        self.conn.txn_enter_count += 1
        self.conn.in_txn = True
        return None

    async def __aexit__(self, *exc: object) -> bool:
        self.conn.in_txn = False
        self.conn.txn_exit_count += 1
        return False


class FakeConn:
    """Answers the raw SQL the router makes directly on a connection."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.txn_enter_count = 0
        self.txn_exit_count = 0
        self.in_txn = False

    def transaction(self) -> _CountingTxn:
        return _CountingTxn(self)

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        flat = " ".join(query.split())
        if "FROM clients" in flat:
            row = self.store.clients.get(args[0])
            return dict(row) if row is not None else None
        if "FROM client_company_links" in flat:
            row = self.store.companies.get(args[0])
            return dict(row) if row is not None else None
        if "SELECT status FROM client_obligations" in flat:
            for row in self.store.obligations:
                if row["id"] == args[0]:
                    return {"status": row["status"]}
            return None
        raise AssertionError(f"unexpected fetchrow query in test fake: {query!r}")

    async def execute(self, query: str, *args: Any) -> str:
        flat = " ".join(query.split())
        if flat.startswith("UPDATE companies SET custom_fields"):
            patch = json.loads(args[0])  # the router passes to_jsonb(...) text
            for row in self.store.companies.values():
                if row.get("company_id") == args[1]:
                    existing = row.get("custom_fields") or {}
                    if isinstance(existing, str):
                        existing = json.loads(existing)
                    # mirrors COALESCE(custom_fields,'{}'::jsonb) || $1::text::jsonb
                    row["custom_fields"] = {**existing, **patch}
                    return "UPDATE 1"
            return "UPDATE 0"
        raise AssertionError(f"unexpected execute query in test fake: {query!r}")


# --------------------------------------------------------------------------- #
# Fake repositories (monkeypatched over the real classes in the router module)
# --------------------------------------------------------------------------- #
def _ob_row(d: dict[str, Any]) -> ObligationRow:
    return ObligationRow(**d)


class FakeObligationsRepository:
    def __init__(self, pool: Store) -> None:
        self.store = pool

    @classmethod
    def with_connection(cls, conn: FakeConn) -> FakeObligationsRepository:
        inst = cls.__new__(cls)
        inst.store = conn.store
        inst.conn = conn
        return inst

    async def list_filtered(
        self,
        *,
        client_id: int | None = None,
        status: str | None = "proposed",
        limit: int = 50,
        offset: int = 0,
    ) -> list[ObligationRow]:
        rows = [
            r
            for r in self.store.obligations
            if (client_id is None or r["client_id"] == client_id)
            and (status is None or r["status"] == status)
        ]
        rows.sort(key=lambda r: (r["due_date"], r["id"]))
        return [_ob_row(r) for r in rows[offset : offset + limit]]

    async def count_filtered(
        self, *, client_id: int | None = None, status: str | None = "proposed"
    ) -> int:
        return len(
            [
                r
                for r in self.store.obligations
                if (client_id is None or r["client_id"] == client_id)
                and (status is None or r["status"] == status)
            ]
        )

    async def get(self, obligation_id: int) -> ObligationRow | None:
        for row in self.store.obligations:
            if row["id"] == obligation_id:
                return _ob_row(row)
        return None

    async def upsert_proposals(self, client_id: int, proposals: Any) -> int:
        existing_keys = {
            (r["client_id"], r["rule_id"], r["period_key"]) for r in self.store.obligations
        }
        inserted = 0
        now = datetime.now(timezone.utc)
        for p in proposals:
            key = (client_id, p.rule_id, p.period_key)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            self.store.obligations.append(
                {
                    "id": self.store.next_id(),
                    "client_id": client_id,
                    "rule_id": p.rule_id,
                    "period_key": p.period_key,
                    "due_date": p.due_date,
                    "status": "proposed",
                    "needs_review_reason": p.needs_review_reason,
                    "reviewer_email": None,
                    "reviewed_at": None,
                    "review_note": None,
                    "alert_id": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            inserted += 1
        return inserted

    async def set_status(
        self, obligation_id: int, status: str, reviewer_email: str, note: str | None = None
    ) -> ObligationRow | None:
        self.store.op_log.append(("set_status", self.conn, self.conn.in_txn))
        for row in self.store.obligations:
            if row["id"] == obligation_id:
                if row["status"] != "proposed":
                    return None
                row["status"] = status
                row["reviewer_email"] = reviewer_email
                row["review_note"] = note
                row["reviewed_at"] = datetime.now(timezone.utc)
                row["updated_at"] = datetime.now(timezone.utc)
                return _ob_row(row)
        return None

    async def mark_alerted(self, obligation_id: int, alert_id: str) -> ObligationRow | None:
        self.store.op_log.append(("mark_alerted", self.conn, self.conn.in_txn))
        for row in self.store.obligations:
            if row["id"] == obligation_id:
                if row["status"] != "approved":
                    return None
                row["status"] = "alerted"
                row["alert_id"] = alert_id
                row["updated_at"] = datetime.now(timezone.utc)
                return _ob_row(row)
        return None


class FakeAlertRepository:
    @classmethod
    def with_connection(cls, conn: FakeConn) -> FakeAlertRepository:
        inst = cls.__new__(cls)
        inst.store = conn.store
        inst.conn = conn
        return inst

    async def find_active_by_dedup_key(self, dedup_key: str) -> AlertRow | None:
        for row in self.store.alerts:
            if row["dedup_key"] == dedup_key and row["status"] in (
                "pending",
                "sent",
                "acknowledged",
            ):
                return AlertRow(**row)
        return None

    async def insert(self, row: AlertRow) -> AlertRow:
        self.store.op_log.append(("alert_insert", self.conn, self.conn.in_txn))
        as_dict = row.__dict__.copy()
        as_dict["created_at"] = datetime.now(timezone.utc)
        self.store.alerts.append(as_dict)
        return AlertRow(**as_dict)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _fake_repositories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compliance_obligations, "ObligationsRepository", FakeObligationsRepository)
    monkeypatch.setattr(compliance_obligations, "AlertRepository", FakeAlertRepository)


@pytest.fixture
def store() -> Store:
    return Store()


def _app(store: Store, user: dict[str, Any]) -> FastAPI:
    app = FastAPI()
    app.include_router(compliance_obligations.router)
    app.dependency_overrides[get_database_pool] = lambda: store
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _seed_proposed(store: Store, **overrides: Any) -> dict[str, Any]:
    row = {
        "id": store.next_id(),
        "client_id": 1,
        "rule_id": "pph21_payment",
        "period_key": "2026-09",
        "due_date": date.today() + timedelta(days=10),
        "status": "proposed",
        "needs_review_reason": None,
        "reviewer_email": None,
        "reviewed_at": None,
        "review_note": None,
        "alert_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    store.obligations.append(row)
    return row


def _seed_client(
    store: Store,
    client_id: int = 1,
    *,
    company: dict[str, Any] | None = None,
    client_custom_fields: dict[str, Any] | None = None,
) -> None:
    """A clients row, optionally with the companies row client_company_links resolves to.

    ``company`` carries ``company_id`` because the PATCH writes to that id — the
    SELECT in ``_load_client_and_company`` is the single place that decides WHICH
    company row a client maps to, for both /generate and the profile routes.
    """
    store.clients[client_id] = {"id": client_id, "custom_fields": client_custom_fields or {}}
    if company is not None:
        store.companies[client_id] = dict(company)


# --------------------------------------------------------------------------- #
# RBAC: 403 for non-admin on every mutating route (and reads, per this
# router's full-admin gate — DESIGN-lane-A.md specifies is_crm_admin for the
# whole router, unlike intake_review's own-chat scoping which doesn't apply
# to obligations).
# --------------------------------------------------------------------------- #
def test_list_403_for_non_admin(store: Store) -> None:
    client = TestClient(_app(store, NON_ADMIN_USER))
    resp = client.get("/api/compliance/obligations")
    assert resp.status_code == 403


def test_get_403_for_non_admin(store: Store) -> None:
    _seed_proposed(store)
    client = TestClient(_app(store, NON_ADMIN_USER))
    resp = client.get("/api/compliance/obligations/1")
    assert resp.status_code == 403


def test_generate_403_for_non_admin(store: Store) -> None:
    client = TestClient(_app(store, NON_ADMIN_USER))
    resp = client.post("/api/compliance/obligations/generate", json={"client_id": 1})
    assert resp.status_code == 403


def test_approve_403_for_non_admin(store: Store) -> None:
    _seed_proposed(store)
    client = TestClient(_app(store, NON_ADMIN_USER))
    resp = client.post("/api/compliance/obligations/1/approve", json={})
    assert resp.status_code == 403


def test_reject_403_for_non_admin(store: Store) -> None:
    _seed_proposed(store)
    client = TestClient(_app(store, NON_ADMIN_USER))
    resp = client.post("/api/compliance/obligations/1/reject", json={"reason": "no"})
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# list / get shape
# --------------------------------------------------------------------------- #
def test_list_returns_paginated_shape(store: Store) -> None:
    _seed_proposed(store, id=1, period_key="2026-09")
    _seed_proposed(store, id=2, period_key="2026-10")
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.get("/api/compliance/obligations")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["items"]) == 2
    assert body["items"][0]["status"] == "proposed"


def test_list_filters_by_client_id_and_status(store: Store) -> None:
    _seed_proposed(store, id=1, client_id=1)
    _seed_proposed(store, id=2, client_id=2)
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.get("/api/compliance/obligations", params={"client_id": 2})

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["client_id"] == 2


def test_get_returns_detail(store: Store) -> None:
    _seed_proposed(store, id=1)
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.get("/api/compliance/obligations/1")

    assert resp.status_code == 200
    assert resp.json()["id"] == 1
    assert resp.json()["rule_id"] == "pph21_payment"


def test_get_unknown_id_404(store: Store) -> None:
    client = TestClient(_app(store, ADMIN_USER))
    resp = client.get("/api/compliance/obligations/999")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# generate: persists + idempotent
# --------------------------------------------------------------------------- #
def test_generate_404_unknown_client(store: Store) -> None:
    client = TestClient(_app(store, ADMIN_USER))
    resp = client.post("/api/compliance/obligations/generate", json={"client_id": 1})
    assert resp.status_code == 404


def test_generate_persists_and_is_idempotent(store: Store) -> None:
    store.clients[1] = {"id": 1, "custom_fields": {}}
    store.companies[1] = {
        "company_type": "PT PMA",
        "custom_fields": {"has_employees": True, "pkp": True},
    }
    client = TestClient(_app(store, ADMIN_USER))

    first = client.post(
        "/api/compliance/obligations/generate",
        json={"client_id": 1, "horizon_days": 400},
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["inserted_count"] > 0
    assert len(first_body["rows"]) == first_body["inserted_count"]
    assert first_body["needs_manual_classification"] is False
    assert first_body["warning"] is None
    first_row_count = len(store.obligations)

    second = client.post(
        "/api/compliance/obligations/generate",
        json={"client_id": 1, "horizon_days": 400},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["inserted_count"] == 0
    assert len(second_body["rows"]) == first_body["inserted_count"]
    assert len(store.obligations) == first_row_count  # no duplicates


def test_generate_flags_other_company_type_for_manual_classification(store: Store) -> None:
    store.clients[1] = {"id": 1, "custom_fields": {}}
    store.companies[1] = {"company_type": "Some Unrecognised Foundation", "custom_fields": {}}
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.post("/api/compliance/obligations/generate", json={"client_id": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["company_type"] == "OTHER"
    assert body["needs_manual_classification"] is True
    assert body["warning"]


# --------------------------------------------------------------------------- #
# approve: bridges into compliance_alerts exactly once, then refuses re-decision
# --------------------------------------------------------------------------- #
def test_approve_writes_exactly_one_alert_and_transitions_to_alerted(store: Store) -> None:
    _seed_proposed(store, id=1, client_id=7, rule_id="pph21_payment", period_key="2026-09")
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.post("/api/compliance/obligations/1/approve", json={"note": "looks right"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["obligation"]["status"] == "alerted"
    assert body["obligation"]["alert_id"] == body["alert_id"]
    assert len(store.alerts) == 1
    alert = store.alerts[0]
    assert alert["category"] == "obligation"
    assert alert["client_id"] == 7
    assert alert["dedup_key"] == "obligation:7:pph21_payment:2026-09"


def test_approve_runs_writes_inside_one_shared_transaction(store: Store) -> None:
    _seed_proposed(store, id=1, client_id=7, rule_id="pph21_payment", period_key="2026-09")
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.post("/api/compliance/obligations/1/approve", json={})

    assert resp.status_code == 200
    assert [name for name, _conn, _in_txn in store.op_log] == [
        "set_status",
        "alert_insert",
        "mark_alerted",
    ]
    assert all(in_txn for _name, _conn, in_txn in store.op_log)
    conns = {conn for _name, conn, _in_txn in store.op_log}
    assert len(conns) == 1, "both repositories must be bound to the same connection"
    conn = conns.pop()
    assert conn.txn_enter_count == 1
    assert conn.txn_exit_count == 1


def test_approve_twice_is_409(store: Store) -> None:
    _seed_proposed(store, id=1)
    client = TestClient(_app(store, ADMIN_USER))

    first = client.post("/api/compliance/obligations/1/approve", json={})
    assert first.status_code == 200

    second = client.post("/api/compliance/obligations/1/approve", json={})
    assert second.status_code == 409
    assert len(store.alerts) == 1  # no second alert from the failed re-approve


def test_reject_after_approve_is_409(store: Store) -> None:
    _seed_proposed(store, id=1)
    client = TestClient(_app(store, ADMIN_USER))

    approve = client.post("/api/compliance/obligations/1/approve", json={})
    assert approve.status_code == 200

    reject = client.post("/api/compliance/obligations/1/reject", json={"reason": "too late"})
    assert reject.status_code == 409


def test_approve_unknown_id_404(store: Store) -> None:
    client = TestClient(_app(store, ADMIN_USER))
    resp = client.post("/api/compliance/obligations/999/approve", json={})
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# reject: records the reason, terminal, no compliance_alerts write
# --------------------------------------------------------------------------- #
def test_reject_records_reason(store: Store) -> None:
    _seed_proposed(store, id=1)
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.post("/api/compliance/obligations/1/reject", json={"reason": "not applicable"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["review_note"] == "not applicable"
    assert store.alerts == []  # reject never bridges into compliance_alerts


def test_reject_without_reason_is_422(store: Store) -> None:
    _seed_proposed(store, id=1)
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.post("/api/compliance/obligations/1/reject", json={})

    assert resp.status_code == 422


def test_reject_twice_is_409(store: Store) -> None:
    _seed_proposed(store, id=1)
    client = TestClient(_app(store, ADMIN_USER))

    first = client.post("/api/compliance/obligations/1/reject", json={"reason": "no"})
    assert first.status_code == 200

    second = client.post("/api/compliance/obligations/1/reject", json={"reason": "no"})
    assert second.status_code == 409


def test_reject_unknown_id_404(store: Store) -> None:
    client = TestClient(_app(store, ADMIN_USER))
    resp = client.post("/api/compliance/obligations/999/reject", json={"reason": "no"})
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# GET /catalog — rule metadata only: no client data, no database, and the path
# segment must NOT be read as an obligation id (route ordering, PR M3).
# --------------------------------------------------------------------------- #
def test_catalog_403_for_non_admin(store: Store) -> None:
    client = TestClient(_app(store, NON_ADMIN_USER))
    assert client.get("/api/compliance/obligations/catalog").status_code == 403


def test_catalog_returns_every_rule_with_reviewer_metadata(store: Store) -> None:
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.get("/api/compliance/obligations/catalog")

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == len(compliance_obligations._cached_rules()) == 21
    by_id = {row["id"]: row for row in rows}
    assert set(by_id["pph21_payment"]) == {
        "id",
        "name",
        "authority",
        "legal_source",
        "verified",
        "frequency",
        "roll",
        "needs_review_reason",
        "trigger",
        "notes",
    }
    assert by_id["pph21_payment"]["frequency"] == "monthly"
    assert by_id["pph21_payment"]["roll"] == "next_business_day"
    assert all(isinstance(row["verified"], bool) and row["name"] for row in rows)


def test_catalog_reads_no_client_data(store: Store) -> None:
    client = TestClient(_app(store, ADMIN_USER))

    assert client.get("/api/compliance/obligations/catalog").status_code == 200

    assert store.acquire_count == 0  # never opens a connection


# --------------------------------------------------------------------------- #
# GET /profile/{client_id}
# --------------------------------------------------------------------------- #
def test_profile_403_for_non_admin(store: Store) -> None:
    _seed_client(store)
    client = TestClient(_app(store, NON_ADMIN_USER))
    assert client.get("/api/compliance/obligations/profile/1").status_code == 403


def test_profile_404_unknown_client(store: Store) -> None:
    client = TestClient(_app(store, ADMIN_USER))
    assert client.get("/api/compliance/obligations/profile/999").status_code == 404


def test_profile_reports_present_and_missing_keys(store: Store) -> None:
    _seed_client(
        store,
        company={"company_id": 90, "company_type": "PT PMA", "custom_fields": {"pkp": True}},
    )
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.get("/api/compliance/obligations/profile/1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["client_id"] == 1
    assert body["profile"]["company_type"] == "PT_PMA"
    assert body["profile"]["pkp"] is True
    assert body["present_keys"] == ["pkp"]
    assert "pse_registered" in body["missing_keys"]
    assert "pkp" not in body["missing_keys"]
    assert body["company_type_raw"] == "PT PMA"
    assert body["needs_manual_classification"] is False


def test_profile_without_a_company_row_is_all_defaults(store: Store) -> None:
    _seed_client(store)  # client exists, no client_company_links row
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.get("/api/compliance/obligations/profile/1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"]["company_type"] == "OTHER"
    assert body["company_type_raw"] is None
    assert body["present_keys"] == []
    assert body["needs_manual_classification"] is True


# --------------------------------------------------------------------------- #
# PATCH /profile/{client_id} — JSONB merge into companies.custom_fields
# --------------------------------------------------------------------------- #
def test_patch_403_for_non_admin(store: Store) -> None:
    _seed_client(store, company={"company_id": 90, "company_type": "PT PMA", "custom_fields": {}})
    client = TestClient(_app(store, NON_ADMIN_USER))
    resp = client.patch("/api/compliance/obligations/profile/1", json={"pkp": True})
    assert resp.status_code == 403


def test_patch_merges_without_wiping_unrelated_keys(store: Store) -> None:
    _seed_client(
        store,
        company={
            "company_id": 90,
            "company_type": "PT PMA",
            "custom_fields": {"risk_status": "rendah", "pkp": False},
        },
    )
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.patch(
        "/api/compliance/obligations/profile/1", json={"pkp": True, "employee_count": 4}
    )

    assert resp.status_code == 200
    stored = store.companies[1]["custom_fields"]
    assert stored["risk_status"] == "rendah"  # untouched by the merge
    assert stored["pkp"] is True
    assert stored["employee_count"] == 4
    body = resp.json()
    assert body["profile"]["pkp"] is True
    assert body["profile"]["employee_count"] == 4
    assert body["profile"]["has_employees"] is True  # derived
    assert set(body["present_keys"]) >= {"pkp", "employee_count"}


def test_patch_company_type_is_stored_under_its_own_key_and_wins(store: Store) -> None:
    _seed_client(
        store,
        company={"company_id": 90, "company_type": "Yayasan Unrecognised", "custom_fields": {}},
    )
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.patch("/api/compliance/obligations/profile/1", json={"company_type": "pt_pma"})

    assert resp.status_code == 200
    stored = store.companies[1]
    assert stored["custom_fields"] == {"compliance_company_type": "PT_PMA"}
    assert stored["company_type"] == "Yayasan Unrecognised"  # the column is never rewritten
    body = resp.json()
    assert body["profile"]["company_type"] == "PT_PMA"
    assert body["company_type_raw"] == "Yayasan Unrecognised"
    assert body["needs_manual_classification"] is False


def test_patch_normalises_values_before_storing(store: Store) -> None:
    _seed_client(store, company={"company_id": 90, "company_type": "CV", "custom_fields": {}})
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.patch(
        "/api/compliance/obligations/profile/1",
        json={"employee_count": "12", "pkp": "yes", "fiscal_year_end": "03-31"},
    )

    assert resp.status_code == 200
    # typed values, not the submitted strings: what profile_inputs reads back
    assert store.companies[1]["custom_fields"] == {
        "employee_count": 12,
        "pkp": True,
        "fiscal_year_end": "03-31",
    }
    assert resp.json()["profile"]["fiscal_year_end"] == "03-31"


def test_patch_unknown_key_is_422_and_writes_nothing(store: Store) -> None:
    _seed_client(store, company={"company_id": 90, "company_type": "PT PMA", "custom_fields": {}})
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.patch(
        "/api/compliance/obligations/profile/1", json={"pkp": True, "is_rich": True}
    )

    assert resp.status_code == 422
    assert "is_rich" in resp.json()["detail"]
    assert store.companies[1]["custom_fields"] == {}


def test_patch_invalid_company_type_is_422(store: Store) -> None:
    _seed_client(store, company={"company_id": 90, "company_type": "PT PMA", "custom_fields": {}})
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.patch("/api/compliance/obligations/profile/1", json={"company_type": "PT_XYZ"})

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "company_type" in detail
    assert "PT_XYZ" not in detail  # the detail names the key and the domain, never the value


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"fiscal_year_end": "31-03"},
        {"employee_count": -2},
        {"pkp": "maybe"},
        {"investment_stage": "pre-seed"},
    ],
)
def test_patch_rejects_an_invalid_value_with_422(store: Store, body: dict[str, Any]) -> None:
    _seed_client(store, company={"company_id": 90, "company_type": "PT PMA", "custom_fields": {}})
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.patch("/api/compliance/obligations/profile/1", json=body)

    assert resp.status_code == 422
    assert store.companies[1]["custom_fields"] == {}


def test_patch_404_unknown_client(store: Store) -> None:
    client = TestClient(_app(store, ADMIN_USER))
    resp = client.patch("/api/compliance/obligations/profile/999", json={"pkp": True})
    assert resp.status_code == 404


def test_patch_409_when_the_client_has_no_company_row(store: Store) -> None:
    _seed_client(store)  # no client_company_links row
    client = TestClient(_app(store, ADMIN_USER))

    resp = client.patch("/api/compliance/obligations/profile/1", json={"pkp": True})

    assert resp.status_code == 409
    assert "no company row" in resp.json()["detail"]


def test_patch_then_generate_proposes_rules_the_default_profile_did_not(store: Store) -> None:
    """The consumer proof: attributes the reviewer PATCHes widen what propose() emits."""
    _seed_client(store, company={"company_id": 90, "company_type": "PT PMA", "custom_fields": {}})
    client = TestClient(_app(store, ADMIN_USER))

    bare = client.post(
        "/api/compliance/obligations/generate", json={"client_id": 1, "horizon_days": 400}
    )
    assert bare.status_code == 200
    bare_rules = {row["rule_id"] for row in bare.json()["rows"]}

    patched = client.patch(
        "/api/compliance/obligations/profile/1",
        json={"has_employees": True, "employee_count": 5, "pkp": True},
    )
    assert patched.status_code == 200

    again = client.post(
        "/api/compliance/obligations/generate", json={"client_id": 1, "horizon_days": 400}
    )
    assert again.status_code == 200
    assert again.json()["inserted_count"] > 0
    assert {row["rule_id"] for row in again.json()["rows"]} > bare_rules
