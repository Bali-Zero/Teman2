#!/usr/bin/env python3
"""
SEO & AEO Optimizer for BaliZero Intel Scraper
===============================================

Optimizes articles for:
- Traditional SEO (Google, Bing)
- AI Search Engines (ChatGPT, Claude, Perplexity, Gemini)

Key Features:
1. Schema.org JSON-LD structured data
2. Meta tags optimization
3. AI-friendly content structure
4. Entity signals for LLM citation
5. FAQ generation for featured snippets

Based on latest GEO (Generative Engine Optimization) best practices.

Author: BaliZero Team
"""

import json
import re
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict


@dataclass
class SEOMetadata:
    """SEO metadata for an article"""

    # Core meta tags
    title: str = ""
    meta_description: str = ""
    keywords: list[str] = field(default_factory=list)

    # Open Graph
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    og_type: str = "article"
    og_locale: str = "en_US"

    # Twitter Card
    twitter_card: str = "summary_large_image"
    twitter_title: str = ""
    twitter_description: str = ""

    # Article-specific
    canonical_url: str = ""
    published_date: str = ""
    modified_date: str = ""
    author: str = "BaliZero Editorial Team"
    reading_time_minutes: int = 5

    # AI/AEO specific
    tldr_summary: str = ""
    key_entities: list[str] = field(default_factory=list)
    faq_items: list[dict] = field(default_factory=list)

    # Schema.org JSON-LD
    schema_article: dict = field(default_factory=dict)
    schema_faq: dict = field(default_factory=dict)
    schema_organization: dict = field(default_factory=dict)
    schema_breadcrumb: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class SEOAEOOptimizer:
    """
    SEO & AEO Optimizer

    Generates comprehensive SEO metadata and AI-friendly structured data
    to maximize visibility in both traditional search and AI assistants.
    """

    # BaliZero brand constants
    BRAND_NAME = "BaliZero"
    BRAND_URL = "https://balizero.com"
    BRAND_LOGO = "https://balizero.com/images/balizero-logo.png"
    BRAND_DESCRIPTION = "Indonesia's trusted guide for expats and investors. Expert visa, tax, and business consulting since 2015."

    # Social profiles for sameAs (helps AI identify the brand)
    BRAND_SAME_AS = [
        "https://www.linkedin.com/company/balizero",
        "https://www.instagram.com/balizero",
        "https://wa.me/6285904369574",
    ]

    # Category to topic mapping for better SEO
    CATEGORY_TOPICS = {
        "immigration": [
            "Indonesia visa",
            "KITAS",
            "KITAP",
            "work permit",
            "digital nomad visa",
            "retirement visa",
        ],
        "tax": [
            "Indonesia tax",
            "NPWP",
            "SPT",
            "corporate tax",
            "expat tax",
            "tax compliance",
        ],
        "business": [
            "PT PMA",
            "company formation",
            "OSS",
            "NIB",
            "foreign investment",
            "BKPM",
        ],
        "property": [
            "Bali property",
            "real estate Indonesia",
            "villa investment",
            "land ownership",
            "HGB",
        ],
        "tech": ["Indonesia tech", "startup ecosystem", "fintech", "digital economy"],
        "lifestyle": [
            "expat life Bali",
            "digital nomad",
            "living in Indonesia",
            "cost of living",
        ],
        "regulation": [
            "Indonesia regulation",
            "government policy",
            "business law",
            "compliance",
        ],
        "investment": [
            "Indonesia investment",
            "foreign investor",
            "portfolio investment",
            "capital market",
        ],
    }

    # Geographic entities for local SEO
    GEO_ENTITIES = [
        "Indonesia",
        "Bali",
        "Jakarta",
        "Denpasar",
        "Ubud",
        "Seminyak",
        "Canggu",
        "Sanur",
        "Nusa Dua",
        "Kuta",
        "Southeast Asia",
    ]

    def __init__(self, use_ai_enhancement: bool = True):
        """
        Initialize optimizer

        Args:
            use_ai_enhancement: If True, use Claude to generate better summaries/FAQs
        """
        self.use_ai_enhancement = use_ai_enhancement

    def optimize(self, article: dict) -> SEOMetadata:
        """
        Generate complete SEO/AEO metadata for an article

        Args:
            article: Dict with keys: title, content, category, source_url,
                     published_date, image_url, enriched_content (optional)

        Returns:
            SEOMetadata with all optimization data
        """
        metadata = SEOMetadata()

        # Extract article data
        title = article.get("title", "")
        content = article.get("enriched_content") or article.get("content", "")
        category = article.get("category", "general").lower()
        source_url = article.get("source_url", "")
        image_url = article.get("image_url", "")
        published = article.get(
            "published_date", datetime.now(timezone.utc).isoformat()
        )

        # 1. Generate optimized title (60 chars max for SERP)
        metadata.title = self._optimize_title(title, category)

        # 2. Generate meta description (155 chars max)
        metadata.meta_description = self._generate_meta_description(
            title, content, category
        )

        # 3. Extract keywords
        metadata.keywords = self._extract_keywords(title, content, category)

        # 4. Generate TL;DR summary (AI-friendly, answer-first format)
        metadata.tldr_summary = self._generate_tldr(title, content)

        # 5. Extract key entities for AI citation
        metadata.key_entities = self._extract_entities(title, content, category)

        # 6. Generate FAQ items (for featured snippets + AI)
        metadata.faq_items = self._generate_faq(title, content, category)

        # 7. Open Graph tags
        metadata.og_title = metadata.title
        metadata.og_description = metadata.meta_description
        metadata.og_image = image_url or f"{self.BRAND_URL}/images/og-default.jpg"

        # 8. Twitter Card
        metadata.twitter_title = metadata.title
        metadata.twitter_description = metadata.meta_description

        # 9. Dates and reading time
        metadata.published_date = published
        metadata.modified_date = datetime.now(timezone.utc).isoformat()
        metadata.reading_time_minutes = self._calculate_reading_time(content)

        # 10. Generate canonical URL
        slug = self._generate_slug(title)
        metadata.canonical_url = f"{self.BRAND_URL}/news/{category}/{slug}"

        # 11. Generate Schema.org JSON-LD
        metadata.schema_article = self._generate_article_schema(
            metadata, content, category
        )
        metadata.schema_faq = self._generate_faq_schema(metadata.faq_items)
        metadata.schema_organization = self._generate_organization_schema()
        metadata.schema_breadcrumb = self._generate_breadcrumb_schema(
            category, metadata.title
        )

        return metadata

    def _optimize_title(self, title: str, category: str) -> str:
        """Optimize title for SEO (max 60 chars, include brand)"""
        # Clean title
        title = title.strip()

        # Add category context if not present
        category_keywords = {
            "immigration": "Visa",
            "tax": "Tax",
            "business": "Business",
            "property": "Property",
            "tech": "Tech",
            "lifestyle": "Life",
        }

        # Ensure title isn't too long
        max_title_len = 55  # Leave room for potential additions
        if len(title) > max_title_len:
            title = title[: max_title_len - 3] + "..."

        # Add BaliZero brand at end if space allows
        if len(title) < 50:
            title = f"{title} | BaliZero"

        return title

    def _generate_meta_description(
        self, title: str, content: str, category: str
    ) -> str:
        """Generate meta description (max 155 chars, compelling + keywords)"""
        # Extract first meaningful paragraph
        paragraphs = [
            p.strip()
            for p in content.split("\n\n")
            if p.strip() and len(p.strip()) > 50
        ]

        if paragraphs:
            # Use first paragraph, clean it
            first_para = paragraphs[0]
            # Remove markdown
            first_para = re.sub(r"[#*_`\[\]]", "", first_para)
            first_para = re.sub(r"\(http[^)]+\)", "", first_para)

            # Truncate to 150 chars
            if len(first_para) > 150:
                first_para = first_para[:147] + "..."

            return first_para

        # Fallback: generate from title
        category_desc = {
            "immigration": "Latest Indonesia visa and immigration updates for expats.",
            "tax": "Indonesia tax news and compliance updates for foreigners.",
            "business": "Business regulations and investment news for Indonesia.",
            "property": "Real estate and property news for investors in Indonesia.",
            "tech": "Technology and startup news from Indonesia.",
            "lifestyle": "Expat lifestyle and living tips for Indonesia.",
        }

        base = category_desc.get(
            category, "Latest news and insights for Indonesia expats and investors."
        )
        return f"{title[:80]}. {base}"[:155]

    def _extract_keywords(self, title: str, content: str, category: str) -> list[str]:
        """Extract SEO keywords from content"""
        keywords = set()

        # Add category-specific topics
        if category in self.CATEGORY_TOPICS:
            keywords.update(self.CATEGORY_TOPICS[category][:3])

        # Add geographic keywords if mentioned
        text = f"{title} {content}".lower()
        for geo in self.GEO_ENTITIES:
            if geo.lower() in text:
                keywords.add(geo)

        # Extract important terms (capitalized words, acronyms)
        # Common Indonesia-specific acronyms
        acronyms = [
            "KITAS",
            "KITAP",
            "NPWP",
            "SPT",
            "PMA",
            "PMDN",
            "OSS",
            "NIB",
            "BKPM",
            "DJP",
            "IMIGRASI",
            "HGB",
            "SHM",
            "SHGB",
            "E33E",
            "E33G",
        ]
        for acr in acronyms:
            if acr in content or acr.lower() in content.lower():
                keywords.add(acr)

        # Add brand
        keywords.add("BaliZero")
        keywords.add("Indonesia expat")

        return list(keywords)[:15]  # Max 15 keywords

    def _generate_tldr(self, title: str, content: str) -> str:
        """
        Generate TL;DR summary (AI-friendly, answer-first format)

        This is crucial for AI citation - LLMs love clear, quotable summaries.
        """
        # Extract first 2-3 sentences that answer "what's this about"
        sentences = re.split(r"(?<=[.!?])\s+", content)
        meaningful = [s for s in sentences if len(s) > 30 and not s.startswith("#")][:3]

        if meaningful:
            tldr = " ".join(meaningful)
            # Clean markdown
            tldr = re.sub(r"[#*_`\[\]]", "", tldr)
            tldr = re.sub(r"\(http[^)]+\)", "", tldr)
            return tldr[:500]  # Max 500 chars

        return f"This article covers {title.lower()} with insights for expats and investors in Indonesia."

    def _extract_entities(self, title: str, content: str, category: str) -> list[str]:
        """
        Extract key entities for AI knowledge graphs

        LLMs use entities to understand and cite content.
        """
        entities = set()

        # Brand entity (always include)
        entities.add("BaliZero")

        # Category entities
        if category in self.CATEGORY_TOPICS:
            entities.update(self.CATEGORY_TOPICS[category][:2])

        # Geographic entities
        text = f"{title} {content}"
        for geo in self.GEO_ENTITIES:
            if geo in text:
                entities.add(geo)

        # Government/regulatory entities
        gov_entities = {
            "Imigrasi": ["imigrasi", "immigration", "visa"],
            "DJP (Tax Office)": ["djp", "tax office", "pajak"],
            "BKPM": ["bkpm", "investment", "oss"],
            "Ministry of Finance": ["ministry of finance", "kemenkeu"],
            "Bank Indonesia": ["bank indonesia", "bi", "central bank"],
        }

        text_lower = text.lower()
        for entity, keywords in gov_entities.items():
            if any(kw in text_lower for kw in keywords):
                entities.add(entity)

        return list(entities)[:10]

    def _generate_faq(self, title: str, content: str, category: str) -> list[dict]:
        """
        Generate FAQ items for featured snippets and AI

        FAQs are gold for both Google featured snippets and AI citations.
        """
        faqs = []

        # Category-specific common questions
        category_faqs = {
            "immigration": [
                {
                    "q": "What visa do I need to live in Indonesia?",
                    "pattern": r"(visa|permit|stay)",
                },
                {
                    "q": "How long can I stay in Indonesia?",
                    "pattern": r"(day|month|year|duration|period)",
                },
                {
                    "q": "What are the requirements?",
                    "pattern": r"(require|document|need)",
                },
            ],
            "tax": [
                {
                    "q": "Do foreigners pay tax in Indonesia?",
                    "pattern": r"(foreigner|expat|tax)",
                },
                {
                    "q": "What is the tax rate in Indonesia?",
                    "pattern": r"(rate|percent|%)",
                },
                {"q": "When is the tax deadline?", "pattern": r"(deadline|due|submit)"},
            ],
            "business": [
                {
                    "q": "Can foreigners own a company in Indonesia?",
                    "pattern": r"(own|foreign|100%)",
                },
                {
                    "q": "How much does it cost to set up a company?",
                    "pattern": r"(cost|price|fee|capital)",
                },
                {
                    "q": "How long does company registration take?",
                    "pattern": r"(time|day|week|process)",
                },
            ],
            "property": [
                {
                    "q": "Can foreigners buy property in Indonesia?",
                    "pattern": r"(buy|own|purchase|foreigner)",
                },
                {
                    "q": "What is the best area to invest?",
                    "pattern": r"(area|location|best|invest)",
                },
                {
                    "q": "What are the property ownership options?",
                    "pattern": r"(hgb|shm|lease|right)",
                },
            ],
        }

        # Try to extract answers from content
        if category in category_faqs:
            for faq_template in category_faqs[category]:
                # Look for relevant content
                pattern = faq_template["pattern"]
                sentences = re.split(r"(?<=[.!?])\s+", content)
                relevant = [
                    s for s in sentences if re.search(pattern, s, re.I) and len(s) > 30
                ]

                if relevant:
                    answer = relevant[0]
                    # Clean answer
                    answer = re.sub(r"[#*_`\[\]]", "", answer)
                    answer = re.sub(r"\(http[^)]+\)", "", answer)

                    faqs.append({"question": faq_template["q"], "answer": answer[:300]})

                if len(faqs) >= 3:
                    break

        # Add generic FAQ if needed
        if len(faqs) < 2:
            faqs.append(
                {
                    "question": f"Where can I get help with {category} in Indonesia?",
                    "answer": f"BaliZero provides expert {category} consulting for expats and investors in Indonesia. Contact us via WhatsApp at +62 859 0436 9574 for a free consultation.",
                }
            )

        return faqs

    def _calculate_reading_time(self, content: str) -> int:
        """Calculate reading time in minutes (avg 200 words/min)"""
        words = len(content.split())
        minutes = max(1, round(words / 200))
        return min(minutes, 15)  # Cap at 15 minutes

    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug from title"""
        slug = title.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")

        # Add hash for uniqueness
        hash_suffix = hashlib.md5(title.encode()).hexdigest()[:6]

        return f"{slug[:50]}-{hash_suffix}"

    def _generate_article_schema(
        self, metadata: SEOMetadata, content: str, category: str
    ) -> dict:
        """
        Generate Article schema (Schema.org JSON-LD)

        This is crucial for AI understanding and citation.
        """
        return {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": metadata.title,
            "description": metadata.meta_description,
            "image": metadata.og_image,
            "datePublished": metadata.published_date,
            "dateModified": metadata.modified_date,
            "author": {
                "@type": "Organization",
                "name": self.BRAND_NAME,
                "url": self.BRAND_URL,
                "logo": self.BRAND_LOGO,
                "sameAs": self.BRAND_SAME_AS,
            },
            "publisher": {
                "@type": "Organization",
                "name": self.BRAND_NAME,
                "url": self.BRAND_URL,
                "logo": {"@type": "ImageObject", "url": self.BRAND_LOGO},
                "sameAs": self.BRAND_SAME_AS,
            },
            "mainEntityOfPage": {"@type": "WebPage", "@id": metadata.canonical_url},
            "articleSection": category.title(),
            "keywords": ", ".join(metadata.keywords),
            "wordCount": len(content.split()),
            "inLanguage": "en",
            "about": [
                {"@type": "Thing", "name": entity}
                for entity in metadata.key_entities[:5]
            ],
            "mentions": [
                {"@type": "Country", "name": "Indonesia"},
                {"@type": "Place", "name": "Bali"},
            ],
            # AI-friendly: explicit expertise signals
            "speakable": {
                "@type": "SpeakableSpecification",
                "cssSelector": [".article-summary", ".key-takeaway", ".tldr"],
            },
        }

    def _generate_faq_schema(self, faq_items: list[dict]) -> dict:
        """Generate FAQPage schema (critical for featured snippets + AI)"""
        if not faq_items:
            return {}

        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["question"],
                    "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
                }
                for item in faq_items
            ],
        }

    def _generate_organization_schema(self) -> dict:
        """Generate Organization schema for brand authority"""
        return {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": self.BRAND_NAME,
            "url": self.BRAND_URL,
            "logo": self.BRAND_LOGO,
            "description": self.BRAND_DESCRIPTION,
            "foundingDate": "2015",
            "foundingLocation": {"@type": "Place", "name": "Bali, Indonesia"},
            "areaServed": {"@type": "Country", "name": "Indonesia"},
            "sameAs": self.BRAND_SAME_AS,
            "contactPoint": {
                "@type": "ContactPoint",
                "telephone": "+62-859-0436-9574",
                "contactType": "customer service",
                "availableLanguage": ["English", "Indonesian", "Italian"],
            },
            "knowsAbout": [
                "Indonesia visa",
                "KITAS",
                "Indonesia tax",
                "PT PMA",
                "Company formation Indonesia",
                "Bali real estate",
                "Expat services Indonesia",
            ],
        }

    def _generate_breadcrumb_schema(self, category: str, title: str) -> dict:
        """Generate BreadcrumbList schema for navigation"""
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Home",
                    "item": self.BRAND_URL,
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": "News",
                    "item": f"{self.BRAND_URL}/news",
                },
                {
                    "@type": "ListItem",
                    "position": 3,
                    "name": category.title(),
                    "item": f"{self.BRAND_URL}/news/{category}",
                },
                {"@type": "ListItem", "position": 4, "name": title[:50]},
            ],
        }

    def get_combined_schema(self, metadata: SEOMetadata) -> str:
        """
        Get all schemas combined as JSON-LD script tag

        Returns ready-to-embed HTML script tag with all schemas.
        """
        schemas = [
            metadata.schema_article,
            metadata.schema_organization,
            metadata.schema_breadcrumb,
        ]

        if metadata.schema_faq:
            schemas.append(metadata.schema_faq)

        # Combine into @graph format
        combined = {"@context": "https://schema.org", "@graph": schemas}

        return json.dumps(combined, indent=2, ensure_ascii=False)

    def get_meta_tags_html(self, metadata: SEOMetadata) -> str:
        """
        Generate HTML meta tags

        Returns ready-to-embed meta tags HTML.
        """
        tags = []

        # Basic meta
        tags.append(f"<title>{metadata.title}</title>")
        tags.append(f'<meta name="description" content="{metadata.meta_description}">')
        tags.append(f'<meta name="keywords" content="{", ".join(metadata.keywords)}">')
        tags.append(f'<link rel="canonical" href="{metadata.canonical_url}">')

        # Open Graph
        tags.append(f'<meta property="og:title" content="{metadata.og_title}">')
        tags.append(
            f'<meta property="og:description" content="{metadata.og_description}">'
        )
        tags.append(f'<meta property="og:image" content="{metadata.og_image}">')
        tags.append(f'<meta property="og:type" content="{metadata.og_type}">')
        tags.append(f'<meta property="og:url" content="{metadata.canonical_url}">')
        tags.append(f'<meta property="og:site_name" content="{self.BRAND_NAME}">')

        # Twitter Card
        tags.append(f'<meta name="twitter:card" content="{metadata.twitter_card}">')
        tags.append(f'<meta name="twitter:title" content="{metadata.twitter_title}">')
        tags.append(
            f'<meta name="twitter:description" content="{metadata.twitter_description}">'
        )
        tags.append(f'<meta name="twitter:image" content="{metadata.og_image}">')

        # Article meta
        tags.append(
            f'<meta property="article:published_time" content="{metadata.published_date}">'
        )
        tags.append(
            f'<meta property="article:modified_time" content="{metadata.modified_date}">'
        )
        tags.append(f'<meta property="article:author" content="{metadata.author}">')

        # Reading time (for AI understanding)
        tags.append(
            f'<meta name="reading-time" content="{metadata.reading_time_minutes} min">'
        )

        return "\n".join(tags)


def optimize_article(article: dict) -> dict:
    """
    Convenience function to optimize an article

    Args:
        article: Dict with title, content, category, etc.

    Returns:
        Article dict with added 'seo' key containing all SEO metadata
    """
    optimizer = SEOAEOOptimizer()
    metadata = optimizer.optimize(article)

    # Add SEO data to article
    article["seo"] = {
        "title": metadata.title,
        "meta_description": metadata.meta_description,
        "keywords": metadata.keywords,
        "canonical_url": metadata.canonical_url,
        "tldr_summary": metadata.tldr_summary,
        "key_entities": metadata.key_entities,
        "faq_items": metadata.faq_items,
        "reading_time_minutes": metadata.reading_time_minutes,
        "og": {
            "title": metadata.og_title,
            "description": metadata.og_description,
            "image": metadata.og_image,
            "type": metadata.og_type,
        },
        "twitter": {
            "card": metadata.twitter_card,
            "title": metadata.twitter_title,
            "description": metadata.twitter_description,
        },
        "schema_json_ld": optimizer.get_combined_schema(metadata),
        "dates": {
            "published": metadata.published_date,
            "modified": metadata.modified_date,
        },
    }

    return article


# CLI for testing
if __name__ == "__main__":
    # Test with sample article
    sample = {
        "title": "Indonesia Launches New Digital Nomad Visa E33G for Remote Workers",
        "content": """
        The Indonesian government has officially launched the E33G Digital Nomad Visa,
        a new visa category specifically designed for remote workers and digital nomads
        who want to live and work in Indonesia.

        The new visa allows holders to stay in Indonesia for up to 5 years, with the
        ability to work remotely for foreign employers. Applicants must prove a minimum
        monthly income of $2,000 USD and have health insurance coverage.

        Key requirements for the E33G visa include:
        - Proof of remote employment or freelance work
        - Minimum monthly income of $2,000 USD
        - Valid passport with 18 months validity
        - Health insurance coverage for Indonesia
        - Clean criminal record

        The visa can be applied for at Indonesian embassies abroad or converted from
        a tourist visa within Indonesia. Processing time is approximately 4-6 weeks.

        This new visa category is part of Indonesia's strategy to attract high-value
        visitors and boost the local economy through increased spending by digital nomads.
        """,
        "category": "immigration",
        "source_url": "https://example.com/news/digital-nomad-visa",
        "image_url": "https://balizero.com/images/news/digital-nomad.jpg",
        "published_date": "2026-01-04T10:00:00Z",
    }

    # Optimize
    optimizer = SEOAEOOptimizer()
    metadata = optimizer.optimize(sample)

    print("=" * 60)
    print("SEO/AEO OPTIMIZATION RESULTS")
    print("=" * 60)
    print(f"\n📌 Title: {metadata.title}")
    print(f"\n📝 Meta Description:\n{metadata.meta_description}")
    print(f"\n🔑 Keywords: {', '.join(metadata.keywords)}")
    print(f"\n⚡ TL;DR:\n{metadata.tldr_summary}")
    print(f"\n🏷️ Key Entities: {', '.join(metadata.key_entities)}")
    print("\n❓ FAQs:")
    for faq in metadata.faq_items:
        print(f"  Q: {faq['question']}")
        print(f"  A: {faq['answer'][:100]}...")
    print(f"\n⏱️ Reading Time: {metadata.reading_time_minutes} min")
    print(f"\n🔗 Canonical URL: {metadata.canonical_url}")
    print("\n📊 Schema.org JSON-LD (Article):")
    print(json.dumps(metadata.schema_article, indent=2)[:500] + "...")
    print("\n✅ Optimization complete!")
