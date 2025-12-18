"""
Debug Context Manager
Provides context manager for enabling debug mode on-demand for specific requests
"""

import logging
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


class DebugContext:
    """
    Context manager for enabling debug mode for specific operations.
    
    Usage:
        with DebugContext(request_id="abc123"):
            # All operations here will have enhanced logging
            result = some_operation()
    """

    def __init__(
        self,
        request_id: str | None = None,
        enable_verbose_logging: bool = True,
        capture_api_calls: bool = True,
        save_state_snapshot: bool = False,
    ):
        """
        Initialize debug context.

        Args:
            request_id: Optional request ID for correlation
            enable_verbose_logging: Whether to enable verbose logging
            capture_api_calls: Whether to capture external API calls
            save_state_snapshot: Whether to save state snapshot
        """
        self.request_id = request_id
        self.enable_verbose_logging = enable_verbose_logging
        self.capture_api_calls = capture_api_calls
        self.save_state_snapshot = save_state_snapshot
        self.original_log_levels: dict[str, int] = {}
        self.api_calls: list[dict[str, Any]] = []
        self.state_snapshot: dict[str, Any] | None = None

    def __enter__(self):
        """Enter debug context."""
        if self.enable_verbose_logging:
            # Store original log levels
            for name in logging.Logger.manager.loggerDict:
                logger_obj = logging.getLogger(name)
                if logger_obj.level != logging.NOTSET:
                    self.original_log_levels[name] = logger_obj.level
                    logger_obj.setLevel(logging.DEBUG)

            # Set root logger to DEBUG
            root_logger = logging.getLogger()
            self.original_log_levels["root"] = root_logger.level
            root_logger.setLevel(logging.DEBUG)

            logger.info(
                f"🔍 Debug context enabled (request_id={self.request_id}, "
                f"verbose_logging={self.enable_verbose_logging})"
            )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit debug context and restore original state."""
        if self.enable_verbose_logging:
            # Restore original log levels
            for name, level in self.original_log_levels.items():
                if name == "root":
                    logging.getLogger().setLevel(level)
                else:
                    logging.getLogger(name).setLevel(level)

            logger.info(
                f"🔍 Debug context disabled (request_id={self.request_id}, "
                f"api_calls_captured={len(self.api_calls)})"
            )

        return False  # Don't suppress exceptions

    def capture_api_call(self, method: str, url: str, **kwargs) -> None:
        """
        Capture an external API call for debugging.

        Args:
            method: HTTP method
            url: API URL
            **kwargs: Additional call metadata
        """
        if self.capture_api_calls:
            self.api_calls.append(
                {
                    "method": method,
                    "url": url,
                    "timestamp": logging.Formatter().formatTime(
                        logging.LogRecord(
                            name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
                        ),
                        datefmt=None,
                    ),
                    **kwargs,
                }
            )

    def get_state_snapshot(self) -> dict[str, Any]:
        """
        Get current state snapshot.

        Returns:
            Dictionary with state information
        """
        return {
            "request_id": self.request_id,
            "api_calls": self.api_calls,
            "api_calls_count": len(self.api_calls),
            "verbose_logging": self.enable_verbose_logging,
            "capture_api_calls": self.capture_api_calls,
        }


@contextmanager
def debug_mode(
    request_id: str | None = None,
    enable_verbose_logging: bool = True,
    capture_api_calls: bool = True,
):
    """
    Convenience context manager for debug mode.

    Args:
        request_id: Optional request ID for correlation
        enable_verbose_logging: Whether to enable verbose logging
        capture_api_calls: Whether to capture external API calls

    Yields:
        DebugContext instance
    """
    with DebugContext(
        request_id=request_id,
        enable_verbose_logging=enable_verbose_logging,
        capture_api_calls=capture_api_calls,
    ) as ctx:
        yield ctx

