#!/usr/bin/env python3
"""
BALI INTEL SCRAPER - Centralized Logging Configuration
========================================================

Provides consistent, efficient logging across all pipeline components.

Features:
- Environment-based log levels (DEBUG in dev, INFO in prod)
- JSON structured logging for production
- Log rotation and retention
- Correlation IDs for request tracing
- Integration with MetricsCollector
- Performance-optimized (lazy evaluation)

Usage:
    from logging_config import setup_logging, get_logger, log_context

    # At application startup
    setup_logging(environment="production")

    # In modules
    logger = get_logger("my_module")
    logger.info("Processing started", article_count=10)

    # With context
    with log_context(request_id="abc123", user="admin"):
        logger.info("Operation completed")

Author: BaliZero Team
"""

import os
import sys
import json
import uuid
import functools
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Callable
from contextlib import contextmanager
from contextvars import ContextVar
from loguru import logger

# =============================================================================
# CONTEXT VARIABLES
# =============================================================================

# Request/correlation ID for tracing
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_log_context: ContextVar[Dict[str, Any]] = ContextVar("log_context", default={})


# =============================================================================
# LOG FORMATS
# =============================================================================

# Console format (colored, human-readable)
CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
    "{extra[context]}"
)

# JSON format for production (machine parseable)
def json_formatter(record: dict) -> str:
    """Format log record as JSON line"""
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
    }

    # Add correlation ID if present
    correlation_id = _correlation_id.get()
    if correlation_id:
        log_entry["correlation_id"] = correlation_id

    # Add extra context
    ctx = _log_context.get()
    if ctx:
        log_entry["context"] = ctx

    # Add any extra fields from the log call
    extra = record.get("extra", {})
    for key, value in extra.items():
        if key not in ("context",) and not key.startswith("_"):
            log_entry[key] = value

    # Add exception info if present
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else None,
            "value": str(record["exception"].value) if record["exception"].value else None,
            "traceback": record["exception"].traceback if record["exception"].traceback else None,
        }

    return json.dumps(log_entry) + "\n"


# File format (detailed, no colors)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} | "
    "{message}"
    "{extra[context]}"
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Log levels by environment
ENV_LOG_LEVELS = {
    "development": "DEBUG",
    "testing": "DEBUG",
    "staging": "INFO",
    "production": "INFO",
}

# Default retention settings
DEFAULT_RETENTION = "7 days"
DEFAULT_ROTATION = "100 MB"


def _format_extra_context(record: dict) -> str:
    """Format extra context for display"""
    extra = record.get("extra", {})
    ctx = _log_context.get()

    # Combine extra fields and context
    all_extra = {**ctx}
    for key, value in extra.items():
        if key not in ("context",) and not key.startswith("_"):
            all_extra[key] = value

    if not all_extra:
        return ""

    parts = [f"{k}={v}" for k, v in all_extra.items()]
    return " | " + " ".join(parts)


def setup_logging(
    environment: str = None,
    log_dir: str = "logs",
    app_name: str = "bali_intel",
    json_logs: bool = None,
    level: str = None,
    rotation: str = DEFAULT_ROTATION,
    retention: str = DEFAULT_RETENTION,
) -> None:
    """
    Configure logging for the application.

    Args:
        environment: Environment name (development, staging, production)
        log_dir: Directory for log files
        app_name: Application name prefix for log files
        json_logs: Force JSON format (default: True in production)
        level: Override log level
        rotation: Log rotation setting (e.g., "100 MB", "1 day")
        retention: Log retention setting (e.g., "7 days")
    """
    # Determine environment
    if environment is None:
        environment = os.getenv("ENVIRONMENT", os.getenv("ENV", "development"))

    # Determine log level
    if level is None:
        level = os.getenv("LOG_LEVEL", ENV_LOG_LEVELS.get(environment, "INFO"))

    # Determine JSON format
    if json_logs is None:
        json_logs = environment in ("production", "staging")

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Remove default logger
    logger.remove()

    # Add context formatter
    logger.configure(
        patcher=lambda record: record["extra"].update(
            context=_format_extra_context(record)
        )
    )

    # Console handler (always human-readable)
    logger.add(
        sys.stderr,
        format=CONSOLE_FORMAT,
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=environment == "development",
    )

    # File handler - main log
    main_log_file = log_path / f"{app_name}.log"
    if json_logs:
        logger.add(
            str(main_log_file),
            format=json_formatter,
            level=level,
            rotation=rotation,
            retention=retention,
            compression="gz",
            serialize=False,
        )
    else:
        logger.add(
            str(main_log_file),
            format=FILE_FORMAT,
            level=level,
            rotation=rotation,
            retention=retention,
            compression="gz",
        )

    # Error log (always capture errors)
    error_log_file = log_path / f"{app_name}_errors.log"
    logger.add(
        str(error_log_file),
        format=FILE_FORMAT if not json_logs else json_formatter,
        level="ERROR",
        rotation=rotation,
        retention=retention,
        compression="gz",
        serialize=False,
    )

    logger.info(
        f"Logging configured",
        environment=environment,
        level=level,
        json_logs=json_logs,
        log_dir=str(log_path),
    )


# =============================================================================
# LOGGER FACTORY
# =============================================================================

