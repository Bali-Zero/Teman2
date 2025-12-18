"""
Agentic RAG Tool Definitions

This module contains all tool class definitions used by the AgenticRAGOrchestrator.
Each tool inherits from BaseTool and implements the required interface:
- name: unique tool identifier
- description: what the tool does
- parameters_schema: JSON schema for tool arguments
- execute(): async method that performs the tool's action

Tools included:
- VectorSearchTool: Knowledge base search with collection routing
- WebSearchTool: Web search (fallback/disabled by default)
- DatabaseQueryTool: Direct database queries for deep dive
- CalculatorTool: Safe mathematical calculations
- VisionTool: Visual document analysis
- PricingTool: Official Bali Zero pricing lookup
"""

import asyncio
import json
import logging

import asyncpg
import httpx

from services.pricing_service import get_pricing_service
from services.rag.vision_rag import VisionRAGService
from services.tools.definitions import BaseTool

logger = logging.getLogger(__name__)


class VectorSearchTool(BaseTool):
    """Tool for vector search in knowledge base with collection routing"""

    def __init__(self, retriever):
        self.retriever = retriever

    @property
    def name(self) -> str:
        return "vector_search"

    @property
    def description(self) -> str:
        return "Search the legal document knowledge base. IMPORTANT: You MUST specify the 'collection' parameter based on the topic:\n- 'tax_genius' for Taxes, VAT, PPh, Finance.\n- 'visa_oracle' for Visas, Immigration, Stay Permits.\n- 'kbli_unified' for Business Classification (KBLI).\n- 'legal_unified' for General Law, Civil Code, Manpower, Criminal Law."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query in natural language"},
                "collection": {
                    "type": "string",
                    "enum": [
                        "legal_unified",
                        "visa_oracle",
                        "tax_genius",
                        "kbli_unified",
                        "litigation_oracle",
                    ],
                    "description": "Specific collection to search. Use 'kbli_unified' for PT PMA, business setup, KBLI codes, company registration.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, collection: str = None, top_k: int = 5, **kwargs) -> str:
        # Use the new search_with_reranking method if available
        if hasattr(self.retriever, "search_with_reranking"):
            result = await self.retriever.search_with_reranking(
                query=query,
                user_level=1,  # Default to standard access
                limit=top_k,
                collection_override=collection,
            )
            chunks = result.get("results", [])
        elif hasattr(self.retriever, "retrieve_with_graph_expansion"):
            # Fallback to old method if present (e.g. mock)
            result = await self.retriever.retrieve_with_graph_expansion(
                query, primary_collection=collection or "legal_unified"
            )
            chunks = result.get("primary_results", {}).get("chunks", [])[:top_k]
        else:
            # Fallback to basic search
            result = await self.retriever.search(
                query=query, user_level=1, limit=top_k, collection_override=collection
            )
            chunks = result.get("results", [])

        if not chunks:
            return json.dumps({"content": "No relevant documents found.", "sources": []})

        formatted_texts = []
        sources_metadata = []

        for i, chunk in enumerate(chunks):
            # Handle both dict and object access if needed, assuming dict for now based on KnowledgeService
            text = (
                chunk.get("text", "")
                if isinstance(chunk, dict)
                else getattr(chunk, "text", str(chunk))
            )

            # Extract metadata for citation
            metadata = chunk.get("metadata", {})
            title = metadata.get("title", f"Document {i+1}")
            url = metadata.get("url", metadata.get("source_url", ""))

            # Extract document ID for Deep Dive (Hybrid Brain)
            # Priorities: chapter_id (from hierarchical indexer) > document_id > id
            doc_id = (
                metadata.get("chapter_id") or metadata.get("document_id") or metadata.get("id", "")
            )

            # Format text with ID for agent visibility
            formatted_texts.append(
                f"[{i + 1}] ID: {doc_id} | Title: {title}\n{text[:800]}"
            )  # Increased context limit slightly

            sources_metadata.append(
                {
                    "id": i + 1,
                    "title": title,
                    "url": url,
                    "score": chunk.get("score", 0.0),
                    "category": metadata.get("category", collection or "general"),
                    "doc_id": doc_id,  # Pass doc_id for potential UI use or debugging
                }
            )

        content_str = "\n\n".join(formatted_texts)

        # Return structured JSON so orchestrator can parse it
        return json.dumps({"content": content_str, "sources": sources_metadata})


class WebSearchTool(BaseTool):
    """Tool for web search (fallback/disabled by default)"""

    def __init__(self, search_client=None):
        self.client = search_client

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for current information. Use this when you need recent updates, news, or information not in the knowledge base."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "num_results": {"type": "integer", "description": "Number of results (default: 5)"},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, num_results: int = 5, **kwargs) -> str:
        if not self.client:
            # Return a helpful message that guides the AI to use vector_search instead
            return (
                "Web search is not available. Please use vector_search tool instead to search "
                "the knowledge base for information about: " + query
            )

        # Implementation with Google Search API or similar
        try:
            results = await self.client.search(query, num_results=num_results)

            formatted = []
            for r in results:
                formatted.append(f"- {r.get('title', 'No Title')}: {r.get('snippet', '')}")

            return "\n".join(formatted) or "No web results found."
        except (httpx.HTTPError, httpx.TimeoutException, asyncio.TimeoutError) as e:
            logger.error(f"Web search failed: {e}", exc_info=True)
            return f"Web search failed: {str(e)}"


class DatabaseQueryTool(BaseTool):
    """Tool for direct database queries (Deep Dive & Knowledge Graph)"""

    def __init__(self, db_pool):
        self.db = db_pool

    @property
    def name(self) -> str:
        return "database_query"

    @property
    def description(self) -> str:
        return "Query the database to retrieve full document text (Deep Dive) or entity relationships. Use 'by_id' with the ID from vector_search results to read the complete document."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "The term to search for (e.g., document title) OR the document ID (if query_type='by_id')",
                },
                "query_type": {
                    "type": "string",
                    "enum": ["full_text", "relationship", "by_id"],
                    "description": "Type of query: 'full_text' (title search), 'relationship' (KG), 'by_id' (exact ID match)",
                },
            },
            "required": ["search_term"],
        }

    async def execute(self, search_term: str, query_type: str = "full_text", **kwargs) -> str:
        # Handle legacy 'entity_name' if passed via kwargs
        if not search_term and "entity_name" in kwargs:
            search_term = kwargs["entity_name"]

        if not self.db:
            return "Database connection not available."

        try:
            async with self.db.acquire() as conn:
                if query_type == "full_text":
                    # Deep Dive: Search in parent_documents
                    # We search for title match first
                    query = """
                        SELECT title, full_text
                        FROM parent_documents
                        WHERE title ILIKE $1
                        LIMIT 1
                    """
                    # Add wildcards for fuzzy search
                    search_pattern = f"%{search_term}%"
                    row = await conn.fetchrow(query, search_pattern)

                    if row:
                        return f"Document Found: {row['title']}\n\nContent:\n{row['full_text']}"
                    else:
                        return f"No full text document found matching '{search_term}'."

                elif query_type == "by_id":
                    # EXACT MATCH by document_id (from vector search metadata)
                    # GUARDRAIL: Use summary when available, cap full_text to prevent token bombs
                    query = """
                        SELECT title, full_text, document_id, summary
                        FROM parent_documents
                        WHERE document_id = $1 OR id = $1
                        LIMIT 1
                    """
                    row = await conn.fetchrow(query, search_term)

                    if row:
                        title = row["title"]
                        doc_id = row["document_id"]
                        summary = row.get("summary")
                        full_text = row["full_text"]

                        # GUARDRAIL: Cap full_text to 10K characters to prevent streaming timeout
                        MAX_CHARS = 10000
                        was_truncated = False

                        if len(full_text) > MAX_CHARS:
                            full_text = full_text[:MAX_CHARS]
                            was_truncated = True

                        # Build response: prefer summary + capped full_text
                        response = (
                            f"=== FULL DOCUMENT (Deep Dive) ===\nID: {doc_id}\nTitle: {title}\n\n"
                        )

                        if summary:
                            response += f"SUMMARY:\n{summary}\n\n"

                        response += f"CONTENT:\n{full_text}"

                        if was_truncated:
                            response += f"\n\n[Note: Content truncated to {MAX_CHARS} characters for performance. Full document available in database.]"

                        response += "\n==============================="

                        return response
                    else:
                        return f"No document found with ID '{search_term}'."

                elif query_type == "relationship":
                    # Placeholder for Knowledge Graph query
                    # In the future, this will query the graph tables
                    return f"Knowledge Graph relationship data for '{search_term}' is currently not populated."

                else:
                    return f"Unknown query_type: {query_type}"

        except (
            asyncpg.PostgresError,
            asyncpg.InterfaceError,
            asyncpg.exceptions.ConnectionDoesNotExistError,
        ) as e:
            logger.error(f"Database query failed: {e}", exc_info=True)
            return f"Database query failed: {str(e)}"


