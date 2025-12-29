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

DESIGN PRINCIPLE: No hardcoded keywords, patterns, or domain knowledge.
The LLM decides which collection to search based on the tool description.
"""

import json
import logging

from app.utils.tracing import trace_span, set_span_attribute, set_span_status
from services.pricing.pricing_service import get_pricing_service
from services.rag.vision_rag import VisionRAGService
from services.tools.definitions import BaseTool
from services.tools.knowledge_graph_tool import KnowledgeGraphTool

logger = logging.getLogger(__name__)

# Available collections - NO domain mapping, NO keywords
# The LLM reads the description and decides which to use
AVAILABLE_COLLECTIONS = [
    "visa_oracle",
    "legal_unified_hybrid",
    "kbli_unified",
    "tax_genius",
    "bali_zero_pricing",
    "training_conversations",
]


class VectorSearchTool(BaseTool):
    """
    Tool for vector search in knowledge base.

    NO pattern matching. NO keyword routing.
    The LLM decides which collection to search based on the description.
    If no collection specified, searches ALL collections (federated).
    """

    def __init__(self, retriever):
        self.retriever = retriever

    @property
    def name(self) -> str:
        return "vector_search"

    @property
    def description(self) -> str:
        return (
            "Search the knowledge base for verified information.\n"
            "You MUST specify a collection based on the query topic:\n"
            "- visa_oracle: Visas, KITAS, KITAP, immigration, stay permits\n"
            "- legal_unified_hybrid: Laws, company types (PT, CV, Firma), regulations, Perseroan Terbatas\n"
            "- kbli_unified: Business classification codes (KBLI), OSS, NIB\n"
            "- tax_genius: Taxes, PPh, PPN, NPWP, fiscal matters, tax treaties\n"
            "- bali_zero_pricing: Official Service Pricing & Costs (Database)\n"
            "- training_conversations: Procedures, practical examples, how-to guides\n\n"
            "If unsure, omit collection to search all."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query in natural language"
                },
                "collection": {
                    "type": "string",
                    "enum": AVAILABLE_COLLECTIONS,
                    "description": "The collection to search. Choose based on query topic. Omit to search all.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, collection: str = None, top_k: int = 5, **kwargs) -> str:
        """
        Execute vector search.

        If collection is specified: search only that collection.
        If collection is None: federated search across ALL collections.
        """
        with trace_span("tool.vector_search", {
            "query_length": len(query),
            "requested_collection": collection or "federated_all",
            "top_k": top_k,
        }):
            top_k = int(top_k) if top_k else 5

            # Determine which collections to search
            if collection:
                # LLM specified a collection - trust its judgment
                target_collections = [collection]
                logger.info(f"🔍 [Vector Search] LLM selected collection: {collection}")
            else:
                # No collection specified - search ALL (federated)
                target_collections = AVAILABLE_COLLECTIONS.copy()
                logger.info(f"🌐 [Federated Search] Searching all {len(target_collections)} collections")

            set_span_attribute("collections_searched", str(target_collections))

            all_chunks = []
            seen_content = set()

            # Execute search across target collections
            for target_col in target_collections:
                try:
                    if hasattr(self.retriever, "search_with_reranking"):
                        res = await self.retriever.search_with_reranking(
                            query=query,
                            user_level=1,
                            limit=3 if len(target_collections) > 1 else top_k,
                            collection_override=target_col
                        )
                    else:
                        res = await self.retriever.search(
                            query=query,
                            user_level=1,
                            limit=3 if len(target_collections) > 1 else top_k,
                            collection_override=target_col
                        )

                    for chunk in res.get("results", []):
                        text = chunk.get("text", "") if isinstance(chunk, dict) else getattr(chunk, "text", "")
                        # Deduplicate by first 100 chars
                        if text[:100] not in seen_content:
                            seen_content.add(text[:100])
                            if isinstance(chunk, dict):
                                chunk["_source_collection"] = target_col
                            all_chunks.append(chunk)

                except Exception as e:
                    logger.warning(f"Search failed for {target_col}: {e}")

            # Sort by score and take top results
            all_chunks.sort(key=lambda x: x.get("score", 0) if isinstance(x, dict) else 0, reverse=True)
            chunks = all_chunks[:top_k]

            if not chunks:
                set_span_status("ok")
                return json.dumps({"content": "No relevant documents found.", "sources": []})

            # Format output
            formatted_texts = []
            sources_metadata = []

            for i, chunk in enumerate(chunks):
                text = chunk.get("text", "") if isinstance(chunk, dict) else getattr(chunk, "text", str(chunk))
                metadata = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
                title = metadata.get("title") or "Document"

                source_col = chunk.get("_source_collection", "unknown")
                doc_id = metadata.get("chapter_id") or metadata.get("document_id") or metadata.get("id", "")

                formatted_texts.append(
                    f"[{i + 1}] Source: {source_col} | Title: {title}\n{text}"
                )

                sources_metadata.append({
                    "id": i + 1,
                    "title": title,
                    "url": metadata.get("url", ""),
                    "score": chunk.get("score", 0.0) if isinstance(chunk, dict) else 0.0,
                    "collection": source_col,
                    "doc_id": doc_id,
                })

            content_str = "\n\n".join(formatted_texts)
            set_span_status("ok")
            return json.dumps({"content": content_str, "sources": sources_metadata})


class CalculatorTool(BaseTool):
    """Tool for safe mathematical calculations"""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Perform mathematical calculations. Use for taxes, fees, currency conversions, or any numerical computation."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression (e.g. '1000 * 0.22' or '15000000 / 15500')"
                },
            },
            "required": ["expression"]
        }

    async def execute(self, expression: str, **kwargs) -> str:
        try:
            import ast
            import operator

            allowed_operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.Mod: operator.mod,
            }

            def safe_eval(node):
                if isinstance(node, ast.Expression):
                    return safe_eval(node.body)
                elif isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    if type(node.op) not in allowed_operators:
                        raise ValueError(f"Operator not allowed: {type(node.op)}")
                    return allowed_operators[type(node.op)](
                        safe_eval(node.left),
                        safe_eval(node.right)
                    )
                elif isinstance(node, ast.UnaryOp):
                    if isinstance(node.op, ast.USub):
                        return -safe_eval(node.operand)
                    elif isinstance(node.op, ast.UAdd):
                        return safe_eval(node.operand)
                    raise ValueError(f"Unary operator not allowed: {type(node.op)}")
                else:
                    raise ValueError(f"Invalid expression node: {type(node)}")

            result = safe_eval(ast.parse(expression, mode="eval"))

            # Format nicely
            if isinstance(result, float):
                if result == int(result):
                    result = int(result)
                else:
                    result = round(result, 2)

            return f"Result: {result:,}" if isinstance(result, (int, float)) else f"Result: {result}"

        except Exception as e:
            return f"Calculation error: {e}"


class VisionTool(BaseTool):
    """Tool for visual document analysis"""

    def __init__(self):
        self.vision_service = VisionRAGService()

    @property
    def name(self) -> str:
        return "vision_analysis"

    @property
    def description(self) -> str:
        return "Analyze visual elements in documents (PDFs, images). Extract text, tables, or analyze document structure."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to analyze"},
                "query": {"type": "string", "description": "What to look for in the document"}
            },
            "required": ["file_path", "query"]
        }

    async def execute(self, file_path: str, query: str, **kwargs) -> str:
        try:
            doc = await self.vision_service.process_pdf(file_path)
            result = await self.vision_service.query_with_vision(query, [doc], include_images=True)
            return f"Analysis result: {result['answer']}"
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return f"Vision analysis error: {e}"


class PricingTool(BaseTool):
    """Tool for official service pricing lookup"""

    def __init__(self):
        self.pricing_service = get_pricing_service()

    @property
    def name(self) -> str:
        return "get_pricing"

    @property
    def description(self) -> str:
        return (
            "Get official service pricing. Use this for any price/cost questions. "
            "Returns current prices from the pricing database."
        )

    @property
    def parameters_schema(self) -> dict:
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

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self._team_data = None
        self._data_file = None

    def _get_data_file_path(self):
        if self._data_file is None:
            from pathlib import Path
            possible_paths = [
                Path(__file__).parent.parent.parent.parent / "data" / "team_members.json",
                Path("/app/backend/data/team_members.json"),
            ]
            for path in possible_paths:
                if path.exists():
                    self._data_file = path
                    break
        return self._data_file

    def _load_team_data(self):
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
        return "team_knowledge"

    @property
    def description(self) -> str:
        return "Get information about team members, their roles, departments, and contact info."

    @property
    def parameters_schema(self) -> dict:
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
                return json.dumps([{"name": m.get("name"), "role": m.get("role")} for m in team_data])

            # Search logic
            matches = [m for m in team_data if search_term in json.dumps(m).lower()]
            return json.dumps({"matches": matches, "count": len(matches)})

        except Exception as e:
            logger.error(f"Team knowledge lookup failed: {e}")
            return json.dumps({"error": str(e)})
