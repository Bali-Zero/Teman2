"""
Resilience utilities for the LAM agent layer.
Provides retry-with-backoff and irreversibility guard for tool calls.
"""

import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger("nuzantara-mcp.resilience")

# Endpoints that cause irreversible side-effects — require explicit confirm=True
IRREVERSIBLE_ENDPOINTS = {
    "/api/crm/clients",           # creates a new client record
    "/api/whatsapp/send",         # sends a WhatsApp message
    "/api/email/send",            # sends an email
    "/api/telegram/send",         # sends a Telegram message
    "/api/crm/interactions",      # logs a CRM interaction (audit trail)
    "/api/practices",             # creates a new practice
    "/api/invoicing/generate",    # generates an invoice
}


def is_irreversible(endpoint: str) -> bool:
    """Return True if the endpoint produces irreversible side-effects."""
    for irr in IRREVERSIBLE_ENDPOINTS:
        if endpoint.startswith(irr):
            return True
    return False


async def call_with_retry(
    fn: Callable,
    endpoint: str,
    method: str = "GET",
    json: Any = None,
    params: Any = None,
    timeout: int = 30,
    max_retries: int = 3,
    base_delay: float = 1.0,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Resilient wrapper around _call_safe with:
    - Exponential backoff retry (3 attempts, 1s/2s/4s)
    - Irreversibility guard (blocks dangerous POST without confirm=True)
    - Structured error envelope on final failure

    Args:
        fn: The _call_safe function from server.py
        endpoint: Backend API endpoint path
        method: HTTP method
        json: Request body
        params: Query params
        timeout: Request timeout seconds
        max_retries: Max attempts before giving up
        base_delay: Initial retry delay seconds (doubles each retry)
        confirm: Must be True for endpoints in IRREVERSIBLE_ENDPOINTS

    Returns:
        dict: API response or {"error": True, "detail": "...", "endpoint": "..."}
    """
    if method.upper() in ("POST", "PUT", "PATCH", "DELETE") and is_irreversible(endpoint):
        if not confirm:
            logger.warning(f"Blocked irreversible call to {endpoint} — confirm=True required")
            return {
                "error": True,
                "blocked": True,
                "detail": (
                    f"This action ({method} {endpoint}) is irreversible. "
                    "Call again with confirm=True to proceed."
                ),
            }

    last_error: Any = None
    for attempt in range(1, max_retries + 1):
        try:
            result = await fn(endpoint, method=method, json=json, params=params, timeout=timeout)
            if isinstance(result, dict) and result.get("error"):
                # Transient HTTP errors (5xx) are retried; 4xx are not
                status = result.get("status", 0)
                if status and 400 <= status < 500:
                    logger.warning(f"Non-retryable {status} from {endpoint}: {result.get('detail')}")
                    return result
                raise RuntimeError(result.get("detail", "backend error"))
            return result
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"Retry {attempt}/{max_retries} for {endpoint} in {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries} retries failed for {endpoint}: {e}")

    return {
        "error": True,
        "detail": f"Failed after {max_retries} attempts: {last_error}",
        "endpoint": endpoint,
    }
