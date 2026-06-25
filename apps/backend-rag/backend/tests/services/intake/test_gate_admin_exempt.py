"""TAC 2026-06-19: admins exempt from the intake gate wall + damar de-admined."""
from __future__ import annotations

import pytest

from backend.app.utils.crm_utils import is_crm_admin
from backend.services.intake import gate_evaluator


@pytest.fixture
def _pool(monkeypatch):
    async def _one(_conn, _email):
        return 3

    monkeypatch.setattr(gate_evaluator, "_count_documents", _one)
    monkeypatch.setattr(gate_evaluator, "_count_late", _one)
    monkeypatch.setattr(gate_evaluator, "_count_deadlines", _one)

    class _Acq:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    class _Pool:
        def acquire(self):
            return _Acq()

    return _Pool()


@pytest.mark.asyncio
async def test_admin_not_walled_despite_counts(_pool):
    res = await gate_evaluator.evaluate_gate_status(
        _pool, user_email="asya@balizero.com", is_admin=True
    )
    assert res["blocked"] is False
    assert res["sections"]["documents"]["count"] == 3


@pytest.mark.asyncio
async def test_non_admin_still_walled(_pool):
    res = await gate_evaluator.evaluate_gate_status(
        _pool, user_email="adit@balizero.com", is_admin=False
    )
    assert res["blocked"] is True


def test_damar_is_no_longer_crm_admin():
    assert is_crm_admin({"email": "damar@balizero.com", "role": "Junior Consultant"}) is False


def test_asya_is_still_admin():
    assert is_crm_admin({"email": "asya@balizero.com"}) is True
