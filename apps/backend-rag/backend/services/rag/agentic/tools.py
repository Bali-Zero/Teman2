"""
Agentic RAG Tool Definitions

This module contains the essential tool class definitions used by the AgenticRAGOrchestrator.
Each tool inherits from BaseTool and implements the required interface.

Essential Tools (Dec 2025):
- VectorSearchTool: Knowledge base search (Legal, Visa, KBLI).
- PricingTool: Official Service pricing lookup (High Precision).
- TeamKnowledgeTool: Team member information.
- CalculatorTool: Safe mathematical calculations (Safe Math).
- VisionTool: Visual document analysis.
- ImageGenerationTool: AI image generation (Google Imagen / Pollinations fallback).
- WebSearchTool: Web search for topics outside KB (tourism, lifestyle, general info).

DESIGN PRINCIPLE: No hardcoded keywords, patterns, or domain knowledge.
The LLM decides which collection to search based on the tool description.
"""

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
from backend.services.pricing.pricing_service import get_pricing_service
from backend.services.rag.vision_rag import VisionRAGService
from backend.services.tools.definitions import BaseTool

logger = logging.getLogger(__name__)

# Module-level persistent HTTP client for agentic tools
_client: httpx.AsyncClient | None = None


def _get_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """Get or create the shared async client for agentic tools."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def close_agentic_tools_client() -> None:
    """Close the module-level async client."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
    logger.info("Agentic tools module HTTP client closed.")


# Available collections - NO domain mapping, NO keywords
# The LLM reads the description and decides which to use
# Note: Collections ending in _hybrid have BM25 sparse vectors for better search
AVAILABLE_COLLECTIONS = [
    "visa_oracle",
    "legal_unified",
    "kbli_2025_final",  # KBLI 2025 - 1,563 BPS codes + 304 gold editorial (BPS Reg. 7/2025 + PP28/2025)
    "tax_genius",
    "bali_zero_pricing_hybrid",
    "training_conversations_hybrid",  # Migrated to hybrid format Dec 2025
    "immigration_circulars",  # Kemnaker/Imigrasi circulars
    "balizero_news",  # BaliZero intel articles: immigration, tax, bali news, business regulations
]


