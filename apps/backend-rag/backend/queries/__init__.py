"""
Shared query helpers for the Nuzantara backend.

Eliminates duplicated SQL across routers and services.
Each function takes an asyncpg connection and returns typed results.

Created: 2026-04-03 (system audit)
"""

from .clients import (
    get_client_assigned_to,
    get_client_by_id,
    get_client_email,
    verify_client_access,
)
from .practices import (
    get_practice_by_id,
    get_practices_by_client,
    get_practices_with_client,
)

__all__ = [
    "get_client_assigned_to",
    "get_client_by_id",
    "get_client_email",
    "verify_client_access",
    "get_practice_by_id",
    "get_practices_by_client",
    "get_practices_with_client",
]
