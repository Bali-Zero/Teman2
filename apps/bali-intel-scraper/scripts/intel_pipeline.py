#!/usr/bin/env python3
"""
BALIZERO INTEL PIPELINE - Complete Flow Orchestrator
=====================================================
The FULL pipeline from RSS to published article with image.

Flow:
┌─────────────────────────────────────────────────────────────────┐
│  0. SEMANTIC DEDUPLICATION (Qdrant)                             │
│     - Check vector similarity > 88% with recent news            │
│     - Skip immediately if duplicate (Save $$$)                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  1. RSS FETCHER                                                 │
│     Raw article: {title, summary, url}                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. LLAMA SCORER (fast, local, free)                            │
│     - Keyword matching + heuristics                             │
│     - Score 0-100, category, priority                           │
│     - Filters obvious noise (score < 40)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. CLAUDE VALIDATOR (intelligent gate)                         │
│     - For ambiguous scores (40-75)                              │
│     - Quick research/validation                                 │
│     - Decides: "Worth enriching?"                               │
│     - Can override LLAMA's category/priority                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (only approved)
┌─────────────────────────────────────────────────────────────────┐
│  4. CLAUDE MAX ENRICHMENT                                       │
│     - Fetches full article content                              │
│     - Writes complete Executive Brief                           │
│     - BaliZero style, actionable insights                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  5. CLAUDE IMAGE REASONING                                      │
│     - Reads the enriched article                                │
│     - Reasons: What scene captures this?                        │
│     - Creates unique Gemini prompt                              │
│     - Browser automation generates image                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  5.5 SEO/AEO OPTIMIZATION                                       │
│     - Schema.org JSON-LD structured data                        │
│     - Meta tags (OG, Twitter, canonical)                        │
│     - TL;DR summary for AI citation                             │
│     - FAQ generation for featured snippets                      │
│     - Entity extraction for LLM knowledge                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  6. SUBMIT FOR APPROVAL (parallel)                              │
│     6a. News Room UI → zantara.balizero.com/intelligence        │
│         (Frontend deployed on Vercel, custom domain)            │
│     6b. Telegram → voting via bot (2/3 majority)                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  7. AUTO-MEMORY (Qdrant)                                        │
│     - Save article vector for future deduplication              │
└─────────────────────────────────────────────────────────────────┘

Cost breakdown:
- Qdrant check: $0 (included in infrastructure)
- LLAMA scoring: $0 (local Ollama)
- Claude validation: ~$0.01 per article (quick validation)
- Claude Max enrichment: ~$0.05 per article (full article)
- Gemini image: $0 (Google One AI Premium)
- SEO/AEO optimization: $0 (local processing)
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from loguru import logger
import httpx

# Import pipeline components
from professional_scorer import score_article
from ollama_scorer import OllamaScorer
from claude_validator import ClaudeValidator
from article_deep_enricher import ArticleDeepEnricher, EnrichedArticle
from gemini_image_generator import GeminiImageGenerator
from seo_aeo_optimizer import SEOAEOOptimizer, optimize_article as seo_optimize
from telegram_approval import TelegramApproval
# Usa versione httpx per evitare problemi TLS con qdrant-client
try:
    from semantic_deduplicator_httpx import SemanticDeduplicator
except ImportError:
    # Fallback alla versione originale se httpx non disponibile
    from semantic_deduplicator import SemanticDeduplicator

# Configure logging
Path("logs").mkdir(exist_ok=True)
logger.add("logs/intel_pipeline_{time}.log", rotation="1 day", retention="7 days")


@dataclass
class PipelineArticle:
    """Article as it flows through the pipeline"""

    # Original data
    title: str
    summary: str
    url: str
    source: str
    content: str = ""
    published_at: Optional[str] = None

    # Deduplication
    is_duplicate: bool = False
    duplicate_of: str = ""
    similarity_score: float = 0.0

    # LLAMA scoring results
    llama_score: int = 0
    llama_category: str = "general"
    llama_priority: str = "medium"
    llama_reason: str = ""
    llama_keywords: List[str] = field(default_factory=list)

    # Claude validation results
    validated: bool = False
    validation_approved: bool = False
    validation_confidence: int = 0
    validation_reason: str = ""
    category_override: Optional[str] = None
    priority_override: Optional[str] = None
    enrichment_hints: List[str] = field(default_factory=list)

    # Enrichment results
    enriched: bool = False
    enriched_article: Optional[EnrichedArticle] = None

    # Image generation
    image_prompt: str = ""
    image_path: str = ""

    # SEO/AEO optimization
    seo_optimized: bool = False
    seo_metadata: Dict = field(default_factory=dict)

    # Approval workflow
    pending_approval: bool = False
    approval_id: str = ""
    approval_status: str = ""  # pending, approved, rejected

    # Final status
    published: bool = False
    publish_result: Dict = field(default_factory=dict)

    @property
    def final_category(self) -> str:
        """Get final category (with override if present)"""
        return self.category_override or self.llama_category

    @property
    def final_priority(self) -> str:
        """Get final priority (with override if present)"""
        return self.priority_override or self.llama_priority


@dataclass
class PipelineStats:
    """Pipeline execution statistics"""

    total_input: int = 0
    dedup_filtered: int = 0
    llama_scored: int = 0
    llama_filtered: int = 0
    claude_validated: int = 0
    claude_approved: int = 0
    claude_rejected: int = 0
    enriched: int = 0
    images_generated: int = 0
    seo_optimized: int = 0
    pending_approval: int = 0
    published: int = 0
    errors: int = 0
    duration_seconds: float = 0


class IntelPipeline:
    """
    Complete intelligence pipeline orchestrator.

    Coordinates all components:
    - Qdrant for semantic deduplication
    - LLAMA for fast scoring
    - Claude for validation
    - Claude Max for enrichment
    - Gemini for images
    """

    def __init__(
        self,
        min_llama_score: int = 40,
        auto_approve_threshold: int = 75,
        generate_images: bool = True,
        require_approval: bool = True,
        dry_run: bool = False,
    ):
        self.min_llama_score = min_llama_score
        self.auto_approve_threshold = auto_approve_threshold
        self.generate_images = generate_images
        self.require_approval = require_approval
        self.dry_run = dry_run

        # Initialize components
        self.deduplicator = SemanticDeduplicator()
        self.ollama_scorer = OllamaScorer()
        self.claude_validator = ClaudeValidator()
        self.enricher = ArticleDeepEnricher(generate_images=generate_images)
        # Initialize image generator if enabled
        if generate_images:
            try:
                self.image_generator = GeminiImageGenerator()
                logger.info("✅ Gemini Image Generator initialized")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Gemini Image Generator: {e}")
                self.image_generator = None
        else:
            self.image_generator = None
        self.seo_optimizer = SEOAEOOptimizer()
        self.approval_system = TelegramApproval() if require_approval else None

        # Stats
        self.stats = PipelineStats()
        
        # Verify critical dependencies
        self._verify_dependencies()

        logger.info("=" * 70)
        logger.info("🚀 BALIZERO INTEL PIPELINE INITIALIZED (v6.5 - Semantic Ready)")
        logger.info(f"   Min LLAMA score: {min_llama_score}")
        logger.info(f"   Auto-approve threshold: {auto_approve_threshold}")
        logger.info(f"   Generate images: {generate_images}")
        logger.info(f"   Require approval: {require_approval}")
        logger.info(f"   Dry run: {dry_run}")
        logger.info("=" * 70)
    
    def _verify_dependencies(self):
        """Verify critical dependencies are available"""
        import os
        
        # Check OpenAI API key (required for semantic deduplication)
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("⚠️ OPENAI_API_KEY not set - semantic deduplication will fail")
        
        # Check Qdrant credentials
        if not os.getenv("QDRANT_API_KEY"):
            logger.warning("⚠️ QDRANT_API_KEY not set - Qdrant operations will fail")
        
        # Check backend URL
        backend_url = os.getenv("BACKEND_API_URL", "https://nuzantara-rag.fly.dev")
        logger.debug(f"Backend URL: {backend_url}")

    async def send_to_news_room(self, article: PipelineArticle) -> bool:
        """
        Send article to backend Intelligence Center News Room.

        This populates https://zantara.balizero.com/intelligence/news-room
        (frontend deployed on Vercel, custom domain) with articles for team 
        review in parallel with Telegram notifications.
        """
        backend_url = os.getenv("BACKEND_API_URL", "https://nuzantara-rag.fly.dev")
        endpoint = f"{backend_url}/api/intel/scraper/submit"

        # Get enriched content if available
        enriched = article.enriched_article
        # EnrichedArticle doesn't have executive_brief, use ai_summary or facts
        if enriched:
            # Build full enriched content
            content_parts = []
            if enriched.ai_summary:
                content_parts.append(f"## Summary\n{enriched.ai_summary}")
            if enriched.facts:
                content_parts.append(f"## Facts\n{enriched.facts}")
            if enriched.bali_zero_take:
                content_parts.append(f"## Bali Zero Take\n{enriched.bali_zero_take}")
            if enriched.next_steps:
                next_steps_str = "\n".join([f"- {k}: {v}" for k, v in enriched.next_steps.items()])
                content_parts.append(f"## Next Steps\n{next_steps_str}")
            
            content = "\n\n".join(content_parts) if content_parts else article.summary
            title = enriched.headline or article.title
        else:
            content = article.summary
            title = article.title

        payload = {
            "title": title,
            "content": content,
            "source_url": article.url,
            "source_name": article.source,
            "category": article.final_category,
            "relevance_score": article.llama_score,
            "published_at": article.published_at,
            "extraction_method": "intel_pipeline",
            "tier": "T2",  # Default tier for pipeline articles
        }
        
        # Add cover image if available
        if enriched and enriched.cover_image:
            payload["cover_image"] = enriched.cover_image
            logger.info(f"   📷 Including cover image: {enriched.cover_image}")

        try:
            # Add API key if available
            headers = {"Content-Type": "application/json"}
            api_key = os.getenv("NUZANTARA_API_KEY")
            if api_key:
                headers["X-API-Key"] = api_key
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

                if result.get("duplicate"):
                    logger.debug(
                        f"News Room: Article already in staging - {title[:50]}"
                    )
                    return False
                else:
                    logger.info(
                        f"✅ Sent to News Room: {result.get('intel_type')} - {title[:50]}"
                    )
                    return True

        except httpx.HTTPError as e:
            logger.warning(f"Failed to send to News Room: {e}")
            return False
        except Exception as e:
            logger.warning(f"News Room send error: {e}")
            return False

    async def process_article(self, article: PipelineArticle) -> PipelineArticle:
        """
        Process a single article through the entire pipeline.

        Steps:
        0. Semantic Deduplication (Qdrant)
        1. LLAMA scoring (fast)
        2. Claude validation (for medium scores)
        3. Claude Max enrichment (if approved)
        4. Image reasoning (if enriched)
        """

        logger.info(f"\n{'=' * 60}")
        logger.info(f"📰 Processing: {article.title[:50]}...")
        logger.info(f"{'=' * 60}")

        # ═══════════════════════════════════════════════════════════════
        # STEP 0: SEMANTIC DEDUPLICATION (The Gatekeeper)
        # ═══════════════════════════════════════════════════════════════
        logger.info("🧠 Step 0: Semantic Deduplication Check...")
        
        try:
            is_dup, original_title, score = await self.deduplicator.is_duplicate(
                article.title, 
                article.summary, 
                article.url
            )
            
            if is_dup:
                logger.warning(f"   🛑 DUPLICATE DETECTED (Score: {score:.2f})")
                logger.warning(f"      Original: {original_title}")
                article.is_duplicate = True
                article.duplicate_of = original_title
                article.similarity_score = score
                self.stats.dedup_filtered += 1
                return article
            
            logger.info("   ✅ New unique content")
            
        except Exception as e:
            logger.error(f"   Dedup check failed (continuing safely): {e}")

        # ═══════════════════════════════════════════════════════════════
        # STEP 1: LLAMA SCORING
        # ═══════════════════════════════════════════════════════════════
        logger.info("\n📊 Step 1: LLAMA Scoring...")

        try:
            # Use professional scorer (keyword-based) + Ollama enhancement
            score_result = await score_article(
                title=article.title,
                content=article.summary or article.content[:500],
                source=article.source,
                source_url=article.url,
                use_ollama=True,  # Enhance with Ollama for edge cases
            )

            article.llama_score = score_result.final_score
            article.llama_category = score_result.matched_category
            article.llama_priority = score_result.priority
            article.llama_reason = score_result.explanation
            article.llama_keywords = score_result.matched_keywords

            self.stats.llama_scored += 1

            logger.info(f"   Score: {article.llama_score}/100")
            logger.info(
                "📊 LLAMA Scoring Results",
                extra={
                    "score": article.llama_score,
                    "category": article.llama_category,
                    "priority": article.llama_priority,
                    "keywords": article.llama_keywords[:10],
                    "source": article.source,
                },
            )

        except Exception as e:
            logger.error(f"   LLAMA scoring failed: {e}")
            article.llama_score = 50  # Default
            article.llama_category = "general"
            self.stats.errors += 1

        # Filter by minimum score
        if article.llama_score < self.min_llama_score:
            logger.info(
                f"   ❌ Filtered (score {article.llama_score} < {self.min_llama_score})"
            )
            self.stats.llama_filtered += 1
            return article

        # ═══════════════════════════════════════════════════════════════
        # STEP 2: CLAUDE VALIDATION
        # ═══════════════════════════════════════════════════════════════
        logger.info("\n🔍 Step 2: Claude Validation...")

        try:
            validation = await self.claude_validator.validate_article(
                title=article.title,
                summary=article.summary,
                content=article.content or article.summary,
                source=article.source,
                llama_score=article.llama_score,
                llama_category=article.llama_category,
                llama_reason=article.llama_reason,
            )

            article.validated = True
            article.validation_approved = validation.approved
            article.validation_confidence = validation.confidence
            article.validation_reason = validation.reason
            article.category_override = validation.category_override
            article.priority_override = validation.priority_override
            article.enrichment_hints = validation.enrichment_hints or []

            self.stats.claude_validated += 1

            if validation.approved:
                self.stats.claude_approved += 1
                logger.success(f"   ✅ Approved (confidence: {validation.confidence})")
                logger.info(
                    "🔍 Claude Validation Success",
                    extra={
                        "confidence": validation.confidence,
                        "category_override": validation.category_override,
                        "priority_override": validation.priority_override,
                        "reason": validation.reason,
                    },
                )
            else:
                self.stats.claude_rejected += 1
                logger.info(f"   ❌ Rejected (confidence: {validation.confidence})")
                logger.info(f"   Reason: {validation.reason}")
                logger.info(
                    "🔍 Claude Validation Rejected",
                    extra={
                        "confidence": validation.confidence,
                        "reason": validation.reason,
                    },
                )
                return article

            if validation.category_override:
                logger.info(
                    f"   Category override: {article.llama_category} → {validation.category_override}"
                )
            if validation.priority_override:
                logger.info(
                    f"   Priority override: {article.llama_priority} → {validation.priority_override}"
                )

        except Exception as e:
            logger.error(f"   Claude validation failed: {e}")
            # On validation error, approve if score is decent
            article.validation_approved = article.llama_score >= 55
            self.stats.errors += 1

        if not article.validation_approved:
            return article

        # ═══════════════════════════════════════════════════════════════
        # STEP 3: CLAUDE MAX ENRICHMENT
        # ═══════════════════════════════════════════════════════════════
        logger.info("\n✍️ Step 3: Claude Max Enrichment...")

        if self.dry_run:
            logger.info("   [DRY RUN] Skipping enrichment")
            return article

        try:
            enriched = await self.enricher.enrich_article(
                title=article.title,
                summary=article.summary,
                source_url=article.url,
                source=article.source,
                category=article.final_category,
                published_at=article.published_at,
            )

            if enriched:
                article.enriched = True
                article.enriched_article = enriched
                self.stats.enriched += 1

                logger.success(f"   ✅ Enriched: {enriched.headline[:50]}...")
                logger.info(
                    "✍️ Article Enrichment Results",
                    extra={
                        "headline": enriched.headline,
                        "category": enriched.category,
                        "priority": enriched.priority,
                        "relevance_score": enriched.relevance_score,
                        "fact_count": len(enriched.facts.split("\n"))
                        if enriched.facts
                        else 0,
                    },
                )
            else:
                logger.error("   ❌ Enrichment failed")
                self.stats.errors += 1

        except Exception as e:
            logger.error(f"   Enrichment error: {e}")
            self.stats.errors += 1

        # ═══════════════════════════════════════════════════════════════
        # STEP 4: IMAGE REASONING (handled by Claude Code)
        # ═══════════════════════════════════════════════════════════════
        if article.enriched and self.generate_images and self.image_generator:
            logger.info("\n🎨 Step 4: Image Reasoning Prepared...")
            logger.info("   Image context saved for Claude to reason about")
            logger.info("   Claude will create unique prompt based on article content")
            # Check if image was prepared in enricher
            if article.enriched_article and article.enriched_article.cover_image:
                self.stats.images_generated += 1
                logger.success(f"   ✅ Image prepared: {article.enriched_article.cover_image}")
            # Actual image generation happens in enricher with browser automation

        # ═══════════════════════════════════════════════════════════════
        # STEP 5.5: SEO/AEO OPTIMIZATION
        # ═══════════════════════════════════════════════════════════════
        if article.enriched and article.enriched_article:
            logger.info("\n🔍 Step 5.5: SEO/AEO Optimization...")

            try:
                # Build article dict for SEO optimizer
                enriched = article.enriched_article
                # Combine article sections for SEO content
                full_content = f"{enriched.facts}\n\n{enriched.bali_zero_take}"
                article_data = {
                    "title": enriched.headline,
                    "content": full_content,
                    "enriched_content": full_content,
                    "category": enriched.category,
                    "source_url": article.url,
                    "image_url": article.image_path or "",
                    "published_date": article.published_at
                    or datetime.now().isoformat(),
                }

                # Optimize for SEO/AEO
                optimized = seo_optimize(article_data)
                article.seo_metadata = optimized.get("seo", {})
                article.seo_optimized = True
                self.stats.seo_optimized += 1

                logger.success("   ✅ SEO/AEO optimization complete")
                logger.info(
                    f"   Title: {article.seo_metadata.get('title', '')[:50]}..."
                )
                logger.info(
                    f"   Keywords: {', '.join(article.seo_metadata.get('keywords', [])[:5])}"
                )
                logger.info(
                    f"   Entities: {', '.join(article.seo_metadata.get('key_entities', [])[:5])}"
                )
                logger.info(
                    f"   FAQs: {len(article.seo_metadata.get('faq_items', []))} generated"
                )

            except Exception as e:
                logger.error(f"   ❌ SEO optimization failed: {e}")
                self.stats.errors += 1

        # ═══════════════════════════════════════════════════════════════
        # STEP 6: SUBMIT FOR APPROVAL (Telegram + News Room)
        # ═══════════════════════════════════════════════════════════════
        # Submit if enriched (SEO is optional, enrichment is required)
        if article.enriched and article.enriched_article:
            logger.info("\n📨 Step 6: Submitting for Approval...")

            # 6a. Send to News Room (zantara.balizero.com/intelligence/news-room)
            if not self.dry_run:
                try:
                    news_room_sent = await self.send_to_news_room(article)
                    if news_room_sent:
                        logger.info("   📰 Sent to News Room UI")
                except Exception as e:
                    logger.warning(f"   ⚠️ News Room submission failed: {e}")

            # 6b. Send to Telegram for voting
            if self.require_approval and self.approval_system:
                try:
                    enriched = article.enriched_article
                    if not enriched:
                        logger.warning("   ⚠️ Cannot submit: enriched_article is None")
                        return article
                    
                    # Build enriched content from available fields
                    enriched_content = enriched.ai_summary or ""
                    if enriched.facts:
                        enriched_content += "\n\n" + enriched.facts
                    if enriched.bali_zero_take:
                        enriched_content += "\n\n" + enriched.bali_zero_take
                    
                    article_data = {
                        "title": enriched.headline or article.title,
                        "content": enriched_content or article.summary,
                        "enriched_content": enriched_content or article.summary,
                        "category": enriched.category or article.final_category,
                        "source": article.source,
                        "source_url": article.url,
                        "image_url": article.image_path or "",
                    }

                    pending = await self.approval_system.submit_for_approval(
                        article=article_data,
                        seo_metadata=article.seo_metadata,
                        enriched_content=enriched_content or article.summary,
                    )

                    article.pending_approval = True
                    article.approval_id = pending.article_id
                    article.approval_status = "pending"
                    self.stats.pending_approval += 1

                    logger.success("   ✅ Submitted for approval")
                    logger.info(f"   Article ID: {pending.article_id}")
                    logger.info(f"   HTML Preview: {pending.preview_html}")
                    if pending.telegram_message_id:
                        logger.info("   📱 Telegram notification sent!")
                    else:
                        logger.warning(
                            "   ⚠️ Telegram notification not sent (check config)"
                        )

                except Exception as e:
                    logger.error(f"   ❌ Approval submission failed: {e}")
                    self.stats.errors += 1
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 7: AUTO-MEMORY (Save to Qdrant)
        # ═══════════════════════════════════════════════════════════════
        # Save ALL approved articles to memory, not just pending approval
        # This ensures future deduplication works even if Telegram fails
        if article.validation_approved and article.enriched and not self.dry_run:
            logger.info("\n💾 Step 7: Saving to Semantic Memory...")
            try:
                # Usa il titolo/contenuto arricchito per l'embedding (più preciso)
                enriched = article.enriched_article
                if not enriched:
                    logger.warning("   ⚠️ Cannot save: enriched_article is None")
                    return article
                
                await self.deduplicator.save_article({
                    "title": enriched.headline or article.title,
                    "summary": enriched.ai_summary or article.summary[:500], # Short AI summary
                    "content": enriched.facts or enriched.ai_summary or article.summary,      # Full facts for deeper context
                    "url": article.url,
                    "source": article.source,
                    "category": article.final_category,
                    "publishedAt": article.published_at,
                    "tier": "T2"
                })
                logger.success("   ✅ Saved to Qdrant (Future deduplication enabled)")
                
            except Exception as e:
                logger.error(f"   Memory save failed: {e}")

        return article

    async def process_batch(
        self, articles: List[Dict]
    ) -> Tuple[List[PipelineArticle], PipelineStats]:
        """
        Process a batch of articles through the pipeline.

        Args:
            articles: List of article dicts with keys:
                     title, summary, url, source, content (optional)

        Returns:
            (processed_articles, stats)
        """
        import time

        start_time = time.time()

        self.stats = PipelineStats()
        self.stats.total_input = len(articles)

        logger.info("=" * 70)
        logger.info(f"🚀 PROCESSING BATCH: {len(articles)} articles")
        logger.info("=" * 70)

        results = []

        for i, article_dict in enumerate(articles, 1):
            logger.info(f"\n[{i}/{len(articles)}] {'=' * 50}")

            # Validate URL before creating article
            # Support multiple URL field names: url, source_url, sourceUrl
            url = (
                article_dict.get("url") 
                or article_dict.get("source_url") 
                or article_dict.get("sourceUrl")
                or ""
            )
            if not url or not url.startswith(("http://", "https://")):
                logger.warning(f"Skipping article with invalid URL: {url}")
                self.stats.errors += 1
                continue
            
            # Create pipeline article
            article = PipelineArticle(
                title=article_dict.get("title", ""),
                summary=article_dict.get("summary", ""),
                url=url,
                source=article_dict.get("source", "Unknown"),
                content=article_dict.get("content", ""),
                published_at=article_dict.get("published_at"),
            )

            # Process through pipeline
            processed = await self.process_article(article)
            results.append(processed)

            # Rate limit between articles
            await asyncio.sleep(1)

        self.stats.duration_seconds = time.time() - start_time

        # Print summary
        self._print_summary()

        # Save batch run audit log
        try:
            audit_dir = Path("logs/audit")
            audit_dir.mkdir(exist_ok=True, parents=True)
            audit_file = (
                audit_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(audit_file, "w") as f:
                json.dump(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "stats": asdict(self.stats),
                        "results_count": len(results),
                    },
                    f,
                    indent=2,
                    default=str, # Fix for serialization issues
                )
            logger.info(f"📁 Run audit saved to {audit_file}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save run audit: {e}")

        # Cleanup resources
        if hasattr(self.deduplicator, 'close'):
            self.deduplicator.close()
        
        return results, self.stats

    def _print_summary(self):
        """Print pipeline execution summary"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 PIPELINE SUMMARY")
        logger.info("=" * 70)
        logger.info(f"   Total input:      {self.stats.total_input}")
        logger.info(f"   Dedup filtered:   {self.stats.dedup_filtered}")
        logger.info(f"   LLAMA scored:     {self.stats.llama_scored}")
        logger.info(f"   LLAMA filtered:   {self.stats.llama_filtered}")
        logger.info(f"   Claude validated: {self.stats.claude_validated}")
        logger.info(f"   Claude approved:  {self.stats.claude_approved}")
        logger.info(f"   Claude rejected:  {self.stats.claude_rejected}")
        logger.info(f"   Enriched:         {self.stats.enriched}")
        logger.info(f"   Images generated: {self.stats.images_generated}")
        logger.info(f"   SEO optimized:    {self.stats.seo_optimized}")
        logger.info(f"   Pending approval: {self.stats.pending_approval}")
        logger.info(f"   Published:        {self.stats.published}")
        logger.info(f"   Errors:           {self.stats.errors}")
        logger.info(f"   Duration:         {self.stats.duration_seconds:.1f}s")
        logger.info("=" * 70)


