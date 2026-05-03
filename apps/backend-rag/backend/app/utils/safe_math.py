"""
Safe mathematical expression evaluation for CalculatorTool.

Restricts evaluation to numbers and basic arithmetic operators only.
Prevents code injection and unsafe operations.
"""

import ast
import operator
from typing import Any

# Allowed binary operators
_BINOP_MAP = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Allowed unary operators
_UNARYOP_MAP = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class SafeMathError(Exception):
    """Raised when expression is invalid or contains disallowed operations."""

    pass


def _eval_node(node: ast.AST) -> Any:
    """Recursively evaluate an AST node (numbers and arithmetic only)."""
    if isinstance(node, ast.Constant):
        val = node.value
        if isinstance(val, (int, float)):
            return val
        raise SafeMathError(f"Invalid constant type: {type(val).__name__}")

    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _UNARYOP_MAP:
            raise SafeMathError(f"Unary operator not allowed: {type(node.op).__name__}")
        operand = _eval_node(node.operand)
        return _UNARYOP_MAP[type(node.op)](operand)

    if isinstance(node, ast.BinOp):
        if type(node.op) not in _BINOP_MAP:
            raise SafeMathError(f"Binary operator not allowed: {type(node.op).__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op = _BINOP_MAP[type(node.op)]
        try:
            return op(left, right)
        except ZeroDivisionError as e:
            raise SafeMathError(f"Division by zero: {e}") from e

    raise SafeMathError(f"Expression node not allowed: {type(node).__name__}")


def safe_evaluate(expression: str) -> int | float:
    """
    Safely evaluate a mathematical expression.

    Allowed: numbers, +, -, *, /, //, %, **, parentheses.
    Disallowed: function calls, imports, attributes, subscripts, etc.

    Args:
        expression: String containing a math expression (e.g. "10 + 20 * 2")

    Returns:
        The computed result (int or float)

    Raises:
        SafeMathError: If expression is invalid or contains disallowed operations
    """
    if not expression or not isinstance(expression, str):
        raise SafeMathError("Expression must be a non-empty string")

    expression = expression.strip()
    if not expression:
        raise SafeMathError("Expression cannot be empty")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise SafeMathError(f"Invalid syntax: {e}") from e

    return _eval_node(tree.body)
