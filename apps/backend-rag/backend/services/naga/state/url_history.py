"""URLHistory — deduplicated URL tracking for Naga research sessions.

Normalises URLs before storage so tracking-parameter variants and
cosmetic differences (fragments, trailing slashes) collapse into
a single canonical form.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Query-string parameters injected by ad/analytics platforms.
# Stripped during normalization so the same content URL is not fetched twice.
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "ref",
        "source",
    }
)


def _normalize_url(raw: str) -> str:
    """Return a canonical form of *raw* suitable for dedup comparison.

    Steps:
    1. Parse with ``urlparse``.
    2. Strip fragment (``#…``).
    3. Remove tracking query params.
    4. Sort remaining params for order-independent matching.
    5. Strip trailing ``/`` from the path.
    """
    parsed = urlparse(raw)

    # Strip tracking params, keep the rest, sort for determinism
    qs = parse_qs(parsed.query, keep_blank_values=True)
    clean_qs = {k: v for k, v in sorted(qs.items()) if k not in _TRACKING_PARAMS}
    query_str = urlencode(clean_qs, doseq=True)

    # Strip trailing slash from path (but preserve "/" root)
    path = parsed.path.rstrip("/") or "/"

    # Reconstruct without fragment
    normalised = urlunparse(
        (parsed.scheme, parsed.netloc, path, parsed.params, query_str, "")
    )
    return normalised


class URLHistory:
    """Set-like container that deduplicates URLs after normalization."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    # --- core API -----------------------------------------------------------

    def add(self, url: str) -> None:
        """Register *url* as visited (after normalization)."""
        self._seen.add(_normalize_url(url))

    def is_new(self, url: str) -> bool:
        """Return ``True`` if *url* has **not** been seen before."""
        return _normalize_url(url) not in self._seen

    def add_many(self, urls: list[str]) -> list[str]:
        """Add multiple URLs; return only those that were genuinely new.

        Preserves input order. Duplicates *within* the batch are handled
        correctly: the first occurrence is reported as new, subsequent
        occurrences are not.
        """
        new_urls: list[str] = []
        for url in urls:
            norm = _normalize_url(url)
            if norm not in self._seen:
                self._seen.add(norm)
                new_urls.append(url)
        return new_urls

    # --- properties ---------------------------------------------------------

    @property
    def count(self) -> int:
        """Number of unique (normalized) URLs tracked."""
        return len(self._seen)
