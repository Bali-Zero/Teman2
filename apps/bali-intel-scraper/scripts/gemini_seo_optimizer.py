#!/usr/bin/env python3
"""
Gemini SEO + AI SEO (GEO/AEO) Optimizer — SOTA 2026
Generates: Meta tags, Schema.org JSON-LD, FAQ schema, Open Graph,
           AI citation tags, answer snippets, entity mentions, E-E-A-T signals

Input: data/enriched/*.json
Output: data/seo_ready/*.json with full SEO + GEO metadata

Optimized for:
- Google AI Overviews (cited sources get 35% more clicks)
- Perplexity AI (2.76x more citations per query vs ChatGPT)
- ChatGPT Browse (authority-first citation model)
- Traditional Google Search (E-E-A-T, Core Web Vitals)
"""

import json
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Any

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENRICHED_DIR = PROJECT_ROOT / "data" / "enriched"
SEO_DIR = PROJECT_ROOT / "data" / "seo_ready"
SEO_DIR.mkdir(exist_ok=True, parents=True)

TIMEOUT = 90

# Category SEO defaults for Bali Zero
CATEGORY_SEO: dict[str, dict[str, str]] = {
    "immigration": {
        "suffix": "Visa & Immigration Guide",
        "primary_kw": "indonesia visa, kitas, kitap, bali visa",
    },
    "business": {
        "suffix": "Business Setup Guide",
        "primary_kw": "pt pma indonesia, company setup bali, business license",
    },
    "tax-legal": {
        "suffix": "Tax & Legal Guide",
        "primary_kw": "indonesia tax, coretax, npwp, pph, ppn",
    },
    "property": {
        "suffix": "Property Investment Guide",
        "primary_kw": "bali property, hak pakai, villa investment",
    },
    "lifestyle": {
        "suffix": "Expat Living Guide",
        "primary_kw": "bali expat, cost of living bali, digital nomad bali",
    },
    "tech": {
        "suffix": "Technology & Innovation",
        "primary_kw": "indonesia tech, digital transformation, ai indonesia",
    },
}


