"""
Unit tests for SafeMathEvaluator
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.agent.tools import SafeMathEvaluator


@pytest.fixture
def evaluator():
    """Create SafeMathEvaluator instance"""
    return SafeMathEvaluator()


class TestSafeMathEvaluator:
    """Tests for SafeMathEvaluator class"""

    def test_evaluate_simple_addition(self, evaluator):
        """Test simple addition"""
        result = evaluator.evaluate("2 + 3")
        assert result == 5.0

    def test_evaluate_simple_subtraction(self, evaluator):
        """Test simple subtraction"""
        result = evaluator.evaluate("10 - 4")
        assert result == 6.0

    def test_evaluate_simple_multiplication(self, evaluator):
        """Test simple multiplication"""
        result = evaluator.evaluate("3 * 4")
        assert result == 12.0

    def test_evaluate_simple_division(self, evaluator):
        """Test simple division"""
        result = evaluator.evaluate("10 / 2")
        assert result == 5.0

    def test_evaluate_power(self, evaluator):
        """Test power operation"""
        result = evaluator.evaluate("2 ** 3")
        assert result == 8.0

    def test_evaluate_parentheses(self, evaluator):
        """Test expression with parentheses"""
        result = evaluator.evaluate("(2 + 3) * 4")
        assert result == 20.0

    def test_evaluate_complex_expression(self, evaluator):
        """Test complex expression"""
        result = evaluator.evaluate("(10 + 5) * 2 - 8 / 2")
        assert result == 26.0

    def test_evaluate_negative_number(self, evaluator):
        """Test negative number"""
        result = evaluator.evaluate("-5")
        assert result == -5.0

    def test_evaluate_positive_unary(self, evaluator):
        """Test positive unary operator"""
        result = evaluator.evaluate("+5")
        assert result == 5.0

    def test_evaluate_float_numbers(self, evaluator):
        """Test floating point numbers"""
        result = evaluator.evaluate("3.5 + 2.5")
        assert result == 6.0

    def test_evaluate_abs_function(self, evaluator):
        """Test abs function"""
        result = evaluator.evaluate("abs(-10)")
        assert result == 10.0

    def test_evaluate_abs_function_positive(self, evaluator):
        """Test abs function with positive number"""
        result = evaluator.evaluate("abs(10)")
        assert result == 10.0

    def test_evaluate_round_function(self, evaluator):
        """Test round function"""
        result = evaluator.evaluate("round(3.7)")
        assert result == 4.0

    def test_evaluate_round_function_decimal(self, evaluator):
        """Test round function with decimal places"""
        result = evaluator.evaluate("round(3.14159)")
        assert result == 3.0

    def test_evaluate_function_in_expression(self, evaluator):
        """Test function in expression"""
        result = evaluator.evaluate("abs(-5) + 3")
        assert result == 8.0

    def test_evaluate_nested_parentheses(self, evaluator):
        """Test nested parentheses"""
        result = evaluator.evaluate("((2 + 3) * 4) - 1")
        assert result == 19.0

    def test_evaluate_whitespace(self, evaluator):
        """Test expression with whitespace"""
        result = evaluator.evaluate("2 + 3")
        assert result == 5.0

    def test_evaluate_invalid_characters(self, evaluator):
        """Test expression with invalid characters"""
        with pytest.raises(ValueError, match="invalid characters"):
            evaluator.evaluate("2 + 3; import os")

    def test_evaluate_invalid_characters_special(self, evaluator):
        """Test expression with special invalid characters"""
        with pytest.raises(ValueError, match="invalid characters"):
            evaluator.evaluate("2 + 3 @ 4")

    def test_evaluate_invalid_syntax(self, evaluator):
        """Test invalid syntax"""
        # "2 + + 3" might be parsed differently, test with clearly invalid syntax
        with pytest.raises(ValueError):
            evaluator.evaluate("2 +")

    def test_evaluate_missing_closing_parenthesis(self, evaluator):
        """Test missing closing parenthesis"""
        with pytest.raises(ValueError, match="Invalid expression"):
            evaluator.evaluate("(2 + 3")

    def test_evaluate_unknown_function(self, evaluator):
        """Test unknown function"""
        with pytest.raises(ValueError, match="Unknown function"):
            evaluator.evaluate("sqrt(16)")

    def test_evaluate_complex_function_call(self, evaluator):
        """Test complex function call (not allowed)"""
        with pytest.raises(ValueError, match="Only simple function calls allowed"):
            evaluator.evaluate("abs.abs(5)")

    def test_evaluate_empty_expression(self, evaluator):
        """Test empty expression"""
        with pytest.raises(ValueError):
            evaluator.evaluate("")

    def test_evaluate_division_by_zero(self, evaluator):
        """Test division by zero"""
        with pytest.raises(ZeroDivisionError):
            evaluator.evaluate("10 / 0")

    def test_evaluate_case_insensitive_function(self, evaluator):
        """Test case insensitive function names"""
        result = evaluator.evaluate("ABS(-10)")
        assert result == 10.0

    def test_evaluate_multiple_functions(self, evaluator):
        """Test multiple functions in expression"""
        result = evaluator.evaluate("abs(-5) + round(3.7)")
        # abs(-5) = 5, round(3.7) = 4, so 5 + 4 = 9
        assert result == 9.0

    def test_evaluate_decimal_precision(self, evaluator):
        """Test decimal precision"""
        result = evaluator.evaluate("0.1 + 0.2")
        # Floating point precision
        assert abs(result - 0.3) < 0.0001