class VectorSearchTool(BaseTool):
    """
    Tool for vector search in knowledge base.

    NO pattern matching. NO keyword routing.
    The LLM decides which collection to search based on the description.
    If no collection specified, searches ALL collections (federated).
    """

    def __init__(self, retriever, user_level: int = 1) -> None:
        self.retriever = retriever
        self.user_level = user_level

    @property
    def name(self) -> str:
        """Return tool name."""
        return "vector_search"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "Search the knowledge base for verified information.\n\n"
            "**DEFAULT: FEDERATED SEARCH** - Omit 'collection' to search ALL collections at once.\n"
            "This is recommended for complex questions that may span multiple topics.\n\n"
            "**OPTIONALLY specify a collection** ONLY for focused single-topic queries:\n"
            "- visa_oracle: Visas, KITAS, KITAP, immigration, stay permits\n"
            "- legal_unified: Laws, company types (PT, CV, Firma), regulations\n"
            "- kbli_2025_final: Business classification codes (KBLI 2025, BPS 7/2025 + PP28/2025), 1,563 codes with licensing detail, PMA status\n"
            "- tax_genius: Taxes, PPh, PPN, NPWP, fiscal matters\n"
            "- bali_zero_pricing_hybrid: Official Bali Zero service pricing and costs\n"
            "- training_conversations_hybrid: Procedures, practical examples, FAQs\n"
            "- immigration_circulars: Immigration policy updates, circulars, Kemnaker regulations\n"
            "- balizero_news: Latest news, intel articles, regulation updates, business news from BaliZero\n\n"
            "Example: 'PT PMA requirements' → federated (legal + visa + tax)\n"
            "Example: 'PPh 21 rates' → collection='tax_genius'\n"
            "Example: 'Quanto costa D12?' → collection='bali_zero_pricing_hybrid'"
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query in natural language"},
                "collection": {
                    "type": "string",
                    "enum": AVAILABLE_COLLECTIONS,
                    "description": "The collection to search. Choose based on query topic. Omit to search all.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 8)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, collection: str = None, top_k: int = 8, **kwargs) -> str:
        """
        Execute vector search.

        If collection is specified: search only that collection.
        If collection is None: federated search across ALL collections.
        """
        with trace_span(
            "tool.vector_search",
            {
                "query_length": len(query),
                "requested_collection": collection or "federated_all",
                "top_k": top_k,
            },
        ):
            top_k = int(top_k) if top_k else 8

            # Determine which collections to search
            if collection:
                # LLM specified a collection - trust its judgment
                target_collections = [collection]
                logger.info(f"🔍 [Vector Search] LLM selected collection: {collection}")
            else:
                # No collection specified - search ALL (federated)
                target_collections = AVAILABLE_COLLECTIONS.copy()
                logger.info(
                    f"🌐 [Federated Search] Searching all {len(target_collections)} collections",
                )

            set_span_attribute("collections_searched", str(target_collections))

            all_chunks = []
            seen_content = set()

            # Execute search across target collections in parallel for better performance
            import asyncio

            # Determine search method based on feature flags
            from backend.app.core.config import settings as _settings

            use_hybrid = getattr(_settings, "enable_hybrid_search", False)

            async def _search_collection(target_col) -> Any:
                try:
                    per_col_limit = 5 if len(target_collections) > 1 else top_k
                    # Per-collection timeout to prevent one slow collection from blocking everything
                    async with asyncio.timeout(15.0 if use_hybrid else 10.0):
                        if use_hybrid and hasattr(self.retriever, "hybrid_search_with_reranking"):
                            # Full pipeline: BM25 + Dense + RRF + CrossEncoder reranking
                            res = await self.retriever.hybrid_search_with_reranking(
                                query=query,
                                user_level=self.user_level,
                                limit=per_col_limit,
                                collection_override=target_col,
                            )
                        elif hasattr(self.retriever, "search_with_reranking"):
                            res = await self.retriever.search_with_reranking(
                                query=query,
                                user_level=self.user_level,
                                limit=per_col_limit,
                                collection_override=target_col,
                            )
                        else:
                            res = await self.retriever.search(
                                query=query,
                                user_level=self.user_level,
                                limit=per_col_limit,
                                collection_override=target_col,
                            )
                        return target_col, res.get("results", [])
                except asyncio.TimeoutError:
                    logger.warning(f"⏱️ Search timeout for collection {target_col}")
                    return target_col, []
                except Exception as e:
                    logger.warning(f"Search failed for {target_col}: {e}")
                    return target_col, []

            if use_hybrid:
                logger.info("🔀 [Hybrid Search] Using BM25+Dense+RRF+CrossEncoder pipeline")

            search_results = await asyncio.gather(
                *[_search_collection(col) for col in target_collections],
            )

            # Process and deduplicate results
            for target_col, chunks_res in search_results:
                for chunk in chunks_res:
                    text = (
                        chunk.get("text", "")
                        if isinstance(chunk, dict)
                        else getattr(chunk, "text", "")
                    )
                    # Deduplicate by first 100 chars
                    if text[:100] not in seen_content:
                        seen_content.add(text[:100])
                        if isinstance(chunk, dict):
                            chunk["_source_collection"] = target_col
                        all_chunks.append(chunk)

            # Sort by score and take top results
            all_chunks.sort(
                key=lambda x: x.get("score", 0) if isinstance(x, dict) else 0, reverse=True,
            )
            chunks = all_chunks[:top_k]

            if not chunks:
                set_span_status("ok")
                return json.dumps({"content": "No relevant documents found.", "sources": []})

            # Format output
            formatted_texts = []
            sources_metadata = []

            for i, chunk in enumerate(chunks):
                text = (
                    chunk.get("text", "")
                    if isinstance(chunk, dict)
                    else getattr(chunk, "text", str(chunk))
                )
                metadata = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
                title = metadata.get("title") or "Document"

                source_col = chunk.get("_source_collection", "unknown")
                doc_id = (
                    metadata.get("chapter_id")
                    or metadata.get("document_id")
                    or metadata.get("id", "")
                )

                # Include document ID in formatted text if available
                id_prefix = f"ID: {doc_id}\n" if doc_id else ""
                formatted_texts.append(
                    f"[{i + 1}] Source: {source_col} | Title: {title}\n{id_prefix}{text}",
                )

                sources_metadata.append(
                    {
                        "id": i + 1,
                        "title": title,
                        "url": metadata.get("url", ""),
                        "score": chunk.get("score", 0.0) if isinstance(chunk, dict) else 0.0,
                        "collection": source_col,
                        "doc_id": doc_id,
                    },
                )

            content_str = "\n\n".join(formatted_texts)
            set_span_status("ok")
            return json.dumps({"content": content_str, "sources": sources_metadata})


class CalculatorTool(BaseTool):
    """Tool for safe mathematical calculations"""

    @property
    def name(self) -> str:
        """Name."""
        return "calculator"

    @property
    def description(self) -> str:
        """Description."""
        return "Perform mathematical calculations. Use for taxes, fees, currency conversions, or any numerical computation."

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression (e.g. '1000 * 0.22' or '15000000 / 15500')",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, expression: str, **kwargs) -> str:
        try:
            from backend.app.utils.safe_math import SafeMathError, safe_evaluate

            try:
                result = safe_evaluate(expression)
            except SafeMathError as e:
                return f"Error in mathematical expression: {e}"

            # Format nicely
            if isinstance(result, float):
                result = int(result) if result == int(result) else round(result, 2)

            return (
                f"Result: {result:,}" if isinstance(result, (int, float)) else f"Result: {result}"
            )

        except Exception as e:
            return f"Calculation error: {e}"


class VisionTool(BaseTool):
    """Tool for visual document analysis"""

    def __init__(self) -> None:
        self.vision_service = VisionRAGService()

    @property
    def name(self) -> str:
        """Name."""
        return "vision_analysis"

    @property
    def description(self) -> str:
        """Description."""
        return "Analyze visual elements in documents (PDFs, images). Extract text, tables, or analyze document structure."

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to analyze"},
                "query": {"type": "string", "description": "What to look for in the document"},
            },
            "required": ["file_path", "query"],
        }

    async def execute(self, file_path: str, query: str, **kwargs) -> str:
        try:
            # Security: validate file path to prevent path traversal
            from pathlib import Path

            from backend.app.core.config import settings

            resolved = Path(file_path).resolve()
            allowed_dirs = [Path(d).resolve() for d in settings.get_vision_allowed_dirs]

            # Use is_relative_to for robust path checking (Python 3.9+)
            is_allowed = False
            for allowed_dir in allowed_dirs:
                try:
                    if resolved.is_relative_to(allowed_dir):
                        is_allowed = True
                        break
                except ValueError:
                    continue

            if not is_allowed:
                logger.warning(f"🛡️ VisionTool path traversal blocked: {file_path}")
                return (
                    "Error: Access denied. File must be in one of the following directories: "
                    + ", ".join(settings.get_vision_allowed_dirs)
                )

            # Validate file extension
            allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
            if resolved.suffix.lower() not in allowed_extensions:
                logger.warning(f"🛡️ VisionTool invalid extension blocked: {resolved.suffix}")
                return f"Error: File type {resolved.suffix} not supported. Allowed types: {', '.join(allowed_extensions)}"

            doc = await self.vision_service.process_pdf(str(resolved))
            result = await self.vision_service.query_with_vision(query, [doc], include_images=True)
            return f"Analysis result: {result['answer']}"
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return f"Vision analysis error: {e}"