class SEOOptimizer:
    def __init__(self) -> None:
        self.stats = {"total": 0, "optimized": 0, "failed": 0}

    def log(self, msg: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {msg}")
        sys.stdout.flush()

    def optimize_article(self, article: dict[str, Any]) -> dict[str, Any] | None:
        """Generate SOTA SEO + GEO metadata using Gemini or Ollama."""

        title = article.get("title", "")
        enr = article.get("enrichment", {})
        summary = enr.get("the_facts", enr.get("executive_brief", ""))
        content = article.get("content", "")[:1500]
        category = article.get("category", "")
        source = article.get("source", "")
        cat_seo = CATEGORY_SEO.get(category, CATEGORY_SEO.get("lifestyle", {}))

        prompt = f"""You are an SEO + AI SEO (GEO/AEO) expert for Bali Zero, Indonesia's AI-powered visa and business consulting firm.

Generate comprehensive SEO metadata for this article. The output MUST be optimized for:
1. Google AI Overviews (answer extraction + citation)
2. Perplexity AI citations
3. Traditional Google Search (E-E-A-T)
4. Featured Snippets / FAQ rich results

Article:
Title: {title}
Category: {category}
Source: {source}
Summary: {summary[:400]}
Content preview: {content[:800]}

Category keywords: {cat_seo.get("primary_kw", "")}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "seoTitle": "<60 chars, keyword-first, include 2026 or current year>",
  "seoDescription": "<155 chars, include primary keyword + call to action>",
  "keywords": ["<5-8 keywords, mix of head terms + long-tail>"],
  "aiOptimization": {{
    "answerSnippet": "<A clear, declarative 2-sentence answer to the article's primary question. This is what AI systems will extract and cite. Be factual and specific.>",
    "primaryQuestion": "<The main question this article answers, phrased as users would search>",
    "entityMentions": [
      {{"name": "<Entity 1>", "type": "<Organization|Regulation|GovernmentOrganization|Product|Place>"}},
      {{"name": "<Entity 2>", "type": "<type>"}}
    ]
  }},
  "faqSchema": [
    {{"question": "<Real question users ask>", "answer": "<Concise factual answer, 1-2 sentences>"}},
    {{"question": "<Another question>", "answer": "<Answer>"}},
    {{"question": "<Third question>", "answer": "<Answer>"}}
  ],
  "og_title": "<Open Graph title, can be slightly longer than seoTitle>",
  "og_description": "<Open Graph description>"
}}"""

        try:
            result = subprocess.run(
                ["gemini", "-m", "gemini-2.5-pro", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )

            if result.returncode == 0 and result.stdout.strip():
                json_match = re.search(r"\{.*\}", result.stdout, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    # Validate required fields
                    if parsed.get("seoTitle") and parsed.get("seoDescription"):
                        return parsed
        except subprocess.TimeoutExpired:
            self.log("  Gemini timeout, trying Ollama fallback...", "WARN")
        except Exception as e:
            self.log(f"  Gemini error: {e}", "WARN")

        # Fallback: generate basic SEO without LLM
        return self._fallback_seo(title, summary, category, cat_seo)

    def _fallback_seo(
        self,
        title: str,
        summary: str,
        category: str,
        cat_seo: dict[str, str],
    ) -> dict[str, Any]:
        """Generate deterministic SEO metadata without LLM."""
        suffix = cat_seo.get("suffix", "Guide")
        seo_title = f"{title[:50]} | {suffix}" if len(title) > 50 else f"{title} | Bali Zero"
        seo_desc = summary[:152] + "..." if len(summary) > 155 else summary

        return {
            "seoTitle": seo_title[:60],
            "seoDescription": seo_desc[:155],
            "keywords": [kw.strip() for kw in cat_seo.get("primary_kw", "").split(",")],
            "aiOptimization": {
                "answerSnippet": summary[:200],
                "primaryQuestion": f"What does {title} mean for expats in Bali?",
                "entityMentions": [],
            },
            "faqSchema": [],
            "og_title": title,
            "og_description": seo_desc,
        }

    def optimize_batch(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.log("=" * 60)
        self.log("SEO + GEO/AEO OPTIMIZER — SOTA 2026")
        self.log("=" * 60)

        optimized = []
        self.stats["total"] = len(articles)

        for i, article in enumerate(articles, 1):
            self.log(f"\n[{i}/{len(articles)}] {article.get('title', '')[:50]}...")

            seo = self.optimize_article(article)
            if seo:
                article["seo"] = seo
                article["seo_optimized_at"] = datetime.now().isoformat()
                self.stats["optimized"] += 1
                ai_opt = seo.get("aiOptimization", {})
                faq_count = len(seo.get("faqSchema", []))
                entity_count = len(ai_opt.get("entityMentions", []))
                self.log(f"  SEO: {len(seo.get('keywords', []))} kw, {faq_count} FAQ, {entity_count} entities")
            else:
                self.stats["failed"] += 1
                self.log("  SEO failed", "WARN")

            optimized.append(article)

        return optimized

    def save_results(self, articles: list[dict[str, Any]], source_file: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = SEO_DIR / f"{timestamp}_seo_ready.json"

        with open(output_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "source_file": str(source_file),
                    "stats": self.stats,
                    "articles": articles,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        self.log(f"\nSaved: {output_file}")
        return output_file

    def print_summary(self) -> None:
        self.log(f"""
SEO + GEO OPTIMIZATION COMPLETE:
   Total:     {self.stats['total']}
   Optimized: {self.stats['optimized']}
   Failed:    {self.stats['failed']}
""")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="SOTA SEO + GEO/AEO Optimizer")
    parser.add_argument("input_file", nargs="?")
    parser.add_argument("--latest", action="store_true")
    args = parser.parse_args()

    if args.latest or not args.input_file:
        files = sorted(ENRICHED_DIR.glob("*.json"), reverse=True)
        if not files:
            print("No enriched files found")
            return 1
        input_file = files[0]
    else:
        input_file = Path(args.input_file)

    with open(input_file) as f:
        data = json.load(f)

    articles = data.get("articles", [])
    optimizer = SEOOptimizer()
    optimized = optimizer.optimize_batch(articles)
    output_file = optimizer.save_results(optimized, input_file)
    optimizer.print_summary()

    print(f"\nOutput: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
