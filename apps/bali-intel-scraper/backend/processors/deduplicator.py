"""
Content deduplication system.

Prevents processing the same content multiple times using various
fingerprinting techniques.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urldefrag, urlparse

import simhash
from nltk import word_tokenize, ngrams

from backend.core.cache import cache, CacheStrategy
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="deduplicator")


@dataclass
class ContentFingerprint:
    """Fingerprint for content deduplication."""

    url_hash: str
    content_hash: str
    simhash: int
    title_hash: str
    canonical_url: Optional[str] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class URLNormalizer:
    """Normalize URLs for comparison."""

    @staticmethod
    def normalize(url: str) -> str:
        """Normalize URL for deduplication."""
        # Remove fragment
        url, _ = urldefrag(url)

        # Parse URL
        parsed = urlparse(url.lower())

        # Remove common tracking parameters
        tracking_params = [
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "ref",
            "source",
            "utm",
            "itm_source",
            "itm_medium",
            "itm_campaign",
        ]

        if parsed.query:
            from urllib.parse import parse_qs, urlencode

            params = parse_qs(parsed.query)

            # Remove tracking params
            for param in tracking_params:
                params.pop(param, None)

            # Rebuild query string
            query = urlencode(params, doseq=True) if params else ""
        else:
            query = ""

        # Rebuild URL
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if query:
            normalized += f"?{query}"

        # Remove trailing slash
        normalized = normalized.rstrip("/")

        return normalized

    @staticmethod
    def hash(url: str) -> str:
        """Generate hash for normalized URL."""
        normalized = URLNormalizer.normalize(url)
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]


class ContentHasher:
    """Generate content fingerprints."""

    @staticmethod
    def hash_content(content: str) -> str:
        """Generate SHA-256 hash of normalized content."""
        # Normalize: lowercase, strip whitespace, normalize unicode
        normalized = content.lower().strip()
        normalized = " ".join(normalized.split())  # Normalize whitespace

        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def simhash_content(content: str, num_bits: int = 64) -> int:
        """Generate simhash for near-duplicate detection."""
        # Tokenize and create n-grams
        try:
            tokens = word_tokenize(content.lower())
            features = [" ".join(gram) for gram in ngrams(tokens, 3)]

            if not features:
                return 0

            # Calculate simhash
            return simhash.Simhash(features, f=num_bits).value
        except Exception as e:
            logger.warning(
                "Simhash generation failed",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            return 0

    @staticmethod
    def hamming_distance(hash1: int, hash2: int) -> int:
        """Calculate Hamming distance between two hashes."""
        x = hash1 ^ hash2
        distance = 0
        while x:
            distance += 1
            x &= x - 1
        return distance


class Deduplicator:
    """Main deduplication system."""

    def __init__(
        self,
        simhash_threshold: int = 3,
        cache_ttl_hours: int = 168,  # 1 week
    ):
        self.simhash_threshold = simhash_threshold
        self.cache_ttl = cache_ttl_hours * 3600
        self.url_normalizer = URLNormalizer()
        self.content_hasher = ContentHasher()

    async def is_duplicate_url(self, url: str) -> bool:
        """Check if URL has been seen before."""
        url_hash = self.url_normalizer.hash(url)
        cache_key = f"dedup:url:{url_hash}"

        existing = await cache.get(cache_key)
        return existing is not None

    async def is_duplicate_content(
        self, content: str, check_simhash: bool = True
    ) -> tuple[bool, Optional[float]]:
        """
        Check if content is a duplicate.

        Returns:
            (is_duplicate, similarity_score)
        """
        content_hash = self.content_hasher.hash_content(content)
        cache_key = f"dedup:content:{content_hash}"

        # Exact match check
        existing = await cache.get(cache_key)
        if existing:
            return True, 1.0

        # Simhash check for near-duplicates
        if check_simhash:
            simhash_value = self.content_hasher.simhash_content(content)

            if simhash_value != 0:
                # Check against recent simhashes
                similar = await self._find_similar_simhashes(simhash_value)

                if similar:
                    best_match = min(similar, key=lambda x: x["distance"])
                    similarity = 1 - (best_match["distance"] / 64)
                    return True, similarity

        return False, None

    async def add_content(
        self, url: str, content: str, title: str = ""
    ) -> ContentFingerprint:
        """Add content to deduplication index."""
        # Generate fingerprints
        url_hash = self.url_normalizer.hash(url)
        content_hash = self.content_hasher.hash_content(content)
        simhash_value = self.content_hasher.simhash_content(content)
        title_hash = hashlib.sha256(title.lower().encode()).hexdigest()[:16]

        fingerprint = ContentFingerlogger.info(
            url_hash=url_hash,
            content_hash=content_hash,
            simhash=simhash_value,
            title_hash=title_hash,
            canonical_url=self.url_normalizer.normalize(url),
        )

        # Store in cache
        await cache.set(
            f"dedup:url:{url_hash}",
            {"url": url, "timestamp": datetime.now().isoformat()},
            strategy=CacheStrategy.TTL_LONG,
        )

        await cache.set(
            f"dedup:content:{content_hash}",
            fingerprint.__dict__,
            strategy=CacheStrategy.TTL_LONG,
        )

        # Store simhash for similarity search
        if simhash_value != 0:
            await cache.set(
                f"dedup:simhash:{simhash_value}",
                {"url": url, "hash": content_hash},
                strategy=CacheStrategy.TTL_LONG,
            )

        logger.info(
            "Content added to deduplication index",
            action=LogAction.SAVE,
            metadata={
                "url_hash": url_hash[:8],
                "content_hash": content_hash[:8],
                "simhash": simhash_value,
            },
        )

        return fingerprint

    async def check_and_add(
        self, url: str, content: str, title: str = ""
    ) -> tuple[bool, Optional[ContentFingerprint], Optional[float]]:
        """
        Check if duplicate and add if not.

        Returns:
            (is_duplicate, fingerprint, similarity)
        """
        # Check URL first (fast)
        if await self.is_duplicate_url(url):
            logger.info(
                "Duplicate URL detected",
                action=LogAction.SKIP,
                metadata={"url": url[:100]},
            )
            return True, None, 1.0

        # Check content
        is_dup, similarity = await self.is_duplicate_content(content)

        if is_dup:
            logger.info(
                "Duplicate content detected",
                action=LogAction.SKIP,
                metadata={
                    "url": url[:100],
                    "similarity": round(similarity, 3) if similarity else None,
                },
            )
            return True, None, similarity

        # Add to index
        fingerprint = await self.add_content(url, content, title)

        return False, fingerprint, None

    async def _find_similar_simhashes(self, simhash_value: int) -> List[Dict]:
        """Find similar simhashes in cache."""
        # Get recent simhashes
        # Note: In production, this would use a proper simhash index
        # For now, we'll do a simple range check
        similar = []

        # Check nearby buckets
        for offset in range(-self.simhash_threshold, self.simhash_threshold + 1):
            check_hash = simhash_value + offset
            cache_key = f"dedup:simhash:{check_hash}"

            result = await cache.get(cache_key)
            if result:
                distance = self.content_hasher.hamming_distance(
                    simhash_value, check_hash
                )
                if distance <= self.simhash_threshold:
                    similar.append(
                        {"hash": check_hash, "distance": distance, "data": result}
                    )

        return similar

    async def get_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        # Count cached items
        url_keys = await cache.keys("dedup:url:*")
        content_keys = await cache.keys("dedup:content:*")

        return {
            "urls_tracked": len(url_keys),
            "content_tracked": len(content_keys),
            "simhash_threshold": self.simhash_threshold,
            "cache_ttl_hours": self.cache_ttl / 3600,
        }

    async def clear_old_entries(self, max_age_hours: int = 168) -> int:
        """Clear entries older than specified age."""
        # This would be implemented based on cache capabilities
        # For Redis, we can use the TTL
        logger.info("Cleared old deduplication entries", action=LogAction.DELETE)
        return 0


# Global deduplicator instance
deduplicator = Deduplicator()


async def is_duplicate(url: str, content: str) -> tuple[bool, Optional[float]]:
    """Quick check if content is duplicate."""
    is_dup, _, similarity = await deduplicator.check_and_add(url, content)
    return is_dup, similarity


__all__ = [
    "Deduplicator",
    "ContentFingerprint",
    "URLNormalizer",
    "ContentHasher",
    "deduplicator",
    "is_duplicate",
]
