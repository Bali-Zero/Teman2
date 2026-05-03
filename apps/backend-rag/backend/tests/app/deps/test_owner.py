"""Tests for owner-only dependency."""
import pytest
from fastapi import HTTPException

from backend.app.deps.owner import OWNER_EMAILS, require_owner


def test_owner_emails_contains_zero():
    assert "zero@balizero.com" in OWNER_EMAILS


def test_owner_emails_contains_antonellosiano():
    assert "antonellosiano@balizero.com" in OWNER_EMAILS


def test_owner_emails_is_frozenset():
    assert isinstance(OWNER_EMAILS, frozenset)


@pytest.mark.asyncio
async def test_require_owner_allows_zero():
    user = {"email": "zero@balizero.com", "role": "admin"}
    result = await require_owner(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_owner_allows_antonellosiano():
    user = {"email": "antonellosiano@balizero.com", "role": "admin"}
    result = await require_owner(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_owner_denies_other_admin():
    user = {"email": "asya@balizero.com", "role": "admin"}
    with pytest.raises(HTTPException) as exc:
        await require_owner(user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_owner_denies_missing_email():
    user = {"role": "admin"}
    with pytest.raises(HTTPException) as exc:
        await require_owner(user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_owner_denies_client():
    user = {"email": "random@example.com", "role": "client"}
    with pytest.raises(HTTPException) as exc:
        await require_owner(user=user)
    assert exc.value.status_code == 403