class PricingTool(BaseTool):
    """Tool for official service pricing lookup"""

    def __init__(self, pricing_service=None) -> None:
        self.pricing_service = pricing_service or get_pricing_service()

    @property
    def name(self) -> str:
        """Name."""
        return "get_pricing"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "🚨 MANDATORY for ALL Bali Zero service price questions. "
            "Get OFFICIAL pricing from Bali Zero database (NO AI generation, NO memory). "
            "USE THIS when user asks: 'quanto costa', 'price', 'prezzo', 'costo', 'harga', 'berapa', 'cost', 'pricing', 'PT PMA', 'KITAS', 'visa'. "
            "Returns EXACT current prices from official pricing database. "
            "NEVER guess prices - ALWAYS call this tool first for price questions."
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "service_type": {
                    "type": "string",
                    "enum": ["visa", "kitas", "business_setup", "tax_consulting", "legal", "all"],
                    "description": "Category of service",
                },
                "query": {
                    "type": "string",
                    "description": "Specific service to search for",
                },
            },
            "required": ["service_type"],
        }

    async def execute(self, service_type: str = "all", query: str = None, **kwargs) -> str:
        try:
            if query:
                result = self.pricing_service.search_service(query)
            else:
                result = self.pricing_service.get_pricing(service_type)
            return str(result)
        except Exception as e:
            logger.error(f"Pricing lookup failed: {e}")
            return f"Pricing lookup error: {e}"


