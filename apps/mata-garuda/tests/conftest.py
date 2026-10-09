"""Suite-wide guards for the mata-garuda tests."""
from __future__ import annotations

import pytest

from mata_garuda.tools import lhkpn_tools


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
