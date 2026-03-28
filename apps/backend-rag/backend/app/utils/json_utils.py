"""
JSON Utilities for asyncpg JSONB compatibility.

asyncpg cannot automatically serialize Python objects like Decimal, datetime,
or UUID to JSONB columns. This module provides utilities to handle serialization
properly.

USAGE:
    from backend.app.utils.json_utils import to_jsonb, json_serializer

    # Method 1: Use to_jsonb helper
    await conn.execute(
        "INSERT INTO t (data) VALUES ($1::jsonb)",
        to_jsonb(my_dict)
    )

    # Method 2: Use json_serializer with json.dumps
    import json
    await conn.execute(
        "INSERT INTO t (data) VALUES ($1::jsonb)",
        json.dumps(my_dict, default=json_serializer)
    )

See: CLAUDE.md "Asyncpg + JSONB Development Guidelines" for full documentation.
"""

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID


def json_serializer(obj: Any) -> str:
    """
    Custom JSON serializer for asyncpg JSONB compatibility.

    Handles common Python types that are not JSON-serializable by default:
    - datetime/date → ISO format string
    - Decimal → string (preserves precision)
    - UUID → string
    - Objects with __dict__ → dict representation

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable representation of the object

    Raises:
        TypeError: If object type is not supported

    Example:
        >>> import json
        >>> from decimal import Decimal
        >>> from datetime import datetime
        >>> data = {"amount": Decimal("100.50"), "created": datetime.now(tz=timezone.utc)}
        >>> json.dumps(data, default=json_serializer)
        '{"amount": "100.50", "created": "2026-01-14T15:30:00"}'
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def to_jsonb(data: dict | list | None) -> str | None:
    """
    Serialize Python dict/list to JSONB-compatible string.

    Convenience wrapper around json.dumps with json_serializer.
    Use this when inserting/updating JSONB columns in PostgreSQL via asyncpg.

    Args:
        data: Dict or list to serialize, or None

    Returns:
        JSON string ready for asyncpg JSONB parameter, or None if input is None

    Example:
        >>> await conn.execute(
        ...     "INSERT INTO activity_log (changes) VALUES ($1::jsonb)",
        ...     to_jsonb({"status": "completed", "amount": Decimal("500")})
        ... )
    """
    if data is None:
        return None
    return json.dumps(data, default=json_serializer)


def from_jsonb(data: str | dict | None) -> dict | list | None:
    """
    Parse JSONB data from PostgreSQL.

    asyncpg typically returns JSONB as dict directly, but this function
    handles edge cases where it might come as a string.

    Args:
        data: JSONB data from PostgreSQL (dict, list, string, or None)

    Returns:
        Parsed Python dict/list, or None if input is None
    """
    if data is None:
        return None
    if isinstance(data, (dict, list)):
        return data
    if isinstance(data, str):
        return json.loads(data)
    return data