class TeamKnowledgeTool(BaseTool):
    """Tool for team member information lookup"""

    def __init__(self, db_pool=None) -> None:
        self.db_pool = db_pool
        self._team_data = None
        self._data_file = None

    def _get_data_file_path(self) -> Path | None:
        if self._data_file is None:
            import os
            from pathlib import Path

            # Logical paths to check (Local Repo vs Docker Container)
            possible_paths = [
                # 1. Local Development (relative to this file)
                Path(__file__).parent.parent.parent.parent / "data" / "team_members.json",
                # 2. Docker Container (Standard App Path)
                Path("/app/backend/data/team_members.json"),
                # 3. Docker Container (Alternative)
                Path("/app/data/team_members.json"),
                # 4. Fallback: Current Working Directory
                Path(os.getcwd()) / "backend" / "data" / "team_members.json",
                # 5. Monorepo Fallback
                Path(os.getcwd())
                / "apps"
                / "backend-rag"
                / "backend"
                / "data"
                / "team_members.json",
                # 6. Monorepo Root Fallback
                Path(os.getcwd()) / "data" / "team_members.json",
            ]

            for path in possible_paths:
                try:
                    if path.exists():
                        self._data_file = path
                        logger.debug(f"[{self.name}] Found team_members.json at: {path}")
                        break
                except Exception as e:
                    logger.warning(f"[{self.name}] Error checking path {path}: {e}")

            if self._data_file is None:
                logger.error(
                    f"[{self.name}] CRITICAL: team_members.json NOT FOUND in any expected location.",
                )

        return self._data_file

    def _load_team_data(self) -> list[dict[str, Any]]:
        if self._team_data is None:
            data_file = self._get_data_file_path()
            if data_file and data_file.exists():
                with open(data_file) as f:
                    self._team_data = json.load(f)
            else:
                self._team_data = []
        return self._team_data

    @property
    def name(self) -> str:
        """Name."""
        return "team_knowledge"

    @property
    def description(self) -> str:
        """Description."""
        return "Get information about team members, their roles, departments, and contact info."

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["list_all", "search_by_role", "search_by_name", "search_by_email"],
                    "description": "Type of query to perform",
                },
                "search_term": {
                    "type": "string",
                    "description": "Term to search for (name, role, or email)",
                },
            },
            "required": ["query_type"],
        }

    async def execute(self, query_type: str = "list_all", search_term: str = "", **kwargs) -> str:
        try:
            team_data = self._load_team_data()
            if not team_data:
                return json.dumps({"error": "Team data not available"})

            search_term = search_term.lower().strip() if search_term else ""

            if query_type == "list_all":
                return json.dumps(
                    [{"name": m.get("name"), "role": m.get("role")} for m in team_data],
                )

            # Search logic
            matches = [m for m in team_data if search_term in json.dumps(m).lower()]
            return json.dumps({"matches": matches, "count": len(matches)})

        except Exception as e:
            logger.error(f"Team knowledge lookup failed: {e}")
            return json.dumps({"error": str(e)})


