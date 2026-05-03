"""
Structured logging system for Bali Intel Scraper.

Provides JSON-structured logging with contextual information,
automatically capturing request IDs, component names, and trace info.
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from config.settings import settings


# Context variables for request tracking
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
component_ctx: ContextVar[str] = ContextVar("component", default="unknown")
user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


class LogAction(str, Enum):
    """Standardized log actions."""

    START = "start"
    END = "end"
    ERROR = "error"
    RETRY = "retry"
    SKIP = "skip"
    VALIDATE = "validate"
    TRANSFORM = "transform"
    FETCH = "fetch"
    PARSE = "parse"
    ANALYZE = "analyze"
    SAVE = "save"
    DELETE = "delete"
    UPDATE = "update"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    AUTHENTICATE = "authenticate"
    AUTHORIZE = "authorize"


class StructuredLogFormatter(logging.Formatter):
    """Custom formatter for structured JSON logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "component": getattr(record, "component", component_ctx.get()),
            "action": getattr(record, "action", None),
            "request_id": getattr(record, "request_id", request_id_ctx.get())
            or str(uuid.uuid4())[:8],
        }

        # Add user context if available
        user_id = getattr(record, "user_id", user_id_ctx.get())
        if user_id:
            log_data["user_id"] = user_id

        # Add structured metadata
        metadata = getattr(record, "metadata", {})
        if metadata:
            log_data["metadata"] = metadata

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add source location in debug mode
        if settings.debug:
            log_data["source"] = {
                "filename": record.filename,
                "lineno": record.lineno,
                "funcName": record.funcName,
            }

        return json.dumps(log_data, default=str)


class StructuredLogger:
    """Structured logger with contextual information."""

    def __init__(self, name: str, component: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.component = component or name

        # Ensure handlers are set up
        if not self.logger.handlers:
            self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup logging handlers based on configuration."""
        level = getattr(logging, settings.monitoring.log_level.value)
        self.logger.setLevel(level)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        if settings.monitoring.log_format == "json":
            formatter = StructuredLogFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler if configured
        if settings.monitoring.log_file:
            file_handler = logging.FileHandler(settings.monitoring.log_file)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _log(
        self,
        level: int,
        message: str,
        action: Optional[LogAction] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Internal log method with structured data."""
        extra = {
            "component": kwargs.get("component", self.component),
            "action": action.value if action else kwargs.get("action"),
            "metadata": metadata or {},
            "request_id": kwargs.get("request_id", request_id_ctx.get()),
            "user_id": kwargs.get("user_id", user_id_ctx.get()),
        }
        self.logger.log(level, message, extra=extra)

    def debug(
        self,
        message: str,
        action: Optional[LogAction] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, action, metadata, **kwargs)

    def info(
        self,
        message: str,
        action: Optional[LogAction] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log info message."""
        self._log(logging.INFO, message, action, metadata, **kwargs)

    def warning(
        self,
        message: str,
        action: Optional[LogAction] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, action, metadata, **kwargs)

    def error(
        self,
        message: str,
        action: Optional[LogAction] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
        **kwargs,
    ) -> None:
        """Log error message."""
        extra = {
            "component": kwargs.get("component", self.component),
            "action": action.value if action else kwargs.get("action"),
            "metadata": metadata or {},
            "request_id": kwargs.get("request_id", request_id_ctx.get()),
            "user_id": kwargs.get("user_id", user_id_ctx.get()),
        }
        self.logger.error(message, extra=extra, exc_info=exc_info)

    def critical(
        self,
        message: str,
        action: Optional[LogAction] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, action, metadata, **kwargs)

    def exception(
        self,
        message: str,
        action: Optional[LogAction] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log exception with traceback."""
        self.error(message, action, metadata, exc_info=True, **kwargs)


# Module-level logger factory
_loggers: Dict[str, StructuredLogger] = {}


def get_logger(name: str, component: Optional[str] = None) -> StructuredLogger:
    """Get or create a structured logger."""
    key = f"{name}:{component}"
    if key not in _loggers:
        _loggers[key] = StructuredLogger(name, component)
    return _loggers[key]


def set_request_id(request_id: str) -> None:
    """Set the current request ID in context."""
    request_id_ctx.set(request_id)


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_ctx.get() or str(uuid.uuid4())[:8]


def set_component(component: str) -> None:
    """Set the current component in context."""
    component_ctx.set(component)


def set_user_id(user_id: Optional[str]) -> None:
    """Set the current user ID in context."""
    user_id_ctx.set(user_id)


class log_context:
    """Context manager for temporary log context."""

    def __init__(
        self,
        component: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.component = component
        self.request_id = request_id
        self.user_id = user_id
        self.tokens = {}

    def __enter__(self) -> "log_context":
        if self.component:
            self.tokens["component"] = component_ctx.set(self.component)
        if self.request_id:
            self.tokens["request_id"] = request_id_ctx.set(self.request_id)
        if self.user_id:
            self.tokens["user_id"] = user_id_ctx.set(self.user_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        for key, token in self.tokens.items():
            if key == "component":
                component_ctx.reset(token)
            elif key == "request_id":
                request_id_ctx.reset(token)
            elif key == "user_id":
                user_id_ctx.reset(token)


# Convenience exports
__all__ = [
    "StructuredLogger",
    "LogAction",
    "get_logger",
    "set_request_id",
    "get_request_id",
    "set_component",
    "set_user_id",
    "log_context",
]
