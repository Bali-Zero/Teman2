"""
Source whitelist for Intel pipeline (decision #3).

Any staging doc whose source domain is not in the whitelist is flagged
`needs_review=True` regardless of validator score. Curated list rather than
regex to avoid false confidence on gov-looking typo-squats.
"""
from __future__ import annotations

from urllib.parse import urlparse


INTEL_SOURCE_WHITELIST: frozenset[str] = frozenset({
    # Government (Indonesia) — bare domains + www
    "imigrasi.go.id",
    "bkpm.go.id",
    "pajak.go.id",
    "oss.go.id",
    "kemenkeu.go.id",
    "kemlu.go.id",
    "kemenkumham.go.id",
    "dpr.go.id",
    "setkab.go.id",
    "peraturan.go.id",
    "jdih.go.id",
    "bi.go.id",
    "ojk.go.id",
    # Known legal/regulatory aggregators
    "hukumonline.com",
    "www.hukumonline.com",
    "lawphil.net",
    "hukumlinemedia.com",
    # Major Indonesian news (vetted for Bali Zero use)
    "kompas.com",
    "tempo.co",
    "detik.com",
    "antaranews.com",
    "jakartaglobe.id",
    "thejakartapost.com",
})


def is_whitelisted(url: str) -> bool:
    """Return True if the url's host is in INTEL_SOURCE_WHITELIST.

    Supports subdomain matching: www.bkpm.go.id is whitelisted if
    bkpm.go.id is in the set.
    """
    if not url:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return False
    if not host:
        return False
    # Direct match
    if host in INTEL_SOURCE_WHITELIST:
        return True
    # Subdomain of a whitelisted root
    parts = host.split(".")
    for i in range(1, len(parts) - 1):
        parent = ".".join(parts[i:])
        if parent in INTEL_SOURCE_WHITELIST:
            return True
    return False


__all__ = ["INTEL_SOURCE_WHITELIST", "is_whitelisted"]