class ImageGenerationTool(BaseTool):
    """Tool for generating images from text prompts using Google Imagen."""

    def __init__(self) -> None:
        self._client = None

    @property
    def name(self) -> str:
        """Name."""
        return "generate_image"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "Generate images from text descriptions. Use this when the user asks to "
            "create, generate, draw, or make an image/picture. Returns a URL to the generated image. "
            "Prompt should be descriptive (e.g., 'a blue lotus flower in digital art style')."
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed text description of the image to generate",
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
                    "description": "Aspect ratio of the image (default: 1:1)",
                },
            },
            "required": ["prompt"],
        }

    async def execute(self, prompt: str, aspect_ratio: str = "1:1", **kwargs) -> str:
        """Generate an image using Google Imagen API."""

        from backend.app.core.config import settings

        with trace_span("tool.generate_image", {"prompt_length": len(prompt)}):
            try:
                # Get API key
                api_key = (
                    getattr(settings, "google_imagen_api_key", None)
                    or getattr(settings, "google_ai_studio_key", None)
                    or getattr(settings, "google_api_key", None)
                )

                if not api_key:
                    return json.dumps(
                        {"success": False, "error": "Image generation not configured"},
                    )

                url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict"
                headers = {
                    "X-Goog-Api-Key": api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "prompt": prompt,
                    "number_of_images": 1,
                    "aspect_ratio": aspect_ratio,
                    "safety_filter_level": "block_some",
                    "person_generation": "allow_adult",
                    "language": "auto",
                }

                logger.info(f"🎨 [ImageGen] Generating image: {prompt[:50]}...")

                client = _get_client()
                response = await client.post(url, json=payload, headers=headers, timeout=60.0)

                if response.status_code == 403:
                    # Fallback to pollinations.ai
                    logger.warning("⚠️ [ImageGen] Imagen API not available, using fallback")
                    fallback_url = (
                        f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
                    )
                    set_span_attribute("fallback", "pollinations")
                    return json.dumps(
                        {
                            "success": True,
                            "image_url": fallback_url,
                            "service": "pollinations_fallback",
                            "message": f"Generated image for: {prompt}",
                        },
                    )

                response.raise_for_status()
                result = response.json()

                # Extract image
                if "generatedImages" in result and result["generatedImages"]:
                    img_data = result["generatedImages"][0].get("bytesBase64Encoded", "")
                    if img_data:
                        image_data_url = f"data:image/png;base64,{img_data}"
                        set_span_attribute("success", True)
                        return json.dumps(
                            {
                                "success": True,
                                "image_data": image_data_url,
                                "service": "google_imagen",
                                "message": f"Generated image for: {prompt}",
                            },
                        )

                return json.dumps({"success": False, "error": "No image generated"})

            except Exception as e:
                logger.error(f"❌ [ImageGen] Failed: {e}")
                set_span_status("error", str(e))
                # Fallback to pollinations
                fallback_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
                return json.dumps(
                    {
                        "success": True,
                        "image_url": fallback_url,
                        "service": "pollinations_fallback",
                        "message": f"Generated image for: {prompt}",
                    },
                )