def get_logger(name: str = None) -> "logger":
    """
    Get a logger instance with optional name binding.

    Args:
        name: Logger name (usually module name)

    Returns:
        Configured logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


# =============================================================================
# CONTEXT MANAGERS
# =============================================================================

@contextmanager
def log_context(**kwargs):
    """
    Context manager to add fields to all log messages within scope.

    Usage:
        with log_context(request_id="abc", user="admin"):
            logger.info("Processing")  # Will include request_id and user
    """
    current = _log_context.get()
    new_context = {**current, **kwargs}
    token = _log_context.set(new_context)
    try:
        yield
    finally:
        _log_context.reset(token)


@contextmanager
def correlation_context(correlation_id: str = None):
    """
    Set correlation ID for request tracing.

    Args:
        correlation_id: Correlation ID (generates UUID if not provided)
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())[:8]

    token = _correlation_id.set(correlation_id)
    try:
        with log_context(correlation_id=correlation_id):
            yield correlation_id
    finally:
        _correlation_id.reset(token)


# =============================================================================
# DECORATORS
# =============================================================================

def log_operation(
    operation_name: str = None,
    log_args: bool = False,
    log_result: bool = False,
):
    """
    Decorator to log function entry/exit with timing.

    Args:
        operation_name: Custom operation name (defaults to function name)
        log_args: Log function arguments
        log_result: Log function result
    """
    def decorator(func: Callable) -> Callable:
        name = operation_name or func.__name__

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = datetime.now(timezone.utc)
            extra = {"operation": name}

            if log_args:
                extra["args"] = str(args)[:100]
                extra["kwargs"] = str(kwargs)[:100]

            logger.debug(f"Starting {name}", **extra)

            try:
                result = func(*args, **kwargs)
                duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

                log_extra = {"duration_ms": f"{duration_ms:.1f}"}
                if log_result and result is not None:
                    log_extra["result"] = str(result)[:100]

                logger.debug(f"Completed {name}", **log_extra)
                return result

            except Exception as e:
                duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                logger.error(
                    f"Failed {name}",
                    duration_ms=f"{duration_ms:.1f}",
                    error=str(e)[:200],
                )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = datetime.now(timezone.utc)
            extra = {"operation": name}

            if log_args:
                extra["args"] = str(args)[:100]
                extra["kwargs"] = str(kwargs)[:100]

            logger.debug(f"Starting {name}", **extra)

            try:
                result = await func(*args, **kwargs)
                duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

                log_extra = {"duration_ms": f"{duration_ms:.1f}"}
                if log_result and result is not None:
                    log_extra["result"] = str(result)[:100]

                logger.debug(f"Completed {name}", **log_extra)
                return result

            except Exception as e:
                duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                logger.error(
                    f"Failed {name}",
                    duration_ms=f"{duration_ms:.1f}",
                    error=str(e)[:200],
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def log_errors(reraise: bool = True):
    """
    Decorator to log exceptions with full context.

    Args:
        reraise: Re-raise the exception after logging (default True)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"Exception in {func.__name__}",
                    function=func.__name__,
                    module=func.__module__,
                )
                if reraise:
                    raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"Exception in {func.__name__}",
                    function=func.__name__,
                    module=func.__module__,
                )
                if reraise:
                    raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# PERFORMANCE LOGGING
# =============================================================================

class PerformanceLogger:
    """
    Track and log performance metrics for operations.

    Usage:
        perf = PerformanceLogger("pipeline")
        perf.start("fetch")
        # ... do work ...
        perf.end("fetch")
        perf.log_summary()
    """

    def __init__(self, name: str):
        self.name = name
        self.timings: Dict[str, list] = {}
        self._starts: Dict[str, datetime] = {}

    def start(self, operation: str):
        """Start timing an operation"""
        self._starts[operation] = datetime.now(timezone.utc)

    def end(self, operation: str) -> float:
        """End timing and return duration in ms"""
        if operation not in self._starts:
            logger.warning(f"Operation {operation} was not started")
            return 0.0

        start = self._starts.pop(operation)
        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        if operation not in self.timings:
            self.timings[operation] = []
        self.timings[operation].append(duration_ms)

        return duration_ms

    @contextmanager
    def track(self, operation: str):
        """Context manager for timing operations"""
        self.start(operation)
        try:
            yield
        finally:
            self.end(operation)

    def get_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for an operation"""
        timings = self.timings.get(operation, [])
        if not timings:
            return {"count": 0, "avg": 0, "min": 0, "max": 0, "total": 0}

        return {
            "count": len(timings),
            "avg": sum(timings) / len(timings),
            "min": min(timings),
            "max": max(timings),
            "total": sum(timings),
        }

    def log_summary(self):
        """Log performance summary"""
        logger.info(f"Performance summary for {self.name}")
        for operation, timings in self.timings.items():
            stats = self.get_stats(operation)
            logger.info(
                f"  {operation}: count={stats['count']}, "
                f"avg={stats['avg']:.1f}ms, "
                f"min={stats['min']:.1f}ms, "
                f"max={stats['max']:.1f}ms"
            )


# =============================================================================
# INITIALIZATION
# =============================================================================

# Auto-setup with default configuration if not already configured
_initialized = False

def ensure_initialized():
    """Ensure logging is initialized with defaults"""
    global _initialized
    if not _initialized:
        setup_logging()
        _initialized = True


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    # Demo logging configuration
    setup_logging(environment="development")

    log = get_logger("demo")

    log.info("Testing logging configuration")
    log.debug("Debug message", extra_field="value")
    log.warning("Warning message")

    with log_context(user="test_user", request_id="123"):
        log.info("Message with context")
        log.error("Error with context")

    with correlation_context() as corr_id:
        log.info(f"Correlated message", correlation_id=corr_id)

    @log_operation("test_operation", log_args=True, log_result=True)
    def sample_function(x, y):
        return x + y

    result = sample_function(1, 2)

    # Performance logging
    perf = PerformanceLogger("demo")

    with perf.track("operation_a"):
        import time
        time.sleep(0.1)

    with perf.track("operation_b"):
        time.sleep(0.05)

    perf.log_summary()

    log.success("Logging demo completed!")