class CalculatorTool(BaseTool):
    """Tool for safe mathematical calculations"""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Perform calculations for taxes, fees, deadlines, or other numerical computations."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '1000000 * 0.25')",
                },
                "calculation_type": {
                    "type": "string",
                    "enum": ["tax", "fee", "deadline", "general"],
                    "description": "Type of calculation",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, expression: str, calculation_type: str = "general", **kwargs) -> str:
        try:
            # Safe math evaluation using ast.literal_eval for simple expressions
            # or manual parsing for basic arithmetic
            import ast
            import operator

            # Define allowed operators for safe math evaluation
            allowed_operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }

            def safe_eval(node):
                if isinstance(node, ast.Expression):
                    return safe_eval(node.body)
                elif isinstance(node, ast.Constant):
                    if isinstance(node.value, (int, float)):
                        return node.value
                    raise ValueError(f"Invalid constant: {node.value}")
                elif isinstance(node, ast.BinOp):
                    op_type = type(node.op)
                    if op_type not in allowed_operators:
                        raise ValueError(f"Operator not allowed: {op_type}")
                    return allowed_operators[op_type](safe_eval(node.left), safe_eval(node.right))
                elif isinstance(node, ast.UnaryOp):
                    op_type = type(node.op)
                    if op_type not in allowed_operators:
                        raise ValueError(f"Operator not allowed: {op_type}")
                    return allowed_operators[op_type](safe_eval(node.operand))
                else:
                    raise ValueError(f"Invalid expression: {type(node)}")

            tree = ast.parse(expression, mode="eval")
            result = safe_eval(tree)

            if calculation_type == "tax":
                return f"Tax calculation: Rp {result:,.0f}"
            elif calculation_type == "fee":
                return f"Fee: Rp {result:,.0f}"
            else:
                return f"Result: {result}"
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
            logger.error(f"Calculation error: {e}", exc_info=True)
            return f"Calculation error: {str(e)}"


