"""
BALI ZERO JOURNAL AI GENERATOR
Multi-AI System with 3-tier fallback for maximum cost efficiency

Primary: Llama 4 Scout ($0.20/$0.20 per 1M tokens) - 91% cheaper
Fallback 1: Gemini 2.0 Flash ($0.075/$0.30 per 1M tokens) - 94% cheaper
Fallback 2: Claude Haiku ($1/$5 per 1M tokens) - Baseline

Average cost per article: ~$0.0004
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger
import yaml
import re
import json
import httpx

# AI Clients
import anthropic
import google.generativeai as genai


class AIJournalGenerator:
    """
    Multi-AI article generator for Bali Zero Journal
    Uses 3-tier fallback system for optimal cost/quality
    """

    def __init__(
        self,
        openrouter_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
    ):
        # API Keys
        self.openrouter_key = openrouter_api_key or os.getenv(
            "OPENROUTER_API_KEY_LLAMA"
        )
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.anthropic_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")

        # Initialize clients
        if self.anthropic_key:
            self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_key)

        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")

        # Metrics tracking
        self.metrics = {
            "total_articles": 0,
            "llama_success": 0,
            "gemini_success": 0,
            "haiku_success": 0,
            "total_cost_usd": 0.0,
            "filtered_out": 0,
            "filter_cost_usd": 0.0,
        }

        # Cost per 1M tokens (input/output)
        self.costs = {
            "llama": (0.20, 0.20),
            "gemini": (0.075, 0.30),
            "haiku": (1.00, 5.00),
        }

        logger.info("✅ AI Journal Generator initialized with 3-tier fallback")

    def generate_with_llama(
        self, content: str, category: str, metadata: Dict
    ) -> tuple[Optional[str], Optional[str]]:
        """Generate article using Llama 4 Scout (PRIMARY - cheapest)

        Returns:
            (article, model_name) or (None, None) on failure
        """

        if not self.openrouter_key:
            return None, None

        try:
            logger.info("🦙 Attempting generation with Llama 4 Scout...")

            prompt = self._build_journal_prompt(content, category, metadata)

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "meta-llama/llama-3.3-70b-instruct",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 2000,
                    },
                )

            if response.status_code == 200:
                result = response.json()
                article = result["choices"][0]["message"]["content"]

                # Calculate cost
                input_tokens = result["usage"]["prompt_tokens"]
                output_tokens = result["usage"]["completion_tokens"]
                cost = (
                    input_tokens / 1_000_000 * self.costs["llama"][0]
                    + output_tokens / 1_000_000 * self.costs["llama"][1]
                )

                self.metrics["llama_success"] += 1
                self.metrics["total_cost_usd"] += cost

                logger.success(f"✅ Llama generated article (Cost: ${cost:.6f})")
                return article, "llama"
            else:
                logger.warning(f"❌ Llama failed: {response.status_code}")
                return None, None

        except Exception as e:
            logger.error(f"❌ Llama error: {e}")
            return None, None

    def generate_with_gemini(
        self, content: str, category: str, metadata: Dict
    ) -> tuple[Optional[str], Optional[str]]:
        """Generate article using Gemini 2.0 Flash (FALLBACK 1)

        Returns:
            (article, model_name) or (None, None) on failure
        """

        if not self.gemini_key:
            return None, None

        try:
            logger.info("💎 Attempting generation with Gemini 2.0 Flash...")

            prompt = self._build_journal_prompt(content, category, metadata)

            response = self.gemini_model.generate_content(prompt)

            if response.text:
                article = response.text

                # Estimate cost (Gemini doesn't provide exact token counts)
                est_input_tokens = len(prompt.split()) * 1.3
                est_output_tokens = len(article.split()) * 1.3
                cost = (
                    est_input_tokens / 1_000_000 * self.costs["gemini"][0]
                    + est_output_tokens / 1_000_000 * self.costs["gemini"][1]
                )

                self.metrics["gemini_success"] += 1
                self.metrics["total_cost_usd"] += cost

                logger.success(f"✅ Gemini generated article (Est. cost: ${cost:.6f})")
                return article, "gemini"
            else:
                logger.warning("❌ Gemini returned empty response")
                return None, None

        except Exception as e:
            logger.error(f"❌ Gemini error: {e}")
            return None, None

    def generate_with_haiku(
        self, content: str, category: str, metadata: Dict
    ) -> tuple[Optional[str], Optional[str]]:
        """Generate article using Claude Haiku (FALLBACK 2 - most expensive but reliable)

        Returns:
            (article, model_name) or (None, None) on failure
        """

        if not self.anthropic_key:
            return None, None

        try:
            logger.info(
                "🎨 Attempting generation with Claude Haiku (final fallback)..."
            )

            prompt = self._build_journal_prompt(content, category, metadata)

            response = self.anthropic_client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=2000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            article = response.content[0].text

            # Calculate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = (
                input_tokens / 1_000_000 * self.costs["haiku"][0]
                + output_tokens / 1_000_000 * self.costs["haiku"][1]
            )

            self.metrics["haiku_success"] += 1
            self.metrics["total_cost_usd"] += cost

            logger.success(f"✅ Haiku generated article (Cost: ${cost:.6f})")
            return article, "haiku"

        except Exception as e:
            logger.error(f"❌ Haiku error: {e}")
            return None, None

    def _parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter robustly using yaml.safe_load

        Returns:
            (metadata dict, content without frontmatter)
        """
        if not content.startswith("---"):
            return {}, content

        try:
            # Split frontmatter from content
            parts = content.split("---", 2)
            if len(parts) < 3:
                return {}, content

            frontmatter_str = parts[1]
            content_only = parts[2].strip()

            # Parse YAML safely
            metadata = yaml.safe_load(frontmatter_str) or {}

            return metadata, content_only

        except yaml.YAMLError as e:
            logger.warning(f"YAML parsing error: {e}, falling back to empty metadata")
            return {}, content
        except Exception as e:
            logger.warning(f"Unexpected frontmatter parsing error: {e}")
            return {}, content

    def should_process_article(self, raw_file: Path) -> Dict[str, Any]:
        """
        Quick AI filter to check if article is worth processing.
        Uses cheap Gemini Flash (~$0.00001 per check)

        Returns:
            {
                "should_process": bool,
                "relevance_score": int (1-10),
                "reason": str,
                "category_match": bool
            }
        """

        # Read raw file
        with open(raw_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract metadata using robust YAML parser
        metadata, content_only = self._parse_frontmatter(content)

        # Build filter prompt
        filter_prompt = f"""Analyze if this scraped content is worth processing for Bali Zero Journal.

TARGET AUDIENCE: Expats, business owners, investors in Bali/Indonesia

DECLARED CATEGORY: {metadata.get('category', 'unknown')}
SOURCE: {metadata.get('source', 'unknown')} (Tier: {metadata.get('tier', 'unknown')})

CONTENT PREVIEW (first 800 chars):
{content_only[:800]}

Evaluate on these criteria (score 1-10):
1. RELEVANCE: Is this about Bali/Indonesia regulations, business, immigration, taxes, property, or legal matters?
2. NEWSWORTHINESS: Is this actual news/policy/regulation or just spam/promotional/generic content?
3. ACTIONABILITY: Does this contain useful information for our target audience?

Respond ONLY with this exact JSON format (no markdown, no extra text):
{{
  "should_process": true or false,
  "relevance_score": <number 1-10>,
  "reason": "<brief explanation max 100 chars>",
  "category_match": true or false
}}"""

        try:
            if not self.gemini_key:
                # No filter available, pass through
                logger.warning("No Gemini key - skipping pre-filter")
                return {
                    "should_process": True,
                    "relevance_score": 5,
                    "reason": "No filter available",
                    "category_match": True
                }

            # Use Gemini Flash for quick cheap check
            response = self.gemini_model.generate_content(
                filter_prompt,
                generation_config={
                    "temperature": 0.1,  # Low temp for consistent filtering
                    "max_output_tokens": 200,
                }
            )

            # Parse JSON response
            response_text = response.text.strip()

            # Remove markdown code blocks if present
            response_text = re.sub(r'```json\n?', '', response_text)
            response_text = re.sub(r'```\n?', '', response_text)
            response_text = response_text.strip()

            result = json.loads(response_text)

            # Calculate cost (Gemini Flash is very cheap)
            # Approximate: 800 chars ~= 200 tokens input, 50 tokens output
            filter_cost = (200 / 1_000_000 * 0.075) + (50 / 1_000_000 * 0.30)
            self.metrics["filter_cost_usd"] += filter_cost

            # Threshold: relevance_score >= 6 to process
            threshold = 6
            if result['relevance_score'] < threshold:
                logger.info(
                    f"❌ FILTERED OUT: {raw_file.name} "
                    f"(score: {result['relevance_score']}/10) - {result['reason']}"
                )
                self.metrics["filtered_out"] += 1
                return {"should_process": False, **result}

            logger.success(
                f"✅ PASSED FILTER: {raw_file.name} "
                f"(score: {result['relevance_score']}/10) - {result['reason']}"
            )
            return {"should_process": True, **result}

        except Exception as e:
            logger.error(f"Filter error for {raw_file.name}: {e}")
            # On error, be conservative and pass through
            return {
                "should_process": True,
                "relevance_score": 5,
                "reason": f"Filter error: {str(e)[:50]}",
                "category_match": True
            }

    def _build_journal_prompt(self, content: str, category: str, metadata: Dict) -> str:
        """Build prompt for journal article generation"""

        return f"""You are a professional business journalist for **Bali Zero Journal**, a premium intelligence publication for expats and business owners in Indonesia/Bali.

Transform the following scraped content into a professional, actionable journal article.

**SOURCE INFORMATION:**
- Category: {category}
- Source: {metadata.get('source', 'Unknown')}
- Tier: {metadata.get('tier', 'Unknown')}
- Target Audience: Expats, Investors, Business Owners in Bali/Indonesia

**RAW CONTENT:**
{content[:3000]}

**OUTPUT FORMAT (STRICT):**

# [Professional, Engaging Title]

## Executive Summary
[2-3 sentences summarizing the key information and why it matters to the target audience]

## Key Findings
* [Finding 1 - specific, actionable]
* [Finding 2 - specific, actionable]
* [Finding 3 - specific, actionable]

## Detailed Analysis

### [Section 1: Main Topic]
[Detailed explanation with context]

### [Section 2: Impact Analysis]
[How this affects expats/business owners]

### [Section 3: Practical Implications]
[What readers need to know/do]

## Action Items
* [Specific action 1]
* [Specific action 2]
* [Specific action 3]

## Relevant Stakeholders
* [Organization/Entity 1]
* [Organization/Entity 2]
* [Organization/Entity 3]

> **Intelligence Note:** [One key insight or quote from the content]

---
*Generated by Bali Zero Intelligence System for internal use*
*Category: {category} | Source Tier: {metadata.get('tier', 'Unknown')}*

**REQUIREMENTS:**
- Professional, clear, actionable tone
- Focus on practical implications for business/expat community
- Include specific dates, numbers, requirements when available
- No marketing fluff - intelligence-focused
- 500-800 words
- Output ONLY the formatted article, no preamble
"""

    def generate_article(self, raw_file: Path, output_dir: Path, skip_filter: bool = False) -> Dict[str, Any]:
        """
        Generate journal article from raw scraped content
        Uses 3-tier fallback: Llama → Gemini → Haiku

        Args:
            raw_file: Path to raw markdown file
            output_dir: Where to save generated article
            skip_filter: Skip AI pre-filter (default: False)
        """

        # PRE-FILTER: Quick AI check for relevance
        if not skip_filter:
            filter_result = self.should_process_article(raw_file)

            if not filter_result['should_process']:
                return {
                    "success": False,
                    "reason": "filtered_out",
                    "filter_result": filter_result,
                    "cost_usd": 0.0
                }

        # Read raw file
        with open(raw_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract metadata using robust YAML parser
        metadata, _ = self._parse_frontmatter(content)

        category = metadata.get("category", "general")

        logger.info(f"📝 Generating journal article for: {raw_file.name}")

        # Try Llama first (cheapest)
        article, model_used = self.generate_with_llama(content, category, metadata)

        # Fallback to Gemini
        if not article:
            logger.warning("⚠️  Llama failed, trying Gemini...")
            article, model_used = self.generate_with_gemini(content, category, metadata)

        # Final fallback to Haiku
        if not article:
            logger.warning("⚠️  Gemini failed, trying Haiku...")
            article, model_used = self.generate_with_haiku(content, category, metadata)

        if not article:
            logger.error("❌ All AI models failed to generate article")
            return {"success": False, "error": "All AI models failed"}

        # Save article
        output_category_dir = output_dir / category
        output_category_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_category_dir / f"{timestamp}_{category}.md"

        # Add metadata header
        final_article = f"""---
generated_at: {datetime.now().isoformat()}
category: {category}
source_file: {raw_file.name}
ai_model: {model_used}
---

{article}
"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_article)

        self.metrics["total_articles"] += 1

        logger.success(f"✅ Article saved: {output_file}")

        return {
            "success": True,
            "output_file": str(output_file),
            "category": category,
            "metrics": self.get_metrics(),
        }

    def get_metrics(self) -> Dict:
        """Get generation metrics and cost savings"""

        if self.metrics["total_articles"] == 0:
            return self.metrics

        # Calculate savings vs Haiku-only
        haiku_only_cost = self.metrics["total_articles"] * 0.0042  # Avg Haiku cost
        actual_cost = self.metrics["total_cost_usd"]
        savings = haiku_only_cost - actual_cost
        savings_pct = (savings / haiku_only_cost * 100) if haiku_only_cost > 0 else 0

        return {
            **self.metrics,
            "avg_cost_per_article": actual_cost / self.metrics["total_articles"],
            "llama_success_rate": f"{self.metrics['llama_success'] / self.metrics['total_articles'] * 100:.1f}%",
            "total_savings_vs_haiku": f"${savings:.4f}",
            "savings_percentage": f"{savings_pct:.1f}%",
            "filter_efficiency": f"{self.metrics['filtered_out']} articles filtered (${self.metrics['filter_cost_usd']:.6f} spent)",
        }


def main():
    """Test the generator"""

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input raw markdown file")
    parser.add_argument(
        "--output-dir", default="data/articles", help="Output directory"
    )

    args = parser.parse_args()

    generator = AIJournalGenerator()

    result = generator.generate_article(
        raw_file=Path(args.input), output_dir=Path(args.output_dir)
    )

    if result["success"]:
        print(f"\n✅ Article generated: {result['output_file']}")
        print("\n📊 Metrics:")
        for key, value in result["metrics"].items():
            print(f"  {key}: {value}")
    else:
        print(f"\n❌ Generation failed: {result['error']}")


if __name__ == "__main__":
    main()
