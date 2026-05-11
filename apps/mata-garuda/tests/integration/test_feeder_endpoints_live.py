"""Live endpoint smoke-tests for Phase 1 setup_team feeders.

These tests hit the real public portals and assert HTTP 200 + a non-trivial
body. They are skipped by default to keep `pytest` fast and offline-safe;
opt in with the env var below.

    MATA_GARUDA_LIVE_ENDPOINTS=1 pytest tests/integration/test_feeder_endpoints_live.py

Why this exists (cf. cicatrix `test infrastructure mock != production stack`,
Sprint 1.B 2026-05-02): unit tests with mocked httpx pass even when the
upstream URL has been moved or rotted. Phase 1's first cron run revealed
3 layers silently 404-ing because their mock-only tests were green. This
suite is the integration counterpart — it talks to the real internet.

Convention:
- Each endpoint defined in a feeder module's `*_URL` constant gets ONE
  smoke-test parametrized below. Adding a new feeder source means adding
  a row here.
- We assert 200 and `len(body) > 1000` to filter out cloudflare splash
  pages or empty redirects.
- We follow redirects (most jdih.* portals 301 to https variants).
- 15s timeout per request — disparda.baliprov.go.id is slow (~30s sometimes)
  but is not in PR-A scope; use 15s as a generous default for the 5
  endpoints currently shipped.
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

ENDPOINTS = [
    # Phase 1.5 PR-A baseline (regulation + immigration national + media).
    ("imigrasi_berita", "https://www.imigrasi.go.id/berita"),
    ("kemenkum_berita_utama", "https://www.kemenkum.go.id/berita-utama"),
    ("jdihn_dokumen_hukum", "https://jdihn.go.id/dokumen-hukum?keyword=2026"),
    ("setkab_category_berita", "https://setkab.go.id/category/berita/"),
    ("tempo_imigrasi_tag", "https://www.tempo.co/tag/imigrasi"),
    # Phase 1.5 PR-C: regulation tier-2.
    ("bpk_search", "https://peraturan.bpk.go.id/Search?type=peraturan"),
    ("peraturan_go_id", "https://www.peraturan.go.id/"),
    # Phase 1.5 PR-C: 3 Bali Kantor Imigrasi (regional).
    (
        "kanim_ngurahrai",
        "https://ngurahrai.imigrasi.go.id/berita-dan-siaran-pers/",
    ),
    ("kanim_denpasar", "https://denpasar.imigrasi.go.id/kat/berita"),
    (
        "kanim_singaraja",
        "https://singaraja.imigrasi.go.id/berita-keimigrasian/",
    ),
]


@pytest.mark.parametrize("name,url", ENDPOINTS)
def test_endpoint_reachable(name: str, url: str) -> None:
    """Each Phase 1.5 source must return 200 with substantive body."""
    # 30s timeout — some Bali offices and the regulation portals can be
    # slow under load (live verified 2026-05-08).
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "mata-garuda-smoke/1.0"})

    assert resp.status_code == 200, (
        f"{name} ({url}) returned HTTP {resp.status_code} — "
        f"endpoint may have moved. Update the feeder constant + the row "
        f"in test_feeders.py and this list."
    )
    assert len(resp.text) > 1000, (
        f"{name} ({url}) returned body of {len(resp.text)} chars — "
        f"likely a placeholder/error page. Investigate."
    )
