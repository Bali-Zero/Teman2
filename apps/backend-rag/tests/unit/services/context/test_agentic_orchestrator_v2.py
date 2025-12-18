"""
Comprehensive unit tests for services/context/agentic_orchestrator_v2.py
Target: 95%+ coverage

Tests cover:
- SafeMathEvaluator: safe math expression evaluation with AST parsing
- CalculatorTool: calculator tool wrapper
- AgenticRAGOrchestrator: agentic RAG with memory and search integration
"""

import ast
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "backend"))

# Mock settings to avoid validation errors
mock_settings = MagicMock()
mock_settings.google_api_key = "test-google-api-key"
mock_settings.gemini_model_smart = "gemini-1.5-flash"


@pytest.fixture
def mock_genai():
    """Mock google.generativeai module"""
    with patch.dict(sys.modules, {"google.generativeai": MagicMock()}):
        yield sys.modules["google.generativeai"]


@pytest.fixture
def mock_config():
    """Mock app.core.config module"""
    with patch("services.context.agentic_orchestrator_v2.settings", mock_settings):
        yield mock_settings


class TestSafeMathEvaluator:
    """Comprehensive test suite for SafeMathEvaluator"""

    @pytest.fixture
    def evaluator(self):
        """Create SafeMathEvaluator instance"""
        from services.context.agentic_orchestrator_v2 import SafeMathEvaluator

        return SafeMathEvaluator()

    # ===== Basic Arithmetic Operations =====

    def test_evaluate_addition(self, evaluator):
        """Test simple addition"""
        result = evaluator.evaluate("2 + 3")
        assert result == 5

    def test_evaluate_subtraction(self, evaluator):
        """Test simple subtraction"""
        result = evaluator.evaluate("10 - 3")
        assert result == 7

    def test_evaluate_multiplication(self, evaluator):
        """Test simple multiplication"""
        result = evaluator.evaluate("4 * 5")
        assert result == 20

    def test_evaluate_division(self, evaluator):
        """Test simple division"""
        result = evaluator.evaluate("15 / 3")
        assert result == 5.0

    def test_evaluate_power(self, evaluator):
        """Test exponentiation"""
        result = evaluator.evaluate("2 ** 3")
        assert result == 8

    # ===== Complex Expressions =====

    def test_evaluate_complex_expression(self, evaluator):
        """Test complex arithmetic expression with multiple operations"""
        result = evaluator.evaluate("(2 + 3) * 4 - 1")
        assert result == 19

    def test_evaluate_nested_parentheses(self, evaluator):
        """Test nested parentheses"""
        result = evaluator.evaluate("((2 + 3) * (4 + 1)) - 5")
        assert result == 20

    def test_evaluate_decimal_numbers(self, evaluator):
        """Test with decimal numbers"""
        result = evaluator.evaluate("3.5 + 2.5")
        assert result == 6.0

    def test_evaluate_negative_numbers(self, evaluator):
        """Test with negative numbers using unary minus"""
        result = evaluator.evaluate("-5 + 3")
        assert result == -2

    def test_evaluate_unary_plus(self, evaluator):
        """Test unary plus operator"""
        result = evaluator.evaluate("+5 + 3")
        assert result == 8

    # ===== Function Calls =====

    def test_evaluate_abs_function(self, evaluator):
        """Test abs() function"""
        result = evaluator.evaluate("abs(-10)")
        assert result == 10

    def test_evaluate_abs_positive(self, evaluator):
        """Test abs() with positive number"""
        result = evaluator.evaluate("abs(5)")
        assert result == 5

    def test_evaluate_round_function(self, evaluator):
        """Test round() function with one argument"""
        result = evaluator.evaluate("round(3.7)")
        assert result == 4

    def test_evaluate_round_with_precision(self, evaluator):
        """Test round() function with precision argument"""
        result = evaluator.evaluate("round(3.14159, 2)")
        assert result == 3.14

    def test_evaluate_nested_functions(self, evaluator):
        """Test nested function calls"""
        result = evaluator.evaluate("abs(round(-3.7))")
        assert result == 4

    def test_evaluate_function_with_expression(self, evaluator):
        """Test function with expression as argument"""
        result = evaluator.evaluate("abs(-5 * 2)")
        assert result == 10

    # ===== Security Tests - Invalid Characters =====

    def test_evaluate_invalid_characters_semicolon(self, evaluator):
        """Test that semicolons are rejected (code injection prevention)"""
        with pytest.raises(ValueError, match="invalid characters"):
            evaluator.evaluate("2 + 3; import os")

    def test_evaluate_invalid_characters_underscore(self, evaluator):
        """Test that underscores are rejected (prevents __import__ etc)"""
        with pytest.raises(ValueError, match="invalid characters"):
            evaluator.evaluate("__import__('os')")

    def test_evaluate_invalid_characters_quotes(self, evaluator):
        """Test that quotes are rejected"""
        with pytest.raises(ValueError, match="invalid characters"):
            evaluator.evaluate("'malicious'")

    def test_evaluate_invalid_characters_brackets(self, evaluator):
        """Test that square brackets are rejected"""
        with pytest.raises(ValueError, match="invalid characters"):
            evaluator.evaluate("[1,2,3]")

    def test_evaluate_invalid_characters_special(self, evaluator):
        """Test that special characters like @ are rejected"""
        with pytest.raises(ValueError, match="invalid characters"):
            evaluator.evaluate("2 @ 3")

    # ===== Security Tests - Invalid Functions =====

    def test_evaluate_unknown_function(self, evaluator):
        """Test that unknown functions are rejected"""
        with pytest.raises(ValueError, match="Unknown function"):
            evaluator.evaluate("eval(2 + 3)")

    def test_evaluate_disallowed_function_import(self, evaluator):
        """Test that import is rejected"""
        with pytest.raises(ValueError, match="invalid characters|Invalid expression"):
            evaluator.evaluate("import('os')")

    # ===== Invalid Expression Tests =====

    def test_evaluate_syntax_error(self, evaluator):
        """Test handling of syntax errors"""
        with pytest.raises(ValueError, match="Invalid expression"):
            evaluator.evaluate("2 + + 3")

    def test_evaluate_empty_expression(self, evaluator):
        """Test handling of empty expression"""
        with pytest.raises(ValueError):
            evaluator.evaluate("")

    def test_evaluate_incomplete_expression(self, evaluator):
        """Test handling of incomplete expression"""
        with pytest.raises(ValueError):
            evaluator.evaluate("2 +")

    # ===== AST Node Type Tests =====

    def test_eval_node_constant(self, evaluator):
        """Test _eval_node with Constant node"""
        node = ast.Constant(value=42)
        result = evaluator._eval_node(node)
        assert result == 42

    def test_eval_node_constant_float(self, evaluator):
        """Test _eval_node with float Constant"""
        node = ast.Constant(value=3.14)
        result = evaluator._eval_node(node)
        assert result == 3.14

    def test_eval_node_constant_invalid_type(self, evaluator):
        """Test _eval_node rejects non-numeric constants"""
        node = ast.Constant(value="string")
        with pytest.raises(ValueError, match="Unsupported constant type"):
            evaluator._eval_node(node)

    def test_eval_node_binop_add(self, evaluator):
        """Test _eval_node with BinOp (addition)"""
        node = ast.BinOp(left=ast.Constant(2), op=ast.Add(), right=ast.Constant(3))
        result = evaluator._eval_node(node)
        assert result == 5

    def test_eval_node_binop_unsupported_operator(self, evaluator):
        """Test _eval_node rejects unsupported binary operators"""
        # FloorDiv is not in OPERATORS
        node = ast.BinOp(left=ast.Constant(7), op=ast.FloorDiv(), right=ast.Constant(2))
        with pytest.raises(ValueError, match="Unsupported operator"):
            evaluator._eval_node(node)

    def test_eval_node_unaryop_neg(self, evaluator):
        """Test _eval_node with UnaryOp (negation)"""
        node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(5))
        result = evaluator._eval_node(node)
        assert result == -5

    def test_eval_node_unaryop_unsupported(self, evaluator):
        """Test _eval_node rejects unsupported unary operators"""
        # Not is not in OPERATORS
        node = ast.UnaryOp(op=ast.Not(), operand=ast.Constant(True))
        with pytest.raises(ValueError, match="Unsupported unary operator"):
            evaluator._eval_node(node)

    def test_eval_node_call_abs(self, evaluator):
        """Test _eval_node with Call node (abs)"""
        node = ast.Call(
            func=ast.Name(id="abs", ctx=ast.Load()),
            args=[ast.Constant(-10)],
            keywords=[],
        )
        result = evaluator._eval_node(node)
        assert result == 10

    def test_eval_node_call_non_simple_function(self, evaluator):
        """Test _eval_node rejects non-simple function calls"""
        # Attribute access like obj.method() is not allowed
        node = ast.Call(
            func=ast.Attribute(value=ast.Name(id="obj"), attr="method"),
            args=[],
            keywords=[],
        )
        with pytest.raises(ValueError, match="Only simple function calls allowed"):
            evaluator._eval_node(node)

    def test_eval_node_unsupported_expression_type(self, evaluator):
        """Test _eval_node rejects unsupported node types"""
        # List is not supported
        node = ast.List(elts=[ast.Constant(1), ast.Constant(2)])
        with pytest.raises(ValueError, match="Unsupported expression type"):
            evaluator._eval_node(node)

    # ===== Edge Cases =====

    def test_evaluate_division_by_zero(self, evaluator):
        """Test division by zero raises ZeroDivisionError"""
        with pytest.raises(ZeroDivisionError):
            evaluator.evaluate("10 / 0")

    def test_evaluate_whitespace(self, evaluator):
        """Test expression with extra whitespace"""
        result = evaluator.evaluate("  2   +   3  ")
        assert result == 5

    def test_evaluate_case_insensitive_function(self, evaluator):
        """Test that function names are case insensitive"""
        result = evaluator.evaluate("ABS(-5)")
        assert result == 5

    def test_evaluate_mixed_case_function(self, evaluator):
        """Test mixed case function names"""
        result = evaluator.evaluate("RoUnD(3.7)")
        assert result == 4


