"""GARUDA indexed Drive with a REVOCABLE user token, and it was revoked.

TRAUMA (2026-08-06). `drive_client.get_drive_service` loaded a per-user OAuth
row out of `google_drive_tokens`. On 2026-07-25 that token was revoked, and
from then on every nightly run died:

    google.auth.exceptions.RefreshError:
        invalid_grant: Token has been expired or revoked
    ... 141 occurrences in ~/logs/cron-tmp/garuda-indexer.log

Eleven nights, exit=1 each time, until a human re-authorised by hand. The
backend had already abandoned this credential class on 2026-05-10 —
`GoogleDriveService._refresh_token` refuses to refresh the SYSTEM row and 16
production files use `ServiceAccountDriveService` instead — but this indexer
was never migrated with them.

A service-account key does not expire and needs no consent screen. Verified
against the live API before making it preferred, because the identities are
NOT the same and this could silently have indexed an empty Drive: the GARUDA
folders are owned by a personal account, and the delegated subject
`zero@balizero.com` resolves root/photos/published anyway — they are shared.

    GUILT      — with an SA key present, the DB is never touched
    GUILT      — the SA is built with delegation, and with the ONE scope the
                 domain-wide grant actually carries
    INNOCENCE  — no SA key → the legacy DB path still works (rollback lives)
    INNOCENCE  — GARUDA_DRIVE_FORCE_OAUTH=1 backs the change out with no deploy
    CONTRACT   — an SA key handed to GOOGLE_DRIVE_CREDENTIALS_FILE is accepted,
                 because the docstring promises that entry takes either kind
"""

from __future__ import annotations

import asyncio
import json
import sys
import types

import pytest

from zantara_media.indexer import drive_client


