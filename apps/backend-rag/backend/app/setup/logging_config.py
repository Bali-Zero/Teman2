"""
Structured Logging Configuration

Provides JSON-formatted logging for production observability and
human-readable logging for development.

Features:
- JSON output in production (suitable for log aggregation systems)
- Colored, readable output in development
- Automatic correlation ID propagation
- Request context tracking
- Performance timing in logs
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs logs in JSON format for easy parsing by log aggregation systems
    like ELK, Datadog, Splunk, or Grafana Loki.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json

        # Base log structure
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "nuzantara-backend",
            "environment": settings.environment,
        }

        # Add source location
        log_entry["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add correlation ID if available (from request context)
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        # Add user context if available
        if hasattr(record, "user_email"):
            log_entry["user"] = record.user_email

        # Add custom context if passed via extra
        if hasattr(record, "context") and record.context:
            log_entry["context"] = record.context

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add timing info if present
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class DevelopmentFormatter(logging.Formatter):
    """
    Human-readable formatter for development.

    Uses colors and indentation for easy reading in terminal.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)

        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Build base message
        message = f"{color}{timestamp} [{record.levelname:8}]{self.RESET} {record.name}: {record.getMessage()}"

        # Add correlation ID if present
        if hasattr(record, "correlation_id"):
            message += f" {color}[{record.correlation_id[:8]}]{self.RESET}"

        # Add context if present
        if hasattr(record, "context") and record.context:
            import json
            context_str = json.dumps(record.context, default=str)
            if len(context_str) > 100:
                context_str = context_str[:100] + "..."
            message += f"\n    {color}context:{self.RESET} {context_str}"

        # Add exception info
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"

        return message


class ContextFilter(logging.Filter):
    """
    Filter that adds context information to log records.

    Automatically injects correlation_id and user context from
    the current request context if available.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Try to get correlation ID from contextvars
        try:
            from contextvars import ContextVar
            correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
            correlation_id = correlation_id_var.get()
            if correlation_id:
                record.correlation_id = correlation_id
        except (ImportError, LookupError):
            pass

        return True


def configure_logging() -> None:
    """
    Configure application-wide logging.

    In production: JSON-formatted logs to stdout + rotating file
    In development: Colored, readable logs to stdout
    """
    is_production = settings.environment == "production"
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if is_production:
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(DevelopmentFormatter())

    console_handler.addFilter(ContextFilter())
    root_logger.addHandler(console_handler)

    # File handler (rotating) - only in production or if log_file is set
    if is_production or settings.log_file:
        log_file = settings.log_file or "./data/zantara_rag.log"
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(StructuredFormatter())  # Always JSON in files
        file_handler.addFilter(ContextFilter())
        root_logger.addHandler(file_handler)

    # Configure third-party loggers to be less verbose
    for logger_name in ["httpx", "httpcore", "urllib3", "asyncio"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Suppress noisy logs from specific libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # Log startup message
    logger = logging.getLogger("zantara.backend")
    logger.info(
        "Logging configured",
        extra={
            "context": {
                "level": settings.log_level,
                "environment": settings.environment,
                "format": "json" if is_production else "development",
            }
        },
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with structured logging support.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    *,
    correlation_id: str | None = None,
    user_email: str | None = None,
    duration_ms: float | None = None,
    **context: Any,
) -> None:
    """
    Log a message with structured context.

    Args:
        logger: Logger instance
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        correlation_id: Optional request correlation ID
        user_email: Optional user email
        duration_ms: Optional operation duration in milliseconds
        **context: Additional context to include
    """
    extra: dict[str, Any] = {}

    if correlation_id:
        extra["correlation_id"] = correlation_id
    if user_email:
        extra["user_email"] = user_email
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    if context:
        extra["context"] = context

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, message, extra=extra if extra else None)
