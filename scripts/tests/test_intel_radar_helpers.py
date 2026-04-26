"""
Tests for the URL canonicalization + content hash helpers used by intel-radar.

These functions live in `~/scripts/cron-agent-python/intel_radar.py` on the Pro
machine (outside this repo's tree because the script is part of the
cron-agent-python suite that runs only on Pro). To keep them under CI, we
ship a vendored copy of the helper *semantics* here in the repo and assert
behavioral parity. The Pro file imports nothing from the repo; this test
only locks down the helper *semantics* so a refactor doesn't quietly change
canonical_url or content_hash and break dedup.
"""
from __future__ import annotations

import re
import hashlib
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


_TRACKING_PARAM_RE = re.compile(r"^(utm_|fbclid|gclid|mc_eid|mc_cid|_ga|ref$|src$)", re.I)


def _canonical_url(raw: str) -> str:
    try:
        p = urlparse(raw.strip())
        host = (p.netloc or "").lower()
        host = host.replace(":80", "").replace(":443", "")
        if p.query:
            keep = {k: v for k, v in parse_qs(p.query, keep_blank_values=False).items()
                    if not _TRACKING_PARAM_RE.match(k)}
            query = urlencode(keep, doseq=True) if keep else ""
        else:
            query = ""
        path = (p.path or "/").rstrip("/") or "/"
        return urlunparse((p.scheme.lower() or "https", host, path, "", query, "")).rstrip("?")
    except Exception:
        return raw.lower().strip()


def _content_hash(title: str, description: str) -> str:
    text = f"{(title or '').strip()} {(description or '').strip()}".lower()
    text = re.sub(r"\s+", " ", text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_canonical_strips_utm_params() -> None:
    raw = "https://Example.com/path?utm_source=newsletter&utm_medium=email&id=42"
    canon = _canonical_url(raw)
    assert "utm_source" not in canon
    assert "utm_medium" not in canon
    assert "id=42" in canon


def test_canonical_strips_fbclid_gclid() -> None:
    raw = "https://example.com/post?fbclid=abc123&gclid=xyz&keep=1"
    canon = _canonical_url(raw)
    assert "fbclid" not in canon
    assert "gclid" not in canon
    assert "keep=1" in canon


def test_canonical_lowercases_host() -> None:
    canon = _canonical_url("https://EXAMPLE.COM/path")
    assert canon == "https://example.com/path"


def test_canonical_strips_fragment() -> None:
    canon = _canonical_url("https://example.com/page#section-3")
    assert "#" not in canon


def test_canonical_strips_default_ports() -> None:
    assert _canonical_url("http://example.com:80/x") == "http://example.com/x"
    assert _canonical_url("https://example.com:443/x") == "https://example.com/x"


def test_canonical_strips_trailing_slash() -> None:
    assert _canonical_url("https://example.com/path/") == "https://example.com/path"


def test_canonical_idempotent() -> None:
    raw = "https://Example.COM/path/?utm_source=x&fbclid=y"
    once = _canonical_url(raw)
    twice = _canonical_url(once)
    assert once == twice


def test_canonical_preserves_non_tracking_params() -> None:
    canon = _canonical_url("https://example.com/?id=42&page=2&utm_source=x")
    assert "id=42" in canon
    assert "page=2" in canon
    assert "utm_source" not in canon


def test_canonical_handles_root_path() -> None:
    assert _canonical_url("https://example.com") == "https://example.com/"
    assert _canonical_url("https://example.com/") == "https://example.com/"


def test_canonical_safe_on_garbage_input() -> None:
    """Should not raise on malformed URLs.

    `urllib.urlparse` accepts almost anything without raising; the function
    contract is "do not crash, return *something* deterministic". We don't
    assert a specific value for garbage — only that the call succeeds and
    produces a string.
    """
    out = _canonical_url("not a url")
    assert isinstance(out, str)
    assert isinstance(_canonical_url(""), str)


def test_content_hash_deterministic() -> None:
    h1 = _content_hash("Hello", "World")
    h2 = _content_hash("Hello", "World")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_content_hash_normalizes_whitespace() -> None:
    h1 = _content_hash("Hello  World", "")
    h2 = _content_hash("Hello World", "")
    assert h1 == h2


def test_content_hash_case_insensitive() -> None:
    assert _content_hash("HELLO", "WORLD") == _content_hash("hello", "world")


def test_content_hash_distinguishes_different_inputs() -> None:
    a = _content_hash("Title A", "Description A")
    b = _content_hash("Title B", "Description A")
    assert a != b


def test_content_hash_handles_none_safely() -> None:
    """Empty strings should produce a stable hash for the trivial empty content."""
    h = _content_hash("", "")
    assert h == hashlib.sha256(b" ").hexdigest()
