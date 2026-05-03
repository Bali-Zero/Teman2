"""
Common type hints and type aliases for the application.

Provides consistent typing across the codebase.
"""

from typing import Any, TypeVar

# Generic type variables
T = TypeVar("T")
R = TypeVar("R")

# Common type aliases
JsonDict = dict[str, Any]
JsonList = list[dict[str, Any]]
Headers = dict[str, str]
QueryParams = dict[str, str | int | float | bool | None]

# Database types
RowId = int | str
DatabaseRow = dict[str, Any]
DatabaseResult = list[DatabaseRow]

# Service types
ServiceResponse = dict[str, Any]
ApiResponse = dict[str, Any]
ErrorResponse = dict[str, str | int | dict[str, Any]]

# LLM types
TokenCount = int
ModelName = str
Prompt = str
Completion = str
Embedding = list[float]

# Cache types
CacheKey = str
CacheValue = Any
TTL = int

# Pagination types
PageNumber = int
PageSize = int
TotalCount = int
PaginatedResult = dict[str, Any]
