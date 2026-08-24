"""Tests for the GARUDA VOA public eligibility funnel (L2).

Each guard here is proven to bite: the companion PR description records, for
every test in this file, the literal red produced by breaking the guarded
line and the literal green produced by restoring it — a test that stays
green either way is worthless (contract: modus VERIFY discipline).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import garuda_voa_public as router_mod
from backend.services.garuda_flow.civil_clock import garuda_today
from backend.services.garuda_flow.public_api import (
    CheckStore,
    EligibilityCheckOutcome,
    IdempotencyConflict,
    StoredCheck,
    UnconfiguredCheckStore,
)

TODAY = garuda_today()
ACCEPT_ENTRY_DATE = TODAY + timedelta(days=7)
ACCEPT_PASSPORT_EXPIRY = ACCEPT_ENTRY_DATE + timedelta(days=200)

VALID_ISSUANCE_BODY: dict[str, object] = {
    "case_type": "issuance",
    "nationality": "USA",
    "entry_date": ACCEPT_ENTRY_DATE.isoformat(),
    "passport_expiry_date": ACCEPT_PASSPORT_EXPIRY.isoformat(),
    "purpose": "tourism",
    "travellers": 1,
    "self_pay": True,
    "extension_already_used": False,
    "retention_notice_acknowledged": True,
}

VALID_IDEMPOTENCY_KEY = "test-key-0123456789abcdef"


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router_mod.router)
    return app


def _client() -> TestClient:
    return TestClient(_app())


class _FakeStore:
    """Minimal in-memory `CheckStore` double for the tests that need one."""

    def __init__(self) -> None:
        self.checks: dict[str, StoredCheck] = {}
        self.deleted: set[str] = set()

    async def create(
        self,
        *,
        idempotency_key: str,
        canonical_request: dict[str, object],
        outcome: EligibilityCheckOutcome,
    ) -> StoredCheck:
        result_id = "r" * 22
        stored = StoredCheck(
            result_id=result_id,
            outcome=outcome,
            idempotency_replayed=False,
            session_secret="s" * 43,
        )
        self.checks[result_id] = stored
        return stored

    async def get(self, *, result_id: str, session_secret: str) -> StoredCheck | None:
        stored = self.checks.get(result_id)
        if stored is None or stored.session_secret != session_secret:
            return None
        return stored

    async def delete(
        self,
        *,
        result_id: str,
        session_secret: str | None,
        idempotency_key: str,
    ) -> bool:
        self.deleted.add(result_id)
        return True


def _override_store(app: FastAPI, store: CheckStore) -> None:
    app.dependency_overrides[router_mod.get_garuda_check_store] = lambda: store


# ============================================================
# Feature flag gate
# ============================================================


def test_flag_disabled_by_default_returns_404_for_all_three_ops(monkeypatch) -> None:
    monkeypatch.delenv("GARUDA_PUBLIC_ENABLED", raising=False)
    client = _client()

    post_response = client.post(
        "/api/visa/voa/eligibility-checks",
        json=VALID_ISSUANCE_BODY,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    get_response = client.get("/api/visa/voa/eligibility-checks/" + "r" * 22)
    delete_response = client.delete(
        "/api/visa/voa/eligibility-checks/" + "r" * 22,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )

    for response in (post_response, get_response, delete_response):
        assert response.status_code == 404
        assert response.json()["code"] == "GARUDA_PUBLIC_DISABLED"


def test_flag_enabled_true_stops_the_disabled_short_circuit(monkeypatch) -> None:
    """Bite proof for the flag check itself: with the flag on and a working
    store, create no longer 404s — it reaches persistence."""
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    app = _app()
    _override_store(app, _FakeStore())
    response = TestClient(app).post(
        "/api/visa/voa/eligibility-checks",
        json=VALID_ISSUANCE_BODY,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert response.status_code != 404


# ============================================================
# Idempotency-Key required (POST + DELETE)
# ============================================================


@pytest.mark.parametrize("method", ["post", "delete"])
def test_missing_idempotency_key_returns_400(monkeypatch, method: str) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    client = _client()
    call = getattr(client, method)
    kwargs = {"json": VALID_ISSUANCE_BODY} if method == "post" else {}
    path = "/api/visa/voa/eligibility-checks" if method == "post" else (
        "/api/visa/voa/eligibility-checks/" + "r" * 22
    )
    response = call(path, **kwargs)
    assert response.status_code == 400
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_malformed_idempotency_key_is_rejected_same_as_missing(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    client = _client()
    response = client.post(
        "/api/visa/voa/eligibility-checks",
        json=VALID_ISSUANCE_BODY,
        headers={"Idempotency-Key": "short"},  # below the 16-char minimum
    )
    assert response.status_code == 400
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


# ============================================================
# Request-shape validation (allOf issuance/extension guard)
# ============================================================


def test_extension_missing_voa_expiry_date_is_invalid_request(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    body = {**VALID_ISSUANCE_BODY, "case_type": "extension"}
    client = _client()
    response = client.post(
        "/api/visa/voa/eligibility-checks",
        json=body,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_issuance_with_voa_expiry_date_is_invalid_request(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    body = {**VALID_ISSUANCE_BODY, "voa_expiry_date": ACCEPT_ENTRY_DATE.isoformat()}
    client = _client()
    response = client.post(
        "/api/visa/voa/eligibility-checks",
        json=body,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_unknown_field_is_invalid_request(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    body = {**VALID_ISSUANCE_BODY, "full_name": "leaked applicant name"}
    client = _client()
    response = client.post(
        "/api/visa/voa/eligibility-checks",
        json=body,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    # No echo of the rejected field/value anywhere in the error body.
    assert "full_name" not in response.text
    assert "leaked applicant name" not in response.text


def test_notice_acknowledgement_required_when_false(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    body = {**VALID_ISSUANCE_BODY, "retention_notice_acknowledged": False}
    client = _client()
    response = client.post(
        "/api/visa/voa/eligibility-checks",
        json=body,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "NOTICE_ACKNOWLEDGEMENT_REQUIRED"


# ============================================================
# Persistence seam — fails closed with the shipped default store
# ============================================================


def test_default_store_is_unconfigured_and_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    assert isinstance(router_mod.get_garuda_check_store(), UnconfiguredCheckStore)
    client = _client()
    response = client.post(
        "/api/visa/voa/eligibility-checks",
        json=VALID_ISSUANCE_BODY,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "PERSISTENCE_POLICY_UNAVAILABLE"


def test_idempotency_conflict_maps_to_409(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")

    class _ConflictingStore(_FakeStore):
        async def create(self, **_kwargs):
            raise IdempotencyConflict("bound to a different payload")

    app = _app()
    _override_store(app, _ConflictingStore())
    response = TestClient(app).post(
        "/api/visa/voa/eligibility-checks",
        json=VALID_ISSUANCE_BODY,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_CONFLICT"


# ============================================================
# Full success path (create -> get -> delete) with a working fake store
# ============================================================


def test_accept_create_then_get_then_delete_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    app = _app()
    store = _FakeStore()
    _override_store(app, store)
    client = TestClient(app)

    create_response = client.post(
        "/api/visa/voa/eligibility-checks",
        json=VALID_ISSUANCE_BODY,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["verdict"] == "ACCEPT"
    assert body["price_idr"] == 790_000
    assert body["reason_codes"] == []
    assert create_response.headers["Location"] == f"/visa/voa/{'r' * 22}"
    assert "garuda_result_session" in create_response.cookies

    get_response = client.get(f"/api/visa/voa/eligibility-checks/{'r' * 22}")
    assert get_response.status_code == 200
    assert get_response.json()["verdict"] == "ACCEPT"

    delete_response = client.delete(
        f"/api/visa/voa/eligibility-checks/{'r' * 22}",
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert delete_response.status_code == 204
    assert "r" * 22 in store.deleted


def test_decline_case_never_carries_a_price_or_deadline(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    body = {**VALID_ISSUANCE_BODY, "nationality": "XXX"}
    app = _app()
    _override_store(app, _FakeStore())
    response = TestClient(app).post(
        "/api/visa/voa/eligibility-checks",
        json=body,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["verdict"] == "DECLINE"
    assert "NATIONALITY_NOT_ELIGIBLE" in payload["reason_codes"]
    assert "price_idr" not in payload
    assert "published_filing_deadline" not in payload


# ============================================================
# GET — non-enumerating result-not-found
# ============================================================


def test_get_malformed_result_id_returns_404_result_not_found(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    client = _client()
    response = client.get(
        "/api/visa/voa/eligibility-checks/short",
        cookies={"garuda_result_session": "whatever"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "RESULT_NOT_FOUND"


def test_get_missing_cookie_returns_404_result_not_found(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    client = _client()
    response = client.get("/api/visa/voa/eligibility-checks/" + "r" * 22)
    assert response.status_code == 404
    assert response.json()["code"] == "RESULT_NOT_FOUND"


def test_get_valid_id_wrong_session_returns_404_not_500(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    app = _app()
    store = _FakeStore()
    _override_store(app, store)
    client = TestClient(app)
    client.post(
        "/api/visa/voa/eligibility-checks",
        json=VALID_ISSUANCE_BODY,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    response = client.get(
        f"/api/visa/voa/eligibility-checks/{'r' * 22}",
        cookies={"garuda_result_session": "wrong-secret"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "RESULT_NOT_FOUND"


# ============================================================
# Privacy headers on every response, success and error alike
# ============================================================


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", "/api/visa/voa/eligibility-checks/" + "r" * 22, {}),
        (
            "post",
            "/api/visa/voa/eligibility-checks",
            {"json": VALID_ISSUANCE_BODY},
        ),
    ],
)
def test_privacy_headers_present_when_flag_disabled(method, path, kwargs) -> None:
    client = _client()
    response = getattr(client, method)(path, **kwargs)
    assert response.headers["Cache-Control"] == "no-store, private"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow, noarchive"


def test_privacy_headers_present_on_successful_create(monkeypatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    app = _app()
    _override_store(app, _FakeStore())
    response = TestClient(app).post(
        "/api/visa/voa/eligibility-checks",
        json=VALID_ISSUANCE_BODY,
        headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
    )
    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store, private"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow, noarchive"
