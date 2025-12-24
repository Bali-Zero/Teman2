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
        return "Search the legal document knowledge base. Available collections:\n- 'legal_unified' (DEFAULT): All laws, regulations, visas, immigration, taxes, business. Use this for most queries.\n- 'kbli_2025': Business classification codes (KBLI) for PT PMA setup."

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
                        "kbli_2025",
                    ],
                    "description": "Collection to search. Default: 'legal_unified' for laws, visas, taxes. Use 'kbli_2025' only for KBLI business codes.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, collection: str = None, top_k: int = 5, **kwargs) -> str:
        # Gemini sometimes passes top_k as float, ensure it's int
        top_k = int(top_k) if top_k else 5

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
            # Build title from legal document metadata fields if 'title' not present
            title = (
                metadata.get("title")
                or (
                    f"{metadata.get('type_abbrev', 'DOC')} {metadata.get('number', '')} "
                    f"Tahun {metadata.get('year', '')} - {metadata.get('topic', 'Unknown')}"
                ).strip()
            )
            url = metadata.get("url", metadata.get("source_url", ""))

            # Extract document ID for Deep Dive (Hybrid Brain)
            # Priorities: chapter_id (from hierarchical indexer) > document_id > id
            doc_id = (
                metadata.get("chapter_id") or metadata.get("document_id") or metadata.get("id", "")
            )

            # Format text with ID for agent visibility
            # Use full chunk text - no artificial truncation
            formatted_texts.append(
                f"[{i + 1}] ID: {doc_id} | Title: {title}\n{text}"
            )  # Full text - let the LLM context window handle limits

            sources_metadata.append(
                {
                    "id": i + 1,
                    "title": title,
                    "url": url,
                    "score": chunk.get("score", 0.0),
                    "collection": collection or metadata.get("category", "general"),
                    "snippet": text[:500] if text else "",  # Preview for UI
                    "content": text if text else "",  # Full content - no truncation
                    "doc_id": doc_id,  # Pass doc_id for potential UI use or debugging
                    "download_url": f"/api/documents/{doc_id}/download" if doc_id else None,
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


class TeamKnowledgeTool(BaseTool):
    """Tool for Bali Zero team member information lookup"""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self._team_data = None
        self._data_file = None

    def _get_data_file_path(self):
        """Get path to team_members.json"""
        if self._data_file is None:
            from pathlib import Path
            # Try multiple possible locations
            possible_paths = [
                Path(__file__).parent.parent.parent.parent / "data" / "team_members.json",
                Path("/app/backend/data/team_members.json"),  # Docker/Fly.io
            ]
            for path in possible_paths:
                if path.exists():
                    self._data_file = path
                    break
        return self._data_file

    def _load_team_data(self):
        """Load team data from JSON file"""
        if self._team_data is None:
            data_file = self._get_data_file_path()
            if data_file and data_file.exists():
                import json as json_module
                with open(data_file) as f:
                    self._team_data = json_module.load(f)
            else:
                self._team_data = []
                logger.warning("TeamKnowledgeTool: team_members.json not found")
        return self._team_data

    @property
    def name(self) -> str:
        return "team_knowledge"

    @property
    def description(self) -> str:
        return """Get information about Bali Zero team members. Use this for questions about:
- Who is the CEO/founder/manager
- Team member names, roles, departments
- Contact information (email)
- Staff count and team structure"""

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["list_all", "search_by_role", "search_by_name", "search_by_email"],
                    "description": "Type of team query: list_all (all members), search_by_role (CEO, founder, tax, etc), search_by_name (person name), search_by_email",
                },
                "search_term": {
                    "type": "string",
                    "description": "The role, name, or email to search for (not needed for list_all)",
                },
            },
            "required": ["query_type"],
        }

    async def execute(self, query_type: str = "list_all", search_term: str = "", **kwargs) -> str:
        try:
            team_data = self._load_team_data()
            if not team_data:
                return json.dumps({"error": "Team data not available", "members": []})

            search_term_lower = search_term.lower().strip() if search_term else ""

            if query_type == "list_all":
                members = [
                    {"name": m["name"], "role": m["role"], "department": m["department"], "email": m["email"]}
                    for m in team_data
                ]
                return json.dumps({
                    "total_members": len(members),
                    "members": members
                })

            elif query_type == "search_by_role":
                # Role mapping for common variations
                role_map = {
                    "ceo": ["ceo", "chief executive"],
                    "founder": ["founder", "co-founder", "cofounder"],
                    "tax": ["tax", "fiscal"],
                    "setup": ["setup", "consultant"],
                    "marketing": ["marketing"],
                    "legal": ["legal", "advisor"],
                }

                # Get search terms for this role
                search_terms = [search_term_lower]
                for role, aliases in role_map.items():
                    if search_term_lower in aliases or role == search_term_lower:
                        search_terms = aliases
                        break

                matches = []
                for m in team_data:
                    role_lower = m.get("role", "").lower()
                    dept_lower = m.get("department", "").lower()
                    if any(term in role_lower or term in dept_lower for term in search_terms):
                        matches.append({
                            "name": m["name"],
                            "role": m["role"],
                            "department": m["department"],
                            "email": m["email"],
                            "notes": m.get("notes", "")
                        })

                if matches:
                    return json.dumps({"matches": matches, "count": len(matches)})
                return json.dumps({"matches": [], "count": 0, "message": f"No team members found with role: {search_term}"})

            elif query_type == "search_by_name":
                matches = []
                for m in team_data:
                    name_lower = m.get("name", "").lower()
                    if search_term_lower in name_lower or name_lower in search_term_lower:
                        matches.append({
                            "name": m["name"],
                            "role": m["role"],
                            "department": m["department"],
                            "email": m["email"],
                            "notes": m.get("notes", ""),
                            "location": m.get("location", "")
                        })

                if matches:
                    return json.dumps({"matches": matches, "count": len(matches)})
                return json.dumps({"matches": [], "count": 0, "message": f"No team member found with name: {search_term}"})

            elif query_type == "search_by_email":
                for m in team_data:
                    if search_term_lower in m.get("email", "").lower():
                        return json.dumps({
                            "name": m["name"],
                            "role": m["role"],
                            "department": m["department"],
                            "email": m["email"],
                            "notes": m.get("notes", "")
                        })
                return json.dumps({"error": f"No team member found with email: {search_term}"})

            else:
                return json.dumps({"error": f"Unknown query_type: {query_type}"})

        except Exception as e:
            logger.error(f"TeamKnowledgeTool failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
