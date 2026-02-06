"""
Pydantic model helpers.

This module standardizes JSON field casing for API contracts.
We keep Python fields in snake_case but expose camelCase in JSON.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    """Convert snake_case to lowerCamelCase."""
    parts = value.split("_")
    if not parts:
        return value
    first, *rest = parts
    return first + "".join(word.capitalize() for word in rest if word)


class CamelModel(BaseModel):
    """
    BaseModel that exposes camelCase aliases in JSON while keeping snake_case in Python.

    - Accepts both snake_case and camelCase in requests.
    - Emits camelCase in responses (FastAPI encodes with by_alias=True).
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )
