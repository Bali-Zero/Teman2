"""Round-12 F16 — under-lock duplicate-phone re-check in ClientRepository.

The router's dedup pre-check runs OUTSIDE the create transaction: two
concurrent creates can both pass it, then serialize on the phonecore advisory
lock and insert twice. The repository must re-check under the held lock and
raise DuplicatePhoneError instead of double-inserting.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.db.repositories.client_repository import (
    ClientRepository,
    DuplicatePhoneError,
)


class _Tx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _make_repo(dup_row: dict | None) -> tuple[ClientRepository, AsyncMock]:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_Tx())
    conn.execute.return_value = None
    # First fetchrow = the dedup re-check; later ones = the INSERT RETURNING.
    conn.fetchrow.side_effect = [
        dup_row,
        {"id": 900, "full_name": "New Client"},
    ]

    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return ClientRepository(pool), conn


@pytest.mark.asyncio
async def test_create_raises_duplicate_phone_under_lock():
    """Guilt: the under-lock re-check finds an owner the pre-check missed —
    the INSERT must never run."""
    repo, conn = _make_repo(
        dup_row={"id": 11654, "full_name": "Existing", "assigned_to": "k@balizero.com"}
    )

    with pytest.raises(DuplicatePhoneError) as exc_info:
        await repo.create_client_with_details(
            {"full_name": "New Client", "phone": "+62 821-3454-721"},
            enforce_unique_phone_core=True,
        )

    assert exc_info.value.existing_client_id == 11654
    # No INSERT INTO clients ever ran (only the dedup fetchrow was consumed).
    for call in conn.fetchrow.await_args_list[1:]:
        assert "INSERT INTO clients" not in call.args[0]
    assert conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_create_proceeds_when_no_duplicate_under_lock():
    """Innocence: no owner under lock — the create completes."""
    repo, conn = _make_repo(dup_row=None)

    record = await repo.create_client_with_details(
        {"full_name": "New Client", "phone": "+62 821-3454-721"},
        enforce_unique_phone_core=True,
    )

    assert record["id"] == 900
    # The second fetchrow was the INSERT ... RETURNING.
    assert "INSERT INTO clients" in conn.fetchrow.await_args_list[1].args[0]


@pytest.mark.asyncio
async def test_create_skips_recheck_when_duplicates_allowed():
    """allow_duplicate_phone=True path: no re-check, straight to INSERT."""
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_Tx())
    conn.execute.return_value = None
    conn.fetchrow.side_effect = [{"id": 901, "full_name": "Shared Phone"}]

    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)

    repo = ClientRepository(pool)
    record = await repo.create_client_with_details(
        {"full_name": "Shared Phone", "phone": "+62 821-3454-721"},
        enforce_unique_phone_core=False,
    )

    assert record["id"] == 901
    assert "INSERT INTO clients" in conn.fetchrow.await_args_list[0].args[0]
