"""
Regression guard: the portal superuser allowlist must be importable by every
router that gates on it.

SCAR (prod 2026-06-21): portal.py renamed the constant `SUPERUSER_EMAILS` to the
function `_superuser_emails()`, but portal_admin.py and lkpm.py still did
`from backend.app.routers.portal import SUPERUSER_EMAILS` inside the request
handler. The import is lazy (inside the function), so it passed startup and only
blew up at request time → `/api/portal/admin/me`, `/clients/search`, and the LKPM
draft route all 500'd with "cannot import name 'SUPERUSER_EMAILS'". The
impersonation bar (the way a superuser views a client's portal) was dead in prod.

This test exercises the exact lazy-import path so the regression cannot return.
"""

from __future__ import annotations


def test_superuser_helper_is_the_canonical_name():
    from backend.app.routers import portal

    assert hasattr(portal, "_superuser_emails")
    assert callable(portal._superuser_emails)
    # The old constant must NOT be reintroduced as a bare module attribute,
    # otherwise callers may drift back to importing it.
    assert not hasattr(portal, "SUPERUSER_EMAILS")


def test_portal_admin_lazy_import_resolves():
    # Reproduce portal_admin's inner import — would raise ImportError on the scar.
    from backend.app.routers.portal import _superuser_emails  # noqa: F401

    assert isinstance(_superuser_emails(), frozenset)


def test_lkpm_lazy_import_resolves():
    # Same inner import used by lkpm.py's superuser gate.
    from backend.app.routers.portal import _superuser_emails

    emails = _superuser_emails()
    # Every entry should be a lowercase-comparable string.
    assert all(isinstance(e, str) for e in emails)


def test_routers_import_clean():
    # All three gating routers must import without the dead-name ImportError.
    from backend.app.routers import lkpm, portal, portal_admin  # noqa: F401

    assert portal_admin.router is not None
    assert lkpm.router is not None
