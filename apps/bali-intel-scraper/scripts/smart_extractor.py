#!/usr/bin/env python3
"""
SMART EXTRACTOR - Unbreakable Article Extraction
=================================================
Multi-layer extraction with LLM fallback for resilience.

Extraction Priority:
1. CSS Selectors (fast, free)
2. Trafilatura (smart, free)
3. Newspaper3k (reliable, free)
4. Llama Local (LLM fallback, free - uses your CPU)

If all structured methods fail, Llama extracts the article body
from raw HTML/text using natural language understanding.

Cost: $0 (runs locally)
"""

import asyncio
import httpx
import re
import json
import os
from typing import Optional, Dict
from bs4 import BeautifulSoup, Comment
from loguru import logger

# Optional imports
try:
    from trafilatura import extract as trafilatura_extract
    from trafilatura import fetch_url as trafilatura_fetch

    TRAFILATURA_OK = True
except ImportError:
    TRAFILATURA_OK = False

try:
    from newspaper import Article

    NEWSPAPER_OK = True
except ImportError:
    NEWSPAPER_OK = False


class SmartExtractor:
    """
    Multi-layer article extraction with LLM fallback.
    If CSS selectors break, falls back to Llama for intelligent extraction.
    """

    def __init__(
        self,
        ollama_model: str = "llama3.2:3b",
        ollama_url: str = "http://localhost:11434",
    ):
        # Allow override via env vars
        self.ollama_model = os.getenv("OLLAMA_MODEL", ollama_model)
        self.ollama_url = os.getenv("OLLAMA_URL", ollama_url)
        self.ollama_available = None  # Lazy check

        # Stats
        self.stats = {
            "css_success": 0,
            "trafilatura_success": 0,
            "newspaper_success": 0,
            "llama_success": 0,
            "failed": 0,
        }

    async def check_ollama(self) -> bool:
        """Check if Ollama is running"""
        if self.ollama_available is not None:
            return self.ollama_available

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    # Check if requested model exists, or any model exists
                    has_model = any(
                        self.ollama_model.split(":")[0] in m.get("name", "")
                        for m in models
                    )
                    if has_model:
                        self.ollama_available = True
                        return True
                    
                    # Fallback to any available model if specific one missing
                    if models:
                        first_model = models[0].get("name")
                        logger.warning(f"Requested model {self.ollama_model} not found, falling back to {first_model}")
                        self.ollama_model = first_model
                        self.ollama_available = True
                        return True
                        
        except Exception:
            pass

        self.ollama_available = False
        return False

    def _clean_html_for_llm(self, html: str) -> str:
        """ Aggressively clean HTML to save tokens and reduce noise for LLM """
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove distracting elements
            for element in soup(["script", "style", "nav", "footer", "iframe", "svg", "noscript"]):
                element.decompose()
                
            # Remove comments
            for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
                comment.extract()
                
            # Get text with minimal structure
            text = soup.get_text(separator="\n", strip=True)
            
            # Collapse whitespace
            text = re.sub(r"\n\s*\n", "\n\n", text)
            
            return text[:20000] # Limit context window safely
        except Exception:
            return html[:15000]

    async def extract_with_llama(
        self, raw_text: str, url: str, hint: str = ""
    ) -> Optional[Dict]:
        """
        Last resort: Use Llama to extract article from raw text.
        This works even when HTML structure is unpredictable.

        Args:
            raw_text: Raw HTML or text content
            url: Source URL for context
            hint: Optional hint about what we're looking for
        """
        if not await self.check_ollama():
            logger.warning("Ollama not available for LLM extraction fallback")
            return None

        # Intelligent cleaning
        clean_text = self._clean_html_for_llm(raw_text)

        prompt = f"""You are an expert news extractor. Your goal is to extract the main article content from the messy text below.

METADATA:
- URL: {url}
{f"- HINT: {hint}" if hint else ""}

INSTRUCTIONS:
1. Extract ONLY the main article body and title.
2. DISCARD navigation menus, ads, "read more" links, footer text, and comments.
3. Format the content as clean paragraphs separated by double newlines.
4. If you cannot find a clear article, return null for fields.

INPUT TEXT:
{clean_text}

OUTPUT FORMAT (JSON ONLY):
{{
  "title": "Exact article headline",
  "content": "Full article body text...",
  "author": "Author name or null",
  "date": "Publication date or null"
}}"""

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json", # Force JSON mode if supported by model
                        "options": {
                            "temperature": 0.1, # Low temp for factual extraction
                            "num_ctx": 4096,    # Ensure enough context
                        },
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    result_text = data.get("response", "").strip()

                    # Extract JSON robustly
                    try:
                        # Try parsing directly first
                        result = json.loads(result_text)
                    except json.JSONDecodeError:
                        # Fallback: find first { and last }
                        if "{" in result_text:
                            json_start = result_text.find("{")
                            json_end = result_text.rfind("}") + 1
                            json_str = result_text[json_start:json_end]
                            result = json.loads(json_str)
                        else:
                            raise ValueError("No JSON found in response")

                    if result.get("content") and len(result["content"]) > 100:
                        logger.success(
                            f"🦙 Llama extracted {len(result['content'])} chars"
                        )
                        self.stats["llama_success"] += 1
                        return result

        except Exception as e:
            logger.error(f"Llama extraction error: {e}")

        return None

    def extract_with_css(self, html: str, selectors: list, url: str) -> Optional[Dict]:
        """Layer 1: Try CSS selectors (fastest)"""
        try:
            soup = BeautifulSoup(html, "html.parser")

            for selector in selectors:
                elements = soup.select(selector)

                for elem in elements:
                    # Extract title - look for h1 inside or near the container
                    title = ""
                    # 1. Try finding h1 inside the element
                    title_elem = elem.find(["h1", "h2"])
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                    else:
                        # 2. Try finding h1 in the whole document
                        page_title = soup.find("h1")
                        if page_title:
                            title = page_title.get_text(strip=True)

                    # Extract content
                    # Remove unwanted tags inside the article body
                    for bad_tag in elem.select("script, style, .ad, .advertisement, .related, .share"):
                        bad_tag.decompose()
                        
                    content = elem.get_text(separator="\n\n", strip=True)

                    if len(content) > 200:
                        self.stats["css_success"] += 1
                        return {"title": title, "content": content, "method": "css"}

        except Exception as e:
            logger.debug(f"CSS extraction failed: {e}")

        return None

    def extract_with_trafilatura(self, html: str, url: str) -> Optional[Dict]:
        """Layer 2: Try Trafilatura (smart extraction)"""
        if not TRAFILATURA_OK:
            return None

        try:
            content = trafilatura_extract(
                html, 
                include_comments=False, 
                include_tables=True, 
                output_format="txt",
                deduplicate=True
            )

            if content and len(content) > 200:
                # Try to extract title from HTML
                soup = BeautifulSoup(html, "html.parser")
                title_elem = soup.find("title") or soup.find("h1")
                title = title_elem.get_text(strip=True) if title_elem else ""

                self.stats["trafilatura_success"] += 1
                return {"title": title, "content": content, "method": "trafilatura"}

        except Exception as e:
            logger.debug(f"Trafilatura extraction failed: {e}")

        return None

    def extract_with_newspaper(self, url: str) -> Optional[Dict]:
        """Layer 3: Try Newspaper3k (downloads and parses)"""
        if not NEWSPAPER_OK:
            return None

        try:
            article = Article(url)
            article.download()
            article.parse()

            if article.text and len(article.text) > 200:
                self.stats["newspaper_success"] += 1
                return {
                    "title": article.title or "",
                    "content": article.text,
                    "author": ", ".join(article.authors) if article.authors else None,
                    "date": str(article.publish_date) if article.publish_date else None,
                    "image": article.top_image,
                    "method": "newspaper",
                }

        except Exception as e:
            logger.debug(f"Newspaper extraction failed: {e}")

        return None

    async def extract(
        self,
        url: str,
        html: Optional[str] = None,
        selectors: list = None,
        hint: str = "",
    ) -> Optional[Dict]:
        """
        Extract article using multi-layer approach.

        Args:
            url: Article URL
            html: Pre-fetched HTML (optional)
            selectors: CSS selectors to try first
            hint: Optional hint for LLM fallback

        Returns:
            {title, content, author?, date?, method} or None
        """
        logger.info(f"🔍 Smart extracting: {url[:60]}...")

        # Fetch HTML if not provided
        if not html:
            try:
                async with httpx.AsyncClient(
                    timeout=30.0, follow_redirects=True
                ) as client:
                    response = await client.get(
                        url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (compatible; BaliZeroBot/1.0)"
                        },
                    )
                    html = response.text
            except Exception as e:
                logger.error(f"Failed to fetch URL: {e}")
                return None

        # Layer 1: CSS Selectors (if provided)
        if selectors:
            result = self.extract_with_css(html, selectors, url)
            if result:
                logger.success(f"✅ CSS extraction: {len(result['content'])} chars")
                return result

        # Layer 2: Trafilatura
        result = self.extract_with_trafilatura(html, url)
        if result:
            logger.success(f"✅ Trafilatura extraction: {len(result['content'])} chars")
            return result

        # Layer 3: Newspaper3k
        result = self.extract_with_newspaper(url)
        if result:
            logger.success(f"✅ Newspaper extraction: {len(result['content'])} chars")
            return result

        # Layer 4: LLM Fallback (Llama)
        logger.info("⚠️ Falling back to Llama cognitive extraction...")
        result = await self.extract_with_llama(html, url, hint)
        if result:
            result["method"] = "llama"
            return result

        self.stats["failed"] += 1
        return None
