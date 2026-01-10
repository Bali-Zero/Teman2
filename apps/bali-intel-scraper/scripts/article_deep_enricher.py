#!/usr/bin/env python3
"""
BALIZERO ARTICLE DEEP ENRICHER
================================
Complete pipeline for transforming news into BaliZero intelligence articles.

Flow:
1. Receive RSS item (title, summary, source_url)
2. Fetch FULL original article from source URL
3. Use Claude Max (via CLI) to:
   - Analyze the full article
   - Conduct supplementary research if needed
   - Write complete BaliZero Executive Brief article
4. Return enriched article ready for API

Uses Claude Max subscription via CLI (no API costs!)
"""

import subprocess
import json
import asyncio
import httpx
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
from loguru import logger

# Note: Using Claude CLI for Claude Max subscription (no API key needed)

# For extracting full article content
try:
    from trafilatura import fetch_url, extract

    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("trafilatura not installed - pip install trafilatura")

try:
    from newspaper import Article

    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False
    logger.warning("newspaper3k not installed - pip install newspaper3k")

# Configure logging
Path("logs").mkdir(exist_ok=True)
logger.add("logs/deep_enricher_{time}.log", rotation="1 day", retention="7 days")


@dataclass
class EnrichedArticle:
    """Complete enriched article ready for API"""

    title: str
    headline: str  # BaliZero headline (benefit/risk driven)
    tldr: Dict  # 30-second brief
    facts: str  # Pure journalism section
    bali_zero_take: str  # Strategic analysis
    next_steps: Dict  # Actionable advice by profile
    category: str
    priority: str
    relevance_score: int
    ai_summary: str
    ai_tags: List[str]
    source: str
    source_url: str
    original_content: str  # Full original article
    published_at: Optional[str]
    components: List[str]  # Suggested interactive components
    cover_image: Optional[str] = None  # Generated cover image path
    image_prompt: Optional[str] = None  # Prompt used for image generation