async def test_pipeline():
    """Test the complete pipeline"""

    pipeline = IntelPipeline(
        min_llama_score=40,
        auto_approve_threshold=75,
        generate_images=False,  # Disable for test
        require_approval=False,  # Disable for test
        dry_run=True,  # Don't actually enrich
    )

    test_articles = [
        {
            "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
            "summary": "The Indonesian government announced a groundbreaking policy extending the digital nomad visa validity from 1 year to 5 years.",
            "url": "https://example.com/nomad-visa",
            "source": "Jakarta Post",
        },
        {
            "title": "New Coretax System Causing NPWP Registration Problems",
            "summary": "The new Coretax tax system is experiencing errors and delays for NPWP registration.",
            "url": "https://example.com/coretax",
            "source": "Bisnis Indonesia",
        },
        {
            "title": "Bali Cultural Festival Attracts Thousands",
            "summary": "Annual festival celebrates traditional Balinese arts and culture.",
            "url": "https://example.com/festival",
            "source": "Tribun Bali",
        },
    ]

    results, stats = await pipeline.process_batch(test_articles)

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    for article in results:
        if article.is_duplicate:
            print(f"\n🔄 DUPLICATE: {article.title[:50]}...")
            print(f"   Of: {article.duplicate_of}")
            continue
            
        emoji = "✅" if article.validation_approved else "❌"
        print(f"\n{emoji} {article.title[:50]}...")
        print(f"   LLAMA: {article.llama_score} ({article.llama_category})")
        print(f"   Validated: {article.validated}")
        print(f"   Approved: {article.validation_approved}")
        print(f"   Reason: {article.validation_reason}")
        if article.seo_optimized:
            print("   SEO: ✅ Optimized")
            print(
                f"   Keywords: {', '.join(article.seo_metadata.get('keywords', [])[:5])}"
            )
            print(
                f"   Entities: {', '.join(article.seo_metadata.get('key_entities', [])[:3])}"
            )


if __name__ == "__main__":
    asyncio.run(test_pipeline())
