"""One permission list, not two.

`ZohoOAuthService.SCOPES` is the declaration of what this system needs from
Zoho. `/admin/zoho/auth` is the URL humans are actually sent to — the mail loop
names it verbatim in its own error message when a grant is too narrow.

Those two disagreed. The service asked for `ZohoMail.folders.READ`; the endpoint
carried its own hardcoded copy (`ZohoInvoice.fullaccess.all,ZohoMail.messages.ALL`)
that mentioned no folders at all. So every consent granted through the endpoint
produced a token that could read mail and could not see a single folder, and the
failure surfaced days later as `UNABLE_TO_PARSE_DATA_TYPE` from Zoho — an error
that points at them and not at us.

Nothing about that was detectable by reading either file alone. These tests
compare the two.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from backend.app.routers import admin_zoho_auth
from backend.services.integrations.zoho_oauth_service import ZohoOAuthService

ADMIN_SECRET = "test-admin-secret"


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_SECRET_KEY", ADMIN_SECRET)
    monkeypatch.setattr(
        admin_zoho_auth.settings, "zoho_client_id", "cid.test", raising=False
    )
    monkeypatch.setattr(
        admin_zoho_auth.settings,
        "zoho_redirect_uri",
        "https://example.test/cb",
        raising=False,
    )


def _call() -> dict:
    return asyncio.run(admin_zoho_auth.admin_zoho_auth(x_admin_secret=ADMIN_SECRET))


class TestScopeHasOneSource:
    def test_every_declared_scope_reaches_the_consent_url(self, wired: None) -> None:
        """The guilt case: a scope the service needs but the URL omits."""
        result = _call()
        missing = [s for s in ZohoOAuthService.SCOPES if s not in result["scope"]]
        assert not missing, f"consent URL omits declared scopes: {missing}"
        for scope in ZohoOAuthService.SCOPES:
            assert scope in result["auth_url"]

    def test_folder_access_is_present_in_both_directions(self, wired: None) -> None:
        """The specific pair this whole incident turned on.

        READ alone is not enough: listing folders succeeds with it while
        `POST /folders` answers 401 INVALID_OAUTHSCOPE, so a mailbox can be read
        and never provisioned.
        """
        assert "ZohoMail.folders.READ" in ZohoOAuthService.SCOPES
        assert "ZohoMail.folders.CREATE" in ZohoOAuthService.SCOPES
        assert "ZohoMail.folders.READ" in _call()["scope"]
        assert "ZohoMail.folders.CREATE" in _call()["scope"]

    def test_invoice_access_is_not_dropped(self, wired: None) -> None:
        """Innocence: the endpoint serves Invoice too, and rewiring the mail
        scopes must not quietly cost the other consumer its access."""
        assert "ZohoInvoice.fullaccess.all" in _call()["scope"]

    def test_no_folder_delete_is_requested(self, wired: None) -> None:
        """Least privilege, pinned. Nothing here deletes folders, so nothing here
        asks to. `folders.ALL` would be the easy way to make the create work and
        would hand over deletion as well."""
        scope = _call()["scope"]
        assert "ZohoMail.folders.DELETE" not in scope
        assert "ZohoMail.folders.ALL" not in scope


class TestTheEndpointTellsTheTruthAboutTheClient:
    def test_it_names_the_self_client_trap(self, wired: None) -> None:
        """A Self Client has no redirect URI, so `auth_url` cannot work for it —
        the browser says 'Invalid Redirect Uri' before any consent screen. A
        reader who follows auth_url blindly loses an hour to that."""
        result = _call()
        assert "Self Client".lower() in result["client_type_note"].lower()
        assert result["instructions_self_client"]
        assert result["instructions_web_client"]

    def test_the_admin_secret_is_still_required(self, wired: None) -> None:
        """Innocence: none of the above weakened the gate on the endpoint."""
        with pytest.raises(HTTPException, match="Invalid admin secret") as caught:
            asyncio.run(admin_zoho_auth.admin_zoho_auth(x_admin_secret="wrong"))
        assert caught.value.status_code == 401