@pytest.fixture
def sa_key(tmp_path):
    """A syntactically valid service-account key. Not a real credential."""
    p = tmp_path / "sa.json"
    p.write_text(
        json.dumps(
            {
                "type": "service_account",
                "client_email": "probe@example.iam.gserviceaccount.com",
                "private_key": "-----BEGIN PRIVATE KEY-----\nnope\n-----END PRIVATE KEY-----\n",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    )
    return p


@pytest.fixture
def fake_google(monkeypatch):
    """Stand in for google.oauth2.service_account and the discovery build.

    Captures what the code ASKS for — scopes and subject — because those are
    the two things a domain-wide grant can refuse, and getting either wrong
    fails at the token exchange with a message that reads like a broken key.
    """
    seen: dict = {}

    class _Creds:
        def with_subject(self, subject):
            seen["subject"] = subject
            return self

    class _SA:
        @staticmethod
        def from_service_account_info(info, scopes=None):
            seen["info"] = info
            seen["scopes"] = scopes
            return _Creds()

    # `from google.oauth2 import service_account` imports the PARENT package
    # and then getattrs the child, so registering only the leaf in sys.modules
    # is not enough — the google libraries are not installed in this venv.
    mod = types.ModuleType("google.oauth2.service_account")
    mod.Credentials = _SA
    pkg_oauth2 = sys.modules.get("google.oauth2") or types.ModuleType("google.oauth2")
    pkg_google = sys.modules.get("google") or types.ModuleType("google")
    monkeypatch.setattr(pkg_oauth2, "service_account", mod, raising=False)
    monkeypatch.setattr(pkg_google, "oauth2", pkg_oauth2, raising=False)
    monkeypatch.setitem(sys.modules, "google", pkg_google)
    monkeypatch.setitem(sys.modules, "google.oauth2", pkg_oauth2)
    monkeypatch.setitem(sys.modules, "google.oauth2.service_account", mod)

    monkeypatch.setattr(
        drive_client, "_build_drive_service", lambda creds: ("service", creds)
    )
    return seen


# ------------------------------------------------------------------- guilt
def test_the_service_account_is_preferred_and_the_db_is_never_touched(
    sa_key, fake_google, monkeypatch
):
    """THE migration. With a key on disk the revocable path must not run at
    all — not "run and be ignored", not "run as a fallback": not run."""

    async def exploding_db():
        pytest.fail("the legacy google_drive_tokens path was still used")

    monkeypatch.setattr(drive_client, "_load_creds_from_db", exploding_db)
    monkeypatch.setenv("GARUDA_DRIVE_SA_FILE", str(sa_key))
    monkeypatch.delenv("GARUDA_DRIVE_FORCE_OAUTH", raising=False)

    asyncio.run(drive_client.get_drive_service())
    assert fake_google["info"]["type"] == "service_account"


def test_it_delegates_with_the_single_granted_scope(sa_key, fake_google, monkeypatch):
    """Domain-wide delegation grants scopes explicitly. This SA carries only
    `drive`; asking for the `drive.readonly` the legacy OAuth path requests
    fails the whole token exchange with `unauthorized_client`, which reads like
    a broken key rather than a missing grant."""
    monkeypatch.setattr(drive_client, "_load_creds_from_db", None)
    monkeypatch.setenv("GARUDA_DRIVE_SA_FILE", str(sa_key))

    asyncio.run(drive_client.get_drive_service())

    assert fake_google["scopes"] == ["https://www.googleapis.com/auth/drive"], (
        fake_google["scopes"]
    )
    assert fake_google["subject"] == "zero@balizero.com", (
        "without impersonation the SA sees its own empty Drive, not GARUDA"
    )


def test_the_subject_is_overridable(sa_key, fake_google, monkeypatch):
    monkeypatch.setenv("GARUDA_DRIVE_SA_FILE", str(sa_key))
    monkeypatch.setenv("GARUDA_DRIVE_SUBJECT", "someone@balizero.com")

    asyncio.run(drive_client.get_drive_service())
    assert fake_google["subject"] == "someone@balizero.com"


# --------------------------------------------------------------- innocence
def test_without_a_key_the_legacy_path_still_runs(monkeypatch, tmp_path):
    """The rollback has to exist, so it has to be tested. Deleting the legacy
    branch would leave no way back if the SA turns out to be misconfigured."""
    used = []

    async def fake_db():
        used.append("db")
        return "legacy-creds"

    monkeypatch.setattr(drive_client, "_load_creds_from_db", fake_db)
    monkeypatch.setattr(drive_client, "_build_drive_service", lambda c: ("svc", c))
    monkeypatch.setenv("GARUDA_DRIVE_SA_FILE", str(tmp_path / "absent.json"))
    monkeypatch.delenv("GOOGLE_DRIVE_CREDENTIALS_FILE", raising=False)

    assert asyncio.run(drive_client.get_drive_service()) == ("svc", "legacy-creds")
    assert used == ["db"]


def test_force_oauth_backs_the_change_out_without_a_deploy(
    sa_key, monkeypatch
):
    """INNOCENCE, and it is the reason the kill-switch exists: a key present on
    disk must not be able to trap the indexer on a path that does not work."""
    used = []

    async def fake_db():
        used.append("db")
        return "legacy-creds"

    monkeypatch.setattr(drive_client, "_load_creds_from_db", fake_db)
    monkeypatch.setattr(drive_client, "_build_drive_service", lambda c: ("svc", c))
    monkeypatch.setenv("GARUDA_DRIVE_SA_FILE", str(sa_key))
    monkeypatch.setenv("GARUDA_DRIVE_FORCE_OAUTH", "1")
    monkeypatch.delenv("GOOGLE_DRIVE_CREDENTIALS_FILE", raising=False)

    asyncio.run(drive_client.get_drive_service())
    assert used == ["db"], "the kill-switch did not reach the legacy path"


# ---------------------------------------------------------------- contract
def test_an_sa_key_via_the_generic_file_var_is_accepted(
    sa_key, fake_google, monkeypatch, tmp_path
):
    """`get_drive_service`'s docstring says entry 2 takes OAuth2 *or* SA. A
    promise a function does not keep is the defect this change is about."""
    monkeypatch.setenv("GARUDA_DRIVE_SA_FILE", str(tmp_path / "absent.json"))
    monkeypatch.setenv("GOOGLE_DRIVE_CREDENTIALS_FILE", str(sa_key))

    asyncio.run(drive_client.get_drive_service())
    assert fake_google["info"]["type"] == "service_account"


def test_a_non_service_account_file_is_rejected_by_name(tmp_path):
    """The error must say WHAT it got. `_load_sa_credentials` pointed at an
    OAuth token file used to die inside the google library with a message
    about the key format."""
    bad = tmp_path / "oauth.json"
    bad.write_text(json.dumps({"type": "authorized_user", "token": "x"}))

    with pytest.raises(ValueError, match="not a service-account key"):
        drive_client._load_sa_credentials(str(bad))


# ------------------------------------------------- the scope under the grant
@pytest.fixture
def fake_oauth_db(monkeypatch):
    """Stand in for asyncpg + google.oauth2.credentials on the LEGACY path.

    Captures the scope list the refresh is built with. That list is not
    cosmetic: Google validates it against what the consent screen actually
    granted and rejects the whole refresh — it does not quietly drop an extra.
    """
    seen: dict = {}

    class _Creds:
        def __init__(self, **kw):
            seen.update(kw)

    class _Conn:
        async def fetchrow(self, *a, **k):
            return {
                "access_token": "at",
                "refresh_token": "rt",
                "expires_at": None,
            }

        async def close(self):
            seen["closed"] = True

    async def _connect(url):
        seen["dsn_given"] = bool(url)
        return _Conn()

    aspg = types.ModuleType("asyncpg")
    aspg.connect = _connect
    monkeypatch.setitem(sys.modules, "asyncpg", aspg)

    mod = types.ModuleType("google.oauth2.credentials")
    mod.Credentials = _Creds
    pkg_oauth2 = sys.modules.get("google.oauth2") or types.ModuleType("google.oauth2")
    pkg_google = sys.modules.get("google") or types.ModuleType("google")
    monkeypatch.setattr(pkg_oauth2, "credentials", mod, raising=False)
    monkeypatch.setattr(pkg_google, "oauth2", pkg_oauth2, raising=False)
    monkeypatch.setitem(sys.modules, "google", pkg_google)
    monkeypatch.setitem(sys.modules, "google.oauth2", pkg_oauth2)
    monkeypatch.setitem(sys.modules, "google.oauth2.credentials", mod)

    monkeypatch.setenv("DATABASE_URL", "postgres://probe/none")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
    return seen


def test_the_legacy_refresh_never_asks_for_a_scope_the_consent_did_not_grant(
    fake_oauth_db,
):
    """THE defect that outlived the revocation.

    The consent screen builds its authorize URL with ONE scope
    (`admin_drive_auth.py:47` — `scope=…/auth/drive`, singular). This call site
    asked for `drive` AND `drive.readonly`, and Google answers a refresh that
    names an ungranted scope with `invalid_scope: Bad Request`.

    It was invisible for as long as the credential was also revoked, because
    `invalid_grant` is decided first. Measured on Pro 2026-08-06: the night
    after the re-auth, `invalid_grant` vanished and `invalid_scope` took its
    place — 14 runs of it in the log, back to 2026-06-28.
    """
    asyncio.run(drive_client._load_creds_from_db())

    assert "drive.readonly" not in " ".join(fake_oauth_db["scopes"]), (
        "asking for a scope the grant never contained fails the WHOLE refresh; "
        "Google does not ignore the extra"
    )
    assert fake_oauth_db["scopes"] == ["https://www.googleapis.com/auth/drive"], (
        "must be exactly the scope admin_drive_auth.py sends to the consent "
        "screen — anything else is a refresh that cannot succeed"
    )


def test_the_two_scope_lists_are_separate_objects(fake_oauth_db):
    """Innocence, and a design assertion.

    SA_SCOPES and OAUTH_SCOPES hold the same string today. They are NOT the
    same thing: one is bounded by the Workspace admin console's delegation, the
    other by what a human approved on a consent screen. Sharing one constant
    would make widening the delegation silently widen the user grant's request
    — which is precisely the class of mistake this test file exists for.
    """
    assert drive_client.SA_SCOPES is not drive_client.OAUTH_SCOPES
    asyncio.run(drive_client._load_creds_from_db())
    assert fake_oauth_db["scopes"] is drive_client.OAUTH_SCOPES, (
        "the legacy path must read OAUTH_SCOPES, not an inlined literal"
    )