class TestCalculatorTool:
    """Comprehensive test suite for CalculatorTool"""

    @pytest.fixture
    def calculator(self, mock_config):
        """Create CalculatorTool instance"""
        from services.context.agentic_orchestrator_v2 import CalculatorTool

        return CalculatorTool()

    # ===== Initialization Tests =====

    def test_init_name(self, calculator):
        """Test CalculatorTool initialization sets name"""
        assert calculator.name == "calculator"

    def test_init_description(self, calculator):
        """Test CalculatorTool initialization sets description"""
        assert "mathematical calculations" in calculator.description.lower()

    def test_init_parameters(self, calculator):
        """Test CalculatorTool initialization sets parameters schema"""
        assert calculator.parameters["type"] == "object"
        assert "expression" in calculator.parameters["properties"]
        assert "expression" in calculator.parameters["required"]

    def test_init_evaluator(self, calculator):
        """Test CalculatorTool has SafeMathEvaluator instance"""
        assert calculator._evaluator is not None
        from services.context.agentic_orchestrator_v2 import SafeMathEvaluator

        assert isinstance(calculator._evaluator, SafeMathEvaluator)

    # ===== Execute Method Tests =====

    @pytest.mark.asyncio
    async def test_execute_simple_calculation(self, calculator):
        """Test execute with simple calculation"""
        result = await calculator.execute(expression="2 + 3")
        assert result == "5"

    @pytest.mark.asyncio
    async def test_execute_complex_calculation(self, calculator):
        """Test execute with complex calculation"""
        result = await calculator.execute(expression="(10 + 5) * 2")
        assert result == "30"

    @pytest.mark.asyncio
    async def test_execute_with_function(self, calculator):
        """Test execute with function call"""
        result = await calculator.execute(expression="abs(-42)")
        assert result == "42"

    @pytest.mark.asyncio
    async def test_execute_decimal_result(self, calculator):
        """Test execute returns decimal result as string"""
        result = await calculator.execute(expression="10 / 4")
        assert result == "2.5"

    @pytest.mark.asyncio
    async def test_execute_invalid_expression(self, calculator):
        """Test execute handles invalid expression gracefully"""
        result = await calculator.execute(expression="invalid expression!")
        assert "Error calculating" in result
        assert "invalid characters" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_division_by_zero(self, calculator):
        """Test execute handles division by zero"""
        result = await calculator.execute(expression="10 / 0")
        assert "Error calculating" in result

    @pytest.mark.asyncio
    async def test_execute_unknown_function(self, calculator):
        """Test execute handles unknown function"""
        result = await calculator.execute(expression="sqrt(16)")
        assert "Error calculating" in result
        assert "Unknown function" in result or "invalid characters" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_returns_string(self, calculator):
        """Test execute always returns string"""
        result = await calculator.execute(expression="42")
        assert isinstance(result, str)


