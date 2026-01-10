"""
Standardized logging utilities for routers.

Provides consistent logging patterns across all API endpoints
with structured context support for observability.
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, TypeVar

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
    correlation_id: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Log an endpoint call with consistent format.

    Args:
        logger: Logger instance
        endpoint: Endpoint path
        method: HTTP method
        user_email: Optional user email
        correlation_id: Optional correlation ID
        **kwargs: Additional context to log
    """
    context: dict[str, Any] = {
        "endpoint": endpoint,
        "method": method,
    }
    if user_email:
        context["user"] = user_email
    if kwargs:
        context.update(kwargs)

    extra: dict[str, Any] = {"context": context}
    if correlation_id:
        extra["correlation_id"] = correlation_id
    if user_email:
        extra["user_email"] = user_email

    logger.info(f"{method} {endpoint}", extra=extra)


def log_success(
    logger: logging.Logger,
    message: str,
    duration_ms: float | None = None,
    **kwargs: Any,
) -> None:
    """
    Log a successful operation.

    Args:
        logger: Logger instance
        message: Success message
        duration_ms: Optional duration in milliseconds
        **kwargs: Additional context
    """
    extra: dict[str, Any] = {}
    if kwargs:
        extra["context"] = kwargs
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms

    logger.info(message, extra=extra if extra else None)


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
    context: dict[str, Any] = {}
    if error:
        context["error"] = str(error)
        context["error_type"] = type(error).__name__
    if kwargs:
        context.update(kwargs)

    logger.error(
        message,
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
    logger.warning(message, extra={"context": kwargs} if kwargs else None)


def log_database_operation(
    logger: logging.Logger,
    operation: str,
    table: str,
    record_id: int | str | None = None,
    duration_ms: float | None = None,
    **kwargs: Any,
) -> None:
    """
    Log a database operation.

    Args:
        logger: Logger instance
        operation: Operation type (CREATE, UPDATE, DELETE, SELECT)
        table: Table name
        record_id: Optional record ID
        duration_ms: Optional duration in milliseconds
        **kwargs: Additional context
    """
    context: dict[str, Any] = {"operation": operation, "table": table}
    if record_id:
        context["record_id"] = record_id
    if kwargs:
        context.update(kwargs)

    extra: dict[str, Any] = {"context": context}
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms

    logger.debug(f"{operation} {table}", extra=extra)


@contextmanager
def log_operation(
    logger: logging.Logger,
    operation_name: str,
    **initial_context: Any,
) -> Generator[dict[str, Any], None, None]:
    """
    Context manager for logging operations with timing.

    Usage:
        with log_operation(logger, "fetch_user", user_id=123) as ctx:
            user = fetch_user(123)
            ctx["user_name"] = user.name  # Add more context

    Args:
        logger: Logger instance
        operation_name: Name of the operation
        **initial_context: Initial context to log

    Yields:
        Mutable context dict that can be updated during the operation
    """
    context = dict(initial_context)
    start_time = time.perf_counter()

    try:
        yield context
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_success(logger, f"{operation_name} completed", duration_ms=duration_ms, **context)
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        context["duration_ms"] = duration_ms
        log_error(logger, f"{operation_name} failed", error=e, **context)
        raise


T = TypeVar("T", bound=Callable[..., Any])


def log_function_call(logger: logging.Logger) -> Callable[[T], T]:
    """
    Decorator to log function calls with timing.

    Usage:
        @log_function_call(logger)
        async def my_function(arg1, arg2):
            ...

    Args:
        logger: Logger instance

    Returns:
        Decorator function
    """

    def decorator(func: T) -> T:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            func_name = func.__name__
            logger.debug(f"Calling {func_name}", extra={"context": {"args_count": len(args)}})

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(
                    f"{func_name} completed",
                    extra={"duration_ms": duration_ms, "context": {"success": True}},
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"{func_name} failed",
                    exc_info=True,
                    extra={
                        "duration_ms": duration_ms,
                        "context": {"error": str(e), "error_type": type(e).__name__},
                    },
                )
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            func_name = func.__name__
            logger.debug(f"Calling {func_name}", extra={"context": {"args_count": len(args)}})

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(
                    f"{func_name} completed",
                    extra={"duration_ms": duration_ms, "context": {"success": True}},
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"{func_name} failed",
                    exc_info=True,
                    extra={
                        "duration_ms": duration_ms,
                        "context": {"error": str(e), "error_type": type(e).__name__},
                    },
                )
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator
