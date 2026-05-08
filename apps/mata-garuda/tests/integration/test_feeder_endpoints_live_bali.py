"""Live endpoint smoke-tests for the Bali regulation_bali feeder.

These tests hit the real public portals listed in BALI_PORTAL_IDS and assert
HTTP 200 + a non-trivial body. Skipped by default; opt in with:

    MATA_GARUDA_LIVE_ENDPOINTS=1 pytest tests/integration/test_feeder_endpoints_live_bali.py

Companion to test_feeder_endpoints_live.py (Phase 1.5 PR-A national/imm
endpoints). Kept separate so PR-A can merge without this file existing —
when both PRs land, refactoring into one parametrized table is trivial.

Why this exists (cf. cicatrix `test infrastructure mock != production
stack`, Sprint 1.B 2026-05-02): unit tests with mocked httpx pass even
when the upstream URL has been moved or rotted. This is the integration
counterpart that talks to the real internet.

Convention:
- One row per portal-id from BALI_PORTAL_IDS. Adding a new id means
  adding a row here AND in gov_apis_inventory.json.
- Assert 200 + body >1000 chars to filter cloudflare splash / placeholder.
- 20s timeout — some kabupaten portals are slow but should still respond.
- follow_redirects so jdih portals doing 301 to https variant pass.
"""
from __future__ import annotations

import os

import httpx
import pytest

LIVE = os.environ.get("MATA_GARUDA_LIVE_ENDPOINTS") == "1"

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not LIVE, reason="set MATA_GARUDA_LIVE_ENDPOINTS=1 to run"),
]

# Mirror of gov_apis_inventory.json regulation_bali rows.
# Update both files together when adding a portal.
BALI_ENDPOINTS = [
    # Original 4 (already in Phase 1).
    ("jdih_baliprov", "https://jdih.baliprov.go.id"),
    ("jdih_badungkab", "https://jdih.badungkab.go.id"),
    ("jdih_gianyarkab", "https://jdih.gianyarkab.go.id"),
    ("jdih_denpasarkota", "https://jdih.denpasarkota.go.id"),
    # Phase 1.5 PR-B additions.
    ("jdih_tabanankab", "https://jdih.tabanankab.go.id"),
    ("jdih_bulelengkab", "https://jdih.bulelengkab.go.id"),
    ("jdih_klungkungkab", "https://jdih.klungkungkab.go.id"),
    ("jdih_karangasemkab", "https://jdih.karangasemkab.go.id"),
    ("pemkab_bangli", "https://www.banglikab.go.id/berita"),
    ("pemkab_jembrana", "https://jembranakab.go.id/articles"),
]


# Portals known to ship an incomplete TLS cert chain. They respond 200 in
# curl/browsers (which use a different root truststore) but Python's certifi
# bundle can't verify them. The production feeder picks them up via the
# probe gate which uses verify=False on retry; here we keep verify on so we
# can detect if/when the server-side chain is fixed.
TLS_CHAIN_ISSUE_PORTALS = {"jdih_tabanankab"}


@pytest.mark.parametrize("portal_id,url", BALI_ENDPOINTS)
def test_bali_endpoint_reachable(portal_id: str, url: str, request) -> None:
    """Each Bali portal must return 200 with substantive body."""
    if portal_id in TLS_CHAIN_ISSUE_PORTALS:
        request.applymarker(
            pytest.mark.xfail(
                reason=(
                    f"{portal_id}: server-side TLS cert chain is incomplete; "
                    "Python's truststore can't verify. curl/browsers accept "
                    "it. Drop from this set when the host fixes the chain."
                ),
                strict=False,
            )
        )

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "mata-garuda-smoke/1.0"})

    assert resp.status_code == 200, (
        f"{portal_id} ({url}) returned HTTP {resp.status_code} — "
        f"portal may be down or moved. Check gov_apis_inventory.json + "
        f"BALI_PORTAL_IDS in nb_intel_regulation_bali.py."
    )
    assert len(resp.text) > 1000, (
        f"{portal_id} ({url}) body is {len(resp.text)} chars — "
        f"likely a splash/error page. Investigate."
    )
