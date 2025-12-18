import ast
import logging
import operator
import re

from services.pricing_service import get_pricing_service
from services.rag.agent.structures import BaseTool
from services.rag.vision_rag import VisionRAGService

logger = logging.getLogger(__name__)


class SafeMathEvaluator:
    """
    Safe arithmetic evaluator using AST parsing.
    Supports: +, -, *, /, **, (), abs(), round()
    No eval() - parses and evaluates AST nodes directly.
    """

    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    FUNCTIONS = {
        "abs": abs,
        "round": round,
    }

    def evaluate(self, expression: str) -> float:
        """Safely evaluate a mathematical expression."""
        if not re.match(r"^[\d\s\+\-\*\/\.\(\)\,a-z]+$", expression.lower()):
            raise ValueError("Expression contains invalid characters")
        try:
            tree = ast.parse(expression, mode="eval")
            return self._eval_node(tree.body)
        except (SyntaxError, TypeError) as e:
            raise ValueError(f"Invalid expression: {e}")

    def _eval_node(self, node: ast.AST) -> float:
        """Recursively evaluate AST nodes."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = self.OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op = self.OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op(operand)
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls allowed")
            func_name = node.func.id.lower()
            func = self.FUNCTIONS.get(func_name)
            if func is None:
                raise ValueError(f"Unknown function: {func_name}")
            args = [self._eval_node(arg) for arg in node.args]
            return func(*args)
        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")


class VectorSearchTool(BaseTool):
    """Tool per ricerca vettoriale nel knowledge base"""

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

    async def execute(self, query: str, collection: str = None, top_k: int = 5) -> str:
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
            return "No relevant documents found."

        formatted = []
        for i, chunk in enumerate(chunks):
            # Handle both dict and object access if needed
            text = (
                chunk.get("text", "")
                if isinstance(chunk, dict)
                else getattr(chunk, "text", str(chunk))
            )
            formatted.append(f"[{i + 1}] {text[:500]}")

        return "\n\n".join(formatted)


class DatabaseQueryTool(BaseTool):
    """Tool per query sul database (Deep Dive & Knowledge Graph)"""

    def __init__(self, db_pool):
        self.db = db_pool

    @property
    def name(self) -> str:
        return "database_query"

    @property
    def description(self) -> str:
        return "Query the database to retrieve full document text (Deep Dive) or entity relationships. Use this when you need to read the complete content of a specific chapter (BAB) or law."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "The term to search for (e.g., document title, chapter name, or entity name)",
                },
                "query_type": {
                    "type": "string",
                    "enum": ["full_text", "relationship"],
                    "description": "Type of query: 'full_text' for reading documents, 'relationship' for knowledge graph",
                },
            },
            "required": ["search_term"],
        }

    async def execute(self, search_term: str, query_type: str = "full_text", **kwargs) -> str:
        if not search_term and "entity_name" in kwargs:
            search_term = kwargs["entity_name"]

        if not self.db:
            return "Database connection not available."

        try:
            async with self.db.acquire() as conn:
                if query_type == "full_text":
                    query = """
                        SELECT title, full_text
                        FROM parent_documents
                        WHERE title ILIKE $1
                        LIMIT 1
                    """
                    search_pattern = f"%{search_term}%"
                    row = await conn.fetchrow(query, search_pattern)

                    if row:
                        return f"Document Found: {row['title']}\n\nContent:\n{row['full_text']}"
                    else:
                        return f"No full text document found matching '{search_term}'."

                elif query_type == "relationship":
                    return f"Knowledge Graph relationship data for '{search_term}' is currently not populated."

                else:
                    return f"Unknown query_type: {query_type}"

        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return f"Database query failed: {str(e)}"


class CalculatorTool(BaseTool):
    """Tool per calcoli (tasse, deadline, etc.)"""

    def __init__(self):
        self._evaluator = SafeMathEvaluator()

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

    async def execute(self, expression: str, calculation_type: str = "general") -> str:
        try:
            result = self._evaluator.evaluate(expression)

            if calculation_type == "tax":
                return f"Tax calculation: Rp {result:,.0f}"
            elif calculation_type == "fee":
                return f"Fee: Rp {result:,.0f}"
            else:
                return f"Result: {result}"
        except Exception as e:
            return f"Calculation error: {str(e)}"


class PricingTool(BaseTool):
    """Tool per prezzi ufficiali Bali Zero"""

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
            },
            "required": ["service_type"],
        }

    async def execute(self, service_type: str) -> str:
        try:
            return await self.pricing_service.get_prices_formatted(service_type)
        except Exception as e:
            return f"Pricing lookup failed: {str(e)}"


class VisionTool(BaseTool):
    """Tool per analisi visiva di documenti"""

    def __init__(self):
        try:
            self.vision_service = VisionRAGService()
        except Exception as e:
            logger.warning(f"Vision service not available: {e}")
            self.vision_service = None

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

    async def execute(self, file_path: str, query: str) -> str:
        if not self.vision_service:
            return "Vision service is not initialized."

        try:
            doc = await self.vision_service.process_pdf(file_path)
            result = await self.vision_service.query_with_vision(query, [doc], include_images=True)
            return f"Vision Analysis Result:\n{result['answer']}\n\nVisual Elements Used: {len(result['visuals_used'])}"
        except Exception as e:
            return f"Vision analysis failed: {str(e)}"
