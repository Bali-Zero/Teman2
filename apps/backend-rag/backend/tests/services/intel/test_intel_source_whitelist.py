"""
Source whitelist: gov.id + known aggregators.
"""
from __future__ import annotations

import pytest

from backend.services.intel.intel_source_whitelist import (
    INTEL_SOURCE_WHITELIST,
    is_whitelisted,
)


def test_gov_id_domain_is_whitelisted() -> None:
    assert is_whitelisted("https://imigrasi.go.id/article/123")
    assert is_whitelisted("https://bkpm.go.id/news/456")
    assert is_whitelisted("https://www.pajak.go.id/spt-2026")


def test_unknown_domain_not_whitelisted() -> None:
    assert not is_whitelisted("https://random-blog.example.com")


def test_invalid_url_returns_false() -> None:
    assert not is_whitelisted("not-a-url")
    assert not is_whitelisted("")


def test_subdomain_of_whitelisted_root_allowed() -> None:
    assert is_whitelisted("https://oss.go.id/")
    assert is_whitelisted("https://www.bkpm.go.id/")


def test_known_aggregators_whitelisted() -> None:
    # At least Hukumonline and similar should be in the list (decision #3).
    assert any("hukumonline" in d for d in INTEL_SOURCE_WHITELIST)


def test_whitelisted_domain_with_explicit_port_matches() -> None:
    assert is_whitelisted("https://bkpm.go.id:443/path")
    assert is_whitelisted("https://imigrasi.go.id:80/article")
    assert is_whitelisted("https://www.bkpm.go.id:8080/x")
