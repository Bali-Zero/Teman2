"""
Safe mathematical expression evaluator.

Provides sandboxed evaluation of mathematical expressions
without arbitrary code execution risk.
"""

import ast
import math
import operator
from typing import Union

# Allowed operators
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Allowed math functions
_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
}


class SafeMathError(Exception):
    """Raised when safe math evaluation fails."""

    pass


def safe_evaluate(expression: str) -> Union[int, float]:
    """
    Safely evaluate a mathematical expression.

    Only supports basic arithmetic operations (+, -, *, /, //, %, **)
    and a limited set of math functions.

    Args:
        expression: Mathematical expression string

    Returns:
        Numeric result

    Raises:
        SafeMathError: If expression is invalid or uses disallowed operations
    """
    if not expression or not isinstance(expression, str):
        raise SafeMathError("Expression must be a non-empty string")

    expression = expression.strip()
    if len(expression) > 500:
        raise SafeMathError("Expression too long (max 500 characters)")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise SafeMathError(f"Invalid expression syntax: {e}") from e

    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> Union[int, float]:
    """Recursively evaluate an AST node."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise SafeMathError(f"Unsupported constant type: {type(node.value).__name__}")

    if isinstance(node, ast.UnaryOp):
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise SafeMathError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_eval_node(node.operand))

    if isinstance(node, ast.BinOp):
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise SafeMathError(f"Unsupported operator: {type(node.op).__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise SafeMathError("Division by zero")
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise SafeMathError("Exponent too large (max 1000)")
        return op_func(left, right)

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
            func = _FUNCTIONS[node.func.id]
            if callable(func):
                args = [_eval_node(arg) for arg in node.args]
                return func(*args)
            return func  # Constants like pi, e
        raise SafeMathError(f"Unsupported function: {getattr(node.func, 'id', '?')}")

    if isinstance(node, ast.Name):
        if node.id in _FUNCTIONS:
            val = _FUNCTIONS[node.id]
            if not callable(val):
                return val  # Constants like pi, e
        raise SafeMathError(f"Unsupported name: {node.id}")

    raise SafeMathError(f"Unsupported expression element: {type(node).__name__}")
