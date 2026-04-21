"""
E2E integration conftest — re-exports all partner fixtures.

The partner unit-test conftest.py is a standard Python file that defines
pytest fixtures using pytest_asyncio. We import everything from it so that
fixtures (db_conn, user_factory, partner_factory, practice_factory,
client_factory, referral_factory) are available in this directory too.
"""
# ruff: noqa: F401, F403
from backend.tests.services.crm.partners.conftest import (  # noqa: F401
    db_conn,
    user_factory,
    partner_factory,
    practice_factory,
    referral_factory,
    client_factory,
    commission_factory,
    admin,
    pytest_unconfigure,
    _shield,
    _SHIELDED,
    _BACKEND_RAG_DIR,
    _DEFAULT_DB_URL,
    _SCHEMA_SQL,
    _TEARDOWN_SQL,
    _UUIDWithId,
    _IntWithId,
)
