#!/usr/bin/env python3
"""
CLAUDE VALIDATOR - Intelligent Gate Between LLAMA and Enrichment
=================================================================
LLAMA scores fast but can miss nuance. Claude validates before enrichment.

Flow:
1. LLAMA scores article (0-100) based on keywords/heuristics
2. Articles with score 40-75 are "ambiguous" - could be valuable or noise
3. CLAUDE VALIDATOR does quick research/validation
4. Only approved articles proceed to expensive Claude Max enrichment

This saves Claude Max time for articles that actually matter.
"""

import subprocess
import json
import asyncio
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path
from loguru import logger

# Configure logging
Path("logs").mkdir(exist_ok=True)
logger.add("logs/claude_validator_{time}.log", rotation="1 day", retention="7 days")


@dataclass
class ValidationResult:
    """Result of Claude validation"""

    approved: bool
    confidence: int  # 0-100
    reason: str
    category_override: Optional[str] = None  # If Claude thinks LLAMA got category wrong
    priority_override: Optional[str] = None  # If Claude thinks priority should change
    research_notes: Optional[str] = None  # Quick research findings
    enrichment_hints: Optional[List[str]] = None  # Hints for enrichment phase


class ClaudeValidator:
    """
    Intelligent validation gate using Claude.

    Validates ambiguous articles before expensive enrichment.
    Can do quick web research to verify article validity/relevance.
    """

    # Score ranges
    AUTO_APPROVE_THRESHOLD = 75  # Score >= 75: auto-approve, skip validation
    AUTO_REJECT_THRESHOLD = 40  # Score < 40: auto-reject, skip validation
    # Score 40-75: needs Claude validation

    def __init__(self, use_web_research: bool = True):
        self.use_web_research = use_web_research
        self.stats = {
            "auto_approved": 0,
            "auto_rejected": 0,
            "validated_approved": 0,
            "validated_rejected": 0,
            "validation_errors": 0,
        }

    def _build_validation_prompt(
        self,
        title: str,
        summary: str,
        content: str,
        source: str,
        llama_score: int,
        llama_category: str,
        llama_reason: str,
    ) -> str:
        """Build the validation prompt for Claude"""

        return f"""You are the Intelligence Gatekeeper at Bali Zero.

LLAMA has pre-scored this article. Your job is to VALIDATE before we spend resources on deep enrichment.

═══════════════════════════════════════════════════════════════════════════════
ARTICLE TO VALIDATE
═══════════════════════════════════════════════════════════════════════════════

TITLE: {title}
SOURCE: {source}
SUMMARY: {summary[:500] if summary else "No summary"}

CONTENT PREVIEW:
{content[:1500] if content else "No content"}

═══════════════════════════════════════════════════════════════════════════════
LLAMA'S ASSESSMENT
═══════════════════════════════════════════════════════════════════════════════

Score: {llama_score}/100
Category: {llama_category}
Reason: {llama_reason}

═══════════════════════════════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

1. VALIDATE: Is this article actually relevant for Bali expats/investors?
   - Does it affect visas, taxes, business, property, or lifestyle in Indonesia?
   - Is the information actionable or just noise?
   - Is this news or just clickbait/speculation?

2. VERIFY: Quick fact-check
   - Does this seem like legitimate news from the title/content?
   - Any red flags (clickbait, speculation, outdated)?
   - Is the source credible for this topic?

3. DECIDE: Should we invest Claude Max time in deep enrichment?
   - YES = Article deserves full BaliZero Executive Brief treatment
   - NO = Skip it, not worth the effort

4. IMPROVE: If LLAMA got something wrong, correct it
   - Wrong category? Suggest correct one
   - Wrong priority? Suggest correct one

═══════════════════════════════════════════════════════════════════════════════
RESPOND WITH ONLY THIS JSON (no markdown, no extra text):
═══════════════════════════════════════════════════════════════════════════════

{{
  "approved": <true/false>,
  "confidence": <0-100>,
  "reason": "<One sentence: why approve or reject>",
  "category_override": "<null or correct category if LLAMA was wrong>",
  "priority_override": "<null or 'high'/'medium'/'low' if should change>",
  "research_notes": "<Any quick findings that would help enrichment, or null>",
  "enrichment_hints": ["<hint1>", "<hint2>"] or null
}}

DECISION GUIDELINES:
- APPROVE if: Directly affects expat/investor life, actionable, from credible source
- REJECT if: General Indonesia news with no expat angle, speculation, clickbait, outdated
- When in doubt about relevance, lean toward REJECT (save Claude Max for quality)
"""

    def _call_claude_cli(self, prompt: str, timeout: int = 120) -> Optional[str]:
        """Call Claude via CLI for validation"""
        try:
            logger.debug("Calling Claude for validation...")

            result = subprocess.run(
                ["claude", "-p", "--output-format", "text", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr}")
                return None

            response = result.stdout.strip()

            # Extract JSON from response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "{" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                response = response[json_start:json_end]

            return response

        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timeout during validation")
            return None
        except FileNotFoundError:
            logger.error("Claude CLI not found")
            return None
        except Exception as e:
            logger.error(f"Claude CLI error: {e}")
            return None

    async def validate_article(
        self,
        title: str,
        summary: str,
        content: str,
        source: str,
        llama_score: int,
        llama_category: str,
        llama_reason: str = "",
    ) -> ValidationResult:
        """
        Validate an article using Claude.

        Args:
            title: Article title
            summary: Article summary
            content: Article content (can be partial)
            source: Source name
            llama_score: Score from LLAMA (0-100)
            llama_category: Category from LLAMA
            llama_reason: LLAMA's scoring reason

        Returns:
            ValidationResult with approval decision and metadata
        """

        # Auto-approve high scores
        if llama_score >= self.AUTO_APPROVE_THRESHOLD:
            self.stats["auto_approved"] += 1
            logger.info(f"✅ Auto-approved (score {llama_score}): {title[:50]}...")
            return ValidationResult(
                approved=True,
                confidence=90,
                reason=f"High LLAMA score ({llama_score}) - auto-approved",
                enrichment_hints=[llama_reason] if llama_reason else None,
            )

        # Auto-reject low scores
        if llama_score < self.AUTO_REJECT_THRESHOLD:
            self.stats["auto_rejected"] += 1
            logger.info(f"❌ Auto-rejected (score {llama_score}): {title[:50]}...")
            return ValidationResult(
                approved=False,
                confidence=90,
                reason=f"Low LLAMA score ({llama_score}) - auto-rejected",
            )

        # Score 40-75: needs Claude validation
        logger.info(f"🔍 Validating (score {llama_score}): {title[:50]}...")

        prompt = self._build_validation_prompt(
            title=title,
            summary=summary,
            content=content,
            source=source,
            llama_score=llama_score,
            llama_category=llama_category,
            llama_reason=llama_reason,
        )

        response = self._call_claude_cli(prompt)

        if not response:
            self.stats["validation_errors"] += 1
            # On error, approve medium-high scores, reject medium-low
            fallback_approve = llama_score >= 55
            logger.warning(
                f"Validation failed, fallback: {'approved' if fallback_approve else 'rejected'}"
            )
            return ValidationResult(
                approved=fallback_approve,
                confidence=30,
                reason="Validation failed, using fallback based on LLAMA score",
            )

        try:
            data = json.loads(response)

            approved = data.get("approved", False)

            if approved:
                self.stats["validated_approved"] += 1
                logger.success(f"✅ Validated & approved: {title[:50]}...")
            else:
                self.stats["validated_rejected"] += 1
                logger.info(f"❌ Validated & rejected: {title[:50]}...")

            return ValidationResult(
                approved=approved,
                confidence=data.get("confidence", 50),
                reason=data.get("reason", "No reason provided"),
                category_override=data.get("category_override"),
                priority_override=data.get("priority_override"),
                research_notes=data.get("research_notes"),
                enrichment_hints=data.get("enrichment_hints"),
            )

        except json.JSONDecodeError as e:
            self.stats["validation_errors"] += 1
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Raw response: {response[:500]}")

            # Fallback
            fallback_approve = llama_score >= 55
            return ValidationResult(
                approved=fallback_approve,
                confidence=30,
                reason="JSON parse error, using fallback",
            )

    async def validate_batch(
        self, articles: List[Dict]
    ) -> List[Tuple[Dict, ValidationResult]]:
        """
        Validate a batch of articles.

        Args:
            articles: List of article dicts with keys:
                      title, summary, content, source,
                      relevance_score, category, score_reason

        Returns:
            List of (article, ValidationResult) tuples
        """
        results = []

        for article in articles:
            validation = await self.validate_article(
                title=article.get("title", ""),
                summary=article.get("summary", ""),
                content=article.get("content", ""),
                source=article.get("source", "Unknown"),
                llama_score=article.get("relevance_score", 50),
                llama_category=article.get("category", "general"),
                llama_reason=article.get("score_reason", ""),
            )

            results.append((article, validation))

            # Small delay between validations
            await asyncio.sleep(0.5)

        return results

    def get_stats(self) -> Dict:
        """Get validation statistics"""
        total = sum(self.stats.values())
        return {
            **self.stats,
            "total_processed": total,
            "approval_rate": (
                (self.stats["auto_approved"] + self.stats["validated_approved"])
                / total
                * 100
                if total > 0
                else 0
            ),
        }


async def test_validator():
    """Test the Claude validator"""

    validator = ClaudeValidator()

    test_articles = [
        {
            "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
            "summary": "New policy allows remote workers to stay longer in Bali",
            "content": "The Indonesian government announced a groundbreaking policy...",
            "source": "Jakarta Post",
            "relevance_score": 85,  # High - should auto-approve
            "category": "immigration",
            "score_reason": "visa policy change",
        },
        {
            "title": "New Tax Rules for Foreign Workers",
            "summary": "Changes to PPh 21 withholding for expatriates",
            "content": "The Directorate General of Taxes has issued new guidelines...",
            "source": "Bisnis Indonesia",
            "relevance_score": 55,  # Medium - needs validation
            "category": "tax",
            "score_reason": "tax regulation",
        },
        {
            "title": "Bali Governor Attends Cultural Festival",
            "summary": "Annual festival celebrates Balinese heritage",
            "content": "Governor attended the opening ceremony of the cultural festival...",
            "source": "Tribun Bali",
            "relevance_score": 35,  # Low - should auto-reject
            "category": "lifestyle",
            "score_reason": "local event",
        },
        {
            "title": "Property Prices in Canggu Rise 20%",
            "summary": "Real estate market sees significant growth",
            "content": "Property values in the popular Canggu area have increased...",
            "source": "Property Wire",
            "relevance_score": 62,  # Medium - needs validation
            "category": "property",
            "score_reason": "property market",
        },
    ]

    print("=" * 70)
    print("🔍 CLAUDE VALIDATOR TEST")
    print("=" * 70)

    for article in test_articles:
        print(f"\n📰 {article['title'][:50]}...")
        print(f"   LLAMA Score: {article['relevance_score']} ({article['category']})")

        result = await validator.validate_article(
            title=article["title"],
            summary=article["summary"],
            content=article["content"],
            source=article["source"],
            llama_score=article["relevance_score"],
            llama_category=article["category"],
            llama_reason=article["score_reason"],
        )

        emoji = "✅" if result.approved else "❌"
        print(
            f"   {emoji} Approved: {result.approved} (confidence: {result.confidence})"
        )
        print(f"   Reason: {result.reason}")

        if result.category_override:
            print(f"   Category override: {result.category_override}")
        if result.enrichment_hints:
            print(f"   Hints: {result.enrichment_hints}")

    print("\n" + "=" * 70)
    print("📊 STATS")
    print("=" * 70)
    stats = validator.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")


if __name__ == "__main__":
    asyncio.run(test_validator())