class ArticleDeepEnricher:
    """
    Deep article enrichment using Claude Max subscription.
    Fetches full article, conducts research, writes BaliZero style.
    """

    # System prompt loaded from style guide
    SYSTEM_PROMPT = """You are the Senior Editor at Bali Zero, an Intelligent Business Operating System for expats and investors in Indonesia.

ROLE:
- You are "L'Insider Intelligente" - the trusted expert who reads boring laws and tells readers only what actually matters
- Think: experienced legal advisor having coffee with a client
- NOT a generic news aggregator or chatbot

AUDIENCE:
- Smart, busy expats and investors in Indonesia
- They hate bureaucracy and want actionable insights
- They ask: "What does this mean for ME?"

TONE GUIDELINES:
- Authoritative but accessible ("Autorevolezza Rilassata")
- Cut the fluff. No "In today's rapidly changing world...". Start with the news.
- Use "We" or "Noi di Bali Zero" when giving opinions
- Be honest about complexity: "This is currently unclear, but here is our best interpretation"
- Confident but not arrogant. Helpful but not sycophantic.

CONTEXT-AWARE ADAPTATION:
- immigration topics → Empathetic tone, quality of life focus
- business/tax topics → Numeric, strategic, ROI focus
- urgent news → C-level brief, immediate point

WRITING RULES:
- Show, don't tell: Use specific numbers, not adjectives
- No jargon without explanation or link
- Max 800 words total (~5 min read)
- Every sentence must earn its place

FORBIDDEN PHRASES:
- "Delve into", "landscape", "tapestry", "paradigm shift"
- "It's important to note that...", "At the end of the day..."
- "Game-changer", "revolutionary" (be specific instead)
- Generic AI filler phrases

INDONESIAN TERMS TO KEEP:
KITAS, KITAP, NPWP, PPh, PT PMA, NIB, OSS, HGB, SHM, BKPM, Imigrasi, Kemenkeu, DJP"""

    def __init__(
        self,
        api_url: str = "https://nuzantara-rag.fly.dev",
        generate_images: bool = True,  # Always True - images are mandatory
    ):
        self.api_url = api_url
        self.generate_images = generate_images
        self.image_generator = None

        # Load image generator if enabled
        if generate_images:
            try:
                from gemini_image_generator import GeminiImageGenerator

                self.image_generator = GeminiImageGenerator()
                logger.info("Gemini Image Generator loaded")
            except ImportError:
                logger.warning("gemini_image_generator not found - images disabled")

        # Load style bible if available
        style_bible_path = Path(__file__).parent.parent / "config" / "style_bible.txt"
        if style_bible_path.exists():
            logger.info(f"Loaded style bible from {style_bible_path}")

    def fetch_full_article(self, url: str) -> Optional[Dict]:
        """
        Fetch the complete article content from source URL.
        Uses trafilatura (primary) with newspaper3k fallback.

        Returns:
            {
                "title": str,
                "content": str,
                "author": str,
                "publish_date": str,
                "top_image": str
            }
        """
        logger.info(f"📥 Fetching full article from: {url[:60]}...")

        result = {
            "title": "",
            "content": "",
            "author": "",
            "publish_date": "",
            "top_image": "",
        }

        # Try trafilatura first (better for news sites)
        if TRAFILATURA_AVAILABLE:
            try:
                downloaded = fetch_url(url)
                if downloaded:
                    content = extract(
                        downloaded,
                        include_comments=False,
                        include_tables=True,
                        output_format="txt",
                    )
                    if content and len(content) > 200:
                        result["content"] = content
                        logger.success(f"✅ Trafilatura extracted {len(content)} chars")
            except Exception as e:
                logger.warning(f"Trafilatura failed: {e}")

        # Fallback to newspaper3k
        if not result["content"] and NEWSPAPER_AVAILABLE:
            try:
                article = Article(url)
                article.download()
                article.parse()

                result["title"] = article.title or ""
                result["content"] = article.text or ""
                result["author"] = ", ".join(article.authors) if article.authors else ""
                result["publish_date"] = (
                    str(article.publish_date) if article.publish_date else ""
                )
                result["top_image"] = article.top_image or ""

                if result["content"]:
                    logger.success(
                        f"✅ Newspaper3k extracted {len(result['content'])} chars"
                    )
            except Exception as e:
                logger.warning(f"Newspaper3k failed: {e}")

        # Final fallback: simple httpx fetch
        if not result["content"]:
            try:
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    response = client.get(
                        url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (compatible; BaliZeroBot/1.0)"
                        },
                    )
                    if response.status_code == 200:
                        # Extract text from HTML (very basic)
                        html = response.text
                        # Remove scripts and styles
                        html = re.sub(
                            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL
                        )
                        html = re.sub(
                            r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL
                        )
                        # Remove HTML tags
                        text = re.sub(r"<[^>]+>", " ", html)
                        # Clean whitespace
                        text = re.sub(r"\s+", " ", text).strip()

                        if len(text) > 500:
                            result["content"] = text[:10000]  # Limit to 10k chars
                            logger.success(
                                f"✅ Basic extraction got {len(result['content'])} chars"
                            )
            except Exception as e:
                logger.error(f"All extraction methods failed: {e}")

        if not result["content"]:
            logger.error(f"❌ Could not extract content from {url}")
            return None

        return result

    def build_enrichment_prompt(
        self,
        original_title: str,
        original_summary: str,
        full_content: str,
        source: str,
        category: str,
    ) -> str:
        """Build the complete prompt for Claude to write BaliZero article"""

        return f"""{self.SYSTEM_PROMPT}

---

## TASK: Write a Complete BaliZero Executive Brief Article

You have received this news item. Your job is to:
1. Analyze the full original article
2. Identify what's REALLY important for expats and investors
3. Write a complete BaliZero article following our "Executive Brief" structure
4. Add your strategic interpretation ("The Bali Zero Take")

---

## SOURCE INFORMATION

**Original Title:** {original_title}
**Source:** {source}
**Category:** {category}
**Original Summary:** {original_summary}

---

## FULL ORIGINAL ARTICLE CONTENT:

{full_content[:8000]}

---

## OUTPUT FORMAT (STRICT JSON)

Respond ONLY with valid JSON (no markdown, no extra text):

{{
  "headline": "<Benefit/Risk-driven headline, max 12 words, in English>",

  "tldr": {{
    "should_worry": "<Yes|No|Depends>",
    "what": "<One line: what happened>",
    "who": "<Who this affects>",
    "when": "<Effective date or timeline>",
    "risk_level": "<High|Medium|Low>"
  }},

  "facts": "<Pure journalism section. What happened, dates, numbers, sources. No opinions. 200-300 words. In English.>",

  "bali_zero_take": {{
    "hidden_insight": "<What they don't tell you - 2-3 sentences>",
    "our_analysis": "<Strategic context, non-obvious implications - 3-4 sentences>",
    "our_advice": "<Clear actionable recommendation - 2-3 sentences>"
  }},

  "next_steps": {{
    "expat": ["<Action 1>", "<Action 2>"],
    "investor": ["<Action 1>", "<Action 2>"]
  }},

  "category": "<immigration|business|tax|property|lifestyle|tech|legal>",
  "priority": "<high|medium|low>",
  "relevance_score": <0-100>,

  "ai_summary": "<Executive summary for social/preview, max 280 chars, in English>",
  "ai_tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],

  "suggested_components": ["<component1>", "<component2>"],

  "research_notes": "<Any additional context you'd add from your knowledge about this topic - regulations, history, comparisons>"
}}

NOTES:
- "suggested_components" can include: "timeline", "comparison-table", "decision-tree", "checklist", "risk-meter", "alert-box", "expert-quote"
- For immigration/visa topics, add specific permit types affected
- For tax topics, include specific tax codes (PPh 21, PPh 26, etc.)
- For business topics, mention relevant government bodies (BKPM, OSS, etc.)
- Be SPECIFIC with numbers, dates, and requirements
"""

    def call_claude_cli(self, prompt: str, timeout: int = 300) -> Optional[str]:
        """
        Call Claude via CLI using Max subscription.
        Uses `claude -p` for prompt mode (no API costs!).
        Requires Claude CLI to be installed and authenticated.
        Supports OAuth token via CLAUDE_CODE_OAUTH_TOKEN env var.
        """
        try:
            logger.info("🤖 Calling Claude Max (via CLI)...")
            
            # Prepare environment with OAuth token if available
            env = os.environ.copy()
            oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
            if oauth_token:
                env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token
                logger.debug("Using OAuth token from environment")

            result = subprocess.run(
                ["claude", "-p", "--output-format", "text", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"Claude CLI error: {error_msg}")
                # Check if authentication is needed
                if "auth" in error_msg.lower() or "login" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    logger.error("Claude CLI authentication required. Set CLAUDE_API_KEY or run: claude auth login")
                return None

            response = result.stdout.strip()

            # Extract JSON from markdown if present
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()

            logger.success("✅ Claude response received")
            return response

        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timeout")
            return None
        except FileNotFoundError:
            logger.error("Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
            return None
        except Exception as e:
            logger.error(f"Claude CLI error: {e}")
            return None


    async def enrich_article(
        self,
        title: str,
        summary: str,
        source_url: str,
        source: str,
        category: str = "business",
        published_at: Optional[str] = None,
    ) -> Optional[EnrichedArticle]:
        """
        Complete enrichment pipeline for a single article.

        1. Fetch full article from URL
        2. Call Claude to analyze and write BaliZero article
        3. Return structured EnrichedArticle
        """
        logger.info("=" * 60)
        logger.info(f"🔬 DEEP ENRICHING: {title[:50]}...")
        logger.info("=" * 60)

        # Step 1: Fetch full article
        full_article = self.fetch_full_article(source_url)

        if not full_article or not full_article.get("content"):
            logger.warning("⚠️ Could not fetch full article, using summary only")
            content = summary
        else:
            content = full_article["content"]
            logger.info(f"📄 Full article: {len(content)} chars")

        # Step 2: Build prompt and call Claude
        prompt = self.build_enrichment_prompt(
            original_title=title,
            original_summary=summary,
            full_content=content,
            source=source,
            category=category,
        )

        response = self.call_claude_cli(prompt)

        if not response:
            logger.error("❌ Claude enrichment failed")
            return None

        # Step 3: Parse response
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Raw response: {response[:500]}")
            return None

        # Step 4: Build EnrichedArticle

        # Format bali_zero_take object as readable text
        bali_zero_take_obj = data.get("bali_zero_take", {})
        if isinstance(bali_zero_take_obj, dict) and bali_zero_take_obj:
            bali_zero_take_text = f"""**What They Don't Tell You:**
{bali_zero_take_obj.get("hidden_insight", "")}

**Our Analysis:**
{bali_zero_take_obj.get("our_analysis", "")}

**Our Advice:**
{bali_zero_take_obj.get("our_advice", "")}"""
        else:
            bali_zero_take_text = str(bali_zero_take_obj) if bali_zero_take_obj else ""

        enriched = EnrichedArticle(
            title=title,
            headline=data.get("headline", title),
            tldr=data.get("tldr", {}),
            facts=data.get("facts", ""),
            bali_zero_take=bali_zero_take_text,
            next_steps=data.get("next_steps", {}),
            category=data.get("category", category),
            priority=data.get("priority", "medium"),
            relevance_score=data.get("relevance_score", 50),
            ai_summary=data.get("ai_summary", summary[:280]),
            ai_tags=data.get("ai_tags", []),
            source=source,
            source_url=source_url,
            original_content=content[:5000],  # Store first 5k chars
            published_at=published_at,
            components=data.get("suggested_components", []),
        )

        logger.success(f"✅ Enriched: {enriched.headline[:50]}...")
        logger.info(
            f"   Category: {enriched.category} | Priority: {enriched.priority} | Score: {enriched.relevance_score}"
        )

        # Step 5: Generate cover image (MANDATORY with retry and fallback)
        if not self.generate_images:
            raise ValueError("Image generation is mandatory but was disabled")
        if not self.image_generator:
            raise ValueError("Image generator is mandatory but not initialized")
        
        logger.info("🎨 Generating cover image (mandatory)...")
        
        # Retry logic: try 3 times
        max_retries = 3
        image_result = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"   Attempt {attempt}/{max_retries}...")
                image_result = await self.generate_cover_image_browser(
                    title=enriched.headline,
                    summary=enriched.ai_summary,
                    category=enriched.category,
                    full_content=content,  # Pass the FULL article content for reasoning
                )
                if image_result and image_result.get("image_path"):
                    enriched.cover_image = image_result.get("image_path")
                    enriched.image_prompt = image_result.get("prompt", "PENDING_CLAUDE_REASONING")
                    logger.success(f"   ✅ Cover image generated: {enriched.cover_image}")
                    if image_result.get("context_file"):
                        logger.info(f"📋 Image context prepared: {image_result.get('context_file')}")
                    break  # Success, exit retry loop
                else:
                    if attempt < max_retries:
                        logger.warning(f"   ⚠️ Attempt {attempt} returned no image_path, retrying...")
                    else:
                        raise ValueError("Image generation returned no image_path after all retries")
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"   ⚠️ Attempt {attempt} failed: {e}, retrying...")
                    await asyncio.sleep(2)  # Wait 2 seconds before retry
                else:
                    logger.error(f"   ❌ All {max_retries} attempts failed: {e}")
                    # Fallback to internet image search
                    logger.info("   🔄 Falling back to internet image search...")
                    try:
                        fallback_image = await self.fetch_image_from_internet(
                            title=enriched.headline,
                            category=enriched.category,
                            summary=enriched.ai_summary
                        )
                        if fallback_image:
                            enriched.cover_image = fallback_image
                            enriched.image_prompt = f"Fallback image from internet for: {enriched.headline}"
                            logger.success(f"   ✅ Fallback image found: {enriched.cover_image}")
                        else:
                            raise RuntimeError("Both image generation and internet fallback failed")
                    except Exception as fallback_error:
                        logger.error(f"   ❌ Fallback also failed: {fallback_error}")
                        raise RuntimeError(f"Failed to generate cover image after {max_retries} attempts and fallback: {e}")
        
        if not enriched.cover_image:
            raise RuntimeError("Cover image is mandatory but was not generated")

        return enriched

    async def fetch_image_from_internet(
        self, title: str, category: str, summary: str = ""
    ) -> Optional[str]:
        """
        Fallback: Fetch a relevant image from internet using Unsplash API.
        
        Uses Unsplash API (free tier) to find relevant images based on article content.
        """
        try:
            import httpx
            
            # Build search query from title and category
            search_query = f"{title} {category}".strip()[:100]  # Limit query length
            
            # Try Unsplash API first (free, no auth needed for basic usage)
            # Using Unsplash Source API (simpler, no API key needed)
            unsplash_url = f"https://source.unsplash.com/1200x630/?{httpx.quote(search_query)}"
            
            # Alternative: Use a more specific search
            # For better results, we could use Unsplash API with a free API key
            # For now, using the source API which is simpler
            
            logger.info(f"   🔍 Searching internet for image: {search_query[:50]}...")
            
            # Return the Unsplash URL (they serve images directly)
            # The image will be fetched by the frontend
            return unsplash_url
            
        except Exception as e:
            logger.warning(f"   ⚠️ Internet image search failed: {e}")
            # Try alternative: Pexels API (also free)
            try:
                # Pexels doesn't require API key for basic usage via their website
                # But for programmatic access, we'd need an API key
                # For now, return None and let the error propagate
                return None
            except Exception:
                return None

    async def generate_cover_image_browser(
        self, title: str, summary: str, category: str, full_content: str = ""
    ) -> Optional[Dict]:
        """
        Prepare cover image generation using Gemini via Chrome browser automation.

        NEW APPROACH: This method provides the REASONING FRAMEWORK for Claude.
        Claude (running this code) should:
        1. Read the full article content
        2. Use the reasoning framework to decide the best scene
        3. Create a unique prompt for THIS specific article
        4. Execute browser automation to generate the image

        The image prompt is NOT auto-generated. Claude must THINK about it.

        Returns:
            {"image_path": str, "reasoning_framework": str, "category_guidelines": dict}
        """
        if not self.image_generator:
            return None

        # Generate output path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:30]
        filename = f"cover_{timestamp}_{slug}.png"
        output_dir = Path("data/images")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / filename)

        # Get the reasoning framework for Claude to use
        reasoning_framework = self.image_generator.build_reasoning_prompt(
            title=title, summary=summary, full_content=full_content, category=category
        )

        # Get category guidelines
        category_guidelines = self.image_generator.get_category_guidelines(category)

        logger.info("🎨 Image generation framework prepared")
        logger.info(f"📁 Output path: {output_path}")
        logger.info(f"📝 Category: {category}")

        # Save the reasoning context for Claude to use
        reasoning_context = {
            "action": "generate_image_with_reasoning",
            "article": {
                "title": title,
                "summary": summary,
                "category": category,
                "content_preview": full_content[:2000] if full_content else summary,
            },
            "output_path": output_path,
            "reasoning_framework": reasoning_framework,
            "category_guidelines": category_guidelines,
            "instructions_for_claude": """
IMPORTANT: Do NOT use a predefined image prompt.

You (Claude) must:
1. READ the article content above
2. ANSWER the 5 reasoning questions:
   - Central theme (problem/solution/info?)
   - Emotional core (how should reader feel?)
   - The moment (what scene captures this?)
   - Universal vs specific
   - 2-second test (will viewers understand immediately?)

3. DECIDE on a specific scene based on your reasoning

4. CREATE a unique Gemini prompt using:
   generator.create_gemini_prompt(
       scene_description="<your decided scene>",
       mood="<emotional tone>",
       category="<category>",
       key_details=["<detail1>", "<detail2>", ...]
   )

5. EXECUTE browser automation with that prompt

Each article deserves a UNIQUE, REASONED image - not a random selection.
""",
            "browser_automation_sequence": self.image_generator.get_browser_automation_sequence(
                prompt="<TO BE CREATED BY CLAUDE AFTER REASONING>",
                output_path=output_path,
            ),
        }

        # Save context file
        context_file = output_dir / f"image_context_{filename.replace('.png', '.json')}"
        with open(context_file, "w") as f:
            json.dump(reasoning_context, f, indent=2, ensure_ascii=False)

        logger.info(f"📋 Image reasoning context saved: {context_file}")

        return {
            "image_path": output_path,
            "context_file": str(context_file),
            "reasoning_framework": reasoning_framework,
            "category_guidelines": category_guidelines,
            "status": "ready_for_claude_reasoning",
        }

    def format_as_markdown(self, article: EnrichedArticle) -> str:
        """Format enriched article as BaliZero markdown"""

        tldr = article.tldr
        # bali_zero_take is now already formatted text, no need to parse
        take_text = article.bali_zero_take
        steps = article.next_steps

        md = f"""# 📰 {article.headline}

---

## ⚡ THE 30-SECOND BRIEF

> **Devo preoccuparmi?** {tldr.get("should_worry", "Dipende")}

- 🎯 **Cosa:** {tldr.get("what", "N/A")}
- 👤 **Chi riguarda:** {tldr.get("who", "N/A")}
- 📅 **Quando:** {tldr.get("when", "N/A")}
- ⚠️ **Rischio/Opportunità:** {tldr.get("risk_level", "Medium")}

---

## 📋 I FATTI

{article.facts}

| Aspetto | Dettaglio |
|---------|-----------|
| Fonte | {article.source} |
| Categoria | {article.category} |
| Priority | {article.priority} |

---

## 🧠 THE BALI ZERO TAKE

> *"Cosa non dicono i giornali..."*

{take_text}

---

## 🚀 NEXT STEPS

### Se sei un Expat:
"""
        for step in steps.get("expat", []):
            md += f"- ✅ {step}\n"

        md += "\n### Se sei un Investitore/Business Owner:\n"
        for step in steps.get("investor", []):
            md += f"- ✅ {step}\n"

        md += f"""
---

## 🔗 RISORSE

- 📄 [Fonte originale]({article.source_url})
- 💬 [Prenota consultazione](/contact)

---

**Tags:** {", ".join(article.ai_tags)}
**Categoria:** {article.category}
**Componenti suggeriti:** {", ".join(article.components)}
"""
        return md

    async def send_to_api(
        self,
        article: EnrichedArticle,
        api_key: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict:
        """Send enriched article to Intelligence/News Room (Nuzantara backend)"""

        endpoint = f"{self.api_url}/api/intel/scraper/submit"

        if dry_run:
            logger.info(f"🔍 DRY RUN - Would send: {article.headline[:50]}...")
            return {"success": True, "dry_run": True}

        # Build payload matching ScraperSubmission schema
        payload = {
            "title": article.headline,
            "content": self.format_as_markdown(article),
            "source_url": article.source_url,
            "source_name": article.source,
            "category": article.category,
            "relevance_score": article.relevance_score,
            "published_at": article.published_at,
            "extraction_method": "claude_max",
            "tier": "T1",  # Full mode = T1 (highest quality)
            "components": article.components,
        }

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        if data.get("duplicate"):
                            logger.info(f"⏭️ Duplicate: {article.headline[:40]}...")
                            return {"success": True, "duplicate": True}
                        else:
                            logger.success(f"✅ Sent: {article.headline[:40]}...")
                            return {
                                "success": True,
                                "id": data.get("data", {}).get("id"),
                            }

                logger.error(
                    f"❌ API error: {response.status_code} - {response.text[:200]}"
                )
                return {"success": False, "error": response.text}

        except Exception as e:
            logger.error(f"❌ Send error: {e}")
            return {"success": False, "error": str(e)}


async def enrich_rss_batch(
    items: List[Dict],
    api_url: str = "https://nuzantara-rag.fly.dev",
    api_key: Optional[str] = None,
    min_score: int = 50,
    dry_run: bool = False,
) -> Dict:
    """
    Process a batch of RSS items through deep enrichment.

    Args:
        items: List of RSS items with {title, summary, sourceUrl, source, category}
        api_url: BaliZero API URL
        api_key: API key for authentication
        min_score: Minimum relevance score to send
        dry_run: Preview without sending

    Returns:
        {sent: int, skipped: int, failed: int}
    """
    enricher = ArticleDeepEnricher(api_url=api_url)

    sent = 0
    skipped = 0
    failed = 0

    for item in items:
        # Enrich article
        enriched = await enricher.enrich_article(
            title=item.get("title", ""),
            summary=item.get("summary", ""),
            source_url=item.get("sourceUrl", item.get("source_url", "")),
            source=item.get("source", "Unknown"),
            category=item.get("category", "business"),
            published_at=item.get("publishedAt", item.get("published_at")),
        )

        if not enriched:
            failed += 1
            continue

        # Check relevance
        if enriched.relevance_score < min_score:
            logger.info(
                f"⏭️ Skipped (score {enriched.relevance_score} < {min_score}): {enriched.headline[:40]}..."
            )
            skipped += 1
            continue

        # Send to API
        result = await enricher.send_to_api(enriched, api_key=api_key, dry_run=dry_run)

        if result.get("success"):
            if not result.get("duplicate"):
                sent += 1
            else:
                skipped += 1
        else:
            failed += 1

        # Rate limit
        await asyncio.sleep(3)  # Be gentle with Claude CLI

    return {"sent": sent, "skipped": skipped, "failed": failed}


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="BaliZero Article Deep Enricher")
    parser.add_argument("--url", help="Single article URL to enrich")
    parser.add_argument("--title", default="Test Article", help="Article title")
    parser.add_argument("--source", default="Test Source", help="Source name")
    parser.add_argument("--category", default="business", help="Category")
    parser.add_argument(
        "--api-url", default="https://balizero.com", help="BaliZero API URL"
    )
    parser.add_argument("--api-key", help="API key")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without sending"
    )
    parser.add_argument("--output", help="Save markdown to file")

    args = parser.parse_args()

    if not args.url:
        # Test with sample
        args.url = "https://www.thejakartapost.com/indonesia/2024/12/15/indonesia-extends-digital-nomad-visa.html"
        args.title = "Indonesia Extends Digital Nomad Visa to 5 Years"
        args.source = "Jakarta Post"
        args.category = "immigration"

    enricher = ArticleDeepEnricher(api_url=args.api_url)

    # Enrich
    enriched = await enricher.enrich_article(
        title=args.title,
        summary="",
        source_url=args.url,
        source=args.source,
        category=args.category,
    )

    if enriched:
        print("\n" + "=" * 60)
        print("📋 ENRICHED ARTICLE")
        print("=" * 60)

        # Format and print
        markdown = enricher.format_as_markdown(enriched)
        print(markdown)

        # Save if requested
        if args.output:
            Path(args.output).write_text(markdown)
            print(f"\n💾 Saved to: {args.output}")

        # Send if not dry run
        if not args.dry_run and args.api_key:
            result = await enricher.send_to_api(enriched, api_key=args.api_key)
            print(f"\n📤 API Result: {result}")
    else:
        print("❌ Enrichment failed")


if __name__ == "__main__":
    asyncio.run(main())
