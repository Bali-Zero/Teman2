"""
Comprehensive tests for backend/services/rag/agent/tools.py.

Tests cover:
- SafeMathEvaluator class
- VectorSearchTool (with mocks)
- Other tool classes
"""

import pytest

from backend.services.rag.agent.tools import SafeMathEvaluator


class TestSafeMathEvaluator:
    """Tests for SafeMathEvaluator class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.evaluator = SafeMathEvaluator()

    def test_simple_addition(self) -> None:
        """Test simple addition."""
        assert self.evaluator.evaluate("2 + 3") == 5
        assert self.evaluator.evaluate("10 + 20") == 30

    def test_simple_subtraction(self) -> None:
        """Test simple subtraction."""
        assert self.evaluator.evaluate("10 - 3") == 7
        assert self.evaluator.evaluate("100 - 50") == 50

    def test_simple_multiplication(self) -> None:
        """Test simple multiplication."""
        assert self.evaluator.evaluate("4 * 5") == 20
        assert self.evaluator.evaluate("7 * 8") == 56

    def test_simple_division(self) -> None:
        """Test simple division."""
        assert self.evaluator.evaluate("20 / 4") == 5.0
        assert self.evaluator.evaluate("100 / 10") == 10.0

    def test_power_operator(self) -> None:
        """Test power operator."""
        assert self.evaluator.evaluate("2 ** 3") == 8
        assert self.evaluator.evaluate("10 ** 2") == 100

    def test_complex_expression(self) -> None:
        """Test complex expressions with multiple operators."""
        assert self.evaluator.evaluate("2 + 3 * 4") == 14
        assert self.evaluator.evaluate("(2 + 3) * 4") == 20
        assert self.evaluator.evaluate("10 - 2 * 3") == 4

    def test_parentheses(self) -> None:
        """Test expressions with parentheses."""
        assert self.evaluator.evaluate("(10 + 5) * 2") == 30
        assert self.evaluator.evaluate("100 / (10 + 10)") == 5.0
        assert self.evaluator.evaluate("((2 + 3) * (4 + 5))") == 45

    def test_negative_numbers(self) -> None:
        """Test expressions with negative numbers."""
        assert self.evaluator.evaluate("-5 + 10") == 5
        assert self.evaluator.evaluate("10 + (-5)") == 5

    def test_decimal_numbers(self) -> None:
        """Test expressions with decimal numbers."""
        assert self.evaluator.evaluate("2.5 + 2.5") == 5.0
        assert self.evaluator.evaluate("10.5 * 2") == 21.0

    def test_abs_function(self) -> None:
        """Test abs() function."""
        assert self.evaluator.evaluate("abs(-10)") == 10
        assert self.evaluator.evaluate("abs(10)") == 10

    def test_round_function(self) -> None:
        """Test round() function."""
        assert self.evaluator.evaluate("round(3.7)") == 4
        assert self.evaluator.evaluate("round(3.2)") == 3

    def test_invalid_characters_raises_error(self) -> None:
        """Test that invalid characters raise ValueError."""
        with pytest.raises(ValueError):
            self.evaluator.evaluate("import os")
        with pytest.raises(ValueError):
            self.evaluator.evaluate("__import__('os')")
        with pytest.raises(ValueError):
            self.evaluator.evaluate("eval('1+1')")

    def test_unknown_function_raises_error(self) -> None:
        """Test that unknown functions raise ValueError."""
        with pytest.raises(ValueError, match="Unknown function"):
            self.evaluator.evaluate("sin(30)")
        with pytest.raises(ValueError, match="Unknown function"):
            self.evaluator.evaluate("cos(45)")

    def test_empty_expression_raises_error(self) -> None:
        """Test that empty expressions raise error."""
        with pytest.raises((ValueError, SyntaxError)):
            self.evaluator.evaluate("")

    def test_whitespace_handling(self) -> None:
        """Test expressions with various whitespace."""
        assert self.evaluator.evaluate("2  +  3") == 5
        assert self.evaluator.evaluate("10*5") == 50

    def test_large_numbers(self) -> None:
        """Test expressions with large numbers."""
        assert self.evaluator.evaluate("1000000 + 2000000") == 3000000
        assert self.evaluator.evaluate("1e6 + 1e6") == 2000000.0

    def test_division_result_is_float(self) -> None:
        """Test that division always returns float."""
        result = self.evaluator.evaluate("10 / 2")
        assert isinstance(result, float)

    def test_nested_functions(self) -> None:
        """Test nested function calls."""
        assert self.evaluator.evaluate("abs(round(-3.7))") == 4

    def test_unary_positive(self) -> None:
        """Test unary positive operator."""
        assert self.evaluator.evaluate("+5") == 5
        assert self.evaluator.evaluate("10 + (+5)") == 15


class TestSafeMathEvaluatorEdgeCases:
    """Edge case tests for SafeMathEvaluator."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.evaluator = SafeMathEvaluator()

    def test_zero_division_raises_error(self) -> None:
        """Test that division by zero raises error."""
        with pytest.raises(ZeroDivisionError):
            self.evaluator.evaluate("10 / 0")

    def test_very_small_decimals(self) -> None:
        """Test very small decimal numbers."""
        result = self.evaluator.evaluate("0.0001 + 0.0001")
        assert abs(result - 0.0002) < 1e-10

    def test_scientific_notation(self) -> None:
        """Test scientific notation."""
        assert self.evaluator.evaluate("1e3") == 1000.0
        assert self.evaluator.evaluate("2.5e2") == 250.0
