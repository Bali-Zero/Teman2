"""
Base service class with standardized error handling and logging.

Provides a foundation for all services with:
- Structured logging
- Error classification
- Metrics collection
- Retry logic
"""

import time
from abc import ABC
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, cast

from backend.core.logger import get_logger, LogAction, log_context
from backend.core.metrics import MetricsCollector

T = TypeVar("T")


class ServiceError(Exception):
    """Base exception for service errors."""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.retryable = retryable


class ValidationError(ServiceError):
    """Validation error - client sent invalid data."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details,
            retryable=False,
        )


class NotFoundError(ServiceError):
    """Resource not found error."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} with id '{resource_id}' not found",
            error_code="NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id},
            retryable=False,
        )


class ConflictError(ServiceError):
    """Resource conflict error."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=409,
            details=details,
            retryable=False,
        )


class ExternalServiceError(ServiceError):
    """External service call failed."""

    def __init__(
        self, message: str, service_name: str, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details={"service": service_name, **(details or {})},
            retryable=True,
        )


class RateLimitError(ServiceError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__(
            message="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details={"retry_after": retry_after},
            retryable=True,
        )


class ErrorCategory(str, Enum):
    """Error categories for monitoring."""

    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    EXTERNAL = "external"
    DATABASE = "database"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


def classify_error(error: Exception) -> ErrorCategory:
    """Classify an error into a category."""
    if isinstance(error, ValidationError):
        return ErrorCategory.VALIDATION
    elif isinstance(error, NotFoundError):
        return ErrorCategory.NOT_FOUND
    elif isinstance(error, ExternalServiceError) or isinstance(error, RateLimitError):
        return ErrorCategory.EXTERNAL
    elif "database" in str(error).lower() or "connection" in str(error).lower():
        return ErrorCategory.DATABASE
    elif "timeout" in str(error).lower():
        return ErrorCategory.TIMEOUT
    else:
        return ErrorCategory.UNKNOWN


def service_method(operation_name: str):
    """Decorator for service methods with logging and metrics."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(self: "BaseService", *args, **kwargs):
            start_time = time.time()
            logger = self._logger

            with log_context(component=self._component_name):
                logger.info(
                    f"{operation_name} started",
                    action=LogAction.START,
                    metadata={
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

                try:
                    result = await func(self, *args, **kwargs)

                    duration = time.time() - start_time
                    self._metrics.timing(f"{operation_name}.duration", duration)
                    self._metrics.increment(f"{operation_name}.success")

                    logger.info(
                        f"{operation_name} completed",
                        action=LogAction.END,
                        metadata={"duration_ms": round(duration * 1000, 2)},
                    )

                    return result

                except ServiceError as e:
                    duration = time.time() - start_time
                    self._metrics.timing(f"{operation_name}.duration", duration)
                    self._metrics.increment(
                        f"{operation_name}.error", tags={"error_code": e.error_code}
                    )

                    logger.error(
                        f"{operation_name} failed",
                        action=LogAction.ERROR,
                        metadata={
                            "error_code": e.error_code,
                            "status_code": e.status_code,
                            "duration_ms": round(duration * 1000, 2),
                            "retryable": e.retryable,
                        },
                    )
                    raise

                except Exception as e:
                    duration = time.time() - start_time
                    error_category = classify_error(e)
                    self._metrics.timing(f"{operation_name}.duration", duration)
                    self._metrics.increment(
                        f"{operation_name}.error",
                        tags={"category": error_category.value},
                    )

                    logger.exception(
                        f"{operation_name} failed with unexpected error",
                        action=LogAction.ERROR,
                        metadata={
                            "error_type": type(e).__name__,
                            "category": error_category.value,
                            "duration_ms": round(duration * 1000, 2),
                        },
                    )

                    # Convert to ServiceError
                    raise ServiceError(
                        message=str(e),
                        error_code="INTERNAL_ERROR",
                        status_code=500,
                        details={"original_error": type(e).__name__},
                        retryable=True,
                    ) from e

        @wraps(func)
        def sync_wrapper(self: "BaseService", *args, **kwargs):
            start_time = time.time()
            logger = self._logger

            with log_context(component=self._component_name):
                logger.info(
                    f"{operation_name} started",
                    action=LogAction.START,
                    metadata={
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

                try:
                    result = func(self, *args, **kwargs)

                    duration = time.time() - start_time
                    self._metrics.timing(f"{operation_name}.duration", duration)
                    self._metrics.increment(f"{operation_name}.success")

                    logger.info(
                        f"{operation_name} completed",
                        action=LogAction.END,
                        metadata={"duration_ms": round(duration * 1000, 2)},
                    )

                    return result

                except ServiceError as e:
                    duration = time.time() - start_time
                    self._metrics.timing(f"{operation_name}.duration", duration)
                    self._metrics.increment(
                        f"{operation_name}.error", tags={"error_code": e.error_code}
                    )

                    logger.error(
                        f"{operation_name} failed",
                        action=LogAction.ERROR,
                        metadata={
                            "error_code": e.error_code,
                            "status_code": e.status_code,
                            "duration_ms": round(duration * 1000, 2),
                        },
                    )
                    raise

                except Exception as e:
                    duration = time.time() - start_time
                    error_category = classify_error(e)
                    self._metrics.timing(f"{operation_name}.duration", duration)
                    self._metrics.increment(
                        f"{operation_name}.error",
                        tags={"category": error_category.value},
                    )

                    logger.exception(
                        f"{operation_name} failed with unexpected error",
                        action=LogAction.ERROR,
                        metadata={
                            "error_type": type(e).__name__,
                            "category": error_category.value,
                            "duration_ms": round(duration * 1000, 2),
                        },
                    )

                    raise ServiceError(
                        message=str(e),
                        error_code="INTERNAL_ERROR",
                        status_code=500,
                        details={"original_error": type(e).__name__},
                        retryable=True,
                    ) from e

        # Return appropriate wrapper based on whether func is async
        import inspect

        if inspect.iscoroutinefunction(func):
            return cast(Callable, async_wrapper)
        return cast(Callable, sync_wrapper)

    return decorator


class BaseService(ABC, Generic[T]):
    """Base class for all services."""

    def __init__(self, service_name: str):
        self._service_name = service_name
        self._component_name = service_name
        self._logger = get_logger(f"services.{service_name}", component=service_name)
        self._metrics = MetricsCollector(prefix=f"service.{service_name}")
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the service. Override in subclasses."""
        if self._initialized:
            return

        self._logger.info(
            f"Initializing {self._service_name} service", action=LogAction.START
        )

        try:
            await self._do_initialize()
            self._initialized = True
            self._logger.info(
                f"{self._service_name} service initialized", action=LogAction.END
            )
        except Exception as e:
            self._logger.error(
                f"Failed to initialize {self._service_name} service",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
                exc_info=True,
            )
            raise

    async def _do_initialize(self) -> None:
        """Override this method for custom initialization."""
        pass

    async def shutdown(self) -> None:
        """Shutdown the service. Override in subclasses."""
        if not self._initialized:
            return

        self._logger.info(
            f"Shutting down {self._service_name} service", action=LogAction.START
        )

        try:
            await self._do_shutdown()
            self._initialized = False
            self._logger.info(
                f"{self._service_name} service shut down", action=LogAction.END
            )
        except Exception as e:
            self._logger.error(
                f"Error shutting down {self._service_name} service",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
                exc_info=True,
            )
            raise

    async def _do_shutdown(self) -> None:
        """Override this method for custom shutdown."""
        pass

    def _validate_input(self, data: Dict[str, Any], required_fields: list) -> None:
        """Validate that required fields are present."""
        missing = [f for f in required_fields if f not in data or data[f] is None]
        if missing:
            raise ValidationError(
                f"Missing required fields: {', '.join(missing)}",
                details={"missing_fields": missing},
            )

    def health_check(self) -> Dict[str, Any]:
        """Return service health status."""
        return {
            "service": self._service_name,
            "status": "healthy" if self._initialized else "not_initialized",
            "initialized": self._initialized,
        }


__all__ = [
    "BaseService",
    "ServiceError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "ExternalServiceError",
    "RateLimitError",
    "ErrorCategory",
    "classify_error",
    "service_method",
]