class WebSearchTool(BaseTool):
    """
    Tool for searching the web when information is not available in the knowledge base.

    Supports two providers:
    - Tavily (preferred): AI-optimized search with 1,000 free queries/month
    - Brave (fallback): Independent search index with 2,000 free queries/month

    Use this tool ONLY when:
    1. The user asks about topics outside Bali Zero's core services (tourism, lifestyle, general info)
    2. The vector_search tool returns no relevant results
    3. The user explicitly asks for current/latest information from the web

    IMPORTANT: Results from this tool are NOT verified by Bali Zero's knowledge base.
    Always include the disclaimer when presenting web search results to users.
    """

    # Standard disclaimer for web results - append to all responses
    WEB_DISCLAIMER = (
        "\n\n---\n"
        "*Note: This information was sourced from the web and has not been verified "
        "by Bali Zero's official knowledge base. For visa, legal, tax, or business setup "
        "questions, please refer to our verified documentation or contact our team directly.*"
    )

    def __init__(self) -> None:
        self._tavily_key = None
        self._brave_key = None

    def _get_keys(self) -> tuple[str | None, str | None]:
        """Lazy load API keys from settings."""
        if self._tavily_key is None and self._brave_key is None:
            from backend.app.core.config import settings

            self._tavily_key = settings.tavily_api_key
            self._brave_key = settings.brave_api_key
        return self._tavily_key, self._brave_key

    @property
    def name(self) -> str:
        """Name."""
        return "web_search"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "Search the web for information NOT available in the knowledge base.\n\n"
            "**USE CASES:**\n"
            "1. Tourism, restaurants, lifestyle, current events, general knowledge\n"
            "2. **LOCAL CONTEXT ENRICHMENT**: When user asks about opening a business in a specific "
            "location (e.g., 'restaurant in Canggu', 'hotel in Dago'), use this to find "
            "local competitors, market atmosphere, and scene description. This helps clients "
            "'breathe the atmosphere' of the area.\n\n"
            "**DO NOT use for:** visas, KITAS, PT PMA, taxes, legal - use vector_search instead.\n"
            "Web results are NOT verified and will include a disclaimer."
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query in natural language"},
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 10)",
                },
            },
            "required": ["query"],
        }

    async def _search_tavily(self, query: str, num_results: int, api_key: str) -> dict[str, Any]:
        """Search using Tavily API (AI-optimized)."""
        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": num_results,
            "search_depth": "basic",
            "include_answer": True,
        }

        client = _get_client()
        response = await client.post(url, headers=headers, json=payload, timeout=15.0)
        response.raise_for_status()
        return response.json()

    async def _search_brave(self, query: str, num_results: int, api_key: str) -> dict[str, Any]:
        """Search using Brave Search API (fallback)."""
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        }
        params = {
            "q": query,
            "count": num_results,
            "text_decorations": False,
            "search_lang": "en",
        }

        client = _get_client()
        response = await client.get(url, headers=headers, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()

    async def execute(self, query: str, num_results: int = 5, **kwargs) -> str:
        """
        Execute web search using Tavily (primary) or Brave (fallback).

        Returns formatted results with source URLs and the standard disclaimer.
        """
        import httpx

        with trace_span(
            "tool.web_search",
            {
                "query_length": len(query),
                "num_results": num_results,
            },
        ):
            tavily_key, brave_key = self._get_keys()

            if not tavily_key and not brave_key:
                logger.warning(
                    "⚠️ [WebSearch] No API keys configured (TAVILY_API_KEY or BRAVE_API_KEY)",
                )
                return json.dumps(
                    {
                        "success": False,
                        "error": "Web search not configured. Please contact support.",
                        "disclaimer": self.WEB_DISCLAIMER,
                    },
                )

            # Clamp num_results
            num_results = min(max(1, int(num_results) if num_results else 5), 10)

            try:
                provider = None
                results = []
                ai_answer = None

                # Try Tavily first (AI-optimized)
                if tavily_key:
                    try:
                        logger.info(f"🌐 [WebSearch] Searching Tavily: {query[:50]}...")
                        data = await self._search_tavily(query, num_results, tavily_key)
                        provider = "tavily"
                        results = data.get("results", [])
                        ai_answer = data.get("answer")  # Tavily provides AI-generated answer
                    except Exception as e:
                        logger.warning(f"⚠️ [WebSearch] Tavily failed: {e}, trying Brave...")

                # Fallback to Brave
                if not results and brave_key:
                    try:
                        logger.info(f"🌐 [WebSearch] Searching Brave: {query[:50]}...")
                        data = await self._search_brave(query, num_results, brave_key)
                        provider = "brave"
                        results = data.get("web", {}).get("results", [])
                    except Exception as e:
                        logger.error(f"❌ [WebSearch] Brave also failed: {e}")
                        raise

                if not results:
                    set_span_status("ok")
                    return json.dumps(
                        {
                            "success": True,
                            "content": "No relevant web results found for this query.",
                            "sources": [],
                            "disclaimer": self.WEB_DISCLAIMER,
                        },
                    )

                # Format results based on provider
                formatted_results = []
                sources = []

                # Add AI answer if available (Tavily)
                if ai_answer:
                    formatted_results.append(f"**Summary:** {ai_answer}\n")

                for i, result in enumerate(results[:num_results]):
                    if provider == "tavily":
                        title = result.get("title", "Untitled")
                        content = result.get("content", "No content available")
                        url = result.get("url", "")
                    else:  # brave
                        title = result.get("title", "Untitled")
                        content = result.get("description", "No description available")
                        content = content.replace("<strong>", "").replace("</strong>", "")
                        url = result.get("url", "")

                    formatted_results.append(
                        f"[{i + 1}] **{title}**\n   {content[:300]}...\n   Source: {url}",
                    )

                    sources.append(
                        {
                            "id": i + 1,
                            "title": title,
                            "url": url,
                            "content": content[:200],
                            "verified": False,
                        },
                    )

                content = "\n\n".join(formatted_results)
                content_with_disclaimer = content + self.WEB_DISCLAIMER

                logger.info(f"✅ [WebSearch] Found {len(sources)} results via {provider}")
                set_span_status("ok")

                return json.dumps(
                    {
                        "success": True,
                        "content": content_with_disclaimer,
                        "sources": sources,
                        "source_type": "web_search",
                        "provider": provider,
                        "disclaimer": self.WEB_DISCLAIMER,
                        "query": query,
                    },
                )

            except httpx.HTTPStatusError as e:
                logger.error(f"❌ [WebSearch] HTTP error: {e.response.status_code}")
                set_span_status("error", str(e))
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Web search failed: HTTP {e.response.status_code}",
                        "disclaimer": self.WEB_DISCLAIMER,
                    },
                )
            except Exception as e:
                logger.error(f"❌ [WebSearch] Error: {e}")
                set_span_status("error", str(e))
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Web search error: {str(e)}",
                        "disclaimer": self.WEB_DISCLAIMER,
                    },
                )


