"""
State Helpers Module
Provides type-safe access to app.state and request.state attributes
"""

from typing import Any, TypeVar

T = TypeVar("T")


def get_app_state(
    app_state: Any, attr_name: str, default: T | None = None, expected_type: type[T] | None = None
) -> T | None:
    """
    Type-safe getattr for app.state attributes.

    Args:
        app_state: The app.state object
        attr_name: Name of the attribute to retrieve
        default: Default value if attribute doesn't exist
        expected_type: Optional type hint for runtime type checking

    Returns:
        The attribute value or default, optionally type-checked

    Example:
        memory_service = get_app_state(app.state, "memory_service", expected_type=MemoryServicePostgres)
    """
    value = getattr(app_state, attr_name, default)

    if value is None:
        return default

    if expected_type and not isinstance(value, expected_type):
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Type mismatch for app.state.{attr_name}: "
            f"expected {expected_type.__name__}, got {type(value).__name__}"
        )
        return default

    return value


def get_request_state(
    request_state: Any,
    attr_name: str,
    default: T | None = None,
    expected_type: type[T] | None = None,
) -> T | None:
    """
    Type-safe getattr for request.state attributes.

    Args:
        request_state: The request.state object
        attr_name: Name of the attribute to retrieve
        default: Default value if attribute doesn't exist
        expected_type: Optional type hint for runtime type checking

    Returns:
        The attribute value or default, optionally type-checked

    Example:
        user = get_request_state(request.state, "user", expected_type=dict)
    """
    value = getattr(request_state, attr_name, default)

    if value is None:
        return default

    if expected_type and not isinstance(value, expected_type):
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Type mismatch for request.state.{attr_name}: "
            f"expected {expected_type.__name__}, got {type(value).__name__}"
        )
        return default

    return value
