#!/usr/bin/env python3
"""
Article Enrichment Service
===========================

Enriches raw scraped articles with:
- Catchy Bali Zero style headlines
- SEO-optimized summaries
- Key points extraction
- FAQ generation

Uses Claude/Gemini for intelligent content transformation.
"""

from typing import Dict, Any, Optional
from loguru import logger
import os


class ArticleEnrichmentService:
    """Enriches raw articles for Bali Zero Intelligence Center"""

    def __init__(self):
        # TODO: Implement Claude Max browser automation for enrichment
        logger.info("ArticleEnrichmentService initialized (using fallback mode)")

    async def enrich_article(
        self, raw_article: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform raw scraped article into polished Bali Zero content.

        Args:
            raw_article: {
                "title": "...",
                "content": "...",
                "category": "immigration",
                "source_name": "Jakarta Post",
                "source_url": "https://..."
            }

        Returns:
            {
                "enriched_title": "Indonesia's New E33G Digital Nomad Visa: What You Need to Know",
                "enriched_summary": "The Indonesian government has announced...",
                "key_points": ["Point 1", "Point 2", ...],
                "faq_items": [{"q": "...", "a": "..."}],
                "seo_keywords": ["visa", "indonesia", ...],
                "reading_time_minutes": 4,
                "image_prompt": "Professional expat working on laptop in Bali rice terrace..."
            }
        """
        title = raw_article.get("title", "Untitled")
        content = raw_article.get("content", "")
        category = raw_article.get("category", "general")
        source_name = raw_article.get("source_name", "Unknown")

        logger.info(
            f"Processing article (fallback mode): {title[:50]}...",
            extra={"category": category, "source": source_name}
        )

        # TODO: Implement Claude Max browser automation here
        # For now, return minimal enrichment
        return {
            "enriched_title": title,
            "enriched_summary": content[:200] + "...",
            "key_points": [],
            "faq_items": [],
            "seo_keywords": [category],
            "reading_time_minutes": max(1, len(content.split()) // 200),
            "image_prompt": f"{category} related news image"
        }

    def _build_enrichment_prompt(
        self, title: str, content: str, category: str, source: str
    ) -> str:
        """Build Claude prompt for article enrichment"""

        return f"""You are the Senior Content Editor at Bali Zero, Indonesia's premier intelligence platform for expats, investors, and business owners.

Your task: Transform this RAW scraped article into POLISHED Bali Zero content.

**RAW ARTICLE:**
Title: {title}
Category: {category}
Source: {source}
Content: {content[:1500]}

**YOUR DELIVERABLES (respond ONLY with this JSON format):**

```json
{{
  "enriched_title": "Catchy, SEO-friendly headline (max 80 chars, Bali Zero style - professional but engaging)",
  "enriched_summary": "2-3 sentence summary focusing on IMPACT for expats/investors (150-200 chars)",
  "key_points": [
    "Bullet point 1 (actionable insight)",
    "Bullet point 2 (what changed)",
    "Bullet point 3 (who's affected)"
  ],
  "faq_items": [
    {{"question": "Practical question?", "answer": "Clear, concise answer"}},
    {{"question": "Another common question?", "answer": "Actionable answer"}}
  ],
  "seo_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "reading_time_minutes": 3,
  "image_prompt": "Detailed visual prompt for AI image generation (Gemini Imagen style): describe scene, lighting, mood, subjects. Example: 'Professional Indonesian immigration office, modern glass building, expats reviewing documents with officer, warm natural lighting, editorial photography style, 16:9'"
}}
```

**BALI ZERO STYLE RULES:**
- Headlines: Direct, benefit-focused, no clickbait
- Tone: Professional authority + approachable expert
- Focus: Practical impact on expats/investors/business owners
- Avoid: Hype, jargon, vague claims
- Emphasize: Deadlines, requirements, costs, steps

**IMAGE PROMPT GUIDELINES:**
- Photorealistic, editorial quality
- Indonesian context (Bali, Jakarta, government buildings)
- Professional subjects (expats, officials, business settings)
- Warm, natural lighting
- 16:9 landscape format
- NO text overlays in image

Reply ONLY with the JSON object, no other text.
"""

    def _parse_enrichment_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response"""
        import json
        import re

        # Extract JSON from response (handle code blocks)
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("No JSON found in Claude response")

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse enrichment JSON: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            raise
