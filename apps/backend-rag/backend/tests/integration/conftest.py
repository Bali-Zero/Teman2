"""
E2E integration conftest — re-exports all partner fixtures.

The partner unit-test conftest.py is a standard Python file that defines
pytest fixtures using pytest_asyncio. We import everything from it so that
fixtures (db_conn, user_factory, partner_factory, practice_factory,
client_factory, referral_factory) are available in this directory too.
"""

# ruff: noqa: F401, F403
from backend.tests.services.crm.partners.conftest import (  # noqa: F401
    _BACKEND_RAG_DIR,
    _DEFAULT_DB_URL,
    _SCHEMA_SQL,
    _SHIELDED,
    _TEARDOWN_SQL,
    _IntWithId,
    _shield,
    _UUIDWithId,
    admin,
    client_factory,
    commission_factory,
    db_conn,
    partner_factory,
    practice_factory,
    pytest_unconfigure,
    referral_factory,
    user_factory,
)