class TestAgenticRAGOrchestrator:
    """Comprehensive test suite for AgenticRAGOrchestrator"""

    @pytest.fixture
    def mock_memory_service(self):
        """Mock memory service"""
        service = MagicMock()
        service.get_memory = AsyncMock()
        service.get_recent_history = AsyncMock()
        return service

    @pytest.fixture
    def mock_search_service(self):
        """Mock search service"""
        service = MagicMock()
        service.search = AsyncMock()
        return service

    @pytest.fixture
    def mock_gemini_model(self):
        """Mock Gemini model"""
        model = MagicMock()
        model.generate_content_async = AsyncMock()
        return model

    @pytest.fixture
    def orchestrator(
        self, mock_config, mock_memory_service, mock_search_service, mock_gemini_model
    ):
        """Create AgenticRAGOrchestrator instance with mocks"""
        with patch("services.context.agentic_orchestrator_v2.genai") as mock_genai:
            mock_genai.configure = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_gemini_model

            from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestrator

            return AgenticRAGOrchestrator(
                memory_service=mock_memory_service, search_service=mock_search_service
            )

    # ===== Initialization Tests =====

    def test_init_tools(self, orchestrator):
        """Test orchestrator initializes with CalculatorTool"""
        assert len(orchestrator.tools) == 1
        from services.context.agentic_orchestrator_v2 import CalculatorTool

        assert isinstance(orchestrator.tools[0], CalculatorTool)

    def test_init_tool_map(self, orchestrator):
        """Test orchestrator creates tool_map"""
        assert "calculator" in orchestrator.tool_map
        assert orchestrator.tool_map["calculator"] == orchestrator.tools[0]

    def test_init_memory_service(self, mock_memory_service, orchestrator):
        """Test orchestrator stores memory_service"""
        assert orchestrator.memory_service == mock_memory_service

    def test_init_search_service(self, mock_search_service, orchestrator):
        """Test orchestrator stores search_service"""
        assert orchestrator.search_service == mock_search_service

    def test_init_without_services(self, mock_config, mock_gemini_model):
        """Test orchestrator can be initialized without services"""
        with patch("services.context.agentic_orchestrator_v2.genai") as mock_genai:
            mock_genai.configure = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_gemini_model

            from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestrator

            orch = AgenticRAGOrchestrator()
            assert orch.memory_service is None
            assert orch.search_service is None

    def test_init_configures_genai(self, mock_config, mock_memory_service, mock_search_service):
        """Test orchestrator configures genai with API key"""
        with patch("services.context.agentic_orchestrator_v2.genai") as mock_genai:
            from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestrator

            AgenticRAGOrchestrator(
                memory_service=mock_memory_service, search_service=mock_search_service
            )
            mock_genai.configure.assert_called_once_with(api_key=mock_settings.google_api_key)

    def test_init_creates_model(self, mock_config, mock_memory_service, mock_search_service):
        """Test orchestrator creates Gemini model"""
        with patch("services.context.agentic_orchestrator_v2.genai") as mock_genai:
            from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestrator

            orch = AgenticRAGOrchestrator(
                memory_service=mock_memory_service, search_service=mock_search_service
            )
            mock_genai.GenerativeModel.assert_called_once_with(mock_settings.gemini_model_smart)
            assert orch.model is not None

    # ===== Initialize Method Tests =====

    @pytest.mark.asyncio
    async def test_initialize(self, orchestrator):
        """Test initialize method completes without error"""
        await orchestrator.initialize()

    # ===== Process Query Tests - Context Building =====

    @pytest.mark.asyncio
    async def test_process_query_calls_memory_service(
        self, orchestrator, mock_memory_service, mock_gemini_model
    ):
        """Test process_query calls memory service methods"""
        mock_memory_service.get_memory.return_value = None
        mock_memory_service.get_recent_history.return_value = []
        orchestrator.search_service.search.return_value = {"results": []}

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        await orchestrator.process_query("test query", user_id="user123")

        mock_memory_service.get_memory.assert_called_once_with("user123")
        mock_memory_service.get_recent_history.assert_called_once_with("user123", limit=5)

    @pytest.mark.asyncio
    async def test_process_query_calls_search_service(
        self, orchestrator, mock_search_service, mock_gemini_model
    ):
        """Test process_query calls search service"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []
        mock_search_service.search.return_value = {"results": []}

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        await orchestrator.process_query("test query")

        mock_search_service.search.assert_called_once_with("test query", user_level=3, limit=3)

    @pytest.mark.asyncio
    async def test_process_query_with_user_memory(
        self, orchestrator, mock_memory_service, mock_gemini_model
    ):
        """Test process_query includes user memory in context"""
        mock_memory = MagicMock()
        mock_memory.profile_facts = ["User is Italian", "User prefers formal language"]
        mock_memory.summary = "Professional user"
        mock_memory_service.get_memory.return_value = mock_memory
        mock_memory_service.get_recent_history.return_value = []
        orchestrator.search_service.search.return_value = {"results": []}

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        await orchestrator.process_query("test query", user_id="user123")

        # Verify the prompt includes user profile
        call_args = mock_gemini_model.generate_content_async.call_args[0][0]
        assert "USER PROFILE" in call_args
        assert "user123" in call_args
        assert "User is Italian" in call_args
        assert "Professional user" in call_args

    @pytest.mark.asyncio
    async def test_process_query_with_search_results(
        self, orchestrator, mock_search_service, mock_gemini_model
    ):
        """Test process_query includes search results in context"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []

        mock_search_service.search.return_value = {
            "results": [
                {
                    "text": "This is a relevant document about Indonesian business law",
                    "metadata": {"filename": "business_law.pdf"},
                },
                {
                    "text": "Another document about PT PMA requirements",
                    "metadata": {"title": "PT PMA Guide"},
                },
            ]
        }

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        result = await orchestrator.process_query("test query")

        # Verify the prompt includes RAG sources
        call_args = mock_gemini_model.generate_content_async.call_args[0][0]
        assert "RELEVANT KNOWLEDGE" in call_args
        assert "business_law.pdf" in call_args
        assert "PT PMA Guide" in call_args

        # Verify sources in result
        assert len(result["sources"]) == 2
        assert result["sources"][0]["title"] == "business_law.pdf"

    @pytest.mark.asyncio
    async def test_process_query_with_conversation_history(
        self, orchestrator, mock_memory_service, mock_gemini_model
    ):
        """Test process_query includes conversation history in context"""
        mock_memory_service.get_memory.return_value = None
        mock_memory_service.get_recent_history.return_value = [
            {"role": "user", "content": "What is a PT PMA?"},
            {"role": "assistant", "content": "A PT PMA is a foreign-owned company in Indonesia."},
            {"role": "user", "content": "What are the requirements?"},
        ]
        orchestrator.search_service.search.return_value = {"results": []}

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        await orchestrator.process_query("Tell me more")

        # Verify the prompt includes conversation history
        call_args = mock_gemini_model.generate_content_async.call_args[0][0]
        assert "RECENT CONVERSATION" in call_args
        assert "What is a PT PMA?" in call_args
        assert "foreign-owned company" in call_args

    @pytest.mark.asyncio
    async def test_process_query_without_memory_service(
        self, mock_config, mock_search_service, mock_gemini_model
    ):
        """Test process_query works without memory service"""
        with patch("services.context.agentic_orchestrator_v2.genai") as mock_genai:
            mock_genai.configure = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_gemini_model

            from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestrator

            orch = AgenticRAGOrchestrator(memory_service=None, search_service=mock_search_service)

            mock_search_service.search.return_value = {"results": []}
            mock_response = MagicMock()
            mock_response.text = "Test answer"
            mock_gemini_model.generate_content_async.return_value = mock_response

            result = await orch.process_query("test query")

            assert result["answer"] == "Test answer"

    @pytest.mark.asyncio
    async def test_process_query_without_search_service(
        self, mock_config, mock_memory_service, mock_gemini_model
    ):
        """Test process_query works without search service"""
        with patch("services.context.agentic_orchestrator_v2.genai") as mock_genai:
            mock_genai.configure = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_gemini_model

            from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestrator

            orch = AgenticRAGOrchestrator(memory_service=mock_memory_service, search_service=None)

            mock_memory_service.get_memory.return_value = None
            mock_memory_service.get_recent_history.return_value = []
            mock_response = MagicMock()
            mock_response.text = "Test answer"
            mock_gemini_model.generate_content_async.return_value = mock_response

            result = await orch.process_query("test query")

            assert result["answer"] == "Test answer"

    @pytest.mark.asyncio
    async def test_process_query_truncates_long_content(
        self, orchestrator, mock_search_service, mock_gemini_model
    ):
        """Test process_query truncates long search results"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []

        long_text = "x" * 1000
        mock_search_service.search.return_value = {
            "results": [{"text": long_text, "metadata": {"filename": "doc.pdf"}}]
        }

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        result = await orchestrator.process_query("test query")

        # Content should be truncated to 500 chars
        assert len(result["sources"][0]["content"]) == 500

    @pytest.mark.asyncio
    async def test_process_query_handles_missing_metadata(
        self, orchestrator, mock_search_service, mock_gemini_model
    ):
        """Test process_query handles search results without metadata"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []

        mock_search_service.search.return_value = {
            "results": [{"text": "Content without metadata", "metadata": {}}]
        }

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        result = await orchestrator.process_query("test query")

        assert result["sources"][0]["title"] == "Unknown Source"

    # ===== Process Query Tests - Response Generation =====

    @pytest.mark.asyncio
    async def test_process_query_generates_response(self, orchestrator, mock_gemini_model):
        """Test process_query generates response from Gemini"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []
        orchestrator.search_service.search.return_value = {"results": []}

        mock_response = MagicMock()
        mock_response.text = "This is the AI response"
        mock_gemini_model.generate_content_async.return_value = mock_response

        result = await orchestrator.process_query("What is Nuzantara?")

        mock_gemini_model.generate_content_async.assert_called_once()
        assert result["answer"] == "This is the AI response"

    @pytest.mark.asyncio
    async def test_process_query_includes_instructions_in_prompt(
        self, orchestrator, mock_gemini_model
    ):
        """Test process_query includes proper instructions in prompt"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []
        orchestrator.search_service.search.return_value = {"results": []}

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        await orchestrator.process_query("test query")

        call_args = mock_gemini_model.generate_content_async.call_args[0][0]
        assert "Zantara" in call_args
        assert "AVAILABLE TOOLS" in call_args
        assert "calculator" in call_args
        assert "INSTRUCTIONS" in call_args

    @pytest.mark.asyncio
    async def test_process_query_result_structure(self, orchestrator, mock_gemini_model):
        """Test process_query returns correctly structured result"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []
        orchestrator.search_service.search.return_value = {"results": []}

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        result = await orchestrator.process_query("test query")

        assert "answer" in result
        assert "sources" in result
        assert "context_used" in result
        assert "execution_time" in result
        assert "route_used" in result
        assert "steps" in result

        assert result["route_used"] == "agentic_v2"
        assert isinstance(result["sources"], list)
        assert isinstance(result["context_used"], int)
        assert isinstance(result["execution_time"], float)
        assert isinstance(result["steps"], list)

    @pytest.mark.asyncio
    async def test_process_query_execution_time(self, orchestrator, mock_gemini_model):
        """Test process_query calculates execution time"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []
        orchestrator.search_service.search.return_value = {"results": []}

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        result = await orchestrator.process_query("test query")

        assert result["execution_time"] >= 0

    @pytest.mark.asyncio
    async def test_process_query_context_used_count(self, orchestrator, mock_gemini_model):
        """Test process_query counts context characters"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []
        orchestrator.search_service.search.return_value = {
            "results": [
                {"text": "Some content", "metadata": {"filename": "doc.pdf"}},
            ]
        }

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        result = await orchestrator.process_query("test query")

        assert result["context_used"] > 0

    @pytest.mark.asyncio
    async def test_process_query_with_enable_vision_flag(self, orchestrator, mock_gemini_model):
        """Test process_query accepts enable_vision parameter"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []
        orchestrator.search_service.search.return_value = {"results": []}

        mock_response = MagicMock()
        mock_response.text = "Test answer"
        mock_gemini_model.generate_content_async.return_value = mock_response

        result = await orchestrator.process_query("test query", enable_vision=True)

        assert result["answer"] == "Test answer"

    # ===== Error Handling Tests =====

    @pytest.mark.asyncio
    async def test_process_query_handles_genai_error(self, orchestrator, mock_gemini_model):
        """Test process_query propagates Gemini API errors"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []
        orchestrator.search_service.search.return_value = {"results": []}

        mock_gemini_model.generate_content_async.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await orchestrator.process_query("test query")

    @pytest.mark.asyncio
    async def test_process_query_handles_memory_service_error(
        self, orchestrator, mock_memory_service, mock_gemini_model
    ):
        """Test process_query handles memory service errors gracefully"""
        mock_memory_service.get_memory.side_effect = Exception("Memory error")

        # Should propagate the error
        with pytest.raises(Exception):
            await orchestrator.process_query("test query")

    @pytest.mark.asyncio
    async def test_process_query_handles_search_service_error(
        self, orchestrator, mock_search_service, mock_gemini_model
    ):
        """Test process_query handles search service errors gracefully"""
        orchestrator.memory_service.get_memory.return_value = None
        orchestrator.memory_service.get_recent_history.return_value = []
        mock_search_service.search.side_effect = Exception("Search error")

        # Should propagate the error
        with pytest.raises(Exception):
            await orchestrator.process_query("test query")


class TestBaseTool:
    """Test suite for BaseTool abstract class"""

    def test_basetool_has_attributes(self):
        """Test BaseTool defines required attributes"""
        from services.context.agentic_orchestrator_v2 import BaseTool

        assert hasattr(BaseTool, "name")
        assert hasattr(BaseTool, "description")
        assert hasattr(BaseTool, "parameters")

    @pytest.mark.asyncio
    async def test_basetool_execute_not_implemented(self):
        """Test BaseTool.execute raises NotImplementedError"""
        from services.context.agentic_orchestrator_v2 import BaseTool

        tool = BaseTool()
        with pytest.raises(NotImplementedError):
            await tool.execute()
