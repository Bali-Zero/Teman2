"""Suite-wide guards for the mata-garuda tests."""
from __future__ import annotations

import pytest

from mata_garuda.tools import brevo_tools, lhkpn_tools


@pytest.fixture
def allow_real_email():
    """Opt-in marker: a test requesting this lets brevo_tools resolve a real key."""


@pytest.fixture(autouse=True)
def _no_real_email(request, monkeypatch):
    """Keep the suite from sending real email.

    Importing mata_garuda loads BREVO_API_KEY from the host's secrets file, so on
    Pro or Mini an unmocked weekly-digest run would mail the owner through Brevo.
    The sender sees no key, exactly as on a host without one.
    """
    if "allow_real_email" in request.fixturenames:
        return
    monkeypatch.setattr(brevo_tools, "_resolve_key", lambda: None)


@pytest.fixture
def allow_osint_launch():
    """Opt-in marker: a test requesting this reaches the real OSINT-Nexus launcher."""


@pytest.fixture(autouse=True)
def _no_osint_nexus_launch(request, monkeypatch):
    """Keep the suite from starting the OSINT-Nexus scraper.

    The default interpreter path exists on Pro, so an unmocked LHKPN lookup would
    drive the real scraper against the government portal with test data.
    """
    if "allow_osint_launch" in request.fixturenames:
        return

    def _blocked(**_kwargs):
        return {
            "ok": False,
            "error": "osint_nexus_launch_blocked_in_tests",
            "records": [],
            "profile": None,
            "pdf_paths": [],
        }

    monkeypatch.setattr(lhkpn_tools, "_invoke_osint_nexus", _blocked)
