"""
Rule-Based Deduplicator (No LLM)
Zero cost, instant, deterministic duplicate detection
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime


class RuleBasedDeduplicator:
    """
    3-layer duplicate detection without LLM
    
    Layer 1: Exact URL match (O(1))
    Layer 2: Normalized title hash (O(1))
    Layer 3: Keyword overlap + date proximity (O(n) but n=100)
    """

    def __init__(self, registry_path: str = "data/published_articles.json"):
        self.registry_path = Path(registry_path)
        self.registry = self.load_registry()

        # Stopwords (common words to ignore)
        self.stopwords = {
            'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
            'or', 'but', 'is', 'are', 'was', 'were', 'has', 'have', 'had',
            'this', 'that', 'these', 'those', 'from', 'with', 'as', 'by'
        }

        # Key immigration/visa terms for NER-like extraction
        self.key_terms = {
            'kitas', 'kitap', 'visa', 'evisa', 'voa', 'golden', 'digital',
            'nomad', 'retirement', 'investor', 'work', 'permit', 'immigration',
            'imigrasi', 'extend', 'extension', 'second', 'home', 'indonesia',
            'bali', 'jakarta', 'passport', 'residence', 'stay'
        }

    def load_registry(self) -> dict:
        """Load published articles registry"""
        if not self.registry_path.exists():
            return {
                "urls": set(),
                "title_hashes": set(),
                "recent_100": [],
                "all_articles": []
            }

        with open(self.registry_path) as f:
            data = json.load(f)
            # Convert lists to sets for O(1) lookup
            data["urls"] = set(data.get("urls", []))
            data["title_hashes"] = set(data.get("title_hashes", []))
            return data

    def save_registry(self):
        """Save registry back to disk"""
        # Convert sets back to lists for JSON
        data = {
            **self.registry,
            "urls": list(self.registry["urls"]),
            "title_hashes": list(self.registry["title_hashes"])
        }

        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)

    def normalize_hash(self, title: str) -> str:
        """
        Normalize title to hash
        
        Steps:
        1. Lowercase
        2. Remove stopwords
        3. Sort words
        4. Hash
        """
        words = title.lower().split()
        # Remove stopwords
        words = [w for w in words if w not in self.stopwords]
        # Sort for order-independence
        words = sorted(words)
        # Hash
        text = ' '.join(words)
        return hashlib.md5(text.encode()).hexdigest()

    def extract_keywords(self, title: str) -> set[str]:
        """
        Extract key terms from title (NER-like, no ML)
        
        Returns:
            Set of key terms found in title
        """
        words = set(title.lower().split())
        # Find intersection with key terms
        keywords = words & self.key_terms

        # Also extract numbers (visa years, percentages, etc.)
        numbers = {w for w in words if w.isdigit() or '%' in w}

        return keywords | numbers

    def calculate_keyword_overlap(self, keywords1: set[str], keywords2: set[str]) -> float:
        """
        Calculate Jaccard similarity between keyword sets
        
        Returns:
            Float between 0 and 1 (1 = identical)
        """
        if not keywords1 or not keywords2:
            return 0.0

        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)

        return intersection / union if union > 0 else 0.0

    def is_duplicate(self, article: dict) -> tuple[bool, str, float]:
        """
        Check if article is duplicate
        
        Args:
            article: {
                "title": str,
                "url": str,
                "published_at": "2026-02-18T12:00:00",
                "category": "immigration"
            }
        
        Returns:
            (is_duplicate: bool, reason: str, confidence: float)
        """
        # Layer 1: Exact URL match
        if article['url'] in self.registry['urls']:
            return True, "Exact URL match", 1.0

        # Layer 2: Title hash collision
        title_hash = self.normalize_hash(article['title'])
        if title_hash in self.registry['title_hashes']:
            return True, f"Title hash collision ({title_hash[:8]}...)", 0.95

        # Layer 3: Keyword overlap + date proximity
        keywords = self.extract_keywords(article['title'])
        article_date = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00'))

        for published in self.registry['recent_100']:
            pub_keywords = set(published.get('keywords', []))
            pub_date = datetime.fromisoformat(published['published_at'].replace('Z', '+00:00'))

            # Calculate overlap
            overlap = self.calculate_keyword_overlap(keywords, pub_keywords)
            date_diff = abs((article_date - pub_date).days)

            # Decision rules
            if overlap >= 0.8 and date_diff <= 7:
                # 80%+ overlap within 7 days = very likely duplicate
                return True, f"80%+ keyword overlap + {date_diff}d proximity (to: {published['title'][:50]}...)", 0.9

            if overlap >= 0.7 and date_diff <= 3:
                # 70%+ overlap within 3 days = likely duplicate
                return True, f"70%+ keyword overlap + {date_diff}d proximity (to: {published['title'][:50]}...)", 0.85

            if overlap >= 0.9 and date_diff <= 30:
                # 90%+ overlap within 30 days = same story different angle?
                return True, f"90%+ keyword overlap + {date_diff}d proximity (to: {published['title'][:50]}...)", 0.8

        # Not a duplicate
        return False, "Unique article", 0.0

    def add_published_article(self, article: dict):
        """
        Add article to registry after publishing
        
        Args:
            article: {
                "title": str,
                "url": str,
                "published_at": str (ISO),
                "category": str
            }
        """
        # Add to sets
        self.registry['urls'].add(article['url'])
        title_hash = self.normalize_hash(article['title'])
        self.registry['title_hashes'].add(title_hash)

        # Extract keywords
        keywords = list(self.extract_keywords(article['title']))

        # Add to recent_100 (FIFO)
        recent_entry = {
            **article,
            "keywords": keywords,
            "title_hash": title_hash
        }

        self.registry['recent_100'].insert(0, recent_entry)
        # Keep only last 100
        self.registry['recent_100'] = self.registry['recent_100'][:100]

        # Add to all_articles
        self.registry['all_articles'].append(recent_entry)

        # Save
        self.save_registry()

    def get_stats(self) -> dict:
        """Get registry statistics"""
        return {
            "total_urls": len(self.registry['urls']),
            "total_title_hashes": len(self.registry['title_hashes']),
            "recent_count": len(self.registry['recent_100']),
            "all_count": len(self.registry['all_articles'])
        }


# ==================== USAGE EXAMPLES ====================

def test_deduplicator():
    """Test the deduplicator with example articles"""

    dedup = RuleBasedDeduplicator(registry_path="/tmp/test_registry.json")

    # Article 1: Original
    article1 = {
        "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
        "url": "https://example.com/digital-nomad-extension",
        "published_at": "2026-02-15T10:00:00Z",
        "category": "immigration"
    }

    is_dup, reason, conf = dedup.is_duplicate(article1)
    print(f"Article 1: {is_dup} - {reason} (confidence: {conf})")
    # Output: False - Unique article (confidence: 0.0)

    # Publish it
    dedup.add_published_article(article1)

    # Article 2: Exact duplicate (same URL)
    article2 = {
        **article1,
        "title": "Different Title But Same URL"
    }

    is_dup, reason, conf = dedup.is_duplicate(article2)
    print(f"Article 2: {is_dup} - {reason} (confidence: {conf})")
    # Output: True - Exact URL match (confidence: 1.0)

    # Article 3: Same content, different URL, 1 day later
    article3 = {
        "title": "Digital Nomad Visa Indonesia Extended Five Years",
        "url": "https://different.com/nomad-extension",
        "published_at": "2026-02-16T10:00:00Z",
        "category": "immigration"
    }

    is_dup, reason, conf = dedup.is_duplicate(article3)
    print(f"Article 3: {is_dup} - {reason} (confidence: {conf})")
    # Output: True - 80%+ keyword overlap + 1d proximity (confidence: 0.9)

    # Article 4: Different topic
    article4 = {
        "title": "Indonesia Tax Reform: New NPWP Requirements",
        "url": "https://example.com/tax-npwp",
        "published_at": "2026-02-16T12:00:00Z",
        "category": "tax"
    }

    is_dup, reason, conf = dedup.is_duplicate(article4)
    print(f"Article 4: {is_dup} - {reason} (confidence: {conf})")
    # Output: False - Unique article (confidence: 0.0)

    # Stats
    print("\nRegistry Stats:")
    print(json.dumps(dedup.get_stats(), indent=2))


if __name__ == "__main__":
    test_deduplicator()