class VisionTool(BaseTool):
    """Tool for visual document analysis (PDFs, images)"""

    def __init__(self):
        self.vision_service = VisionRAGService()

    @property
    def name(self) -> str:
        return "vision_analysis"

    @property
    def description(self) -> str:
        return "Analyze visual elements in documents (PDFs, images). Use this to extract data from tables, charts, or understand complex layouts."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to analyze (PDF or Image)",
                },
                "query": {
                    "type": "string",
                    "description": "Specific question about the visual content",
                },
            },
            "required": ["file_path", "query"],
        }

    async def execute(self, file_path: str, query: str, **kwargs) -> str:
        try:
            # Process the document
            doc = await self.vision_service.process_pdf(file_path)

            # Execute visual query
            result = await self.vision_service.query_with_vision(query, [doc], include_images=True)

            return f"Vision Analysis Result:\n{result['answer']}\n\nVisual Elements Used: {len(result['visuals_used'])}"
        except (OSError, FileNotFoundError, ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            return f"Vision analysis failed: {str(e)}"


class PricingTool(BaseTool):
    """Tool for official Bali Zero pricing lookup"""

    def __init__(self):
        self.pricing_service = get_pricing_service()

    @property
    def name(self) -> str:
        return "get_pricing"

    @property
    def description(self) -> str:
        return "Get OFFICIAL Bali Zero pricing for services. ALWAYS use this for price questions. Returns prices for Visa, KITAS, Business Setup, Tax."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "service_type": {
                    "type": "string",
                    "enum": ["visa", "kitas", "business_setup", "tax_consulting", "legal", "all"],
                    "description": "Type of service to get pricing for",
                },
                "query": {
                    "type": "string",
                    "description": "Optional specific search query (e.g. 'investor kitas')",
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
        except (ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Pricing lookup failed: {e}", exc_info=True)
            return f"Pricing lookup failed: {str(e)}"
