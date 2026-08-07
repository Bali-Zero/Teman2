"""Privacy boundary shared by middleware for public Visa Oracle evaluation."""

from __future__ import annotations

import uuid
from typing import Any

VISA_ORACLE_EVALUATE_PATH = "/api/visa-oracle/evaluate"
_PRIVATE_REQUEST_ID_STATE_KEY = "visa_oracle_private_request_id"


def is_private_visa_evaluation(method: str, path: str) -> bool:
    """Return whether a request is the exact anonymous evaluation endpoint."""

    return method.upper() == "POST" and path == VISA_ORACLE_EVALUATE_PATH


def get_or_create_private_request_id(request: Any) -> str:
    """Return a server-generated opaque ID, never an identifier from the caller."""

    existing = getattr(request.state, _PRIVATE_REQUEST_ID_STATE_KEY, None)
    if isinstance(existing, str) and existing:
        return existing
    request_id = str(uuid.uuid4())
    setattr(request.state, _PRIVATE_REQUEST_ID_STATE_KEY, request_id)
    return request_id
