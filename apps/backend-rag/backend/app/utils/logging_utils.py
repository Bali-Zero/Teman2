"""
Standardized logging utilities for routers.

Provides consistent logging patterns across all API endpoints.
"""

import logging
from typing import Any

# Standard log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name (usually __name__)

    Returns:
        Logger instance configured for the module
    """
    return logging.getLogger(name)


def log_endpoint_call(
    logger: logging.Logger,
    endpoint: str,
    method: str,
    user_email: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Log an endpoint call with consistent format.

    Args:
        logger: Logger instance
        endpoint: Endpoint path
        method: HTTP method
        user_email: Optional user email
        **kwargs: Additional context to log
    """
    context = {
        "endpoint": endpoint,
        "method": method,
    }
    if user_email:
        context["user"] = user_email
    if kwargs:
        context.update(kwargs)

    logger.info(f"📞 {method} {endpoint}", extra={"context": context})


def log_success(
    logger: logging.Logger,
    message: str,
    **kwargs: Any,
) -> None:
    """
    Log a successful operation.

    Args:
        logger: Logger instance
        message: Success message
        **kwargs: Additional context
    """
    logger.info(f"✅ {message}", extra={"context": kwargs} if kwargs else None)


def log_error(
    logger: logging.Logger,
    message: str,
    error: Exception | None = None,
    exc_info: bool = True,
    **kwargs: Any,
) -> None:
    """
    Log an error with consistent format.

    Args:
        logger: Logger instance
        message: Error message
        error: Optional exception object
        exc_info: Whether to include exception info
        **kwargs: Additional context
    """
    context = {"error": str(error)} if error else {}
    if kwargs:
        context.update(kwargs)

    logger.error(
        f"❌ {message}",
        exc_info=exc_info if error else False,
        extra={"context": context} if context else None,
    )


def log_warning(
    logger: logging.Logger,
    message: str,
    **kwargs: Any,
) -> None:
    """
    Log a warning.

    Args:
        logger: Logger instance
        message: Warning message
        **kwargs: Additional context
    """
    logger.warning(f"⚠️ {message}", extra={"context": kwargs} if kwargs else None)


def log_database_operation(
    logger: logging.Logger,
    operation: str,
    table: str,
    record_id: int | str | None = None,
    **kwargs: Any,
) -> None:
    """
    Log a database operation.

    Args:
        logger: Logger instance
        operation: Operation type (CREATE, UPDATE, DELETE, SELECT)
        table: Table name
        record_id: Optional record ID
        **kwargs: Additional context
    """
    context = {"operation": operation, "table": table}
    if record_id:
        context["record_id"] = record_id
    if kwargs:
        context.update(kwargs)

    logger.debug(f"🗄️ {operation} {table}", extra={"context": context})