class TimeSheetTool(BaseTool):
    """Tool for team timesheet management (clock-in, clock-out, status)"""

    def __init__(self) -> None:
        self._team_data = None

    @property
    def name(self) -> str:
        """Name."""
        return "timesheet"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "Manage work timesheet. Use this to clock in, clock out, or check work status. "
            "REQUIRED: User email address."
            "Actions: clock_in, clock_out, status"
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["clock_in", "clock_out", "status"],
                    "description": "Action to perform",
                },
                "email": {
                    "type": "string",
                    "description": "User email address (required)",
                },
            },
            "required": ["action", "email"],
        }

    def _get_user_id_by_email(self, email: str) -> str | None:
        try:
            from pathlib import Path

            # Try relative to this file first (Local Dev)
            path = Path(__file__).parent.parent.parent.parent / "data" / "team_members.json"

            # If not found, try Docker paths
            if not path.exists():
                path = Path("/app/backend/data/team_members.json")

            if not path.exists():
                path = Path("/app/data/team_members.json")

            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                    for m in data:
                        if m.get("email", "").lower() == email.lower():
                            return m.get("id")
        except Exception as e:
            logger.debug(f"[TimeSheetTool] Failed to lookup user by email {email}: {e}")
        return None

    async def execute(self, action: str, email: str, **kwargs) -> str:
        try:
            from backend.services.analytics.team_timesheet_service import get_timesheet_service

            service = get_timesheet_service()
            if not service:
                return json.dumps({"error": "Timesheet service unavailable"})

            user_id = self._get_user_id_by_email(email)
            if not user_id:
                return json.dumps({"error": f"User ID not found for email {email}"})

            if action == "clock_in":
                res = await service.clock_in(user_id, email, metadata={"source": "agent"})
                return json.dumps(res)
            if action == "clock_out":
                res = await service.clock_out(user_id, email, metadata={"source": "agent"})
                return json.dumps(res)
            if action == "status":
                res = await service.get_my_status(user_id)
                return json.dumps(res)
            return json.dumps({"error": f"Unknown action {action}"})

        except Exception as e:
            return json.dumps({"error": str(e)})


def create_default_tools(search_service: Any = None) -> list[BaseTool]:
    """
    Create default tool set for AgenticRAGOrchestrator.

    This is used as a fallback when creating a minimal orchestrator
    for channel routing when the main orchestrator is not initialized.

    Args:
        search_service: Optional SearchService instance for VectorSearchTool

    Returns:
        List of BaseTool instances with essential tools
    """
    tools = []

    # 1. VectorSearchTool (if search_service available)
    if search_service:
        tools.append(VectorSearchTool(retriever=search_service))

    # 2. PricingTool (essential for pricing queries)
    pricing_service = get_pricing_service()
    tools.append(PricingTool(pricing_service=pricing_service))

    # 3. CalculatorTool (always available)
    tools.append(CalculatorTool())

    # 4. TeamKnowledgeTool (always available)
    tools.append(TeamKnowledgeTool())

    logger.info(f"Created {len(tools)} default tools for orchestrator")
    return tools
